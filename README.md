# AquaWatch

Satellite water-quality and contamination intelligence prototype. It reads cached Sentinel-2 L2A scenes, estimates relative turbidity, chlorophyll-a, and transparency, and ranks zones for ground sampling.

Outputs are decision support, not laboratory results. Every API payload includes a confidence score and a lab-verification disclaimer. The demo does not call a live satellite API.

The directory layout and build order are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[geo,indicators]"
python scripts/seed_demo.py
uvicorn aquawatch.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

Place scenes at `data/scenes/{water_body_id}/{YYYYMMDD}/` with `B02`, `B03`, `B04`, `B08`, `B11`, `B12`, and `SCL`. Optional `B05` and `B06` enable the Dall'Olmo / Gitelson chlorophyll index. Download the water-model weights before the demo; see `models/README.md`. With `LLM_PROVIDER=none` (the default), alerts stay on the template and the assistant quotes the corpus.

## Data layout

The offline loader in `aquawatch.data` reads a second, explicit cache. It does not call the network.

```
data/<water_body_id>/<YYYYMMDD>/
  B2.tif   B3.tif   B4.tif   B8.tif    # 10 m
  B11.tif  B12.tif                      # 20 m accepted; resampled to 10 m
  SCL.tif
```

`B02.tif`-style names are accepted as well. Monitored water bodies are declared in `config/data_catalog.yaml` with `id`, `name`, a GeoJSON boundary polygon, and the list of scene dates. `load_scene` stacks those bands into one xarray dataset (`stack` has dimensions `band`, `y`, `x`), resamples B11 and B12 onto the 10 m grid, and clips to the polygon.

A configured date with no folder still returns a dataset: reflectance is NaN, SCL is `0`, and `status` is `missing`. The API scene tree under `data/scenes/` is unchanged.

Water masks are a separate one-time step, not part of an API request:

```bash
python scripts/preprocess_water.py
```

That command reads `data/<water_body_id>/<YYYYMMDD>/`, drops cloud and cloud-shadow pixels using SCL, and skips a date when less than 60% of the AOI is valid. Otherwise it runs `giswqs/s2-water-unetplusplus-efficientnet-b4` locally (weights loaded once from `models/s2-water-unetplusplus-efficientnet-b4`; nothing is downloaded). NDWI from B3 and B8 is the cross-check: disagreement over more than 25% of the valid area is stored as `low_confidence`. Each kept date gets `water_mask.tif` plus extent in hectares (water pixels × 100 m²) in `data/products/water_extent.sqlite` and `.parquet`.

Relative indexes are a second one-time step. They use `qda_modelos` (Miller–McKee 2004 on B4, Giardino et al. 2001 on B3 and B2, and Dall'Olmo / Gitelson when B5 and B6 are present) and only on the intersection of the water mask and clear SCL pixels:

```bash
python scripts/preprocess_indicators.py
```

Each date gets full-resolution GeoTIFFs under `data/products/indicators/` and per-zone mean and p90 for a grid over the water body. Those rows live in the same SQLite file (`indicator_zones`) and in `data/products/indicator_zones.parquet`. The unit on every raster and row is `index`. They are relative indexes, not laboratory concentrations.

The same zone table feeds the temporal layer. For each zone and indicator (extent, turbidity, chlorophyll-a, transparency) the baseline is a leave-one-out seasonal mean and ±1 standard deviation. A season with fewer than two other dates falls back to the rest of the record, and a short history lowers confidence. Both views call that fit:

```bash
GET /waterbodies/{id}/timeseries
GET /waterbodies/{id}/compare?date1=YYYYMMDD&date2=YYYYMMDD
```

The same paths are also mounted under `/api`. Timeseries returns dates, values, baseline mean, and the baseline band. Compare returns the two dates' values, their difference, and a `date2 - date1` GeoTIFF when both indicator rasters exist. Extent is square metres of valid water pixels in the zone. The indexes stay `unit=index`.

Alerts are computed from that same series when a zone-date is more than `sigma_threshold` (default 3) from its baseline. Two or more indicators in one zone, such as an extent drop together with a chlorophyll-a spike, become one compound alert. Severity is `low`, `med`, or `high` from how far the largest sigma sits past the threshold. Confidence is the weakest of the clear-pixel fraction, mask agreement, and baseline length. Each alert carries a template sentence and the value-versus-baseline evidence. Nothing is prewritten:

```bash
GET /alerts
GET /alerts/{id}
GET /alerts/{id}/evidence
```

The evidence card is deterministic: each contributing indicator's value, baseline mean and standard deviation, sigma, and whether it crossed the threshold, plus the clear-pixel fraction and mask agreement. `summary` is a one-line placeholder for later plain language. Alert and indicator payloads use this disclaimer: "Satellite-derived estimate for prioritisation only — requires laboratory verification".

Active anomaly zones are ranked for sampling with one product, not a model:

```bash
GET /waterbodies/{id}/priorities
```

`priority = severity × consecutive_anomalous_dates × proximity`. Severity is the largest absolute sigma divided by the configured cap. Persistence is how many stored dates in a row, ending on the latest date, are anomalous. Proximity falls off with distance from the zone centroid to the nearest intake and settlement in the water-body config. The response repeats that formula in one line, breaks out each term, and recommends the zone centroid as the GPS sample point. A zone whose latest date is back inside the baseline is left off the list.

```bash
pytest
```
