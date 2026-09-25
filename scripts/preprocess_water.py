"""One-time water detection over cached scenes.

Not used by the API. Requires local weights for
giswqs/s2-water-unetplusplus-efficientnet-b4. This script does not download them.

Writes:
  data/products/water_masks/<water_body_id>/<YYYYMMDD>/water_mask.tif
  data/products/water_extent.sqlite
  data/products/water_extent.parquet

Scenes below 60% valid AOI pixels are stored as insufficient_data and get no mask.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.data.catalog import load_catalog  # noqa: E402
from aquawatch.preprocess.run import preprocess_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Precompute water masks and extent from cached Sentinel-2 scenes.")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models" / "s2-water-unetplusplus-efficientnet-b4")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "products" / "water_masks")
    parser.add_argument("--store", type=Path, default=ROOT / "data" / "products" / "water_extent.sqlite")
    args = parser.parse_args()
    catalog = load_catalog()
    rows = preprocess_catalog(catalog, args.model_dir, args.output_dir, args.store)
    for row in rows:
        print(f"{row['water_body_id']} {row['date']} {row['status']} ha={row['extent_ha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
