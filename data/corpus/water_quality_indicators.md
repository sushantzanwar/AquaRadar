# Water Quality Indicators — AquaWatch Science Guide

## What is Turbidity?

Turbidity measures the cloudiness or haziness of water caused by suspended particles such as sediment, algae, or pollutants. In AquaWatch, turbidity is estimated from the SWIR (short-wave infrared) and red spectral bands of Sentinel-2 imagery as a relative index.

**Key facts:**
- Higher turbidity values indicate more suspended material in the water column.
- Turbidity alone cannot identify the *type* of contaminant — only that particles are elevated above baseline.
- Seasonal variation is normal: rainfall, runoff, and wind events naturally raise turbidity.
- Sustained high turbidity can block sunlight, harm aquatic life, and indicate erosion or pollution events.

**WHO guideline:** Drinking water turbidity should ideally be below 1 NTU (nephelometric turbidity unit). Above 4 NTU triggers treatment review. AquaWatch turbidity is a relative index and cannot be converted directly to NTU.

## What is Chlorophyll-a?

Chlorophyll-a (chl-a) is the primary pigment in phytoplankton and algae. Elevated chlorophyll-a signals algal growth — which can precede harmful algal blooms (HABs).

**Key facts:**
- AquaWatch estimates chl-a using the Dall'Olmo / Gitelson red-edge index (requires Sentinel-2 bands B05 and B06).
- Without B05/B06, chlorophyll is reported as unavailable.
- Chl-a values exceeding 3–4 sigma above baseline indicate a potential bloom.
- Some algal species produce cyanotoxins dangerous to humans, livestock, and wildlife.
- **WHO alert level:** Cyanobacterial blooms above 100,000 cells/mL or 50 µg/L chl-a pose a moderate health risk.

## What is Transparency (Secchi Depth)?

Water transparency reflects how deep light penetrates the water column. In AquaWatch, transparency is modelled from the inverse relationship with turbidity and chlorophyll.

**Key facts:**
- Decreasing transparency = worsening water clarity.
- Useful as a proxy for eutrophication status.
- Secchi depth < 1 m in lakes often indicates hypereutrophic conditions.

## Water Extent

Water extent tracks the surface area (in m²) of the water body in each satellite scene.

**Key facts:**
- Large decreases in extent may indicate drought, water extraction, or dam operations.
- Large increases may indicate flooding.
- Changes > 2 sigma from baseline are flagged by AquaWatch as anomalies.

## Sigma Deviation (Anomaly Scoring)

AquaWatch calculates how many standard deviations (sigma, σ) the current value is from the seasonal baseline mean.

| Sigma value | Interpretation |
|---|---|
| 0 – 1σ | Normal range |
| 1 – 2σ | Slightly elevated, monitor |
| 2 – 3σ | Anomalous, flag for review |
| > 3σ | Severe anomaly, high priority |

A "fused score" combines sigma deviations from multiple indicators (turbidity, chlorophyll, extent) into a single zone-level risk score.
