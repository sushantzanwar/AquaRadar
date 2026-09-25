"""Orchestrate ingest through priority. Stress-test mode calls this same object."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from aquawatch.disclaimer import merge_confidence, public_stamp
from aquawatch.domain.schemas import (
    AlertFeed,
    AnomalyResponse,
    EvidenceCard,
    IndicatorComparison,
    PriorityList,
    PrioritySite,
    SceneDateStatus,
    TrendPoint,
    TrendSeries,
    ZoneScore,
)
from aquawatch.geo.catalog import band_paths, list_dates, scene_dir, scene_hash, valid_date
from aquawatch.geo.clip import feature_id, feature_name, geometry_point, load_features
from aquawatch.pipeline.alerts import DraftAlert, apply_polish, dominant_indicator
from aquawatch.pipeline.anomaly import IndicatorSample, ZoneAnomaly, evaluate_zone, normalized_severity
from aquawatch.pipeline.indicators import IndicatorBackendMissing, relative_indicators
from aquawatch.pipeline.ingest import read_stack
from aquawatch.pipeline.preprocess import preprocess_stack
from aquawatch.pipeline.priority import formula_text, nearest_distance, priority_score, proximity_factor
from aquawatch.pipeline.segment import segment_bands, water_extent_m2
from aquawatch.pipeline.temporal import persistence_ratio, season_of
from aquawatch.settings import Settings, WaterBody
from aquawatch.storage.baselines import BaselineStore
from aquawatch.storage.products import ProductStore


@dataclass
class ZoneRecord:
    zone_id: str
    zone_name: str
    lon: float
    lat: float
    means: dict[str, float]
    extent_m2: float | None
    anomaly: ZoneAnomaly | None
    reasons: list[str] = field(default_factory=list)


@dataclass
class DateAnalysis:
    water_body_id: str
    date: str
    status: str
    reason: str | None
    confidence: float
    confidence_reasons: list[str]
    scene_extent_m2: float | None
    zones: list[ZoneRecord]
    persistence: dict[str, float] = field(default_factory=dict)


class PipelineRunner:
    def __init__(self, settings: Settings, baselines: BaselineStore, products: ProductStore):
        self.settings = settings
        self.baselines = baselines
        self.products = products
        self._cache: dict[tuple, DateAnalysis] = {}
        self.bump_for = lambda _body, _zone: 0.0
        self.provider = None

    def clear_cache(self) -> None:
        self._cache.clear()

    def analyze(self, body_id: str, date: str, scenes_root: Path | None = None) -> DateAnalysis:
        root = scenes_root or self.settings.scenes_dir
        computed = self._cached_compute(body_id, date, root)
        if computed.status != "ok":
            computed.persistence = {}
            return computed
        body = self.settings.body(body_id)
        flags: dict[str, list[bool]] = {zone.zone_id: [] for zone in computed.zones}
        for other in list_dates(root, body_id, body.dates if body else []):
            if not valid_date(other):
                continue
            analysis = self._cached_compute(body_id, other, root)
            if analysis.status != "ok":
                continue
            for zone in analysis.zones:
                if zone.anomaly is None:
                    continue
                flags.setdefault(zone.zone_id, []).append(bool(zone.anomaly.flagged))
        computed.persistence = {zone_id: persistence_ratio(values) for zone_id, values in flags.items()}
        return computed

    def _cached_compute(self, body_id: str, date: str, scenes_root: Path) -> DateAnalysis:
        key = (body_id, date, str(scenes_root.resolve()))
        if key not in self._cache:
            self._cache[key] = self._compute(body_id, date, scenes_root)
        return self._cache[key]

    def _compute(self, body_id: str, date: str, scenes_root: Path) -> DateAnalysis:
        body = self.settings.body(body_id)
        if body is None or not valid_date(date):
            return self._empty(body_id, date, "unusable", "unknown_water_body_or_date", 0.0, ["unknown_water_body"])
        folder = scene_dir(scenes_root, body_id, date)
        if not folder.is_dir():
            return self._empty(body_id, date, "missing", "scene_folder_missing", 0.0, ["scene_missing"])
        paths, missing = band_paths(folder)
        if missing:
            return self._empty(body_id, date, "unusable", "missing_bands:" + ",".join(missing), 0.0, ["missing_bands"])
        try:
            stack = read_stack(body_id, date, paths)
        except Exception as exc:
            return self._empty(body_id, date, "geo_backend_missing", exc.__class__.__name__, 0.0, ["geo_backend_missing"])
        prepared = preprocess_stack(
            stack,
            body.boundary,
            swir_scale=self.settings.swir_scale,
            min_valid_fraction=self.settings.min_valid_fraction,
            fallback_area=self.settings.pixel_area_m2,
        )
        if prepared.status != "ok" or prepared.bands is None or prepared.valid is None:
            return self._empty(body_id, date, prepared.status, prepared.reason, prepared.confidence, prepared.confidence_reasons)
        digest = scene_hash(paths)
        loaded = self._load_cached(body_id, date, digest)
        if loaded is None:
            work = self.settings.cache_dir / "work" / body_id / date / digest
            work.mkdir(parents=True, exist_ok=True)
            segmented = segment_bands(prepared.bands, prepared.valid, self.settings, work, prepared.profile or {})
            try:
                indicators, indicator_reasons = relative_indicators(prepared.bands, segmented["mask"])
            except IndicatorBackendMissing:
                return self._empty(body_id, date, "unusable", "indicator_backend_missing", 0.0, ["indicator_backend_missing"])
            mask = segmented["mask"]
            mask_confidence = float(segmented["confidence"])
            mask_reasons = list(segmented["confidence_reasons"]) + indicator_reasons
            self.products.save_mask(
                body_id,
                date,
                digest,
                mask,
                {
                    "confidence": mask_confidence,
                    "reasons": mask_reasons,
                    "has_chlorophyll": "chlorophyll" in indicators,
                },
            )
            self.products.save_indicators(body_id, date, digest, indicators)
        else:
            mask, indicators, mask_confidence, mask_reasons = loaded
        zones = self._zone_records(body, date, prepared, mask, indicators)
        scene_confidence, scene_reasons = merge_confidence(
            [(prepared.confidence, prepared.confidence_reasons), (mask_confidence, mask_reasons)]
        )
        status = "ok"
        reason = None
        if zones and all(zone.anomaly is None for zone in zones):
            status = "no_baseline"
            reason = "missing_baseline"
            scene_reasons = [*scene_reasons, "missing_baseline"]
        for zone in zones:
            if zone.anomaly is None:
                continue
            zone.anomaly.confidence, zone.anomaly.confidence_reasons = merge_confidence(
                [
                    (scene_confidence, scene_reasons),
                    (zone.anomaly.confidence, [*zone.anomaly.confidence_reasons, *zone.reasons]),
                ]
            )
        if any(zone.anomaly is not None for zone in zones):
            scene_confidence = min(
                scene_confidence,
                min(zone.anomaly.confidence for zone in zones if zone.anomaly is not None),
            )
        return DateAnalysis(
            water_body_id=body_id,
            date=date,
            status=status,
            reason=reason,
            confidence=scene_confidence,
            confidence_reasons=scene_reasons,
            scene_extent_m2=water_extent_m2(mask, prepared.pixel_area_m2),
            zones=zones,
        )

    def _load_cached(self, body_id: str, date: str, digest: str):
        import json

        mask = self.products.load_mask(body_id, date, digest)
        if mask is None:
            return None
        meta_path = self.products._mask_folder(body_id, date, digest) / "meta.json"
        if not meta_path.is_file():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        names = ["turbidity", "transparency"]
        if meta.get("has_chlorophyll"):
            names.append("chlorophyll")
        indicators = self.products.load_indicators(body_id, date, digest, names)
        if indicators is None:
            return None
        return mask, indicators, float(meta.get("confidence", 1)), list(meta.get("reasons", []))

    def _zone_records(self, body: WaterBody, date: str, prepared, mask, indicators) -> list[ZoneRecord]:
        features = load_features(body.zones)
        zone_raster = self._rasterize_zones(features, mask.shape, prepared.transform)
        records: list[ZoneRecord] = []
        for index, feature in enumerate(features, start=1):
            point = geometry_point(feature.get("geometry") or {}) or (0.0, 0.0)
            zone_id = feature_id(feature, f"zone-{index}")
            means: dict[str, float] = {}
            extent = None
            if zone_raster is not None:
                water = (zone_raster == index) & mask
                extent = water_extent_m2(water, prepared.pixel_area_m2)
                means["extent"] = extent
                for name, array in indicators.items():
                    values = np.asarray(array)[water]
                    values = values[np.isfinite(values)]
                    if values.size:
                        means[name] = float(np.mean(values))
            anomaly, reasons = self._score_zone(body.id, zone_id, date, means)
            records.append(
                ZoneRecord(
                    zone_id=zone_id,
                    zone_name=feature_name(feature, zone_id),
                    lon=float(point[0]),
                    lat=float(point[1]),
                    means=means,
                    extent_m2=extent,
                    anomaly=anomaly,
                    reasons=reasons,
                )
            )
        return records

    def _rasterize_zones(self, features, shape, transform):
        shapes = [(feature["geometry"], index) for index, feature in enumerate(features, start=1) if feature.get("geometry")]
        if not shapes:
            return None
        try:
            from rasterio.features import rasterize

            return rasterize(shapes, out_shape=shape, transform=transform, fill=0, dtype="int16")
        except Exception:
            return None

    def _score_zone(self, body_id: str, zone_id: str, date: str, means: dict[str, float]):
        if not means:
            return None, ["no_zone_pixels"]
        season = season_of(date)
        samples: list[IndicatorSample] = []
        reasons: list[str] = []
        for indicator, value in means.items():
            if indicator not in self.settings.fusion_weights and indicator != "transparency":
                continue
            view = self.baselines.lookup(body_id, zone_id, indicator, season)
            if view is None:
                continue
            if view.used_fallback:
                reasons.append("season_pool_fallback")
            samples.append(
                IndicatorSample(
                    indicator=indicator,
                    value=value,
                    mean=view.mean,
                    std=view.std,
                    sample_count=view.sample_count,
                )
            )
        if not samples:
            return None, ["missing_baseline"]
        anomaly = evaluate_zone(
            samples,
            sigma_threshold=self.settings.sigma_threshold,
            weights=self.settings.fusion_weights,
            min_baseline_samples=self.settings.min_baseline_samples,
            z_cap=self.settings.z_cap,
        )
        return anomaly, reasons

    def _empty(self, body_id, date, status, reason, confidence, reasons) -> DateAnalysis:
        return DateAnalysis(body_id, date, status, reason, confidence, reasons, None, [])

    def stamp(self, confidence: float, reasons: list[str]) -> dict:
        return public_stamp(confidence, reasons, self.settings.disclaimer)

    def scene_status(self, body: WaterBody, date: str, scenes_root: Path | None = None) -> SceneDateStatus:
        analysis = self.analyze(body.id, date, scenes_root)
        return SceneDateStatus(
            date=date,
            status=analysis.status,  # type: ignore[arg-type]
            reason=analysis.reason,
            **self.stamp(analysis.confidence, analysis.confidence_reasons),
        )

    def anomalies(self, body_id: str, date: str, scenes_root: Path | None = None) -> AnomalyResponse:
        analysis = self.analyze(body_id, date, scenes_root)
        zones = [self._zone_score(analysis, zone) for zone in analysis.zones if zone.anomaly is not None]
        return AnomalyResponse(
            water_body_id=body_id,
            date=date,
            status=analysis.status,
            reason=analysis.reason,
            scene_extent_m2=analysis.scene_extent_m2,
            zones=zones,
            **self.stamp(analysis.confidence, analysis.confidence_reasons),
        )

    def _zone_score(self, analysis: DateAnalysis, zone: ZoneRecord) -> ZoneScore:
        anomaly = zone.anomaly
        assert anomaly is not None
        return ZoneScore(
            zone_id=zone.zone_id,
            zone_name=zone.zone_name,
            date=analysis.date,
            flagged=anomaly.flagged,
            fused_score=anomaly.fused_score,
            severity_label=anomaly.severity_label,
            contributing_indicators=list(anomaly.contributing),
            comparisons=[self._comparison(row) for row in anomaly.comparisons],
            extent_m2=zone.extent_m2,
            lat=zone.lat,
            lon=zone.lon,
            **self.stamp(anomaly.confidence, anomaly.confidence_reasons),
        )

    def _comparison(self, row) -> IndicatorComparison:
        return IndicatorComparison(
            indicator=row.indicator,
            value=row.value,
            baseline_mean=row.baseline_mean,
            baseline_std=row.baseline_std,
            sigma=row.sigma,
            threshold=row.threshold,
            crossed=row.crossed,
            sample_count=row.sample_count,
            fused=row.fused,
        )

    def evidence(self, body_id: str, zone_id: str, date: str, scenes_root: Path | None = None) -> EvidenceCard | None:
        analysis = self.analyze(body_id, date, scenes_root)
        zone = next((item for item in analysis.zones if item.zone_id == zone_id and item.anomaly is not None), None)
        if zone is None or zone.anomaly is None:
            return None
        extent_change = None
        for row in zone.anomaly.comparisons:
            if row.indicator == "extent":
                extent_change = row.value - row.baseline_mean
        return EvidenceCard(
            evidence_id=f"ev-{body_id}-{zone_id}-{date}",
            water_body_id=body_id,
            zone_id=zone_id,
            zone_name=zone.zone_name,
            date=date,
            comparisons=[self._comparison(row) for row in zone.anomaly.comparisons],
            extent_m2=zone.extent_m2,
            extent_change_m2=extent_change,
            contributing_indicators=list(zone.anomaly.contributing),
            thresholds_crossed=[f"{name}>{self.settings.sigma_threshold:g}sigma" for name in zone.anomaly.contributing],
            **self.stamp(zone.anomaly.confidence, zone.anomaly.confidence_reasons),
        )

    def alerts(self, body_id: str, date: str, scenes_root: Path | None = None) -> AlertFeed:
        analysis = self.analyze(body_id, date, scenes_root)
        body = self.settings.body(body_id)
        location = body.name if body else body_id
        built = []
        provider = self.provider
        for zone in analysis.zones:
            card = self.evidence(body_id, zone.zone_id, date, scenes_root)
            if card is None or not zone.anomaly or not zone.anomaly.flagged:
                continue
            indicator, severity = dominant_indicator(card)
            draft = DraftAlert(evidence=card, location=location, severity=severity, indicator=indicator)
            if provider is None:
                from aquawatch.llm.provider import TemplateProvider

                provider = TemplateProvider()
            built.append(apply_polish(draft, provider, self.settings.disclaimer))
        confidence = min((alert.confidence for alert in built), default=analysis.confidence)
        reasons = list(analysis.confidence_reasons)
        return AlertFeed(
            water_body_id=body_id,
            date=date,
            status=analysis.status,
            reason=analysis.reason,
            alerts=built,
            **self.stamp(confidence, reasons),
        )

    def priority(self, body_id: str, date: str, scenes_root: Path | None = None) -> PriorityList:
        analysis = self.analyze(body_id, date, scenes_root)
        body = self.settings.body(body_id)
        if body is None:
            return PriorityList(
                water_body_id=body_id,
                date=date,
                status="unusable",
                reason="unknown_water_body",
                sites=[],
                **self.stamp(0.0, ["unknown_water_body"]),
            )
        intakes = _points_for(body.intakes, body_id)
        settlements = _points_for(body.settlements, body_id)
        formula = formula_text(body.intake_weight, body.settlement_weight, body.proximity_scale_m)
        sites: list[PrioritySite] = []
        for zone in analysis.zones:
            if zone.anomaly is None or not zone.anomaly.flagged:
                continue
            intake_distance = nearest_distance((zone.lon, zone.lat), intakes)
            settlement_distance = nearest_distance((zone.lon, zone.lat), settlements)
            proximity = proximity_factor(
                intake_distance,
                settlement_distance,
                body.intake_weight,
                body.settlement_weight,
                body.proximity_scale_m,
            )
            bump = float(self.bump_for(body_id, zone.zone_id))
            severity = min(1.0, normalized_severity(zone.anomaly.max_abs_sigma, self.settings.z_cap) + bump)
            persistence = analysis.persistence.get(zone.zone_id, 1.0 if zone.anomaly.flagged else 0.0)
            score = priority_score(severity, persistence, proximity)
            sites.append(
                PrioritySite(
                    rank=0,
                    water_body_id=body_id,
                    zone_id=zone.zone_id,
                    zone_name=zone.zone_name,
                    date=date,
                    lat=zone.lat,
                    lon=zone.lon,
                    priority=score,
                    severity=severity,
                    persistence=persistence,
                    proximity=proximity,
                    distance_to_intake_m=intake_distance,
                    distance_to_settlement_m=settlement_distance,
                    severity_bump=bump,
                    formula=formula,
                    **self.stamp(zone.anomaly.confidence, zone.anomaly.confidence_reasons),
                )
            )
        sites.sort(key=lambda site: site.priority, reverse=True)
        for index, site in enumerate(sites, start=1):
            site.rank = index
        confidence = min((site.confidence for site in sites), default=analysis.confidence)
        return PriorityList(
            water_body_id=body_id,
            date=date,
            status=analysis.status,
            reason=analysis.reason,
            sites=sites,
            **self.stamp(confidence, analysis.confidence_reasons),
        )

    def trends(self, body_id: str, zone_id: str, indicator: str, scenes_root: Path | None = None) -> TrendSeries:
        body = self.settings.body(body_id)
        root = scenes_root or self.settings.scenes_dir
        points: list[TrendPoint] = []
        reasons: list[str] = []
        confidence = 1.0
        if body is not None:
            for date in list_dates(root, body_id, body.dates):
                analysis = self.analyze(body_id, date, root)
                zone = next((item for item in analysis.zones if item.zone_id == zone_id), None)
                value = None if zone is None else zone.means.get(indicator)
                view = None
                if zone is not None:
                    view = self.baselines.lookup(body_id, zone_id, indicator, season_of(date))
                if analysis.confidence < confidence:
                    confidence = analysis.confidence
                reasons.extend(analysis.confidence_reasons)
                points.append(
                    TrendPoint(
                        date=date,
                        value=value,
                        baseline_mean=None if view is None else view.mean,
                        baseline_std=None if view is None else view.std,
                        status=analysis.status,
                    )
                )
        return TrendSeries(
            water_body_id=body_id,
            zone_id=zone_id,
            indicator=indicator,
            points=points,
            **self.stamp(confidence, reasons or ["not_a_detection"]),
        )

    def observations(self, scenes_root: Path | None = None) -> list[dict]:
        """Per-date zone means for the baseline fit. Skips dates that did not process."""
        rows = []
        root = scenes_root or self.settings.scenes_dir
        for body in self.settings.water_bodies:
            for date in list_dates(root, body.id, body.dates):
                analysis = self._cached_compute(body.id, date, root)
                if analysis.status not in {"ok", "no_baseline"}:
                    continue
                for zone in analysis.zones:
                    for indicator, value in zone.means.items():
                        rows.append(
                            {
                                "water_body_id": body.id,
                                "zone_id": zone.zone_id,
                                "indicator": indicator,
                                "date": date,
                                "value": value,
                            }
                        )
        return rows


def _points_for(path: Path, body_id: str) -> list[tuple[float, float]]:
    points = []
    for feature in load_features(path):
        props = feature.get("properties") or {}
        owner = props.get("water_body_id")
        if owner and owner != body_id:
            continue
        point = geometry_point(feature.get("geometry") or {})
        if point is not None and (feature.get("geometry") or {}).get("type") == "Point":
            points.append(point)
    return points
