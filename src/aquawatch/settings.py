"""Load YAML configuration and optional LLM environment overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from aquawatch.disclaimer import DEFAULT_DISCLAIMER


def repo_root() -> Path:
    override = os.environ.get("AQUAWATCH_ROOT")
    if override:
        return Path(override).resolve()
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "config" / "settings.yaml").is_file():
            return candidate
    return Path.cwd()


@dataclass
class WaterBody:
    id: str
    name: str
    boundary: Path
    zones: Path
    settlements: Path
    intakes: Path
    dates: list[str]
    intake_weight: float
    settlement_weight: float
    proximity_scale_m: float


@dataclass
class Settings:
    root: Path
    scenes_dir: Path
    cache_dir: Path
    baselines_path: Path
    products_store: Path
    residuals_path: Path
    credits_path: Path
    uploads_dir: Path
    corpus_dir: Path
    model_dir: Path
    model_repo_id: str
    tile_size: int
    tile_overlap: int
    allow_model_download: bool
    ndwi_threshold: float
    agreement_floor: float
    model_missing_confidence: float
    disagreement_confidence: float
    swir_scale: int
    min_valid_fraction: float
    pixel_area_m2: float
    zone_rows: int
    zone_cols: int
    sigma_threshold: float
    min_baseline_samples: int
    z_cap: float
    fusion_weights: dict[str, float]
    credit_award: int
    duplicate_distance_m: float
    duplicate_seconds: int
    severity_bump: float
    severity_bump_cap: float
    demo_user: str
    cors_origins: list[str]
    disclaimer: str
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    water_bodies: list[WaterBody] = field(default_factory=list)

    def body(self, body_id: str) -> WaterBody | None:
        for item in self.water_bodies:
            if item.id == body_id:
                return item
        return None


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path)


def load_settings(root: Path | None = None) -> Settings:
    root = (root or repo_root()).resolve()
    with (root / "config" / "settings.yaml").open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    with (root / "config" / "water_bodies.yaml").open(encoding="utf-8") as handle:
        bodies_raw = yaml.safe_load(handle)

    paths = raw["paths"]
    model = raw["model"]
    preprocess = raw["preprocess"]
    anomaly = raw["anomaly"]
    credits = raw["credits"]
    bodies: list[WaterBody] = []
    for item in bodies_raw.get("water_bodies", []):
        weights = item.get("priority_weights", {})
        bodies.append(
            WaterBody(
                id=str(item["id"]),
                name=str(item["name"]),
                boundary=_path(root, item["boundary"]),
                zones=_path(root, item["zones"]),
                settlements=_path(root, item["settlements"]),
                intakes=_path(root, item["intakes"]),
                dates=[str(date) for date in item.get("dates", [])],
                intake_weight=float(weights.get("intake", 0.7)),
                settlement_weight=float(weights.get("settlement", 0.3)),
                proximity_scale_m=float(weights.get("proximity_scale_m", 5000)),
            )
        )
    return Settings(
        root=root,
        scenes_dir=_path(root, paths["scenes"]),
        cache_dir=_path(root, paths["cache"]),
        baselines_path=_path(root, paths["baselines"]),
        products_store=_path(root, paths.get("products_store", "data/products/water_extent.sqlite")),
        residuals_path=_path(root, paths["residuals"]),
        credits_path=_path(root, paths["credits"]),
        uploads_dir=_path(root, paths["uploads"]),
        corpus_dir=_path(root, paths["corpus"]),
        model_dir=_path(root, paths["models"]),
        model_repo_id=str(model["repo_id"]),
        tile_size=int(model["tile_size"]),
        tile_overlap=int(model["overlap"]),
        allow_model_download=bool(model["allow_download"]),
        ndwi_threshold=float(model["ndwi_threshold"]),
        agreement_floor=float(model["agreement_floor"]),
        model_missing_confidence=float(model["model_missing_confidence"]),
        disagreement_confidence=float(model["disagreement_confidence"]),
        swir_scale=int(preprocess["swir_scale"]),
        min_valid_fraction=float(preprocess["min_valid_fraction"]),
        pixel_area_m2=float(preprocess["pixel_area_m2"]),
        zone_rows=int(preprocess.get("zone_rows", 4)),
        zone_cols=int(preprocess.get("zone_cols", 4)),
        sigma_threshold=float(anomaly["sigma_threshold"]),
        min_baseline_samples=int(anomaly["min_baseline_samples"]),
        z_cap=float(anomaly["z_cap"]),
        fusion_weights={key: float(value) for key, value in anomaly["weights"].items()},
        credit_award=int(credits["award"]),
        duplicate_distance_m=float(credits["duplicate_distance_m"]),
        duplicate_seconds=int(credits["duplicate_seconds"]),
        severity_bump=float(credits["severity_bump"]),
        severity_bump_cap=float(credits["severity_bump_cap"]),
        demo_user=str(credits["demo_user"]),
        cors_origins=list(raw["api"]["cors_origins"]),
        disclaimer=" ".join(str(raw.get("disclaimer", DEFAULT_DISCLAIMER)).split()),
        llm_provider=os.environ.get("LLM_PROVIDER", "none"),
        llm_model=os.environ.get("LLM_MODEL", ""),
        llm_base_url=os.environ.get("LLM_BASE_URL", ""),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        water_bodies=bodies,
    )
