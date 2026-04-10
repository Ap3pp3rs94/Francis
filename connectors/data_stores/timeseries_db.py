"""
===============================================================================
Francis 2.0 — Data Store Connectors (Time Series DB Utilities)
Path: connectors/data_stores/timeseries_db.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *time-series specific but dependency-free* primitives and helpers
used by TSDB-capable data store connectors (Prometheus, InfluxDB, TimescaleDB, VictoriaMetrics,
ClickHouse-as-TS, OpenTSDB, etc.).

It is intentionally driver/provider neutral:
  - No prometheus_client / requests / influxdb-client / psycopg imports here.
  - Standard library only.

It provides:
  - Stable time-series types:
      * TimeSeriesMetricRef
      * TimeSeriesQuery / TimeSeriesQueryResult
      * TimeSeriesSeries / TimeSeriesPoint
  - Optional capability Protocols for TSDB connectors:
      * TimeSeriesQueryRunner (run_query)
      * TimeSeriesWriter (write_series / write_points)
  - Safety + observability helpers:
      * conservative name/label key sanitizers for safe helper paths
      * query fingerprinting (stable hash; never logs raw query expression)
      * label/value summaries that avoid leaking PII/secrets
  - DataStoreResourceRef helpers:
      * metrics: kind="metric", id="<metric_name>"
      * series:  kind="series", id="<metric_name>#<hash(labelset)>"
        (default is hashed because label values can be sensitive)

DESIGN NOTES
------------
TSDB query languages vary (PromQL, Flux, InfluxQL, SQL, custom). This module avoids
forcing one query language:
  - query.language is an identifier string (not an enum)
  - query.expression is opaque and never logged
  - connectors map these into provider-specific APIs

SAFETY & OBSERVABILITY
----------------------
- Query text is suppressed from repr() and never included in summaries.
- Label values are treated as potentially sensitive; summaries include hashes only.
- Results summarize counts and field names; they do not log point values.

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from . import (
    DataStoreErrorContext,
    DataStoreIdentity,
    DataStoreResourceRef,
    DataStoreValidationError,
    redact_mapping,
    redact_uri,
    redact_value,
)

__all__ = [
    # Constants
    "TIMESERIES_CATEGORY",
    "TIMESERIES_SERVICE",
    # Normalization / sanitization
    "TimeSeriesQueryLanguage",
    "normalize_ts_query_language",
    "normalize_ts_seconds",
    "normalize_step_seconds",
    "sanitize_metric_name",
    "sanitize_label_key",
    "sanitize_label_value",
    # Hashing / summaries
    "hash_stable",
    "summarize_labelset",
    "summarize_query_params",
    "timeseries_query_summary",
    "timeseries_result_summary",
    # Types
    "TimeSeriesMetricRef",
    "TimeSeriesPoint",
    "TimeSeriesSeries",
    "TimeSeriesQuery",
    "TimeSeriesQueryResult",
    # Resource ref helpers
    "ts_metric_resource_ref",
    "ts_series_resource_ref",
    # Optional capability protocols
    "TimeSeriesQueryRunner",
    "TimeSeriesWriter",
]


# =============================================================================
# Constants
# =============================================================================

TIMESERIES_CATEGORY = "timeseries"
TIMESERIES_SERVICE = "timeseries"


# =============================================================================
# Stable hashing for correlation (no raw values in logs)
# =============================================================================


def hash_stable(value: str, *, salt: str = "francis") -> str:
    """
    Stable short hash for log correlation without revealing raw values.

    NOT a security boundary. Intended for observability hygiene.
    """
    v = (value or "").encode("utf-8", errors="ignore")
    s = (salt or "").encode("utf-8", errors="ignore")
    h = hashlib.sha256(s + b":" + v).hexdigest()
    return h[:12]


# =============================================================================
# Time + step normalization
# =============================================================================


def normalize_ts_seconds(value: int | float | datetime | None) -> int | None:
    """
    Normalize a timestamp into UTC unix seconds.

    Accepts:
      - int/float seconds
      - int/float milliseconds (heuristic)
      - int/float nanoseconds (heuristic)
      - datetime (assumed UTC if naive)

    Heuristics (safe/practical):
      - >= 1e14 => nanoseconds (divide by 1e9)
      - >= 1e11 => milliseconds (divide by 1e3)
      - else => seconds

    Returns:
      - int seconds, or None if value is None
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp())

    try:
        v = float(value)  # handles int/float-ish inputs
    except Exception as exc:  # noqa: BLE001
        raise DataStoreValidationError(
            "timestamp must be numeric or datetime",
            details={"value": redact_value(str(value))},
            context=DataStoreErrorContext(operation="timeseries.normalize_ts"),
        ) from exc

    if v < 0:
        raise DataStoreValidationError(
            "timestamp cannot be negative",
            details={"value": v},
            context=DataStoreErrorContext(operation="timeseries.normalize_ts"),
        )

    # ns
    if v >= 1e14:
        return int(v / 1e9)
    # ms
    if v >= 1e11:
        return int(v / 1e3)
    # seconds
    return int(v)


