"""
===============================================================================
Francis 2.0 — Data Store Connectors (MongoDB Utilities)
Path: connectors/data_stores/mongodb.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *MongoDB-specific but dependency-free* primitives and helpers
used by MongoDB-capable data store connectors.

It is intentionally provider-neutral at the SDK level:
  - No pymongo imports here.
  - Standard library only.

It provides:
  - Stable MongoDB-ish types:
      * MongoNamespace (db + collection)
      * MongoQuery / MongoQueryResult (safe-by-default models)
      * MongoWrite / MongoWriteResult (insert/update/delete/bulk-style intent)
  - Optional capability Protocols for Mongo connectors:
      * MongoQueryRunner (run_query)
      * MongoWriteRunner (run_write)
  - Safe validation and log hygiene:
      * conservative db/collection name sanitizers
      * ObjectId helpers (string-only; no bson dependency)
      * query/write fingerprinting (stable hash; never logs raw filters/docs)
      * parameter/document summaries that avoid PII/secrets

DESIGN NOTES
------------
MongoDB is a document store with flexible schemas and rich query syntax.
This module avoids forcing a single rigid model by:
  - Treating filter/pipeline/update/document as opaque mappings, suppressed from repr()
  - Logging only fingerprints + shapes (counts/types), not raw values
  - Providing "resource ref" helpers that default to hashed document ids (because
    DataStoreResourceRef.id is not redacted automatically)

SAFETY & OBSERVABILITY
----------------------
- Query/write payloads are never included in repr() and are never emitted in redacted_dict().
- Fingerprints allow correlation without revealing contents.
- Names and ids are validated against conservative rules to prevent control characters.

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from . import (
    DataStoreErrorContext,
    DataStoreIdentity,
    DataStoreResourceRef,
    DataStoreValidationError,
    redact_mapping,
    redact_value,
)

__all__ = [
    # Constants
    "MONGODB_PROVIDER_ID",
    "MONGODB_CATEGORY",
    "MONGODB_SERVICE",
    # Names / ids helpers
    "sanitize_mongo_database_name",
    "sanitize_mongo_collection_name",
    "sanitize_mongo_field_name",
    "is_object_id",
    "normalize_object_id",
    "hash_stable",
    # Types
    "MongoNamespace",
    "MongoQuery",
    "MongoQueryResult",
    "MongoWrite",
    "MongoWriteResult",
    # Optional capability protocols
    "MongoQueryRunner",
    "MongoWriteRunner",
    # DataStoreResourceRef helpers
    "mongo_collection_resource_ref",
    "mongo_document_resource_ref",
    # Log-safe summaries
    "summarize_mongo_value",
    "summarize_mongo_mapping",
    "mongo_query_summary",
    "mongo_result_summary",
    "mongo_write_summary",
    "mongo_write_result_summary",
]


# =============================================================================
# Constants
# =============================================================================

MONGODB_PROVIDER_ID = "mongodb"
MONGODB_CATEGORY = "nosql"
MONGODB_SERVICE = "nosql"  # aligns with connectors/data_stores/__init__.py example for Mongo collections


# =============================================================================
# Conservative name / id validation
# =============================================================================
# MongoDB allows many characters in names, but for *safe helper utilities* we use
# a conservative subset to prevent control characters, separator ambiguity, and log issues.
#
# Providers/connectors can accept broader names if they need to; these helpers are for
# safe-by-default code paths and resource refs.
_MONGO_DB_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,62}[A-Za-z0-9]$")
_MONGO_COLL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,126}[A-Za-z0-9]$")

# Field names are trickier; Mongo typically discourages "." and leading "$".
# We'll be conservative and disallow:
#   - NUL, CR, LF
#   - empty
#   - leading "$"
#   - containing "."
_MONGO_FIELD_RE = re.compile(r"^(?!\$)[^\x00\r\n\.]{1,255}$")

_OBJECT_ID_RE = re.compile(r"^[a-fA-F0-9]{24}$")


def sanitize_mongo_database_name(name: str) -> str:
    """
    Validate a MongoDB database name for safe helpers.

    Conservative rules:
      - 2..64-ish chars (enforced by regex length)
      - [A-Za-z0-9_-]
      - no CR/LF/NUL
    """
    s = (name or "").strip()
    if not s:
        raise DataStoreValidationError(
            "mongo database name is required",
            details={"field": "database"},
            context=DataStoreErrorContext(operation="mongodb.sanitize_database"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            "mongo database name contains illegal control characters",
            details={"database": redact_value(s)},
            context=DataStoreErrorContext(operation="mongodb.sanitize_database"),
        )
    if not _MONGO_DB_RE.match(s):
        raise DataStoreValidationError(
            "mongo database name has invalid format (conservative rule)",
            details={"database": redact_value(s), "expected": _MONGO_DB_RE.pattern},
            context=DataStoreErrorContext(operation="mongodb.sanitize_database"),
        )
    return s


def sanitize_mongo_collection_name(name: str) -> str:
    """
    Validate a MongoDB collection name for safe helpers.

    Conservative rules:
      - 1..128-ish chars
      - [A-Za-z0-9_.-] (dot allowed)
      - no CR/LF/NUL
    """
    s = (name or "").strip()
    if not s:
        raise DataStoreValidationError(
            "mongo collection name is required",
            details={"field": "collection"},
            context=DataStoreErrorContext(operation="mongodb.sanitize_collection"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise DataStoreValidationError(
            "mongo collection name contains illegal control characters",
            details={"collection": redact_value(s)},
            context=DataStoreErrorContext(operation="mongodb.sanitize_collection"),
        )
    if not _MONGO_COLL_RE.match(s):
        raise DataStoreValidationError(
            "mongo collection name has invalid format (conservative rule)",
            details={"collection": redact_value(s), "expected": _MONGO_COLL_RE.pattern},
            context=DataStoreErrorContext(operation="mongodb.sanitize_collection"),
        )
    return s


def sanitize_mongo_field_name(name: str) -> str:
    """
    Validate a MongoDB field name for safe helper logic.

    Conservative rules:
      - 1..255 chars
      - no NUL/CR/LF
      - no "." and not starting with "$"

    NOTE:
      Real MongoDB allows more in some contexts. This is a safe helper, not a full spec.
    """
    s = (name or "").strip()
    if not s:
        raise DataStoreValidationError(
            "mongo field name is required",
            details={"field": "field_name"},
            context=DataStoreErrorContext(operation="mongodb.sanitize_field"),
        )
    if not _MONGO_FIELD_RE.match(s):
        raise DataStoreValidationError(
            "mongo field name has invalid format (conservative rule)",
            details={"field_name": redact_value(s)},
            context=DataStoreErrorContext(operation="mongodb.sanitize_field"),
        )
    return s


def is_object_id(value: str | None) -> bool:
    """Return True if value looks like a 24-hex MongoDB ObjectId string."""
    if not value:
        return False
    s = str(value).strip()
    if "\r" in s or "\n" in s or "\x00" in s:
        return False
    return bool(_OBJECT_ID_RE.match(s))


def normalize_object_id(value: str) -> str:
    """
    Normalize an ObjectId string to lowercase.

    Raises DataStoreValidationError if not an ObjectId string.
    """
    s = (value or "").strip()
    if not is_object_id(s):
        raise DataStoreValidationError(
            "invalid ObjectId format",
            details={"object_id": redact_value(s)},
            context=DataStoreErrorContext(operation="mongodb.normalize_object_id"),
        )
    return s.lower()


# =============================================================================
# Stable hashing for correlation (no raw payloads in logs)
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


def _fingerprintable_value(v: Any, *, max_depth: int = 6, max_keys: int = 200, max_items: int = 50) -> Any:
    """
    Convert arbitrary Mongo-ish values into a deterministic, non-sensitive structure
    suitable for hashing.

    Strategy:
      - Replace strings/bytes with {t,len,hash}
      - Keep numbers/bools/null as-is
      - For dict/list, recurse with caps
      - For unknown objects, include type name + hash of str(value) (not the raw string)
    """
    if max_depth <= 0:
        return {"t": "depth_limit"}

    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and not isinstance(v, bool):
        return {"t": "int"}
    if isinstance(v, float):
        return {"t": "float"}
    if isinstance(v, str):
        return {"t": "str", "len": len(v), "h": hash_stable(v)}
    if isinstance(v, (bytes, bytearray)):
        # hash only a prefix representation to avoid huge compute
        hx = bytes(v)[:256].hex()
        return {"t": "bytes", "len": len(v), "h": hash_stable(hx)}
    if isinstance(v, Mapping):
        out: dict[str, Any] = {"t": "obj", "k": len(v), "items": {}}
        keys = sorted(str(k) for k in v.keys())
        truncated = False
        if len(keys) > max_keys:
            keys = keys[:max_keys]
            truncated = True
        items: dict[str, Any] = {}
        for k in keys:
            try:
                items[k] = _fingerprintable_value(
                    v.get(k), max_depth=max_depth - 1, max_keys=max_keys, max_items=max_items
                )
            except Exception:
                items[k] = {"t": "error"}
        if truncated:
            items["…"] = {"t": "truncated"}
        out["items"] = items
        return out
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        n = len(v)
        sample_n = min(n, max_items)
        sample = []
        for i in range(sample_n):
            try:
                sample.append(
                    _fingerprintable_value(v[i], max_depth=max_depth - 1, max_keys=max_keys, max_items=max_items)
                )
            except Exception:
                sample.append({"t": "error"})
        return {"t": "arr", "len": n, "sample": sample, "truncated": n > sample_n}

    # Unknown object (datetime, ObjectId class, Decimal, etc.)
    # Avoid raw repr; hash it.
    try:
        s = str(v)
    except Exception:
        s = type(v).__name__
    return {"t": type(v).__name__, "h": hash_stable(s)}


def _fingerprint_payload(payload: Mapping[str, Any], *, salt: str = "francis") -> str:
    """
    Create a stable fingerprint hash of a payload without embedding raw values.
    """
    obj = _fingerprintable_value(payload)
    try:
        s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        s = str(obj)
    return hash_stable(s, salt=salt)


# =============================================================================
# Resource references
# =============================================================================


@dataclass(frozen=True, slots=True)
class MongoNamespace:
    """
    Mongo namespace: database + collection.

    - Names are validated with conservative sanitizers by default.
    - For unusual names, you can set strict=False and manage validation upstream.
    """

    database: str
    collection: str

    strict: bool = True

    def __post_init__(self) -> None:
        db = (self.database or "").strip()
        coll = (self.collection or "").strip()
        if self.strict:
            db = sanitize_mongo_database_name(db)
            coll = sanitize_mongo_collection_name(coll)
        else:
            if not db or not coll:
                raise DataStoreValidationError(
                    "database and collection are required",
                    details={"database": redact_value(db), "collection": redact_value(coll)},
                    context=DataStoreErrorContext(operation="mongodb.namespace.validate"),
                )
            if "\x00" in db or "\x00" in coll or "\r" in db or "\n" in db or "\r" in coll or "\n" in coll:
                raise DataStoreValidationError(
                    "database/collection contains illegal control characters",
                    context=DataStoreErrorContext(operation="mongodb.namespace.validate"),
                )
        object.__setattr__(self, "database", db)
        object.__setattr__(self, "collection", coll)

    def canonical(self) -> str:
        return f"{self.database}.{self.collection}"

    def redacted_dict(self) -> dict[str, Any]:
        # namespace names are generally not secrets; still avoid weird meta/log issues upstream.
        return {"database": self.database, "collection": self.collection}


def mongo_collection_resource_ref(
    *,
    database: str,
    collection: str,
    provider_id: str = MONGODB_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    strict_names: bool = True,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a MongoDB collection.

    Matches the example contract:
      provider_id="mongodb", service="nosql", kind="collection", id="db.collection"
    """
    ns = MongoNamespace(database=database, collection=collection, strict=strict_names)
    return DataStoreResourceRef(
        provider_id=provider_id,
        service=MONGODB_SERVICE,
        kind="collection",
        id=ns.canonical(),
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


def mongo_document_resource_ref(
    *,
    database: str,
    collection: str,
    document_id: str,
    provider_id: str = MONGODB_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    strict_names: bool = True,
    include_raw_id: bool = False,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a MongoDB document.

    IMPORTANT:
    DataStoreResourceRef.id is not automatically redacted; so by default we use a
    hashed document id to avoid leaking PII-like ids into logs.

    id format:
      - include_raw_id=False (default):  "db.collection#<hash>"
      - include_raw_id=True:             "db.collection/<raw_id>"
    """
    ns = MongoNamespace(database=database, collection=collection, strict=strict_names)

    doc = (document_id or "").strip()
    if not doc:
        raise DataStoreValidationError(
            "document_id is required",
            details={"field": "document_id"},
            context=DataStoreErrorContext(operation="mongodb.document_ref"),
        )
    if "\x00" in doc or "\r" in doc or "\n" in doc:
        raise DataStoreValidationError(
            "document_id contains illegal control characters",
            details={"document_id": redact_value(doc)},
            context=DataStoreErrorContext(operation="mongodb.document_ref"),
        )

    if include_raw_id:
        rid = f"{ns.canonical()}/{doc}"
    else:
        rid = f"{ns.canonical()}#{hash_stable(doc)}"

    return DataStoreResourceRef(
        provider_id=provider_id,
        service=MONGODB_SERVICE,
        kind="document",
        id=rid,
        identity=identity,
        uri=uri,
        meta=dict(meta) if meta else {},
    )


# =============================================================================
# Query + results
# =============================================================================

_ALLOWED_QUERY_OPS = {"find_one", "find", "aggregate", "count", "distinct"}


def _normalize_query_op(op: str) -> str:
    s = (op or "").strip().lower()
    if not s:
        raise DataStoreValidationError(
            "mongo query op is required",
            details={"field": "op"},
            context=DataStoreErrorContext(operation="mongodb.query.validate"),
        )
    if s not in _ALLOWED_QUERY_OPS:
        raise DataStoreValidationError(
            "unsupported mongo query op",
            details={"op": redact_value(s), "allowed": sorted(_ALLOWED_QUERY_OPS)},
            context=DataStoreErrorContext(operation="mongodb.query.validate"),
        )
    return s


@dataclass(frozen=True, slots=True)
class MongoQuery:
    """
    MongoDB query intent.

    SAFETY:
      - filter/pipeline/projection are suppressed from repr()
      - use mongo_query_summary() for log-safe details
    """

    namespace: MongoNamespace
    op: str = "find"

    filter: Mapping[str, Any] | None = field(default=None, repr=False)
    pipeline: Sequence[Mapping[str, Any]] | None = field(default=None, repr=False)
    projection: Mapping[str, Any] | None = field(default=None, repr=False)

    # Common options
    sort: Sequence[tuple[str, int]] | None = None  # [("field", 1|-1), ...]
    limit: int | None = None
    skip: int | None = None
    max_time_ms: int | None = None

    read_only: bool = True  # for governance hints upstream
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        op = _normalize_query_op(self.op)
        object.__setattr__(self, "op", op)

        # Validate numeric options
        if self.limit is not None:
            try:
                lim = int(self.limit)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "limit must be an integer",
                    details={"limit": redact_value(str(self.limit))},
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                ) from exc
            if lim < 0:
                raise DataStoreValidationError(
                    "limit cannot be negative",
                    details={"limit": lim},
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                )
            object.__setattr__(self, "limit", lim)

        if self.skip is not None:
            try:
                sk = int(self.skip)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "skip must be an integer",
                    details={"skip": redact_value(str(self.skip))},
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                ) from exc
            if sk < 0:
                raise DataStoreValidationError(
                    "skip cannot be negative",
                    details={"skip": sk},
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                )
            object.__setattr__(self, "skip", sk)

        if self.max_time_ms is not None:
            try:
                mt = int(self.max_time_ms)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "max_time_ms must be an integer",
                    details={"max_time_ms": redact_value(str(self.max_time_ms))},
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                ) from exc
            if mt <= 0:
                raise DataStoreValidationError(
                    "max_time_ms must be > 0",
                    details={"max_time_ms": mt},
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                )
            object.__setattr__(self, "max_time_ms", mt)

        # Validate sort spec shallowly (names only)
        if self.sort is not None:
            out: list[tuple[str, int]] = []
            for item in self.sort:
                if not isinstance(item, tuple) or len(item) != 2:
                    raise DataStoreValidationError(
                        "sort must be a sequence of (field, direction)",
                        details={"sort_item": redact_value(str(item))},
                        context=DataStoreErrorContext(operation="mongodb.query.validate"),
                    )
                field, direction = item
                fname = sanitize_mongo_field_name(str(field))
                try:
                    direc = int(direction)
                except Exception as exc:  # noqa: BLE001
                    raise DataStoreValidationError(
                        "sort direction must be int",
                        details={"field": fname, "direction": redact_value(str(direction))},
                        context=DataStoreErrorContext(operation="mongodb.query.validate"),
                    ) from exc
                if direc not in (1, -1):
                    raise DataStoreValidationError(
                        "sort direction must be 1 or -1",
                        details={"field": fname, "direction": direc},
                        context=DataStoreErrorContext(operation="mongodb.query.validate"),
                    )
                out.append((fname, direc))
            object.__setattr__(self, "sort", tuple(out))

        # Enforce basic consistency: aggregate uses pipeline; find uses filter
        if op == "aggregate":
            if self.pipeline is None:
                raise DataStoreValidationError(
                    "aggregate op requires pipeline",
                    context=DataStoreErrorContext(operation="mongodb.query.validate"),
                )

    def fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable fingerprint of the query structure without exposing filter/pipeline values.
        """
        payload: dict[str, Any] = {
            "op": self.op,
            "ns": self.namespace.canonical(),
            "filter": self.filter,
            "pipeline": self.pipeline,
            "projection": self.projection,
            "sort": list(self.sort) if self.sort else None,
            "limit": self.limit,
            "skip": self.skip,
            "max_time_ms": self.max_time_ms,
            "read_only": bool(self.read_only),
        }
        return _fingerprint_payload(payload, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return mongo_query_summary(self)


@dataclass(frozen=True, slots=True)
class MongoQueryResult:
    """
    Provider-agnostic MongoDB query result container.

    SAFETY:
      - documents are suppressed from repr()
      - redacted_dict returns only counts/field names and safe stats
    """

    op: str
    namespace: MongoNamespace
    query_fingerprint: str

    documents: Sequence[Mapping[str, Any]] = field(default_factory=tuple, repr=False)

    # Provider-defined stats (must be log-safe; still passed through redact_mapping)
    # Examples: {"matched": 10, "returned": 5, "cursor_id": "...", "duration_ms": 12}
    stats: Mapping[str, Any] = field(default_factory=dict)

    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return mongo_result_summary(self)


# =============================================================================
# Write intents + results
# =============================================================================

_ALLOWED_WRITE_OPS = {
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "delete_one",
    "delete_many",
    "bulk",
}


def _normalize_write_op(op: str) -> str:
    s = (op or "").strip().lower()
    if not s:
        raise DataStoreValidationError(
            "mongo write op is required",
            details={"field": "op"},
            context=DataStoreErrorContext(operation="mongodb.write.validate"),
        )
    if s not in _ALLOWED_WRITE_OPS:
        raise DataStoreValidationError(
            "unsupported mongo write op",
            details={"op": redact_value(s), "allowed": sorted(_ALLOWED_WRITE_OPS)},
            context=DataStoreErrorContext(operation="mongodb.write.validate"),
        )
    return s


@dataclass(frozen=True, slots=True)
class MongoWrite:
    """
    MongoDB write/mutation intent.

    SAFETY:
      - document/update/filter are suppressed from repr()
      - use mongo_write_summary() for log-safe details

    Notes:
      - For bulk, pass operations as a sequence of MongoWrite in `bulk_ops`.
    """

    namespace: MongoNamespace
    op: str

    filter: Mapping[str, Any] | None = field(default=None, repr=False)
    update: Mapping[str, Any] | None = field(default=None, repr=False)
    document: Mapping[str, Any] | None = field(default=None, repr=False)
    documents: Sequence[Mapping[str, Any]] | None = field(default=None, repr=False)

    upsert: bool = False
    multi: bool | None = None  # may be implied by op; connector can ignore

    bulk_ops: Sequence[MongoWrite] | None = field(default=None, repr=False)

    max_time_ms: int | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        op = _normalize_write_op(self.op)
        object.__setattr__(self, "op", op)

        # basic consistency checks
        if op in ("insert_one",):
            if self.document is None:
                raise DataStoreValidationError(
                    "insert_one requires document",
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                )

        if op in ("insert_many",):
            if not self.documents:
                raise DataStoreValidationError(
                    "insert_many requires documents",
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                )

        if op in ("update_one", "update_many"):
            if self.filter is None or self.update is None:
                raise DataStoreValidationError(
                    "update requires filter and update",
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                )

        if op in ("delete_one", "delete_many"):
            if self.filter is None:
                raise DataStoreValidationError(
                    "delete requires filter",
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                )

        if op == "bulk":
            if not self.bulk_ops:
                raise DataStoreValidationError(
                    "bulk requires bulk_ops",
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                )

        if self.max_time_ms is not None:
            try:
                mt = int(self.max_time_ms)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "max_time_ms must be an integer",
                    details={"max_time_ms": redact_value(str(self.max_time_ms))},
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                ) from exc
            if mt <= 0:
                raise DataStoreValidationError(
                    "max_time_ms must be > 0",
                    details={"max_time_ms": mt},
                    context=DataStoreErrorContext(operation="mongodb.write.validate"),
                )
            object.__setattr__(self, "max_time_ms", mt)

    def fingerprint(self, *, salt: str = "francis") -> str:
        payload: dict[str, Any] = {
            "op": self.op,
            "ns": self.namespace.canonical(),
            "filter": self.filter,
            "update": self.update,
            "document": self.document,
            "documents": self.documents,
            "upsert": bool(self.upsert),
            "multi": self.multi,
            "bulk_ops": [bo.op for bo in (self.bulk_ops or ())],
        }
        return _fingerprint_payload(payload, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return mongo_write_summary(self)


@dataclass(frozen=True, slots=True)
class MongoWriteResult:
    """
    Provider-agnostic result container for Mongo write operations.

    SAFETY:
      - does not include inserted documents or updated fields
      - includes counts + safe stats
    """

    op: str
    namespace: MongoNamespace
    write_fingerprint: str

    acknowledged: bool = True

    inserted_count: int | None = None
    matched_count: int | None = None
    modified_count: int | None = None
    deleted_count: int | None = None
    upserted_id: str | None = None  # NOTE: may be sensitive; prefer hashed ids in connectors

    stats: Mapping[str, Any] = field(default_factory=dict)
    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return mongo_write_result_summary(self)


# =============================================================================
# Optional capability protocols
# =============================================================================


@runtime_checkable
class MongoQueryRunner(Protocol):
    """
    Optional capability: run MongoDB queries.

    Implementations SHOULD:
      - accept MongoQuery
      - raise DataStoreError subclasses on failure (from connectors/data_stores/__init__.py)
      - never log raw filters/pipelines/documents
    """

    def run_query(
        self,
        query: MongoQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> MongoQueryResult: ...


@runtime_checkable
class MongoWriteRunner(Protocol):
    """
    Optional capability: run MongoDB writes/mutations.
    """

    def run_write(
        self,
        write: MongoWrite,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> MongoWriteResult: ...


# =============================================================================
# Log-safe summaries
# =============================================================================


def summarize_mongo_value(v: Any) -> dict[str, Any]:
    """
    Summarize a value without returning it.

    This is intended for log-safe shapes (types/lengths/hashes).
    """
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
        return {"type": "bytes", "len": len(v), "hash": hash_stable(bytes(v)[:256].hex())}
    if isinstance(v, Mapping):
        return {"type": "object", "keys": len(v)}
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        return {"type": "array", "len": len(v)}
    return {"type": type(v).__name__}


def summarize_mongo_mapping(m: Mapping[str, Any] | None, *, max_keys: int = 50) -> dict[str, Any]:
    """
    Summarize a mapping (filter/document/update) without revealing values.
    """
    if not m:
        return {"count": 0, "keys": [], "shapes": {}}
    if not isinstance(m, Mapping):
        return {
            "count": 1,
            "keys": ["<non_mapping>"],
            "shapes": {"<non_mapping>": {"type": type(m).__name__}},
        }

    keys = [str(k) for k in m.keys()]
    keys_sorted = sorted(keys)
    truncated = False
    if len(keys_sorted) > max_keys:
        keys_sorted = keys_sorted[:max_keys]
        truncated = True

    shapes: dict[str, Any] = {}
    for k in keys_sorted:
        kk = k
        if "\x00" in kk or "\r" in kk or "\n" in kk:
            kk = "<invalid_key>"
        try:
            shapes[kk] = summarize_mongo_value(m.get(k))
        except Exception:
            shapes[kk] = {"type": "error"}

    if truncated:
        shapes["…"] = {"truncated": True}

    return {"count": len(keys), "keys": keys_sorted, "shapes": shapes}


def mongo_query_summary(query: MongoQuery) -> dict[str, Any]:
    """
    Log-safe summary of a MongoQuery.

    - excludes raw filter/pipeline/projection
    - includes fingerprint and structural info
    """
    if not isinstance(query, MongoQuery):
        raise DataStoreValidationError(
            "mongo_query_summary expects MongoQuery",
            details={"type": type(query).__name__},
            context=DataStoreErrorContext(operation="mongodb.query.summary"),
        )

    pipeline_len = len(query.pipeline or ()) if query.pipeline is not None else 0
    proj_keys = list(query.projection.keys()) if isinstance(query.projection, Mapping) else []
    proj_sample = sorted(str(k) for k in proj_keys)[:50]

    return {
        "op": query.op,
        "namespace": query.namespace.redacted_dict(),
        "read_only": bool(query.read_only),
        "fingerprint": query.fingerprint(),
        "filter": summarize_mongo_mapping(query.filter),
        "pipeline_len": pipeline_len,
        "projection_key_count": len(proj_keys),
        "projection_keys_sample": proj_sample,
        "sort": list(query.sort) if query.sort else None,
        "limit": query.limit,
        "skip": query.skip,
        "max_time_ms": query.max_time_ms,
        "meta": redact_mapping(query.meta),
    }


def mongo_result_summary(result: MongoQueryResult) -> dict[str, Any]:
    """
    Log-safe summary of a MongoQueryResult.

    - excludes document values
    - includes record count and sampled top-level field names
    """
    if not isinstance(result, MongoQueryResult):
        return {"type": type(result).__name__}

    count = len(result.documents or ())
    fields: set[str] = set()

    sample_n = min(count, 10)
    for i in range(sample_n):
        try:
            doc = result.documents[i]  # type: ignore[index]
            if isinstance(doc, Mapping):
                for k in doc.keys():
                    fields.add(str(k))
        except Exception:
            continue

    return {
        "op": result.op,
        "namespace": result.namespace.redacted_dict(),
        "query_fingerprint": result.query_fingerprint,
        "document_count": count,
        "sampled_fields": sorted(fields)[:100],
        "stats": redact_mapping(result.stats),
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }


def mongo_write_summary(write: MongoWrite) -> dict[str, Any]:
    """
    Log-safe summary of a MongoWrite.

    - excludes raw filter/update/document(s)
    - includes fingerprint and structural info
    """
    if not isinstance(write, MongoWrite):
        raise DataStoreValidationError(
            "mongo_write_summary expects MongoWrite",
            details={"type": type(write).__name__},
            context=DataStoreErrorContext(operation="mongodb.write.summary"),
        )

    docs_count = len(write.documents or ()) if write.documents is not None else (1 if write.document is not None else 0)
    bulk_count = len(write.bulk_ops or ()) if write.bulk_ops is not None else 0

    return {
        "op": write.op,
        "namespace": write.namespace.redacted_dict(),
        "fingerprint": write.fingerprint(),
        "upsert": bool(write.upsert),
        "multi": write.multi,
        "filter": summarize_mongo_mapping(write.filter),
        "update": summarize_mongo_mapping(write.update),
        "document_shape": summarize_mongo_mapping(write.document) if write.document is not None else {"count": 0},
        "documents_count": docs_count if write.op in ("insert_many",) else docs_count,
        "bulk_ops_count": bulk_count if write.op == "bulk" else 0,
        "max_time_ms": write.max_time_ms,
        "meta": redact_mapping(write.meta),
    }


def mongo_write_result_summary(result: MongoWriteResult) -> dict[str, Any]:
    """
    Log-safe summary of a MongoWriteResult.

    NOTE:
      - upserted_id may be sensitive; we hash it for logs.
    """
    if not isinstance(result, MongoWriteResult):
        return {"type": type(result).__name__}

    upserted = result.upserted_id
    upserted_safe = hash_stable(upserted) if upserted else None

    return {
        "op": result.op,
        "namespace": result.namespace.redacted_dict(),
        "write_fingerprint": result.write_fingerprint,
        "acknowledged": bool(result.acknowledged),
        "inserted_count": result.inserted_count,
        "matched_count": result.matched_count,
        "modified_count": result.modified_count,
        "deleted_count": result.deleted_count,
        "upserted_id_hash": upserted_safe,
        "stats": redact_mapping(result.stats),
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }
