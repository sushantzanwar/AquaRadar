# AquaWatch — Project Structure

Satellite water-quality and contamination intelligence prototype. Decision support and early warning only. Every product carries a confidence score and an explicit lab-verification disclaimer. Runtime is offline: locally cached Sentinel-2 L2A scenes, no live satellite API.

Prep scripts and notebooks are outside the demo path. Judges may drop in new cached scenes; nothing in the API returns hardcoded detections.

## Layout principles

- **One pipeline, many surfaces.** Ingest through priority ranking is a chain of pure stage functions. HTTP, the RAG assistant, and stress-test mode all call that chain. They do not reimplement it.
- **Numbers are born in the pipeline.** Alerts, evidence cards, and LLM narration read a typed evidence payload. The model may rephrase; it may not invent index values, thresholds, or GPS points.
- **Prep vs runtime.** `scripts/` and `notebooks/` fit baselines, build the vector index, and seed demo state. The FastAPI process only reads `config/`, `data/`, and `models/`.
- **Confidence is a stage output.** Each stage returns a confidence in `[0, 1]` plus a reason code (`cloud_fraction`, `model_agreement`, `baseline_sample_size`, `insufficient_data`, …). Later stages multiply or take the minimum; they never reset it to 1.
- **Disclaimer is a schema field**, filled from one constant, on every public response: indicator maps, anomalies, alerts, priorities, assistant answers, and credit verdicts.

## Directory tree

```
.
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── settings.yaml
│   └── water_bodies.yaml
├── data/
│   ├── README.md
│   ├── scenes/
│   │   └── {water_body_id}/{YYYYMMDD}/
│   │       ├── B02.tif
│   │       ├── B03.tif
│   │       ├── B04.tif
│   │       ├── B08.tif
│   │       ├── B11.tif
│   │       ├── B12.tif
│   │       └── SCL.tif
│   ├── boundaries/
│   │   └── {water_body_id}.geojson
│   ├── zones/
│   │   └── {water_body_id}.geojson
│   ├── context/
│   │   ├── settlements.geojson
│   │   └── intakes.geojson
│   ├── cache/
│   │   ├── masks/
│   │   └── indicators/
│   ├── baselines/
│   │   └── baselines.sqlite
│   ├── credits/
│   │   └── credits.sqlite
│   └── corpus/
│       ├── product_boundary.md
│       ├── spectral_indices.md
│       ├── indicator_models.md
│       ├── alert_language.md
│       └── profiles/
│           └── {water_body_id}.md
├── models/
│   └── README.md
├── scripts/
│   ├── prepare_scene_stack.py
│   ├── generate_water_masks.py
│   ├── fit_seasonal_baselines.py
│   ├── index_corpus.py
│   └── seed_demo.py
├── notebooks/
│   └── 01_scene_qc.ipynb
├── src/
│   └── aquawatch/
│       ├── __init__.py
│       ├── main.py
│       ├── settings.py
│       ├── disclaimer.py
│       ├── domain/
│       │   ├── __init__.py
│       │   └── schemas.py
│       ├── geo/
│       │   ├── __init__.py
│       │   ├── catalog.py
│       │   ├── resample.py
│       │   ├── cloud_mask.py
│       │   ├── clip.py
│       │   └── tiles.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── runner.py
│       │   ├── ingest.py
│       │   ├── preprocess.py
│       │   ├── segment.py
│       │   ├── indicators.py
│       │   ├── temporal.py
│       │   ├── anomaly.py
│       │   ├── alerts.py
│       │   ├── priority.py
│       │   └── stress.py
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── products.py
│       │   └── baselines.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── provider.py
│       │   ├── retriever.py
│       │   ├── assistant.py
│       │   └── prompts.py
│       ├── credits/
│       │   ├── __init__.py
│       │   ├── reports.py
│       │   ├── checks.py
│       │   └── leaderboard.py
│       └── api/
│           ├── __init__.py
│           ├── deps.py
│           └── routes/
│               ├── __init__.py
│               ├── health.py
│               ├── scenes.py
│               ├── maps.py
│               ├── anomalies.py
│               ├── alerts.py
│               ├── explain.py
│               ├── priority.py
│               ├── assistant.py
│               ├── credits.py
│               └── stress.py
├── tests/
│   ├── conftest.py
│   ├── test_anomaly.py
│   ├── test_preprocess_gates.py
│   ├── test_priority.py
│   ├── test_evidence_contract.py
│   └── fixtures/
│       └── synthetic_zone_series.json
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts
│       ├── map/
│       │   ├── AnomalyMap.tsx
│       │   ├── SwipeCompare.tsx
│       │   └── layers.ts
│       ├── components/
│       │   ├── DisclaimerBanner.tsx
│       │   ├── ConfidenceBadge.tsx
│       │   ├── EvidenceCard.tsx
│       │   ├── AlertFeed.tsx
│       │   ├── PriorityList.tsx
│       │   ├── TrendChart.tsx
│       │   ├── AssistantPanel.tsx
│       │   ├── Leaderboard.tsx
│       │   ├── PhotoUpload.tsx
│       │   └── StressControls.tsx
│       ├── pages/
│       │   ├── OverviewPage.tsx
│       │   ├── WaterBodyPage.tsx
│       │   └── CreditsPage.tsx
│       └── styles.css
└── docs/
    └── ARCHITECTURE.md
```

