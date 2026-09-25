"""Sigma threshold, fusion, a quiet scene, and thin-baseline confidence."""

from aquawatch.pipeline.anomaly import IndicatorSample, evaluate_zone


def _evaluate(series, name):
    samples = [IndicatorSample(**row) for row in series[name]["samples"]]
    return evaluate_zone(
        samples,
        sigma_threshold=series["sigma_threshold"],
        weights=series["weights"],
        min_baseline_samples=series["min_baseline_samples"],
        z_cap=series["z_cap"],
    )


def test_quiet_scene_is_not_flagged(series):
    result = _evaluate(series, "quiet")
    assert result.flagged is False
    assert result.contributing == []


def test_turbidity_spike_crosses_three_sigma(series):
    result = _evaluate(series, "turbidity_spike")
    assert result.flagged is True
    assert result.contributing == ["turbidity"]
    turbidity = next(row for row in result.comparisons if row.indicator == "turbidity")
    assert turbidity.sigma == 4
    assert turbidity.crossed is True


def test_two_indicators_raise_the_fused_score(series):
    single = _evaluate(series, "turbidity_spike")
    dual = _evaluate(series, "dual_spike")
    assert dual.flagged is True
    assert set(dual.contributing) == {"turbidity", "chlorophyll"}
    assert dual.fused_score > single.fused_score


def test_thin_baseline_lowers_confidence(series):
    full = _evaluate(series, "turbidity_spike")
    thin = _evaluate(series, "low_history_spike")
    assert thin.flagged is True
    assert thin.confidence < full.confidence
    assert "baseline_sample_size" in thin.confidence_reasons
    assert thin.confidence == 2 / series["min_baseline_samples"]
