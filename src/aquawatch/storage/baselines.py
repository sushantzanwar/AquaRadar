"""Seasonal baseline statistics. An optional joblib residual file can adjust them."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from aquawatch.pipeline.temporal import BaselineView, select_baseline


class BaselineStore:
    def __init__(self, path: Path, residuals_path: Path | None = None):
        self.path = path
        self.residuals_path = residuals_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._residuals = None
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS baselines (
                    water_body_id TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    indicator TEXT NOT NULL,
                    season TEXT NOT NULL,
                    mean REAL NOT NULL,
                    std REAL,
                    sample_count INTEGER NOT NULL,
                    PRIMARY KEY (water_body_id, zone_id, indicator, season)
                )
                """
            )

    def replace_all(self, rows: list[dict]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM baselines")
            connection.executemany(
                """
                INSERT INTO baselines
                    (water_body_id, zone_id, indicator, season, mean, std, sample_count)
                VALUES
                    (:water_body_id, :zone_id, :indicator, :season, :mean, :std, :sample_count)
                """,
                rows,
            )

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM baselines").fetchone()[0])

    def lookup(self, water_body_id: str, zone_id: str, indicator: str, season: str) -> BaselineView | None:
        with self._connect() as connection:
            season_row = connection.execute(
                """
                SELECT * FROM baselines
                WHERE water_body_id = ? AND zone_id = ? AND indicator = ? AND season = ?
                """,
                (water_body_id, zone_id, indicator, season),
            ).fetchone()
            all_row = connection.execute(
                """
                SELECT * FROM baselines
                WHERE water_body_id = ? AND zone_id = ? AND indicator = ? AND season = 'ALL'
                """,
                (water_body_id, zone_id, indicator),
            ).fetchone()
        view = select_baseline(
            dict(season_row) if season_row else None,
            dict(all_row) if all_row else None,
            season,
        )
        if view is None:
            return None
        return self._apply_residual(water_body_id, zone_id, indicator, view)

    def _load_residuals(self):
        if self._residuals is not None:
            return self._residuals
        self._residuals = {}
        if self.residuals_path is None or not self.residuals_path.is_file():
            return self._residuals
        import joblib

        loaded = joblib.load(self.residuals_path)
        if isinstance(loaded, dict):
            self._residuals = loaded
        return self._residuals

    def _apply_residual(self, body: str, zone: str, indicator: str, view: BaselineView) -> BaselineView:
        model = self._load_residuals().get((body, zone, indicator, view.season))
        if model is None or not hasattr(model, "adjust"):
            return view
        mean, std = model.adjust(view.mean, view.std)
        return BaselineView(
            mean=float(mean),
            std=None if std is None else float(std),
            sample_count=view.sample_count,
            season=view.season,
            used_fallback=view.used_fallback,
        )
