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

```bash
pytest
```