Raster binaries, model weights, FAISS indexes, and SQLite files stay out of git. `data/README.md` and `models/README.md` document the expected on-disk layout so a fresh checkout can be filled from the cache.

## File and module descriptions

### Repository root

- `README.md` — What AquaWatch is and is not, offline demo steps, disclaimer, and pointers to config and this document.
- `.gitignore` — Ignores scenes, weights, caches, SQLite, FAISS indexes, virtualenvs, and frontend build output.
- `.env.example` — LLM provider switch (`none` | `local` | `api`), model name, and optional API key; demo runs with `none` and template text only.
- `pyproject.toml` — Package metadata, `src` layout, pytest config, and the `aquawatch` console entry.
- `requirements.txt` — Pinned runtime deps: FastAPI, rasterio, geopandas, numpy, xarray, torch/timm/geoai stack, `qda_modelos`, joblib, faiss-cpu, sentence-transformers.

### Config

- `config/settings.yaml` — Data and model paths, tile size (512), sigma threshold (default 3), fusion weights, priority weights, cloud-fraction cutoff, and the canonical disclaimer string.
- `config/water_bodies.yaml` — Per water body: id, display name, AOI polygon path, zone layer, scene date list, settlement and intake layers, and ranking weights. Adding a body is a config change, not a code change.

### Data (cached inputs and derived state)

- `data/README.md` — Scene folder convention, required bands, CRS expectation (metric, 10 m grid), and which paths the runtime may write.
- `data/scenes/{water_body_id}/{YYYYMMDD}/*.tif` — Local Sentinel-2 L2A bands B2, B3, B4, B8, B11, B12 and SCL. One folder per acquisition.
- `data/boundaries/{water_body_id}.geojson` — Fixed analysis footprint used for clipping and for the citizen-photo “inside water” check.
- `data/zones/{water_body_id}.geojson` — Sub-zones (polygons) that own baselines, anomaly scores, and sample points.
- `data/context/settlements.geojson` — Settlement points or polygons used only as a proximity term in the priority score.
- `data/context/intakes.geojson` — Drinking-water intakes or abstraction points, same proximity term, higher default weight.
- `data/cache/masks/` — Optional on-disk water masks so a repeat demo does not re-run the UNet; invalidated when the source scene changes.
- `data/cache/indicators/` — Optional cached indicator rasters (turbidity, chlorophyll-a, transparency), same invalidation rule.
- `data/baselines/baselines.sqlite` — Seasonal baseline statistics per water body, zone, indicator, and season. Written by the fit script; read by the temporal engine.
- `data/credits/credits.sqlite` — Demo-user photo reports, duplicate hashes, credit totals, and severity upgrades. No auth tables.
- `data/corpus/product_boundary.md` — States that outputs are relative indicators and require lab verification; the assistant must quote this when asked about accuracy.
- `data/corpus/spectral_indices.md` — NDWI definition, band roles, and how the UNet mask and NDWI cross-check are combined.
- `data/corpus/indicator_models.md` — Miller–McKee turbidity, Gitelson/Dall'Olmo chlorophyll family, and transparency as implemented by `qda_modelos`, including known limits.
- `data/corpus/alert_language.md` — Allowed severity words and the rule that narrative must cite evidence-card fields.
- `data/corpus/profiles/{water_body_id}.md` — Short profile: name, why it is watched, zone names, intakes, and typical seasonality. One file per configured body.

