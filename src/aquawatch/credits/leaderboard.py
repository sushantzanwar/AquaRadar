"""Credit totals and the severity bump applied when a report hits a flagged zone."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aquawatch.credits.checks import fingerprint, is_duplicate, locate
from aquawatch.settings import Settings


class CreditsService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.path = settings.credits_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    water_body_id TEXT NOT NULL,
                    image_hash TEXT NOT NULL,
                    lon REAL NOT NULL,
                    lat REAL NOT NULL,
                    taken_at TEXT NOT NULL,
                    note TEXT,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    credits INTEGER NOT NULL,
                    zone_id TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bumps (
                    water_body_id TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    bump REAL NOT NULL,
                    PRIMARY KEY (water_body_id, zone_id)
                )
                """
            )

    def bump_for(self, water_body_id: str, zone_id: str) -> float:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT bump FROM bumps WHERE water_body_id = ? AND zone_id = ?",
                (water_body_id, zone_id),
            ).fetchone()
        return 0.0 if row is None else float(row["bump"])

    def total(self, user_id: str | None = None) -> int:
        user_id = user_id or self.settings.demo_user
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(credits), 0) AS credits FROM reports WHERE user_id = ? AND status = 'accepted'",
                (user_id,),
            ).fetchone()
        return int(row["credits"])

    def leaderboard(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT user_id, COALESCE(SUM(credits), 0) AS credits
                FROM reports
                WHERE status = 'accepted'
                GROUP BY user_id
                ORDER BY credits DESC
                """
            ).fetchall()
        if not rows:
            return [{"user_id": self.settings.demo_user, "credits": 0}]
        return [{"user_id": row["user_id"], "credits": int(row["credits"])} for row in rows]

    def _accepted_rows(self, water_body_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reports WHERE water_body_id = ? AND status = 'accepted'",
                (water_body_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def submit(self, *, water_body_id: str, filename: str, data: bytes, lon: float, lat: float, taken_at: datetime | None, note: str, zone_is_flagged: bool) -> dict:
        body = self.settings.body(water_body_id)
        if body is None:
            return self._result(False, "unknown_water_body", 0, None, 0.0)
        taken_at = taken_at or datetime.now(timezone.utc)
        if taken_at.tzinfo is None:
            taken_at = taken_at.replace(tzinfo=timezone.utc)
        image_hash = fingerprint(data)
        zone_id, where = locate(body.boundary, body.zones, lon, lat)
        if where == "outside_water_boundary":
            return self._store(water_body_id, image_hash, lon, lat, taken_at, note, "rejected", where, 0, None, 0.0, data, filename)
        duplicate = is_duplicate(
            self._accepted_rows(water_body_id),
            image_hash,
            lon,
            lat,
            taken_at,
            self.settings.duplicate_distance_m,
            self.settings.duplicate_seconds,
        )
        if duplicate:
            return self._store(water_body_id, image_hash, lon, lat, taken_at, note, "rejected", "duplicate", 0, zone_id, 0.0, data, filename)
        bump = 0.0
        if zone_id and zone_is_flagged:
            bump = self._add_bump(water_body_id, zone_id)
        return self._store(
            water_body_id,
            image_hash,
            lon,
            lat,
            taken_at,
            note,
            "accepted",
            where,
            self.settings.credit_award,
            zone_id,
            bump,
            data,
            filename,
        )

    def _add_bump(self, water_body_id: str, zone_id: str) -> float:
        current = self.bump_for(water_body_id, zone_id)
        updated = min(self.settings.severity_bump_cap, current + self.settings.severity_bump)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bumps (water_body_id, zone_id, bump) VALUES (?, ?, ?)
                ON CONFLICT(water_body_id, zone_id) DO UPDATE SET bump = excluded.bump
                """,
                (water_body_id, zone_id, updated),
            )
        return updated

    def _store(self, water_body_id, image_hash, lon, lat, taken_at, note, status, reason, credits, zone_id, bump, data, filename) -> dict:
        report_id = uuid.uuid4().hex[:12]
        safe_name = Path(filename).name or "photo.jpg"
        destination = self.settings.uploads_dir / f"{report_id}-{safe_name}"
        destination.write_bytes(data)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reports (
                    report_id, user_id, water_body_id, image_hash, lon, lat, taken_at,
                    note, status, reason, credits, zone_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    self.settings.demo_user,
                    water_body_id,
                    image_hash,
                    lon,
                    lat,
                    taken_at.isoformat(),
                    note,
                    status,
                    reason,
                    credits,
                    zone_id,
                ),
            )
        result = self._result(status == "accepted", reason, credits, zone_id, bump)
        result["report_id"] = report_id
        result["total_credits"] = self.total()
        return result

    def _result(self, accepted: bool, reason: str, credits: int, zone_id: str | None, bump: float) -> dict:
        return {
            "report_id": "",
            "accepted": accepted,
            "reason": reason,
            "credits_awarded": credits,
            "zone_id": zone_id,
            "severity_bump": bump,
            "total_credits": self.total() if accepted else self.total(),
        }
