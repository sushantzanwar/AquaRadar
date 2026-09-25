# AquaWatch Alerts — Interpretation Guide

## Alert Severity Levels

AquaWatch generates three levels of water quality alerts based on fused anomaly scores across all active indicators:

### Watch 🟡
- **Trigger:** Fused score 1σ – 2σ above seasonal baseline
- **Meaning:** Conditions are elevated but within the range of natural variability extremes. Worth tracking.
- **Recommended action:** Increase monitoring frequency. Review if the pattern persists across multiple dates.
- **Do NOT:** Issue public warnings or take operational decisions based on a single Watch alert.

### Warning 🟠
- **Trigger:** Fused score 2σ – 3σ above seasonal baseline  
- **Meaning:** Statistically significant anomaly. Likely not normal variation. Investigate.
- **Recommended action:** Dispatch field sampling team. Collect water samples from flagged zones. Submit to certified lab for analysis.

### Severe 🔴
- **Trigger:** Fused score > 3σ above seasonal baseline, or multiple indicators simultaneously crossing thresholds
- **Meaning:** Major anomaly. High probability of a real contamination, bloom, or pollution event.
- **Recommended action:** Urgent field sampling. Notify water authority. Consider precautionary intake management. Await lab results before public advisories.

## Reading an Evidence Card

An evidence card provides zone-level detail for a flagged anomaly.

### Comparisons Table
Each row shows one indicator:
- **Value:** Current satellite-derived index for this zone on this date
- **Baseline mean:** Long-term seasonal average from historical scenes
- **Baseline std:** Standard deviation of the baseline (variability)
- **Sigma (σ):** How many standard deviations the current value is from the baseline mean. Higher = more anomalous.
- **Threshold crossed:** Whether the sigma value exceeds the configured detection threshold (default: 2σ)

### Fused Score
The overall zone risk score is a weighted combination of individual indicator sigma values:
- Turbidity: highest weight (dominant signal for contamination)
- Chlorophyll-a: medium weight
- Extent change: lower weight unless extreme

### Contributing Indicators
The list of indicators that crossed their thresholds and contributed to the alert.

## Priority Sampling List

The "Sample here first" list ranks flagged zones by a priority formula that accounts for:
- **Severity:** How anomalous is the zone? (sigma-based)
- **Persistence:** Has the zone been flagged on multiple previous dates?
- **Proximity:** How close is the zone to water intakes or human settlements?
- **Distance to intake (m):** Closer = higher risk to drinking water supply
- **Distance to settlement (m):** Closer = higher risk to communities

**Interpretation:** Zone ranked #1 poses the highest combined risk and should receive the first field visit.

## Alert Narrative

Each alert includes a text summary. The narrative source indicates where it came from:

| Source | Meaning |
|---|---|
| `template` | Pre-written text template, no LLM used |
| `llm` | AI-generated narrative from LLM + evidence |
| `llm_disabled` | LLM not configured, showing extracted text |
| `llm_rejected` | LLM output rejected (didn't respect evidence), using template |
| `llm_unreachable` | LLM API failed, using template |

## Confidence Scores

Every AquaWatch response includes a confidence score (0.0 – 1.0):
- **> 0.8:** High confidence — multiple indicators agree, strong baseline, clear satellite image
- **0.6 – 0.8:** Moderate confidence — some uncertainty (e.g., cloud cover, thin baseline)
- **< 0.6:** Low confidence — exercise caution. Check confidence reasons.

**Confidence is reduced by:**
- Cloud coverage or shadow over the zone (SCL mask)
- Segmentation model unavailable (falls back to NDWI only)
- Fewer than the minimum number of baseline scenes
- Sensor disagreement between model and NDWI
