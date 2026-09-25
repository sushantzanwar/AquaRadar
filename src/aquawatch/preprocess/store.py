"""SQLite and Parquet record of per-date water extent."""

from __future__ import annotations

import sqlite3
from pathlib import Path

COLUMNS = (
    "water_body_id",
    "date",
    "status",
    "valid_fraction",
    "disagreement_fraction",
    "low_confidence",
    "water_pixels",
    "extent_m2",
    "extent_ha",
    "mask_path",
)

INDICATOR_COLUMNS = (
    "water_body_id",
    "date",
    "zone_id",
    "indicator",
    "mean",
    "p90",
    "pixel_count",
    "unit",
    "representation",
    "lab_grade",
    "model",
    "raster_path",
    "disclaimer",
)


class ExtentStore:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.parquet_path = sqlite_path.with_suffix(".parquet")
        self.indicator_parquet_path = sqlite_path.with_name("indicator_zones.parquet")
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS water_detection (
                    water_body_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    valid_fraction REAL,
                    disagreement_fraction REAL,
                    low_confidence INTEGER NOT NULL,
                    water_pixels INTEGER,
                    extent_m2 REAL,
                    extent_ha REAL,
                    mask_path TEXT,
                    PRIMARY KEY (water_body_id, date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS indicator_zones (
                    water_body_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    indicator TEXT NOT NULL,
                    mean REAL,
                    p90 REAL,
                    pixel_count INTEGER NOT NULL,
                    unit TEXT NOT NULL,
                    representation TEXT NOT NULL,
                    lab_grade INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    raster_path TEXT,
                    disclaimer TEXT NOT NULL,
                    PRIMARY KEY (water_body_id, date, zone_id, indicator)
                )
                """
            )

    def upsert(self, row: dict) -> None:
        payload = {column: row.get(column) for column in COLUMNS}
        payload["low_confidence"] = int(bool(payload["low_confidence"]))
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO water_detection ({", ".join(COLUMNS)})
                VALUES ({", ".join(":" + column for column in COLUMNS)})
                ON CONFLICT(water_body_id, date) DO UPDATE SET
                    status = excluded.status,
                    valid_fraction = excluded.valid_fraction,
                    disagreement_fraction = excluded.disagreement_fraction,
                    low_confidence = excluded.low_confidence,
                    water_pixels = excluded.water_pixels,
                    extent_m2 = excluded.extent_m2,
                    extent_ha = excluded.extent_ha,
                    mask_path = excluded.mask_path
                """,
                payload,
            )

    def rows(self) -> list[dict]:
        with self._connect() as connection:
            fetched = connection.execute(
                f"SELECT {', '.join(COLUMNS)} FROM water_detection ORDER BY water_body_id, date"
            ).fetchall()
        return [dict(row) for row in fetched]

    def replace_indicators(self, water_body_id: str, date: str, rows: list[dict]) -> None:
        payloads = []
        for row in rows:
            payload = {column: row.get(column) for column in INDICATOR_COLUMNS}
            payload["water_body_id"] = water_body_id
            payload["date"] = date
            payload["lab_grade"] = int(bool(payload["lab_grade"]))
            payloads.append(payload)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM indicator_zones WHERE water_body_id = ? AND date = ?",
                (water_body_id, date),
            )
            if payloads:
                connection.executemany(
                    f"""
                    INSERT INTO indicator_zones ({", ".join(INDICATOR_COLUMNS)})
                    VALUES ({", ".join(":" + column for column in INDICATOR_COLUMNS)})
                    """,
                    payloads,
                )

    def indicator_rows(self) -> list[dict]:
        with self._connect() as connection:
            fetched = connection.execute(
                f"""
                SELECT {", ".join(INDICATOR_COLUMNS)}
                FROM indicator_zones
                ORDER BY water_body_id, date, zone_id, indicator
                """
            ).fetchall()
        return [dict(row) for row in fetched]

    def write_parquet(self) -> Path:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(self.rows())
        pq.write_table(table, self.parquet_path)
        return self.parquet_path

    def write_indicator_parquet(self) -> Path:
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = self.indicator_rows()
        if rows:
            table = pa.Table.from_pylist(rows)
        else:
            table = pa.table({column: [] for column in INDICATOR_COLUMNS})
        pq.write_table(table, self.indicator_parquet_path)
        return self.indicator_parquet_path
