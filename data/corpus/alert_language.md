# Alert language

Severity words are only `watch`, `warning`, and `severe`. `watch` starts just above the sigma threshold, `warning` above 4 sigma, and `severe` above 5 sigma, using the largest absolute z-score among fused indicators that crossed.

An alert must name the water body, the zone, the acquisition date, the driving indicator, the severity, the confidence, and the evidence id. A narrative must cite the evidence-card numbers: the indicator value, the baseline mean, the baseline standard deviation, and the sigma. It must not add a concentration, a pollutant name, or a laboratory result that is not in the card.

Polished wording sits beside the template. If the language model is disabled, unreachable, or introduces numbers that are not on the card, the template remains the narrative.

Priority language is "sample here first". The score is severity times persistence times proximity. Proximity is a weighted falloff to the nearest intake and the nearest settlement. The score orders fieldwork. It does not estimate health risk.