def normalize_step_seconds(step_s: int | float | None) -> int | None:
    """
    Normalize a step/resolution into whole seconds (int).

    Returns:
      - None if step_s is None
      - int >= 1 otherwise
    """
    if step_s is None:
        return None
    try:
        s = int(step_s)
    except Exception as exc:  # noqa: BLE001
        raise DataStoreValidationError(
            "step_s must be an integer number of seconds",
            details={"step_s": redact_value(str(step_s))},
            context=DataStoreErrorContext(operation="timeseries.normalize_step"),
        ) from exc
    if s <= 0:
        raise DataStoreValidationError(
            "step_s must be > 0",
            details={"step_s": s},
            context=DataStoreErrorContext(operation="timeseries.normalize_step"),
        )
    return s


# =============================================================================
# Query language + metric/label sanitization (conservative helpers)
# =============================================================================

TimeSeriesQueryLanguage = str

_LANG_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,30}[a-z0-9]$")

# Metric name: allow Prometheus-ish superset (letters/digits/_/:)
# Many TSDBs are more permissive; this is a safe helper, not a full spec.
_METRIC_RE = re.compile(r"^[A-Za-z_:][A-Za-z0-9_:]{0,199}$")

# Label keys: conservative safe identifier
_LABEL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def normalize_ts_query_language(language: str) -> TimeSeriesQueryLanguage:
    """
    Normalize/validate a TSDB query language identifier.

    Examples:
      - "promql"
      - "flux"
      - "influxql"
      - "sql"
      - "opentsdb"
      - "grafana_expr"

    This is intentionally not an enum.
    """
    lang = (language or "").strip().lower()
    if not lang:
        raise DataStoreValidationError(
            "timeseries query language is required",
            details={"field": "language"},
            context=DataStoreErrorContext(operation="timeseries.normalize_language"),
        )
    if not _LANG_RE.match(lang):
        raise DataStoreValidationError(
            "timeseries query language has invalid format",
            details={"language": redact_value(lang), "expected": _LANG_RE.pattern},
            context=DataStoreErrorContext(operation="timeseries.normalize_language"),
        )
    return lang


