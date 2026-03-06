from collections import Counter


_METRICS = Counter()


def incr(metric: str, value: int = 1) -> None:
    _METRICS[metric] += value


def snapshot() -> dict[str, int]:
    return dict(_METRICS)
