"""Consecutive anomaly streaks and intake proximity rank sampling zones."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aquawatch.api.deps import get_state
from aquawatch.api.routes import series_alerts
from aquawatch.pipeline.investigation import rank_active_zones
from aquawatch.pipeline.priority import consecutive_anomalous_dates, priority_score
from aquawatch.pipeline.series_alerts import AlertEvidence, SeriesAlert, alert_id

DISCLAIMER = "Relative index only. Laboratory verification is required."


def test_streak_counts_only_the_trailing_anomalous_dates():
    dates = ["20240101", "20240201", "20240301", "20240401"]
    assert consecutive_anomalous_dates(dates, set(dates)) == 4
    assert consecutive_anomalous_dates(dates, {"20240101", "20240301", "20240401"}) == 2
    assert consecutive_anomalous_dates(dates, {"20240101", "20240201"}) == 0


def test_active_zones_rank_by_severity_streak_and_proximity():
    near = _alert("r0c0", "20240301", 6, lat=0.0, lon=0.0)
    far = _alert("r1c0", "20240301", 6, lat=1.0, lon=1.0)
    brief = _alert("r0c1", "20240301", 6, lat=0.0, lon=0.0)
    quiet_latest = _alert("r1c1", "20240201", 6, lat=0.0, lon=0.0)
    observed = {
        "r0c0": ["20240101", "20240201", "20240301"],
        "r1c0": ["20240301"],
        "r0c1": ["20240301"],
        "r1c1": ["20240201", "20240301"],
    }
    alerts = [
        near,
        _alert("r0c0", "20240201", 4, lat=0.0, lon=0.0),
        _alert("r0c0", "20240101", 4, lat=0.0, lon=0.0),
        far,
        brief,
        quiet_latest,
    ]
    ranked, formula = rank_active_zones(
        alerts,
        observed,
        intakes=[(0.0, 0.0)],
        settlements=[(0.0, 0.0)],
        intake_weight=0.7,
        settlement_weight=0.3,
        scale_m=5000,
        z_cap=6,
        sigma_threshold=3,
    )
    assert "\n" not in formula
    assert formula.startswith("priority = severity × consecutive_anomalous_dates × proximity")
    by_zone = {zone.zone_id: zone for zone in ranked}
    assert "r1c1" not in by_zone
    assert by_zone["r0c0"].persistence == 3
    assert by_zone["r0c1"].persistence == 1
    assert by_zone["r0c0"].severity == pytest.approx(1)
    assert by_zone["r0c0"].sample_lat == 0.0
    assert by_zone["r0c0"].sample_lon == 0.0
    assert by_zone["r0c0"].proximity == pytest.approx(1)
    assert by_zone["r0c0"].priority == pytest.approx(
        priority_score(by_zone["r0c0"].severity, by_zone["r0c0"].persistence, by_zone["r0c0"].proximity)
    )
    assert [zone.zone_id for zone in ranked] == ["r0c0", "r0c1", "r1c0"]
    assert ranked[0].rank == 1
    assert by_zone["r0c1"].priority > by_zone["r1c0"].priority


def test_priorities_endpoint_states_the_formula(tmp_path):
    intake = tmp_path / "intakes.geojson"
    settlement = tmp_path / "settlements.geojson"
    _points(intake, "pond", 0.5, 0.5)
    _points(settlement, "pond", 0.5, 0.5)
    client = _client(tmp_path, intake, settlement)
    response = client.get("/waterbodies/pond/priorities")
    assert response.status_code == 200
    body = response.json()
    assert body["formula"].startswith("priority = severity × consecutive_anomalous_dates × proximity")
    assert body["zones"] == []
    assert client.get("/waterbodies/missing/priorities").status_code == 404


def _alert(zone_id: str, date: str, sigma: float, lat: float, lon: float) -> SeriesAlert:
    return SeriesAlert(
        id=alert_id("pond", zone_id, date),
        water_body_id="pond",
        water_body_name="Pond",
        zone_id=zone_id,
        lat=lat,
        lon=lon,
        polygon=None,
        datetime=f"{date[:4]}-{date[4:6]}-{date[6:8]}T00:00:00Z",
        affected_region=f"Pond zone {zone_id}",
        indicators=["turbidity"],
        compound=False,
        severity="high" if sigma > 5 else "low",
        confidence=0.9,
        confidence_reasons=["relative_index"],
        template="Anomaly.",
        evidence=[
            AlertEvidence(
                indicator="turbidity",
                value=10 + sigma,
                baseline_mean=10,
                baseline_std=1,
                baseline_low=9,
                baseline_high=11,
                sigma=sigma,
                threshold=3,
                crossed=True,
                sample_count=8,
                unit="index",
            )
        ],
        disclaimer=DISCLAIMER,
    )


def _points(path, water_body_id, lon, lat):
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"water_body_id": water_body_id},
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _client(tmp_path, intake_path, settlement_path):
    class Body:
        id = "pond"
        name = "Pond"
        intake_weight = 0.7
        settlement_weight = 0.3
        proximity_scale_m = 5000

    Body.intakes = intake_path
    Body.settlements = settlement_path

    class Settings:
        products_store = tmp_path / "missing.sqlite"
        pixel_area_m2 = 100.0
        zone_rows = 4
        zone_cols = 4
        sigma_threshold = 3.0
        min_baseline_samples = 8
        z_cap = 6.0
        disclaimer = DISCLAIMER
        water_bodies = [Body()]

        def body(self, water_body_id):
            return Body() if water_body_id == "pond" else None

    class State:
        settings = Settings()

    app = FastAPI()
    app.include_router(series_alerts.router)
    app.dependency_overrides[get_state] = lambda: State()
    return TestClient(app)