### Models and one-time prep

- `models/README.md` — Local cache instructions for `giswqs/s2-water-unetplusplus-efficientnet-b4` (6-band, 512×512, UNet++ / EfficientNet-B4). Weights are not downloaded at request time.
- `scripts/prepare_scene_stack.py` — One-time: verify band set, CRS, and date folders for a water body. Not imported by the API.
- `scripts/generate_water_masks.py` — One-time: run segmentation over the cached archive and write `data/cache/masks/`.
- `scripts/fit_seasonal_baselines.py` — One-time: aggregate valid water pixels per zone and season into `baselines.sqlite`.
- `scripts/index_corpus.py` — One-time: embed `data/corpus/` into a local FAISS index under `data/cache/`.
- `scripts/seed_demo.py` — Loads config, checks the cache, fits or copies baselines if missing, and prints the judge walkthrough URLs. Safe to re-run.
- `notebooks/01_scene_qc.ipynb` — Exploratory SCL and band QC. Never on the demo path.

### Backend package

- `src/aquawatch/__init__.py` — Package version.
- `src/aquawatch/main.py` — FastAPI app factory, router mount, CORS for the Vite dev server, static product routes.
- `src/aquawatch/settings.py` — Loads `settings.yaml`, `water_bodies.yaml`, and env overrides into one settings object.
- `src/aquawatch/disclaimer.py` — Single disclaimer constant and a helper that stamps `confidence` and `lab_verification_required` onto any public model.
- `src/aquawatch/domain/schemas.py` — Pydantic models shared by pipeline and API: `SceneStatus`, `WaterExtent`, `IndicatorGrid`, `ZoneScore`, `Anomaly`, `EvidenceCard`, `Alert`, `PrioritySite`, `AssistantAnswer`, `CreditReport`. Evidence cards hold only deterministic fields.
- `src/aquawatch/geo/catalog.py` — Discovers scene dates from the folder tree for a configured water body. Unknown folders are ignored; missing required bands mark the date unusable.
- `src/aquawatch/geo/resample.py` — Resamples 20 m SWIR (B11, B12) onto the 10 m grid of the visible/NIR bands.
- `src/aquawatch/geo/cloud_mask.py` — Builds a valid-pixel mask from SCL (drops cloud, shadow, snow, no-data, saturated).
- `src/aquawatch/geo/clip.py` — Clips the stack to the configured AOI and returns an explicit insufficient-data result when valid pixels fall under the cutoff.
- `src/aquawatch/geo/tiles.py` — Cuts 512×512 six-band tiles and stitches the binary mask back to the AOI grid.
- `src/aquawatch/pipeline/runner.py` — Orchestrates stages for one date or a date range. Short-circuits to insufficient-data without calling the model or indicators. This is the only entry stress-test mode and the API use.
- `src/aquawatch/pipeline/ingest.py` — Opens the seven-band stack for one date via rasterio and records acquisition time from the folder name.
- `src/aquawatch/pipeline/preprocess.py` — Resample, SCL mask, AOI clip, and the insufficient-data gate.
- `src/aquawatch/pipeline/segment.py` — Runs the local UNet++ water model, computes NDWI as a cross-check, writes a binary water mask, and sets extent to water-pixel count × 100 m². Disagreement between model and NDWI lowers confidence.
- `src/aquawatch/pipeline/indicators.py` — Calls `qda_modelos` for turbidity (Miller–McKee 2004), chlorophyll-a (Gitelson/Dall'Olmo family), and transparency. Masks results to water pixels and labels them relative indicators.
- `src/aquawatch/pipeline/temporal.py` — Looks up the adaptive seasonal baseline per zone and indicator. Serves both map comparison (date A vs date B) and trend series. Thin history widens the baseline variance and lowers confidence.
- `src/aquawatch/pipeline/anomaly.py` — Flags zones at greater than N sigma versus baseline, fuses extent, turbidity, and chlorophyll into one zone score, and records which indicators crossed. This module is the unit-test focus.
- `src/aquawatch/pipeline/alerts.py` — Fills a fixed template (location, datetime, region, indicator, severity, confidence, evidence ids), then optionally asks the LLM to polish wording from that template alone.
- `src/aquawatch/pipeline/priority.py` — Computes `severity × persistence × proximity` using settlements and intakes, emits a ranked “sample here first” list with a representative GPS point per zone.
- `src/aquawatch/pipeline/stress.py` — Copies a cached scene in a temp workspace and paints a synthetic plume (location, radius, which indicator, magnitude) before `runner` executes. Original GeoTIFFs are never overwritten.
- `src/aquawatch/storage/products.py` — Reads and writes cached masks and indicator rasters keyed by scene id and content hash.
- `src/aquawatch/storage/baselines.py` — SQLite access for seasonal mean, std, and sample count. Joblib is used only if a zone stores a small fitted residual model alongside the SQL row.
- `src/aquawatch/llm/provider.py` — Narrow interface (`complete(prompt) -> str`) with three backends: template-only, local model, or remote API. Selected by env.
- `src/aquawatch/llm/retriever.py` — FAISS plus sentence-transformers over the curated corpus. Returns passages with source ids; empty retrieval yields “not in corpus” rather than a free answer.
- `src/aquawatch/llm/assistant.py` — One stack for science questions and for narrating evidence cards and alerts. Context is retrieved passages plus the JSON evidence payload. Refuses to state lab-grade concentrations.
- `src/aquawatch/llm/prompts.py` — System prompt binding the model to corpus passages and evidence JSON, plus the disclaimer reminder.
- `src/aquawatch/credits/reports.py` — Accepts one demo user’s geo-tagged photo metadata (path, GPS, time, note) and stores the report.
- `src/aquawatch/credits/checks.py` — Rejects points outside the water boundary; flags duplicates by perceptual hash and GPS-time proximity.
- `src/aquawatch/credits/leaderboard.py` — Awards credits for accepted reports and, when a verified report falls in a flagged zone, bumps that zone’s severity for ranking.
- `src/aquawatch/api/deps.py` — Request-scoped settings, pipeline runner, and stores.
- `src/aquawatch/api/routes/health.py` — Liveness plus a cache check: which water bodies and dates are actually on disk.
- `src/aquawatch/api/routes/scenes.py` — Lists configured bodies and available dates, including insufficient-data dates and why.
- `src/aquawatch/api/routes/maps.py` — Serves water extent, indicator rasters, and zone GeoJSON for Leaflet, including a before/after pair for the swipe control.
- `src/aquawatch/api/routes/anomalies.py` — Zone anomaly scores for a date, with per-indicator contributions.
- `src/aquawatch/api/routes/alerts.py` — Alert feed generated from current anomalies.
- `src/aquawatch/api/routes/explain.py` — “Why was this flagged?” evidence card: values, baseline, sigma, threshold, contributing indicators, confidence breakdown.
- `src/aquawatch/api/routes/priority.py` — Ranked sample sites with GPS, score terms, and the formula inputs visible to the client.
- `src/aquawatch/api/routes/assistant.py` — Question answering and “narrate this card / this alert” using the shared retriever and provider.
- `src/aquawatch/api/routes/credits.py` — Photo submit, check result, leaderboard, and the severity bump applied to a zone.
- `src/aquawatch/api/routes/stress.py` — Accepts plume parameters and returns the same anomaly, alert, and priority payloads as a real scene.

### Tests

- `tests/conftest.py` — Builds small in-memory zone series so anomaly tests do not need GeoTIFFs or the neural net.
- `tests/test_anomaly.py` — Sigma threshold, multi-indicator fusion, no-flag when inside the band, and confidence drop when baseline sample count is low.
- `tests/test_preprocess_gates.py` — Insufficient-data short-circuit when the valid-pixel fraction is below the cutoff; SWIR grid alignment expectation.
- `tests/test_priority.py` — Weight formula, persistence across dates, and proximity ordering between an intake-adjacent zone and a remote one.
- `tests/test_evidence_contract.py` — Evidence cards expose only pipeline numbers; disclaimer and confidence are present; a polished alert cannot add fields that were not in the card.
- `tests/fixtures/synthetic_zone_series.json` — Hand-built seasonal means and a spike date used by the anomaly tests.

### Frontend

- `frontend/package.json` — React, Vite, and Leaflet.
- `frontend/vite.config.ts` — Dev server and proxy to the FastAPI origin.
- `frontend/index.html` — Vite entry.
- `frontend/tsconfig.json` — Strict TypeScript settings.
- `frontend/src/main.tsx` — React mount.
- `frontend/src/App.tsx` — Shell: water-body switcher, date control, and route outlets.
- `frontend/src/api/client.ts` — Typed fetch wrappers. Responses with missing confidence or disclaimer are treated as errors in the UI.
- `frontend/src/map/AnomalyMap.tsx` — Leaflet map of zones colored by fused score, click to open an evidence card.
- `frontend/src/map/SwipeCompare.tsx` — Before/after swipe of two dates (extent or a chosen indicator).
- `frontend/src/map/layers.ts` — Source and layer definitions for zones, sample points, intakes, and the stress-test plume outline.
- `frontend/src/components/DisclaimerBanner.tsx` — Persistent lab-verification banner, same string as the API.
- `frontend/src/components/ConfidenceBadge.tsx` — Renders the score and the dominant reason code.
- `frontend/src/components/EvidenceCard.tsx` — Values versus baseline, thresholds crossed, contributing indicators.
- `frontend/src/components/AlertFeed.tsx` — Template alerts with optional polished summary underneath the structured fields.
- `frontend/src/components/PriorityList.tsx` — “Sample here first” ordered list with GPS and the three score factors.
- `frontend/src/components/TrendChart.tsx` — Zone time series against the seasonal baseline band.
- `frontend/src/components/AssistantPanel.tsx` — Science questions and “explain this card”, showing retrieved corpus sources.
- `frontend/src/components/Leaderboard.tsx` — Demo-user credit totals.
- `frontend/src/components/PhotoUpload.tsx` — Single-user geo-tagged photo submit and accept/reject reasons.
- `frontend/src/components/StressControls.tsx` — Plume center, radius, indicator, and magnitude; reruns the live pipeline.
- `frontend/src/pages/OverviewPage.tsx` — All watched water bodies, latest alert, and data-quality state.
- `frontend/src/pages/WaterBodyPage.tsx` — Map, swipe, trends, alerts, evidence, priority, assistant, stress controls.
- `frontend/src/pages/CreditsPage.tsx` — Upload flow and leaderboard.
- `frontend/src/styles.css` — Layout for map-plus-side-panel and the always-visible disclaimer.

## Runtime contract (shared by all phases)

Public JSON objects include:

- `confidence` — float in `[0, 1]`
- `confidence_reasons` — short machine codes
- `lab_verification_required` — always `true`
- `disclaimer` — the string from `config/settings.yaml`

Insufficient-data dates return `status: "insufficient_data"` with a reason and do not produce indicators, anomalies, or alerts.

Priority score, exposed on the wire so the ranking is auditable:

```
priority = severity × persistence × proximity
proximity = w_intake × f(distance to nearest intake) + w_settlement × f(distance to nearest settlement)
```

Weights live in `config/water_bodies.yaml`.

## Build order

### Phase 1 — Core pipeline

1. **Skeleton and contract.** Package layout, settings loader, disclaimer helper, domain schemas, `.gitignore`, data README. No detection logic yet.
2. **Catalog and config.** `water_bodies.yaml` for one body and five or six dates; `geo/catalog.py` lists what is actually on disk.
3. **Preprocess.** Resample SWIR to 10 m, SCL mask, AOI clip, insufficient-data gate. Cover with `test_preprocess_gates.py`.
4. **Segmentation and extent.** Local UNet++ tiles plus NDWI cross-check; extent = water pixels × 100 m². Cache masks.
5. **Indicators.** `qda_modelos` turbidity, chlorophyll-a, and transparency, clipped to water, stored as relative grids.
6. **Prep scripts.** `prepare_scene_stack.py`, `generate_water_masks.py`, `fit_seasonal_baselines.py` write SQLite baselines. Confirm the API process does not import `scripts/`.
7. **Temporal engine.** Seasonal baseline lookup, trend series, wider uncertainty when history is short.
8. **Anomaly fusion.** Sigma test and multi-indicator zone score. `test_anomaly.py` against the synthetic fixture, including a case that must not flag.
9. **Read API.** Health, scenes, map overlays, anomaly zones.
10. **Map UI.** Water-body page with anomaly map, date swipe, trend chart, confidence badge, and disclaimer banner. Overview page shows insufficient-data honestly.

Phase 1 is demoable as “here is the water mask, the relative indicators, and the zones that moved versus baseline,” with no generated prose.

### Phase 2 — Explainability and alerts

11. **Evidence cards.** `explain` route returns only deterministic comparisons (value, baseline mean and std, sigma, indicators that crossed, extent change). Lock this with `test_evidence_contract.py`.
12. **Alert templates.** Structured fields first: location, datetime, region, indicator, severity, confidence, evidence id. Feed works with LLM provider `none`.
13. **Optional polish.** `llm/provider.py` rewrites the template when a provider is configured. Polished text is stored beside the structured alert, not instead of it.
14. **Priority ranking.** Weighted score, GPS sample point per zone, visible factor breakdown. `test_priority.py`.
15. **UI for decisions.** Evidence card on zone click, alert feed, “sample here first” list. Banner stays visible on these views.

### Phase 3 — RAG, AquaCredits, stress-test

16. **Corpus and index.** Write the five corpus docs from the methodology you will actually cite. `index_corpus.py` builds the local FAISS index. No network at query time.
17. **Shared assistant.** One retriever plus one provider answers science questions and narrates a card or alert. Answers cite passage ids and echo evidence numbers; if retrieval is empty, say so.
18. **Assistant panel** on the water-body page, with sources shown.
19. **AquaCredits minimal path.** Photo metadata in, boundary check, duplicate check, credits, leaderboard. A accepted report inside a flagged zone increases that zone’s severity and therefore its priority. No accounts; one implicit demo user.
20. **Stress-test mode.** Plume parameters create a temp scene copy; `pipeline/runner.py` returns anomalies, an alert, an evidence card, and a re-ranked sample list. UI control sits on the water-body page so a judge can move the plume and rerun.
21. **`seed_demo.py`.** Validates cache, baselines, and vector index, then prints the click-path: open body, swipe dates, open a flagged zone, read the card, ask the assistant, inject a plume, submit a photo, see the leaderboard move.

## Demo failure rules

- Missing bands, heavy cloud, or an unknown water-body id produce a typed error or insufficient-data state, not a fallback alert.
- Stress-test writes under a temp directory and leaves `data/scenes/` unchanged.
- With `LLM_PROVIDER=none`, alerts and the assistant still return structured fields and the disclaimer; narrative is the template or a clear “language model disabled” line.