def sanitize_metric_name(name: str) -> str:
    """
    Validate a metric name for safe helper paths.

    NOTE:
      - This is conservative and Prometheus-friendly.
      - Providers can accept broader metric naming as needed.
    """
    s = (name or "").strip()
    if not s:
        raise DataStoreValidationError(
            "metric name is required",
            details={"field": "metric"},
            context=DataStoreErrorContext(operation="timeseries.sanitize_metric"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            "metric name contains illegal control characters",
            details={"metric": redact_value(s)},
            context=DataStoreErrorContext(operation="timeseries.sanitize_metric"),
        )
    if not _METRIC_RE.match(s):
        raise DataStoreValidationError(
            "metric name has invalid format (conservative rule)",
            details={"metric": redact_value(s), "expected": _METRIC_RE.pattern},
            context=DataStoreErrorContext(operation="timeseries.sanitize_metric"),
        )
    return s


def sanitize_label_key(key: str) -> str:
    """
    Validate a label/tag key for safe helper paths.
    """
    s = (key or "").strip()
    if not s:
        raise DataStoreValidationError(
            "label key is required",
            details={"field": "label_key"},
            context=DataStoreErrorContext(operation="timeseries.sanitize_label_key"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            "label key contains illegal control characters",
            details={"label_key": redact_value(s)},
            context=DataStoreErrorContext(operation="timeseries.sanitize_label_key"),
        )
    if not _LABEL_KEY_RE.match(s):
        raise DataStoreValidationError(
            "label key has invalid format (conservative rule)",
            details={"label_key": redact_value(s), "expected": _LABEL_KEY_RE.pattern},
            context=DataStoreErrorContext(operation="timeseries.sanitize_label_key"),
        )
    return s


def sanitize_label_value(value: str, *, max_len: int = 512) -> str:
    """
    Validate/sanitize a label/tag value for safe helper paths.

    - Disallows NUL/CR/LF
    - Caps length to avoid accidental huge payloads/log issues
    """
    s = "" if value is None else str(value)
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            "label value contains illegal control characters",
            context=DataStoreErrorContext(operation="timeseries.sanitize_label_value"),
        )
    if len(s) > max_len:
        # Values can be large; truncate for safety in helper paths.
        s = s[:max_len] + "…"
    return s


# =============================================================================
# Labelset summaries (no raw label values in logs)
# =============================================================================


def summarize_labelset(labels: Mapping[str, str] | None, *, max_keys: int = 50) -> dict[str, Any]:
    """
    Return a log-safe summary of a labelset.

    - Preserves keys (keys can still be sensitive; keep your label keys clean)
    - Values are represented by {len, hash}, never raw values
    """
    if not labels:
        return {"count": 0, "items": {}}

    if not isinstance(labels, Mapping):
        return {"count": 1, "items": {"<non_mapping>": {"type": type(labels).__name__}}}

    keys = sorted(str(k) for k in labels.keys())
    truncated = False
    if len(keys) > max_keys:
        keys = keys[:max_keys]
        truncated = True

    items: dict[str, Any] = {}
    for k in keys:
        kk = k
        if "\x00" in kk or "\r" in kk or "\n" in kk:
            kk = "<invalid_key>"
        try:
            v = "" if labels.get(k) is None else str(labels.get(k))
            items[kk] = {"len": len(v), "hash": hash_stable(v)}
        except Exception:
            items[kk] = {"type": "error"}

    if truncated:
        items["…"] = {"truncated": True}

    return {"count": len(labels), "items": items}


def summarize_query_params(params: Mapping[str, Any] | None, *, max_keys: int = 50) -> dict[str, Any]:
    """
    Return a log-safe summary of query parameters.

    - No raw values
    - Provides type + length/hash for strings/bytes
    """
    if not params:
        return {"count": 0, "items": {}}
    if not isinstance(params, Mapping):
        return {"count": 1, "items": {"<non_mapping>": {"type": type(params).__name__}}}

    keys = sorted(str(k) for k in params.keys())
    truncated = False
    if len(keys) > max_keys:
        keys = keys[:max_keys]
        truncated = True

    def _shape(v: Any) -> dict[str, Any]:
        if v is None:
            return {"type": "null"}
        if isinstance(v, bool):
            return {"type": "bool"}
        if isinstance(v, int) and not isinstance(v, bool):
            return {"type": "int"}
        if isinstance(v, float):
            return {"type": "float"}
        if isinstance(v, str):
            return {"type": "str", "len": len(v), "hash": hash_stable(v)}
        if isinstance(v, (bytes, bytearray)):
            b = bytes(v)
            return {"type": "bytes", "len": len(b), "hash": hash_stable(b[:256].hex())}
        if isinstance(v, Mapping):
            return {"type": "object", "keys": len(v)}
        if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
            return {"type": "array", "len": len(v)}
        return {"type": type(v).__name__}

    items: dict[str, Any] = {}
    for k in keys:
        kk = k
        if "\x00" in kk or "\r" in kk or "\n" in kk:
            kk = "<invalid_key>"
        try:
            items[kk] = _shape(params.get(k))
        except Exception:
            items[kk] = {"type": "error"}

    if truncated:
        items["…"] = {"truncated": True}

    return {"count": len(params), "items": items}


# =============================================================================
# Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class TimeSeriesMetricRef:
    """
    Provider-agnostic reference to a metric.

    - provider_id is the data store provider id (e.g., "prometheus", "influxdb", "timescaledb")
    - name is the metric/measurement identifier
    """

    provider_id: str
    name: str

    identity: DataStoreIdentity | None = None
    uri: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # metric names are generally safe, but still avoid control chars and enforce
        # a conservative safe subset for helper usage.
        object.__setattr__(self, "name", sanitize_metric_name(self.name))

    def canonical(self) -> str:
        parts = [self.provider_id, TIMESERIES_SERVICE, "metric", self.name]
        if self.identity and self.identity.region:
            parts.insert(1, self.identity.region)
        return ":".join(p for p in parts if p)

    def redacted_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "identity": self.identity.redacted_dict() if self.identity else None,
            "uri": redact_uri(self.uri) if self.uri else None,
            "meta": redact_mapping(self.meta),
        }


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    """
    One time-series data point.

    values:
      - supports one or more numeric fields (e.g., {"value": 1.0} or {"min":..., "max":...})
    """

    ts: int
    values: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        t = normalize_ts_seconds(self.ts)
        if t is None:
            raise DataStoreValidationError(
                "point timestamp is required",
                context=DataStoreErrorContext(operation="timeseries.point.validate"),
            )
        object.__setattr__(self, "ts", t)

        if not isinstance(self.values, Mapping):
            raise DataStoreValidationError(
                "point values must be a mapping",
                context=DataStoreErrorContext(operation="timeseries.point.validate"),
            )

        # Ensure values are floats (best-effort) and keys are sane
        out: dict[str, float] = {}
        for k, v in self.values.items():
            key = str(k).strip() or "value"
            if "\x00" in key or "\r" in key or "\n" in key:
                raise DataStoreValidationError(
                    "point value key contains illegal control characters",
                    details={"key": redact_value(key)},
                    context=DataStoreErrorContext(operation="timeseries.point.validate"),
                )
            try:
                out[key] = float(v)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "point value must be numeric",
                    details={"key": redact_value(key), "value": redact_value(str(v))},
                    context=DataStoreErrorContext(operation="timeseries.point.validate"),
                ) from exc
        object.__setattr__(self, "values", out)


