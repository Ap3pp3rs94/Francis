from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.telemetry.tracing import current_context


def _metrics_path() -> Path:
    return data_dir() / "logs" / "metrics" / "metrics.jsonl"


def _coerce_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _coerce_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce_jsonable(item) for item in value]
    return str(value)


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


@dataclass(frozen=True, slots=True)
class MetricPoint:
    ts: float
    name: str
    kind: str
    value: float
    unit: str
    fields: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "name": self.name,
            "kind": self.kind,
            "value": self.value,
            "unit": self.unit,
            **self.fields,
        }


def emit_metric(
    name: str,
    *,
    kind: str,
    value: float = 1.0,
    unit: str = "count",
    **fields: Any,
) -> dict[str, Any]:
    payload = MetricPoint(
        ts=time.time(),
        name=name.strip() or "metric.unknown",
        kind=kind.strip() or "counter",
        value=float(value),
        unit=unit.strip() or "count",
        fields={**current_context().as_dict(), **{key: _coerce_jsonable(item) for key, item in fields.items()}},
    ).to_dict()
    _append_line(_metrics_path(), payload)
    return payload


def increment(name: str, value: float = 1.0, **fields: Any) -> dict[str, Any]:
    return emit_metric(name, kind="counter", value=value, unit="count", **fields)


def gauge(name: str, value: float, *, unit: str = "value", **fields: Any) -> dict[str, Any]:
    return emit_metric(name, kind="gauge", value=value, unit=unit, **fields)


def histogram(name: str, value: float, *, unit: str = "ms", **fields: Any) -> dict[str, Any]:
    return emit_metric(name, kind="histogram", value=value, unit=unit, **fields)


def read_metrics(*, name: str | None = None, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    path = _metrics_path()
    if not path.exists():
        return []

    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if name and str(payload.get("name", "")).strip().lower() != name.strip().lower():
            continue
        if kind and str(payload.get("kind", "")).strip().lower() != kind.strip().lower():
            continue
        items.append(payload)
    if limit <= 0:
        return items
    return items[-limit:]
