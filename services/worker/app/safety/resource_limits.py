from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerLimits:
    max_jobs_per_cycle: int
    max_runtime_seconds: int


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def normalize_limits(*, max_jobs_per_cycle: int, max_runtime_seconds: int) -> WorkerLimits:
    return WorkerLimits(
        max_jobs_per_cycle=_clamp(int(max_jobs_per_cycle), 1, 500),
        max_runtime_seconds=_clamp(int(max_runtime_seconds), 1, 600),
    )
