"""Accepted and rejected photo reports for the single demo user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class StoredReport:
    report_id: str
    user_id: str
    image_hash: str
    lon: float
    lat: float
    taken_at: datetime
    note: str
    status: str
    reason: str
    credits: int
    zone_id: str | None
    water_body_id: str
