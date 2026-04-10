"""
===============================================================================
Francis 2.0 — Data Store Connectors (PostgreSQL Utilities)
Path: connectors/data_stores/postgres.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *PostgreSQL-specific but dependency-free* primitives and helpers
used by Postgres-capable data store connectors.

It is intentionally driver neutral:
  - No psycopg / asyncpg / pg8000 imports here.
  - Standard library only.

It provides:
  - Stable Postgres-ish types:
      * PostgresNamespace (schema + table)
      * PostgresQuery / PostgresQueryResult (safe-by-default models)
  - Optional capability Protocols for Postgres connectors:
      * PostgresQueryRunner (run_query)
      * PostgresExecRunner (run_exec)
  - Safe validation + log hygiene:
      * conservative identifier sanitizers (schema/table/column)
      * query fingerprinting (stable hash; never logs raw SQL text)
      * parameter summaries that avoid leaking PII/secrets
  - DataStoreResourceRef helpers:
      * tables: kind="table", id="schema.table"
      * rows: kind="row", id="schema.table#<hash>" (default) to avoid leaking PKs

DESIGN NOTES
------------
Postgres supports many advanced features (CTEs, JSONB, COPY, LISTEN/NOTIFY, etc.).
This file deliberately does NOT model all of them. It provides the minimum stable
surface area that providers can build on safely.

SAFETY & OBSERVABILITY
----------------------
- SQL text is suppressed from repr() and never emitted in summaries.
- Params are summarized by type/len/hash, not raw values.
- Results are summarized by row count + column names only.
- Read-only detection is a best-effort heuristic (not a security boundary).

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
    "POSTGRES_PROVIDER_ID",
    "POSTGRES_CATEGORY",
    "POSTGRES_SERVICE",
    # Identifier helpers
    "sanitize_postgres_identifier",
    "sanitize_postgres_schema_name",
    "sanitize_postgres_table_name",
    "sanitize_postgres_column_name",
    "quote_postgres_identifier",
    # Namespace + resource refs
    "PostgresNamespace",
    "postgres_table_resource_ref",
    "postgres_row_resource_ref",
    # Query models
    "PostgresQuery",
    "PostgresQueryResult",
    # Optional capability protocols
    "PostgresQueryRunner",
    "PostgresExecRunner",
    # Safe summaries
    "hash_stable",
    "summarize_sql_params",
    "is_probably_read_only_sql",
    "postgres_query_summary",
    "postgres_result_summary",
]


# =============================================================================
# Constants
# =============================================================================

POSTGRES_PROVIDER_ID = "postgres"
POSTGRES_CATEGORY = "sql"
POSTGRES_SERVICE = "sql"


# =============================================================================
# Safe hashing for logs/correlation
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
# Conservative identifier sanitization
# =============================================================================
# Postgres identifiers are limited to NAMEDATALEN-1 bytes (63 bytes by default).
# Postgres allows quoted identifiers with broad charset. For safe helper utilities,
# we restrict to a conservative, portable subset:
#   - 1..63 chars
#   - [A-Za-z_][A-Za-z0-9_]*
_PG_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def sanitize_postgres_identifier(name: str, *, what: str = "identifier") -> str:
    """
    Validate a Postgres identifier (conservative rule).

    - 1..63 chars
    - [A-Za-z_][A-Za-z0-9_]*

    Raises DataStoreValidationError on invalid input.
    """
    s = (name or "").strip()
    if not s:
        raise DataStoreValidationError(
            f"postgres {what} is required",
            details={"field": what},
            context=DataStoreErrorContext(operation="postgres.sanitize_identifier"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            f"postgres {what} contains illegal control characters",
            details={what: redact_value(s)},
            context=DataStoreErrorContext(operation="postgres.sanitize_identifier"),
        )
    if not _PG_IDENT_RE.match(s):
        raise DataStoreValidationError(
            f"postgres {what} has invalid format (conservative rule)",
            details={what: redact_value(s), "expected": _PG_IDENT_RE.pattern},
            context=DataStoreErrorContext(operation="postgres.sanitize_identifier"),
        )
    return s


def sanitize_postgres_schema_name(name: str) -> str:
    return sanitize_postgres_identifier(name, what="schema")


def sanitize_postgres_table_name(name: str) -> str:
    return sanitize_postgres_identifier(name, what="table")


def sanitize_postgres_column_name(name: str) -> str:
    return sanitize_postgres_identifier(name, what="column")


def quote_postgres_identifier(name: str) -> str:
    """
    Return a double-quoted identifier *after* conservative validation.

    This is for builder-style helpers only; provider connectors may support wider
    identifier sets using proper escaping and driver quote functions.
    """
    ident = sanitize_postgres_identifier(name, what="identifier")
    return f'"{ident}"'


# =============================================================================
# Namespace + resource refs
# =============================================================================


@dataclass(frozen=True, slots=True)
class PostgresNamespace:
    """
    Postgres namespace: schema + table.

    - Names are validated with conservative sanitizers by default.
    - For unusual names, set strict=False and handle validation upstream.
    """

    schema: str
    table: str
    strict: bool = True

    def __post_init__(self) -> None:
        sc = (self.schema or "").strip()
        tb = (self.table or "").strip()

        if self.strict:
            sc = sanitize_postgres_schema_name(sc)
            tb = sanitize_postgres_table_name(tb)
        else:
            if not sc or not tb:
                raise DataStoreValidationError(
                    "schema and table are required",
                    details={"schema": redact_value(sc), "table": redact_value(tb)},
                    context=DataStoreErrorContext(operation="postgres.namespace.validate"),
                )
            if "\x00" in sc or "\x00" in tb or "\r" in sc or "\n" in sc or "\r" in tb or "\n" in tb:
                raise DataStoreValidationError(
                    "schema/table contains illegal control characters",
                    context=DataStoreErrorContext(operation="postgres.namespace.validate"),
                )

        object.__setattr__(self, "schema", sc)
        object.__setattr__(self, "table", tb)

    def canonical(self) -> str:
        return f"{self.schema}.{self.table}"

    def redacted_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "table": self.table}


def postgres_table_resource_ref(
    *,
    schema: str,
    table: str,
    provider_id: str = POSTGRES_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    strict_names: bool = True,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a Postgres table.

    provider_id="postgres", service="sql", kind="table", id="schema.table"
    """
    ns = PostgresNamespace(schema=schema, table=table, strict=strict_names)
    return DataStoreResourceRef(
        provider_id=provider_id,
        service=POSTGRES_SERVICE,
        kind="table",
        id=ns.canonical(),
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


def postgres_row_resource_ref(
    *,
    schema: str,
    table: str,
    row_id: str,
    provider_id: str = POSTGRES_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    strict_names: bool = True,
    include_raw_id: bool = False,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a row in a Postgres table.

    IMPORTANT:
    DataStoreResourceRef.id is not automatically redacted. Primary keys can be PII.
    So by default we store a hashed row id.

    id format:
      - include_raw_id=False (default): "schema.table#<hash>"
      - include_raw_id=True:            "schema.table/<raw_id>"
    """
    ns = PostgresNamespace(schema=schema, table=table, strict=strict_names)

    rid = (row_id or "").strip()
    if not rid:
        raise DataStoreValidationError(
            "row_id is required",
            details={"field": "row_id"},
            context=DataStoreErrorContext(operation="postgres.row_ref"),
        )
    if "\x00" in rid or "\r" in rid or "\n" in rid:
        raise DataStoreValidationError(
            "row_id contains illegal control characters",
            details={"row_id": redact_value(rid)},
            context=DataStoreErrorContext(operation="postgres.row_ref"),
        )

    ref_id = f"{ns.canonical()}/{rid}" if include_raw_id else f"{ns.canonical()}#{hash_stable(rid)}"

    return DataStoreResourceRef(
        provider_id=provider_id,
        service=POSTGRES_SERVICE,
        kind="row",
        id=ref_id,
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


# =============================================================================
# SQL read-only heuristic (best-effort)
# =============================================================================

_READONLY_PREFIXES = (
    "select",
    "show",
    "explain",
    "values",
    "fetch",
    "declare",
    "listen",
    "notify",
    "unlisten",
    "set",  # session-level changes only; still not a data write
    "reset",
    "begin",
    "start",
    "commit",
    "rollback",
)

_WRITE_PREFIXES = (
    "insert",
    "update",
    "delete",
    "merge",  # Postgres 15+
    "create",
    "alter",
    "drop",
    "truncate",
    "rename",
    "grant",
    "revoke",
    "call",
    "do",
    "copy",  # COPY can write
    "vacuum",
    "cluster",
    "reindex",
    "refresh",  # refresh materialized view
)


def _strip_leading_sql_comments(s: str) -> str:
    """
    Remove leading SQL comments (very lightweight).

    Supports:
      - -- comment
      - /* comment */
    """
    sql = s
    while True:
        t = sql.lstrip()
        if t.startswith("--"):
            nl = t.find("\n")
            sql = "" if nl < 0 else t[nl + 1 :]
            continue
        if t.startswith("/*"):
            end = t.find("*/")
            sql = "" if end < 0 else t[end + 2 :]
            continue
        return t


def is_probably_read_only_sql(sql: str) -> bool:
    """
    Best-effort heuristic: determine if SQL is *probably* read-only.

    Not a security boundary. Governance should enforce write permissions elsewhere.

    Notes:
      - WITH can precede INSERT/UPDATE/DELETE. We try a conservative check:
        if we see insert/update/delete/merge/copy in the statement, treat as write.
    """
    if sql is None:
        return True

    s = _strip_leading_sql_comments(str(sql)).strip().lower()
    if not s:
        return True

    first = s.split(None, 1)[0] if s else ""
    if first in _WRITE_PREFIXES:
        return False
    if first in _READONLY_PREFIXES:
        return True

    if first == "with":
        # Conservative: if any clear write keyword appears, treat as not read-only.
        if re.search(r"\b(insert|update|delete|merge|copy|create|alter|drop|truncate|refresh)\b", s):
            return False
        # Otherwise likely a WITH ... SELECT ...
        return True if re.search(r"\bselect\b", s) else False

    # Unknown keyword: default conservative (not read-only)
    return False


# =============================================================================
# Params summarization (no raw values)
# =============================================================================


def _param_shape(v: Any) -> dict[str, Any]:
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


def summarize_sql_params(params: Any, *, max_items: int = 50) -> dict[str, Any]:
    """
    Return a log-safe summary of SQL parameters.

    Supports common patterns:
      - dict-like named parameters
      - list/tuple positional parameters
      - None
    """
    if params is None:
        return {"kind": "none", "count": 0}

    if isinstance(params, Mapping):
        items: dict[str, Any] = {}
        keys = sorted(str(k) for k in params.keys())
        truncated = False
        if len(keys) > max_items:
            keys = keys[:max_items]
            truncated = True
        for k in keys:
            kk = k
            if "\x00" in kk or "\r" in kk or "\n" in kk:
                kk = "<invalid_key>"
            try:
                items[kk] = _param_shape(params.get(k))
            except Exception:
                items[kk] = {"type": "error"}
        if truncated:
            items["…"] = {"truncated": True}
        return {"kind": "mapping", "count": len(params), "items": items}

    if isinstance(params, Sequence) and not isinstance(params, (str, bytes, bytearray)):
        n = len(params)
        sample_n = min(n, max_items)
        sample = []
        for i in range(sample_n):
            try:
                sample.append(_param_shape(params[i]))
            except Exception:
                sample.append({"type": "error"})
        return {"kind": "sequence", "count": n, "sample": sample, "truncated": n > sample_n}

    return {"kind": "scalar", "count": 1, "shape": _param_shape(params)}


# =============================================================================
# Query + results
# =============================================================================


@dataclass(frozen=True, slots=True)
class PostgresQuery:
    """
    Provider-agnostic Postgres SQL query model.

    SAFETY:
      - sql is suppressed from repr()
      - redacted_dict()/summary never include raw SQL text
    """

    sql: str = field(repr=False)
    params: Any = None

    # Governance hint; default derived from sql heuristic if not provided
    read_only: bool | None = None

    # Hints; connector may ignore or map to driver options
    timeout_s: float | None = None
    max_rows: int | None = None

    # Optional DSN/URI hints for context (will be redacted in summaries)
    uri: str | None = None

    # Postgres-specific hints (connectors may ignore)
    search_path: Sequence[str] | None = None  # list of schema names to set for session/txn

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        s = "" if self.sql is None else str(self.sql)
        if "\x00" in s:
            raise DataStoreValidationError(
                "sql contains NUL",
                context=DataStoreErrorContext(operation="postgres.query.validate"),
            )
        if len(s) > 2_000_000:
            raise DataStoreValidationError(
                "sql too large",
                details={"sql_len": len(s), "max": 2_000_000},
                context=DataStoreErrorContext(operation="postgres.query.validate"),
            )

        if self.read_only is None:
            object.__setattr__(self, "read_only", bool(is_probably_read_only_sql(s)))

        if self.max_rows is not None:
            try:
                mr = int(self.max_rows)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "max_rows must be an integer",
                    details={"max_rows": redact_value(str(self.max_rows))},
                    context=DataStoreErrorContext(operation="postgres.query.validate"),
                ) from exc
            if mr <= 0:
                raise DataStoreValidationError(
                    "max_rows must be > 0",
                    details={"max_rows": mr},
                    context=DataStoreErrorContext(operation="postgres.query.validate"),
                )
            object.__setattr__(self, "max_rows", mr)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=DataStoreErrorContext(operation="postgres.query.validate"),
                ) from exc
            if ts <= 0:
                raise DataStoreValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=DataStoreErrorContext(operation="postgres.query.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

        if self.search_path is not None:
            # Validate schema names conservatively if provided
            sp = []
            for item in self.search_path:
                sp.append(sanitize_postgres_schema_name(str(item)))
            object.__setattr__(self, "search_path", tuple(sp))

    def fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable fingerprint of the SQL text + parameter *shapes* (not values).

        Never returns the raw SQL string.
        """
        payload = {
            "sql_hash": hash_stable(self.sql or "", salt=salt),
            "sql_len": len(self.sql or ""),
            "params": summarize_sql_params(self.params),
            "read_only": bool(self.read_only),
            "max_rows": self.max_rows,
            "search_path": list(self.search_path) if self.search_path else None,
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return postgres_query_summary(self)


@dataclass(frozen=True, slots=True)
class PostgresQueryResult:
    """
    Provider-agnostic query result container.

    SAFETY:
      - rows are suppressed from repr()
      - redacted_dict returns counts + column names + safe stats only
    """

    query_fingerprint: str

    columns: Sequence[str] = field(default_factory=tuple)
    rows: Sequence[Mapping[str, Any]] = field(default_factory=tuple, repr=False)

    # Provider-defined stats (must be log-safe; will be passed through redact_mapping)
    # Examples: {"rowcount": 10, "duration_ms": 12, "command": "SELECT"}
    stats: Mapping[str, Any] = field(default_factory=dict)

    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return postgres_result_summary(self)


# =============================================================================
# Optional capability protocols
# =============================================================================


@runtime_checkable
class PostgresQueryRunner(Protocol):
    """
    Optional capability: run read-style queries (SELECT/SHOW/etc).

    Implementations SHOULD:
      - accept PostgresQuery
      - raise DataStoreError subclasses on failure (from connectors/data_stores/__init__.py)
      - never log raw SQL text or raw parameters
    """

    def run_query(
        self,
        query: PostgresQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> PostgresQueryResult: ...


@runtime_checkable
class PostgresExecRunner(Protocol):
    """
    Optional capability: run exec-style statements (INSERT/UPDATE/DDL/etc).
    """

    def run_exec(
        self,
        query: PostgresQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> PostgresQueryResult: ...


# =============================================================================
# Log-safe summaries
# =============================================================================


def postgres_query_summary(query: PostgresQuery, *, salt: str = "francis") -> dict[str, Any]:
    """
    Log-safe summary of a PostgresQuery.

    - excludes raw SQL text
    - includes fingerprint + length + param shapes
    """
    if not isinstance(query, PostgresQuery):
        raise DataStoreValidationError(
            "postgres_query_summary expects PostgresQuery",
            details={"type": type(query).__name__},
            context=DataStoreErrorContext(operation="postgres.query.summary"),
        )

    sql_len = len(query.sql or "")
    return {
        "sql_len": sql_len,
        "sql_hash": hash_stable(query.sql or "", salt=salt),
        "fingerprint": query.fingerprint(salt=salt),
        "read_only": bool(query.read_only),
        "timeout_s": query.timeout_s,
        "max_rows": query.max_rows,
        "params": summarize_sql_params(query.params),
        "search_path": list(query.search_path) if query.search_path else None,
        "uri": redact_uri(query.uri) if query.uri else None,
        "meta": redact_mapping(query.meta),
    }


def postgres_result_summary(result: PostgresQueryResult) -> dict[str, Any]:
    """
    Log-safe summary of a PostgresQueryResult.

    - excludes row values
    - includes row count and column names (capped)
    """
    if not isinstance(result, PostgresQueryResult):
        return {"type": type(result).__name__}

    row_count = len(result.rows or ())
    cols = [str(c) for c in (result.columns or ())]
    cols_sample = cols[:200]

    return {
        "query_fingerprint": result.query_fingerprint,
        "row_count": row_count,
        "column_count": len(cols),
        "columns_sample": cols_sample,
        "stats": redact_mapping(result.stats),
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }
