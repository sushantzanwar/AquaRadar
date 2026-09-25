"""One-time relative water-quality indexes over cached scenes.

Not used by the API. Requires the water masks from scripts/preprocess_water.py
and the qda_modelos package.

Writes:
  data/products/indicators/<water_body_id>/<YYYYMMDD>/{turbidity,transparency,chlorophyll}.tif
  zone rows in data/products/water_extent.sqlite (table indicator_zones)
  data/products/indicator_zones.parquet

Each value is a relative index. The rasters and the table say unit=index.
They are not laboratory concentrations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.data.catalog import load_catalog  # noqa: E402
from aquawatch.indicators.compute import IndicatorBackendMissing  # noqa: E402
from aquawatch.preprocess.indicators import preprocess_indicator_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Precompute relative water-quality indexes on valid water pixels.")
    parser.add_argument("--mask-dir", type=Path, default=ROOT / "data" / "products" / "water_masks")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "products" / "indicators")
    parser.add_argument("--store", type=Path, default=ROOT / "data" / "products" / "water_extent.sqlite")
    parser.add_argument("--zone-rows", type=int, default=4)
    parser.add_argument("--zone-cols", type=int, default=4)
    args = parser.parse_args()
    catalog = load_catalog()
    try:
        results = preprocess_indicator_catalog(
            catalog,
            args.mask_dir,
            args.output_dir,
            args.store,
            zone_rows=args.zone_rows,
            zone_cols=args.zone_cols,
        )
    except IndicatorBackendMissing as exc:
        print(exc, file=sys.stderr)
        return 1
    for result in results:
        print(f"{result.water_body_id} {result.date} {result.status} zones={len(result.zones)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
