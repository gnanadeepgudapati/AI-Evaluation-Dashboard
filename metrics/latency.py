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


def tokens_per_sec(output_tokens: int, latency_ms: float, call_count: int = 1) -> float | None:
    """Approximate generation throughput: average output tokens per call
    divided by the p50 call latency. An estimate — token totals are summed
    across calls while latency is a percentile, not a sum."""
    if latency_ms <= 0 or call_count <= 0:
        return None
    return (output_tokens / call_count) / (latency_ms / 1000.0)
