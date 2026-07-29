# latency.py
# Small aggregation helper for latency numbers collected across suite runs.

import statistics


def p50(latencies: list[float]) -> float:
    """Return the median latency from a list of latency measurements (ms).

    Returns 0.0 for an empty list — no data means nothing to report.
    """
    if not latencies:
        return 0.0
    return statistics.median(latencies)
