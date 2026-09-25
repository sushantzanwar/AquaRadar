# Product boundary

AquaWatch is a decision-support and early-warning view of cached Sentinel-2 imagery. It is not a laboratory test and it does not certify that water is safe or unsafe to drink.

Every indicator is relative to the sensor, the bio-optical model, and the seasonal baseline for that zone. A high score means the satellite record moved away from that baseline. It does not by itself name a pollutant or a concentration in milligrams per litre.

Every public product carries a confidence score and states that laboratory verification is required before an operational or public-health decision. Dates with too much cloud, missing bands, or no baseline return an insufficient-data or no-baseline state and do not emit an alert.

Confidence falls when the water model disagrees with NDWI, when the segmentation weights are absent, when the seasonal sample is small, or when a season must fall back to the all-date pool.
