"""
===============================================================================
Francis 2.0 — Data Store Connectors (MySQL Utilities)
Path: connectors/data_stores/mysql.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *MySQL-specific but dependency-free* primitives and helpers
used by MySQL-capable data store connectors.

It is intentionally SDK/driver neutral:
  - No mysqlclient / PyMySQL / mysql-connector-python imports here.
  - Standard library only.

It provides:
  - Stable MySQL-ish types:
      * MySqlNamespace (database + table)
      * MySqlQuery / MySqlQueryResult (safe-by-default models)
  - Optional capability Protocols for MySQL connectors:
      * MySqlQueryRunner (run_query)
      * MySqlExecRunner (run_exec)
  - Safe validation and log hygiene:
      * conservative identifier sanitizers (db/table/column)
      * query fingerprinting (stable hash; never logs raw SQL text)
      * parameter summaries that avoid leaking PII/secrets
  - DataStoreResourceRef helpers for tables/rows:
      * default row refs use hashed ids (because DataStoreResourceRef.id is not auto-redacted)

DESIGN NOTES
------------
MySQL is "just SQL", but:
  - parameter styles vary by driver (%s, ?, :name)
  - results may be tuples or dicts
  - server-side cursor behavior differs

This module avoids enforcing one driver shape:
  - params are "Any"
  - rows are "Sequence[Mapping[str, Any]]" (dict-like) in the model, but connectors can
    normalize tuples to dicts (column->value) in provider code.

SAFETY & OBSERVABILITY
----------------------
- SQL text is suppressed from repr() and never emitted in redacted summaries.
- Params are summarized by type/len/hash, not raw values.
- Results are summarized by row count + column names only.

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
    "MYSQL_PROVIDER_ID",
    "MYSQL_CATEGORY",
    "MYSQL_SERVICE",
    # Identifier helpers
    "sanitize_mysql_identifier",
    "sanitize_mysql_database_name",
    "sanitize_mysql_table_name",
    "sanitize_mysql_column_name",
    "quote_mysql_identifier",
    # Namespace + resource refs
    "MySqlNamespace",
    "mysql_table_resource_ref",
    "mysql_row_resource_ref",
    # Query models
    "MySqlQuery",
    "MySqlQueryResult",
    # Optional capability protocols
    "MySqlQueryRunner",
    "MySqlExecRunner",
    # Safe summaries
    "hash_stable",
    "summarize_sql_params",
    "is_probably_read_only_sql",
    "mysql_query_summary",
    "mysql_result_summary",
]


# =============================================================================
# Constants
# =============================================================================

MYSQL_PROVIDER_ID = "mysql"
MYSQL_CATEGORY = "sql"
MYSQL_SERVICE = "sql"


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
# MySQL allows quoted identifiers (backticks) with lots of characters.
# For *safe helper utilities*, we use a conservative subset to prevent:
#   - control chars
#   - ambiguous separators
#   - log injection surprises
#
# If you need broader identifier support, do it in the provider connector and
# keep it out of logs.
_MYSQL_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")  # 1..64


def sanitize_mysql_identifier(name: str, *, what: str = "identifier") -> str:
    """
    Validate a MySQL identifier (conservative rule).

    - 1..64 chars
    - [A-Za-z_][A-Za-z0-9_]*

    Raises DataStoreValidationError on invalid input.
    """
    s = (name or "").strip()
    if not s:
        raise DataStoreValidationError(
            f"mysql {what} is required",
            details={"field": what},
            context=DataStoreErrorContext(operation="mysql.sanitize_identifier"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            f"mysql {what} contains illegal control characters",
            details={what: redact_value(s)},
            context=DataStoreErrorContext(operation="mysql.sanitize_identifier"),
        )
    if not _MYSQL_IDENT_RE.match(s):
        raise DataStoreValidationError(
            f"mysql {what} has invalid format (conservative rule)",
            details={what: redact_value(s), "expected": _MYSQL_IDENT_RE.pattern},
            context=DataStoreErrorContext(operation="mysql.sanitize_identifier"),
        )
    return s


def sanitize_mysql_database_name(name: str) -> str:
    return sanitize_mysql_identifier(name, what="database")


def sanitize_mysql_table_name(name: str) -> str:
    return sanitize_mysql_identifier(name, what="table")


def sanitize_mysql_column_name(name: str) -> str:
    return sanitize_mysql_identifier(name, what="column")


def quote_mysql_identifier(name: str) -> str:
    """
    Return a backtick-quoted identifier *after* conservative validation.

    This is for builder-style helpers only; provider connectors may support wider
    identifier sets using proper escaping.
    """
    ident = sanitize_mysql_identifier(name, what="identifier")
    return f"`{ident}`"


# =============================================================================
# Namespace + resource refs
# =============================================================================


@dataclass(frozen=True, slots=True)
class MySqlNamespace:
    """
    MySQL namespace: database + table.

    - Names are validated with conservative sanitizers by default.
    - For unusual names, you can set strict=False and handle validation upstream.
    """

    database: str
    table: str
    strict: bool = True

    def __post_init__(self) -> None:
        db = (self.database or "").strip()
        tb = (self.table or "").strip()

        if self.strict:
            db = sanitize_mysql_database_name(db)
            tb = sanitize_mysql_table_name(tb)
        else:
            if not db or not tb:
                raise DataStoreValidationError(
                    "database and table are required",
                    details={"database": redact_value(db), "table": redact_value(tb)},
                    context=DataStoreErrorContext(operation="mysql.namespace.validate"),
                )
            if "\x00" in db or "\x00" in tb or "\r" in db or "\n" in db or "\r" in tb or "\n" in tb:
                raise DataStoreValidationError(
                    "database/table contains illegal control characters",
                    context=DataStoreErrorContext(operation="mysql.namespace.validate"),
                )

        object.__setattr__(self, "database", db)
        object.__setattr__(self, "table", tb)

    def canonical(self) -> str:
        return f"{self.database}.{self.table}"

    def redacted_dict(self) -> dict[str, Any]:
        # DB/table names are generally not secrets; still keep it structured.
        return {"database": self.database, "table": self.table}


def mysql_table_resource_ref(
    *,
    database: str,
    table: str,
    provider_id: str = MYSQL_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    strict_names: bool = True,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a MySQL table.

    provider_id="mysql", service="sql", kind="table", id="db.table"
    """
    ns = MySqlNamespace(database=database, table=table, strict=strict_names)
    return DataStoreResourceRef(
        provider_id=provider_id,
        service=MYSQL_SERVICE,
        kind="table",
        id=ns.canonical(),
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


def mysql_row_resource_ref(
    *,
    database: str,
    table: str,
    row_id: str,
    provider_id: str = MYSQL_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    strict_names: bool = True,
    include_raw_id: bool = False,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a row in a MySQL table.

    IMPORTANT:
    DataStoreResourceRef.id is not automatically redacted. Primary keys can be PII.
    So by default we store a hashed row id.

    id format:
      - include_raw_id=False (default): "db.table#<hash>"
      - include_raw_id=True:            "db.table/<raw_id>"
    """
    ns = MySqlNamespace(database=database, table=table, strict=strict_names)

    rid = (row_id or "").strip()
    if not rid:
        raise DataStoreValidationError(
            "row_id is required",
            details={"field": "row_id"},
            context=DataStoreErrorContext(operation="mysql.row_ref"),
        )
    if "\x00" in rid or "\r" in rid or "\n" in rid:
        raise DataStoreValidationError(
            "row_id contains illegal control characters",
            details={"row_id": redact_value(rid)},
            context=DataStoreErrorContext(operation="mysql.row_ref"),
        )

    ref_id = f"{ns.canonical()}/{rid}" if include_raw_id else f"{ns.canonical()}#{hash_stable(rid)}"

    return DataStoreResourceRef(
        provider_id=provider_id,
        service=MYSQL_SERVICE,
        kind="row",
        id=ref_id,
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


# =============================================================================
# SQL read-only heuristic
# =============================================================================

_READONLY_PREFIXES = (
    "select",
    "show",
    "describe",
    "desc",
    "explain",
    "with",  # could still mutate depending on statement; treat as likely read
    "set",  # could change session vars only; treat as not a data write
)

_WRITE_PREFIXES = (
    "insert",
    "update",
    "delete",
    "replace",
    "merge",
    "create",
    "alter",
    "drop",
    "truncate",
    "rename",
    "grant",
    "revoke",
    "call",
    "load",
)


def is_probably_read_only_sql(sql: str) -> bool:
    """
    Best-effort heuristic: determine if SQL is *probably* read-only.

    Not a security boundary. Governance should enforce write permissions elsewhere.
    """
    if sql is None:
        return True
    s = str(sql).strip().lower()
    if not s:
        return True

    # Strip leading SQL comments (very lightweight)
    # -- comment
    # /* comment */
    while True:
        s2 = s.lstrip()
        if s2.startswith("--"):
            nl = s2.find("\n")
            s = "" if nl < 0 else s2[nl + 1 :]
            continue
        if s2.startswith("/*"):
            end = s2.find("*/")
            s = "" if end < 0 else s2[end + 2 :]
            continue
        s = s2
        break

    tok = s.split(None, 1)[0] if s else ""
    if tok in _WRITE_PREFIXES:
        return False
    if tok in _READONLY_PREFIXES:
        return True

    # Unknown keyword: default to "not sure" -> treat as not read-only.
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

    # Fallback single scalar
    return {"kind": "scalar", "count": 1, "shape": _param_shape(params)}


# =============================================================================
# Query + results
# =============================================================================


@dataclass(frozen=True, slots=True)
class MySqlQuery:
    """
    Provider-agnostic MySQL SQL query model.

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

    # Optional DSN/URI hints for context (should be redacted in summaries)
    uri: str | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        s = "" if self.sql is None else str(self.sql)
        if "\x00" in s:
            raise DataStoreValidationError(
                "sql contains NUL",
                context=DataStoreErrorContext(operation="mysql.query.validate"),
            )
        if len(s) > 2_000_000:
            raise DataStoreValidationError(
                "sql too large",
                details={"sql_len": len(s), "max": 2_000_000},
                context=DataStoreErrorContext(operation="mysql.query.validate"),
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
                    context=DataStoreErrorContext(operation="mysql.query.validate"),
                ) from exc
            if mr <= 0:
                raise DataStoreValidationError(
                    "max_rows must be > 0",
                    details={"max_rows": mr},
                    context=DataStoreErrorContext(operation="mysql.query.validate"),
                )
            object.__setattr__(self, "max_rows", mr)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=DataStoreErrorContext(operation="mysql.query.validate"),
                ) from exc
            if ts <= 0:
                raise DataStoreValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=DataStoreErrorContext(operation="mysql.query.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

    def fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable fingerprint of the SQL text + parameter *shapes* (not values).

        Never returns the raw SQL string.
        """
        payload = {
            "sql_hash": hash_stable(self.sql, salt=salt),
            "sql_len": len(self.sql or ""),
            "params": summarize_sql_params(self.params),
            "read_only": bool(self.read_only),
            "max_rows": self.max_rows,
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return mysql_query_summary(self)


@dataclass(frozen=True, slots=True)
class MySqlQueryResult:
    """
    Provider-agnostic query result container.

    SAFETY:
      - rows are suppressed from repr()
      - redacted_dict returns counts + column names + safe stats only
    """

    query_fingerprint: str

    # Column names as returned by the connector/driver (best-effort)
    columns: Sequence[str] = field(default_factory=tuple)

    # Rows normalized to mapping-like by connector (recommended), suppressed from repr()
    rows: Sequence[Mapping[str, Any]] = field(default_factory=tuple, repr=False)

    # Provider-defined stats (must be log-safe; will be passed through redact_mapping)
    # Examples: {"rowcount": 10, "duration_ms": 12, "server_status": "..."}
    stats: Mapping[str, Any] = field(default_factory=dict)

    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return mysql_result_summary(self)


# =============================================================================
# Optional capability protocols
# =============================================================================


@runtime_checkable
class MySqlQueryRunner(Protocol):
    """
    Optional capability: run read-style queries (SELECT/SHOW/etc).

    Implementations SHOULD:
      - accept MySqlQuery
      - raise DataStoreError subclasses on failure (from connectors/data_stores/__init__.py)
      - never log raw SQL text or raw parameters
    """

    def run_query(
        self,
        query: MySqlQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> MySqlQueryResult: ...


@runtime_checkable
class MySqlExecRunner(Protocol):
    """
    Optional capability: run exec-style statements (INSERT/UPDATE/DDL/etc).

    Many connectors can implement both run_query and run_exec with shared plumbing.
    """

    def run_exec(
        self,
        query: MySqlQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> MySqlQueryResult: ...


# =============================================================================
# Log-safe summaries
# =============================================================================


def mysql_query_summary(query: MySqlQuery, *, salt: str = "francis") -> dict[str, Any]:
    """
    Log-safe summary of a MySqlQuery.

    - excludes raw SQL text
    - includes fingerprint + length + param shapes
    """
    if not isinstance(query, MySqlQuery):
        raise DataStoreValidationError(
            "mysql_query_summary expects MySqlQuery",
            details={"type": type(query).__name__},
            context=DataStoreErrorContext(operation="mysql.query.summary"),
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
        "uri": redact_uri(query.uri) if query.uri else None,
        "meta": redact_mapping(query.meta),
    }


def mysql_result_summary(result: MySqlQueryResult) -> dict[str, Any]:
    """
    Log-safe summary of a MySqlQueryResult.

    - excludes row values
    - includes row count and column names (capped)
    """
    if not isinstance(result, MySqlQueryResult):
        return {"type": type(result).__name__}

    row_count = len(result.rows or ())
    cols = [str(c) for c in (result.columns or ())]
    cols_sample = cols[:200]  # avoid log spam

    return {
        "query_fingerprint": result.query_fingerprint,
        "row_count": row_count,
        "column_count": len(cols),
        "columns_sample": cols_sample,
        "stats": redact_mapping(result.stats),
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }
