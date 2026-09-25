"""Severity, persistence, and intake proximity order the sample list."""

from aquawatch.pipeline.priority import priority_score, proximity_factor
from aquawatch.pipeline.temporal import persistence_ratio


def test_intake_adjacent_zone_outranks_a_remote_zone():
    scale = 5000
    near = proximity_factor(100, 5000, 0.7, 0.3, scale)
    remote = proximity_factor(20000, 5000, 0.7, 0.3, scale)
    assert priority_score(0.8, 1.0, near) > priority_score(0.8, 1.0, remote)


def test_persistence_increases_priority():
    proximity = proximity_factor(100, 1000, 0.7, 0.3, 5000)
    steady = persistence_ratio([True, True, True, False])
    brief = persistence_ratio([True, False, False, False])
    assert steady == 0.75
    assert brief == 0.25
    assert priority_score(0.8, steady, proximity) > priority_score(0.8, brief, proximity)


def test_score_is_the_product_of_the_three_terms():
    assert priority_score(0.5, 0.5, 0.5) == 0.125