@dataclass(frozen=True, slots=True)
class TimeSeriesSeries:
    """
    One series in a result set: metric + labelset + points.

    SAFETY:
      - points are suppressed from repr()
      - redacted_dict never includes label values or point values
    """

    metric: str
    labels: Mapping[str, str] = field(default_factory=dict)
    points: Sequence[TimeSeriesPoint] = field(default_factory=tuple, repr=False)

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric", sanitize_metric_name(self.metric))

        # Validate label keys conservatively; values are sanitized for control chars
        if self.labels and not isinstance(self.labels, Mapping):
            raise DataStoreValidationError(
                "labels must be a mapping",
                context=DataStoreErrorContext(operation="timeseries.series.validate"),
            )

        norm: dict[str, str] = {}
        for k, v in (self.labels or {}).items():
            kk = sanitize_label_key(str(k))
            vv = sanitize_label_value("" if v is None else str(v))
            norm[kk] = vv
        object.__setattr__(self, "labels", norm)

    def labelset_fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable fingerprint of metric + labelset without exposing label values.
        """
        # Deterministic order of keys
        items = [(k, self.labels.get(k, "")) for k in sorted(self.labels.keys())]
        payload = {
            "metric": self.metric,
            "labels": [{"k": k, "v_hash": hash_stable(v)} for k, v in items],
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "labels": summarize_labelset(self.labels),
            "points_count": len(self.points or ()),
            "labelset_fingerprint": self.labelset_fingerprint(),
            "meta": redact_mapping(self.meta),
        }


@dataclass(frozen=True, slots=True)
class TimeSeriesQuery:
    """
    Provider-agnostic time-series query.

    SAFETY:
      - expression is suppressed from repr()
      - redacted_dict never includes raw expression text
    """

    language: TimeSeriesQueryLanguage
    expression: str = field(repr=False)

    # Optional time range / resolution
    start_ts: int | float | datetime | None = None
    end_ts: int | float | datetime | None = None
    step_s: int | float | None = None

    # Optional params for templating/bindings (connector-defined usage)
    params: Mapping[str, Any] = field(default_factory=dict)

    # Governance hint; TSDB queries are typically read-only
    read_only: bool = True

    # Connector hints
    timeout_s: float | None = None
    max_series: int | None = None

    # Optional URI for context; redacted in summaries
    uri: str | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        lang = normalize_ts_query_language(self.language)
        object.__setattr__(self, "language", lang)

        expr = "" if self.expression is None else str(self.expression)
        if "\x00" in expr:
            raise DataStoreValidationError(
                "query expression contains NUL",
                details={"language": lang},
                context=DataStoreErrorContext(operation="timeseries.query.validate"),
            )
        if len(expr) > 2_000_000:
            raise DataStoreValidationError(
                "query expression too large",
                details={"language": lang, "expr_len": len(expr), "max": 2_000_000},
                context=DataStoreErrorContext(operation="timeseries.query.validate"),
            )
        object.__setattr__(self, "expression", expr)

        st = normalize_ts_seconds(self.start_ts)
        en = normalize_ts_seconds(self.end_ts)
        object.__setattr__(self, "start_ts", st)
        object.__setattr__(self, "end_ts", en)

        if st is not None and en is not None and st > en:
            raise DataStoreValidationError(
                "start_ts cannot be after end_ts",
                details={"start_ts": st, "end_ts": en},
                context=DataStoreErrorContext(operation="timeseries.query.validate"),
            )

        step = normalize_step_seconds(self.step_s)
        object.__setattr__(self, "step_s", step)

        if self.max_series is not None:
            try:
                ms = int(self.max_series)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "max_series must be an integer",
                    details={"max_series": redact_value(str(self.max_series))},
                    context=DataStoreErrorContext(operation="timeseries.query.validate"),
                ) from exc
            if ms <= 0:
                raise DataStoreValidationError(
                    "max_series must be > 0",
                    details={"max_series": ms},
                    context=DataStoreErrorContext(operation="timeseries.query.validate"),
                )
            object.__setattr__(self, "max_series", ms)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=DataStoreErrorContext(operation="timeseries.query.validate"),
                ) from exc
            if ts <= 0:
                raise DataStoreValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=DataStoreErrorContext(operation="timeseries.query.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

    def fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable fingerprint of language + expression + query options.

        Safe for logs/correlation. Never returns the raw expression.
        """
        payload = {
            "language": self.language,
            "expr_hash": hash_stable(self.expression, salt=salt),
            "expr_len": len(self.expression),
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "step_s": self.step_s,
            "read_only": bool(self.read_only),
            "max_series": self.max_series,
            "params": summarize_query_params(self.params),
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return timeseries_query_summary(self)


@dataclass(frozen=True, slots=True)
class TimeSeriesQueryResult:
    """
    Provider-agnostic result container.

    SAFETY:
      - series points are suppressed from repr()
      - redacted_dict returns counts + safe summaries only
    """

    language: TimeSeriesQueryLanguage
    query_fingerprint: str

    series: Sequence[TimeSeriesSeries] = field(default_factory=tuple, repr=False)

    # Provider-defined stats (must be log-safe; still passed through redact_mapping)
    # Examples: {"duration_ms": 12, "partial": False, "warnings": [...]}
    stats: Mapping[str, Any] = field(default_factory=dict)

    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return timeseries_result_summary(self)


# =============================================================================
# DataStoreResourceRef helpers
# =============================================================================


def ts_metric_resource_ref(
    metric: str,
    *,
    provider_id: str,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a metric.

    kind="metric", id="<metric_name>"
    """
    m = sanitize_metric_name(metric)
    return DataStoreResourceRef(
        provider_id=provider_id,
        service=TIMESERIES_SERVICE,
        kind="metric",
        id=m,
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


def ts_series_resource_ref(
    metric: str,
    labels: Mapping[str, str] | None,
    *,
    provider_id: str,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    include_raw_label_values: bool = False,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a series (metric + labelset).

    IMPORTANT:
    DataStoreResourceRef.id is not automatically redacted. Label values can be PII.
    So by default we store a hashed labelset id.

    id format:
      - include_raw_label_values=False (default): "<metric>#<hash(labelset)>"
      - include_raw_label_values=True:            "<metric>{k=v,...}" (NOT RECOMMENDED unless you never log refs)

    kind="series"
    """
    m = sanitize_metric_name(metric)
    lab = labels or {}

    # Normalize label keys/values for determinism (and safety).
    norm: dict[str, str] = {}
    for k, v in lab.items():
        kk = sanitize_label_key(str(k))
        vv = sanitize_label_value("" if v is None else str(v))
        norm[kk] = vv

    if include_raw_label_values:
        # WARNING: raw label values in id; do not log this ref.
        parts = [f"{k}={norm[k]}" for k in sorted(norm.keys())]
        sid = f"{m}" + "{" + ",".join(parts) + "}"
    else:
        items = [(k, norm[k]) for k in sorted(norm.keys())]
        payload = {"metric": m, "labels": [{"k": k, "v_hash": hash_stable(v)} for k, v in items]}
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        sid = f"{m}#{hash_stable(s)}"

    return DataStoreResourceRef(
        provider_id=provider_id,
        service=TIMESERIES_SERVICE,
        kind="series",
        id=sid,
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


# =============================================================================
# Optional capability protocols
# =============================================================================


@runtime_checkable
class TimeSeriesQueryRunner(Protocol):
    """
    Optional capability: run time-series queries.

    Implementations SHOULD:
      - accept TimeSeriesQuery
      - raise DataStoreError subclasses on failure (from connectors/data_stores/__init__.py)
      - never log raw query expressions or raw label values
    """

    def run_query(
        self,
        query: TimeSeriesQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> TimeSeriesQueryResult: ...


@runtime_checkable
class TimeSeriesWriter(Protocol):
    """
    Optional capability: write/ingest time-series points.

    Providers differ (line protocol, remote write, SQL inserts). Keep generic:
      - write_series: series-level ingest (metric + labels + points)
      - write_points: metric-level ingest with per-point values
    """

    def write_series(
        self,
        series: TimeSeriesSeries,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> Any: ...

    def write_points(
        self,
        metric: str,
        points: Sequence[TimeSeriesPoint],
        *,
        labels: Mapping[str, str] | None = None,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> Any: ...


# =============================================================================
# Log-safe summaries
# =============================================================================


def timeseries_query_summary(query: TimeSeriesQuery, *, salt: str = "francis") -> dict[str, Any]:
    """
    Log-safe summary of a TimeSeriesQuery.

    - excludes raw expression
    - includes fingerprint + expression length/hash + option summaries
    """
    if not isinstance(query, TimeSeriesQuery):
        raise DataStoreValidationError(
            "timeseries_query_summary expects TimeSeriesQuery",
            details={"type": type(query).__name__},
            context=DataStoreErrorContext(operation="timeseries.query.summary"),
        )

    return {
        "language": query.language,
        "expr_len": len(query.expression or ""),
        "expr_hash": hash_stable(query.expression or "", salt=salt),
        "fingerprint": query.fingerprint(salt=salt),
        "read_only": bool(query.read_only),
        "start_ts": query.start_ts,
        "end_ts": query.end_ts,
        "step_s": query.step_s,
        "timeout_s": query.timeout_s,
        "max_series": query.max_series,
        "params": summarize_query_params(query.params),
        "uri": redact_uri(query.uri) if query.uri else None,
        "meta": redact_mapping(query.meta),
    }


def timeseries_result_summary(result: TimeSeriesQueryResult) -> dict[str, Any]:
    """
    Log-safe summary of a TimeSeriesQueryResult.

    - excludes label values and point values
    - includes series count, point counts, and sampled metric names / label keys
    """
    if not isinstance(result, TimeSeriesQueryResult):
        return {"type": type(result).__name__}

    series_count = len(result.series or ())
    total_points = 0
    metric_names: set[str] = set()
    label_keys: set[str] = set()

    # Best-effort sampling (avoid walking huge results)
    sample_series_n = min(series_count, 20)
    for i in range(sample_series_n):
        try:
            s = result.series[i]  # type: ignore[index]
            if isinstance(s, TimeSeriesSeries):
                metric_names.add(s.metric)
                total_points += len(s.points or ())
                for k in (s.labels or {}).keys():
                    label_keys.add(str(k))
        except Exception:
            continue

    return {
        "language": result.language,
        "query_fingerprint": result.query_fingerprint,
        "series_count": series_count,
        "sampled_total_points": total_points,
        "sampled_metrics": sorted(metric_names)[:50],
        "sampled_label_keys": sorted(label_keys)[:100],
        "stats": redact_mapping(result.stats),
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }
