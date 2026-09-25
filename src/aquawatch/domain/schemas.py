"""Pydantic models shared by the pipeline and the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Stamp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0, le=1)
    confidence_reasons: list[str]
    lab_verification_required: Literal[True] = True
    disclaimer: str


class SceneDateStatus(Stamp):
    date: str
    status: Literal["ok", "insufficient_data", "missing", "unusable", "no_baseline", "geo_backend_missing"]
    reason: str | None = None


class IndicatorComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str
    value: float
    baseline_mean: float
    baseline_std: float | None
    sigma: float | None
    threshold: float
    crossed: bool
    sample_count: int
    fused: bool


class EvidenceCard(Stamp):
    evidence_id: str
    water_body_id: str
    zone_id: str
    zone_name: str
    date: str
    comparisons: list[IndicatorComparison]
    extent_m2: float | None
    extent_change_m2: float | None
    contributing_indicators: list[str]
    thresholds_crossed: list[str]


class Alert(Stamp):
    alert_id: str
    evidence_id: str
    water_body_id: str
    location: str
    datetime: str
    affected_region: str
    indicator: str
    severity: Literal["watch", "warning", "severe"]
    template: str
    polished_summary: str | None
    narrative_source: Literal["template", "llm", "llm_disabled", "llm_rejected", "llm_unreachable"]


class AlertFeed(Stamp):
    water_body_id: str
    date: str
    status: str
    reason: str | None = None
    alerts: list[Alert]


class ZoneScore(Stamp):
    zone_id: str
    zone_name: str
    date: str
    flagged: bool
    fused_score: float
    severity_label: str | None
    contributing_indicators: list[str]
    comparisons: list[IndicatorComparison]
    extent_m2: float | None
    lat: float
    lon: float


class AnomalyResponse(Stamp):
    water_body_id: str
    date: str
    status: str
    reason: str | None = None
    scene_extent_m2: float | None = None
    zones: list[ZoneScore]


class PrioritySite(Stamp):
    rank: int
    water_body_id: str
    zone_id: str
    zone_name: str
    date: str
    lat: float
    lon: float
    priority: float
    severity: float
    persistence: float
    proximity: float
    distance_to_intake_m: float | None
    distance_to_settlement_m: float | None
    severity_bump: float
    formula: str


class PriorityList(Stamp):
    water_body_id: str
    date: str
    status: str
    reason: str | None = None
    sites: list[PrioritySite]


class TrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    value: float | None
    baseline_mean: float | None
    baseline_std: float | None
    status: str


class TrendSeries(Stamp):
    water_body_id: str
    zone_id: str
    indicator: str
    points: list[TrendPoint]


class Passage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    text: str


class AssistantAnswer(Stamp):
    answer: str
    source_ids: list[str]
    passages: list[Passage]
    evidence_id: str | None = None
    grounded: bool


class AssistantRequest(BaseModel):
    question: str
    water_body_id: str | None = None
    zone_id: str | None = None
    date: str | None = None


class CreditVerdict(Stamp):
    report_id: str
    accepted: bool
    reason: str
    credits_awarded: int
    zone_id: str | None
    severity_bump: float
    total_credits: int


class LeaderboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    credits: int


class Leaderboard(Stamp):
    entries: list[LeaderboardEntry]


class PlumeRequest(BaseModel):
    water_body_id: str
    date: str
    lon: float
    lat: float
    radius_m: float = Field(gt=0)
    indicator: Literal["turbidity", "chlorophyll", "transparency"]
    magnitude: float


class StressResponse(Stamp):
    water_body_id: str
    date: str
    status: str
    reason: str | None = None
    anomalies: AnomalyResponse | None = None
    alerts: AlertFeed | None = None
    evidence: list[EvidenceCard] = Field(default_factory=list)
    priority: PriorityList | None = None


class WaterBodyOverview(Stamp):
    id: str
    name: str
    dates: list[SceneDateStatus]
    latest_alert: Alert | None = None


class SceneIndex(Stamp):
    water_bodies: list[WaterBodyOverview]


class HealthBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    configured_dates: list[str]
    dates_on_disk: list[str]


class HealthResponse(Stamp):
    status: Literal["ok"]
    water_bodies: list[HealthBody]
