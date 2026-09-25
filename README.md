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

```bash
pytest
```
