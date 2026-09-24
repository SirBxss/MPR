"""Count-only reference outcomes and exact integer timestamp summaries."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def _quantiles(values: list[int]) -> dict[str, int | None]:
    ordered = sorted(values)
    if not ordered:
        return dict.fromkeys(("min", "p50", "p95", "p99", "max"))
    result = {"min": ordered[0], "max": ordered[-1]}
    for percentile in (50, 95, 99):
        result[f"p{percentile}"] = ordered[(percentile * len(ordered) + 99) // 100 - 1]
    return result


def summarize_timestamp_deltas(deltas_ns: Iterable[int]) -> dict[str, Any]:
    """Reference minus estimate; nearest-rank percentiles, no float rounding."""
    values = list(deltas_ns)
    if any(type(value) is not int for value in values):
        raise TypeError("timestamp deltas must be Python integers")
    return {
        "count": len(values),
        "negative_count": sum(value < 0 for value in values),
        "zero_count": values.count(0),
        "positive_count": sum(value > 0 for value in values),
        "signed_reference_minus_estimate_ns": _quantiles(values),
        "absolute_ns": _quantiles([abs(value) for value in values]),
    }


class PairDiagnostics:
    """Only bounded scalar deltas and aggregate counts survive conversion."""

    def __init__(self) -> None:
        self.reference_failures: Counter[str] = Counter()
        self.segment_failures: Counter[str] = Counter()
        self.by_topology: dict[str, dict[str, Any]] = {}
        self.deltas: dict[str, list[int]] = {
            "all_numeric_pairs": [],
            "anchored_h100_pairs": [],
            "sensor_anchored_h100_pairs": [],
        }

    def reference(self, failure: str | None, segment_failures: dict[str, int]) -> None:
        if failure is not None:
            self.reference_failures[failure] += 1
        self.segment_failures.update(segment_failures)

    def pair(self, *, topology: str, estimator_available: bool,
             reference_failure: str | None, outcome: str,
             sensor_ready: bool, delta_ns: int) -> None:
        row = self.by_topology.setdefault(topology, {
            "pair_count": 0, "available_estimator_pair_count": 0,
            "outcome_counts": Counter(), "reference_failure_counts": Counter(),
            "reference_failure_counts_with_available_estimator": Counter(),
        })
        row["pair_count"] += 1
        row["available_estimator_pair_count"] += int(estimator_available)
        row["outcome_counts"][outcome] += 1
        if reference_failure is not None:
            row["reference_failure_counts"][reference_failure] += 1
            if estimator_available:
                row["reference_failure_counts_with_available_estimator"][reference_failure] += 1
        self.deltas["all_numeric_pairs"].append(delta_ns)
        if outcome == "anchored_h100_ready":
            self.deltas["anchored_h100_pairs"].append(delta_ns)
            if sensor_ready:
                self.deltas["sensor_anchored_h100_pairs"].append(delta_ns)

    def summary(self) -> dict[str, Any]:
        return {
            "reference_failure_detail_counts": dict(sorted(self.reference_failures.items())),
            "reference_segment_failure_counts": dict(sorted(self.segment_failures.items())),
            "pair_outcomes_by_estimate_topology": {
                topology: {key: dict(sorted(value.items())) if isinstance(value, Counter) else value
                           for key, value in row.items()}
                for topology, row in sorted(self.by_topology.items())
            },
            "timestamp_delta_summaries": {
                key: summarize_timestamp_deltas(values) for key, values in self.deltas.items()
            },
        }
