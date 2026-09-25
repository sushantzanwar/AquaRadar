# Sentinel-2 Satellite Remote Sensing for Water Quality

## About Sentinel-2

Sentinel-2 is a European Space Agency (ESA) satellite mission providing high-resolution multispectral imagery of Earth's surface. AquaWatch uses Sentinel-2 Level-2A (L2A) scenes — atmospherically corrected surface reflectance data.

**Key characteristics:**
- **Revisit time:** ~5 days at the equator (10-day per satellite)
- **Resolution:** 10 m (visible/NIR bands), 20 m (red-edge/SWIR bands, resampled to 10 m by AquaWatch)
- **Swath width:** 290 km
- **Free and open data:** via Copernicus programme

## Spectral Bands Used by AquaWatch

| Band | Wavelength | Resolution | AquaWatch Use |
|---|---|---|---|
| B02 (Blue) | 492 nm | 10 m | Water masking (NDWI) |
| B03 (Green) | 560 nm | 10 m | NDWI, turbidity |
| B04 (Red) | 665 nm | 10 m | Turbidity, sediment |
| B05 (Red-edge 1) | 705 nm | 20 m | Chlorophyll (optional) |
| B06 (Red-edge 2) | 740 nm | 20 m | Chlorophyll (optional) |
| B08 (NIR) | 833 nm | 10 m | Water masking (NDWI) |
| B11 (SWIR 1) | 1614 nm | 20 m | Turbidity (SWIR ratio) |
| B12 (SWIR 2) | 2202 nm | 20 m | Turbidity |
| SCL | — | 20 m | Scene Classification (cloud mask) |

## How AquaWatch Measures Water Quality

### Water Masking
AquaWatch identifies water pixels using two approaches combined:
1. **NDWI (Normalized Difference Water Index):** NDWI = (B03 – B08) / (B03 + B08). Values > threshold = water.
2. **Deep Learning Segmentation:** A UNet++ model with EfficientNet-B4 encoder trained on Sentinel-2 water scenes provides a more accurate mask, especially for complex shorelines.

When the segmentation model is unavailable, NDWI-only masking is used and confidence is lowered.

### Turbidity Estimation
Turbidity is estimated from the SWIR/red ratio. High SWIR reflectance relative to green indicates suspended sediment. The raw index is compared against the seasonal baseline for each zone.

**Formula (simplified):** Turbidity Index = B11 / B03 (scaled)

### Chlorophyll-a Estimation
When B05 and B06 are available, AquaWatch uses the two-band red-edge ratio:
**Chl-a Index = B05 / B04 – 1** (Gitelson / Dall'Olmo index)

This is sensitive to phytoplankton and algal biomass. Requires red-edge bands at 20 m resolution (resampled).

### Transparency (Secchi Depth Proxy)
Modelled as the inverse of the turbidity + chlorophyll combined index. Decreasing transparency = increasing optical depth of the water column.

## Cloud Masking

AquaWatch uses the Sentinel-2 Scene Classification Layer (SCL) to mask out:
- Cloud pixels (SCL class 8, 9)
- Cloud shadow pixels (SCL class 3)
- Snow/ice pixels (SCL class 11)

Scenes with more than a configured fraction of masked pixels over the water body are marked as `unusable`. Confidence is reduced for partially cloudy scenes.

## Baseline Construction

For each water body zone and each indicator, AquaWatch maintains a seasonal baseline:
- Computed from all historical scenes of the same calendar month (± 1 month)
- Minimum number of baseline scenes required (configurable)
- Stored as mean + standard deviation per zone

Anomalies are detected as deviations beyond a sigma threshold from this baseline.

## Limitations of Satellite-Based Water Quality Monitoring

1. **Surface only:** Satellites see only the top ~1 m of the water column. Deep contaminants are invisible.
2. **Optical only:** AquaWatch cannot detect dissolved chemicals (heavy metals, bacteria, viruses, most pharmaceuticals).
3. **Cloud cover:** Cloudy days produce no data. Revisit time means events can be missed between passes.
4. **Atmospheric correction errors:** Haze, aerosols, and sun glint can affect reflectance values.
5. **No species identification:** Algae species cannot be distinguished from satellite data.
6. **Relative, not absolute:** All AquaWatch indices are relative measurements compared to a local baseline, not absolute physical concentrations.

All of these limitations make laboratory verification an essential complement to satellite monitoring — never a replacement for it.
