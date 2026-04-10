"""
===============================================================================
Francis 2.0 — Data Store Connectors (Graph DB Utilities)
Path: connectors/data_stores/graph_db.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *provider-agnostic* primitives and helpers for graph databases,
sitting alongside the generic data store contract in connectors/data_stores/__init__.py.

It is intentionally provider-neutral:
  - No Neo4j / Neptune / JanusGraph / TigerGraph / RDF store SDK imports here.
  - Standard library only.

It provides:
  - Graph-specific stable types:
      * GraphNodeRef / GraphEdgeRef
      * GraphQuery / GraphQueryResult
  - A small set of optional Protocols for graph-capable connectors:
      * GraphQueryRunner (run_query)
      * GraphMutationRunner (run_write)
  - Safe logging helpers:
      * query fingerprinting (hash + length; no raw query text in logs)
      * param summaries that avoid leaking PII/secrets
      * result summaries that avoid leaking row values

DESIGN NOTES
------------
Graph systems differ (Property Graph vs RDF/Triple Store), and query languages differ
(Cypher, Gremlin, SPARQL, openCypher, etc.). This module avoids forcing one shape by:
  - Treating the query language as an identifier string
  - Treating query text as opaque bytes/str (never logged)
  - Letting providers return a provider-specific "stats" blob in a log-safe way

SAFETY & OBSERVABILITY
----------------------
- Query text is never included in repr()/redacted_dict() by default.
- Parameters are summarized by type/length/hash, not raw values.
- Results are summarized by record count and field names only.

===============================================================================
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable, Mapping, Sequence
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
    redact_uri,
    redact_value,
)

__all__ = [
    # Constants
    "GRAPH_CATEGORY",
    "GRAPH_SERVICE",
    # Graph types
    "GraphLabel",
    "GraphRelType",
    "GraphNodeRef",
    "GraphEdgeRef",
    "GraphQueryLanguage",
    "GraphQuery",
    "GraphQueryResult",
    # Optional capability protocols
    "GraphQueryRunner",
    "GraphMutationRunner",
    # Validation / normalization helpers
    "normalize_graph_language",
    "sanitize_graph_identifier",
    "sanitize_graph_labels",
    "sanitize_graph_rel_type",
    # ResourceRef helpers
    "graph_node_resource_ref",
    "graph_edge_resource_ref",
    # Log-safe summaries
    "hash_stable",
    "summarize_graph_params",
    "graph_query_summary",
    "graph_result_summary",
]


# =============================================================================
# Constants
# =============================================================================

GRAPH_CATEGORY = "graph"
GRAPH_SERVICE = "graph"


# =============================================================================
# Identifier helpers
# =============================================================================

GraphLabel = str
GraphRelType = str
GraphQueryLanguage = str

# Conservative safe identifier for labels/relationship types if used outside of raw query text.
# Providers can still support quoted/backticked identifiers; this is for safe-by-default utilities.
_GRAPH_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

# Language id: allow lowercase, digits, "_" "-" (like other connector ids)
_GRAPH_LANG_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,30}[a-z0-9]$")


def normalize_graph_language(language: str) -> GraphQueryLanguage:
    """
    Normalize/validate a graph query language identifier.

    Examples:
      - "cypher"
      - "opencypher"
      - "gremlin"
      - "sparql"
      - "gsql"
      - "graphql" (some graph systems expose GraphQL endpoints)

    This is intentionally *not* an enum.
    """
    lang = (language or "").strip().lower()
    if not lang:
        raise DataStoreValidationError(
            "graph query language is required",
            details={"field": "language"},
            context=DataStoreErrorContext(operation="graph.normalize_language"),
        )
    if not _GRAPH_LANG_RE.match(lang):
        raise DataStoreValidationError(
            "graph query language has invalid format",
            details={"language": redact_value(lang), "expected": _GRAPH_LANG_RE.pattern},
            context=DataStoreErrorContext(operation="graph.normalize_language"),
        )
    return lang


def sanitize_graph_identifier(identifier: str) -> str:
    """
    Validate a graph identifier (label, relationship type, property key) for safe helpers.

    NOTE:
    - This is a helper for *builder-style* utilities.
    - Raw query text may legitimately contain quoted identifiers; provider connectors
      can accept those without using this helper.
    """
    s = (identifier or "").strip()
    if not s:
        raise DataStoreValidationError(
            "graph identifier is required",
            details={"field": "identifier"},
            context=DataStoreErrorContext(operation="graph.sanitize_identifier"),
        )
    if "\x00" in s:
        raise DataStoreValidationError(
            "graph identifier contains NUL",
            details={"identifier": redact_value(s)},
            context=DataStoreErrorContext(operation="graph.sanitize_identifier"),
        )
    if not _GRAPH_IDENT_RE.match(s):
        raise DataStoreValidationError(
            "graph identifier has invalid format",
            details={"identifier": redact_value(s), "expected": _GRAPH_IDENT_RE.pattern},
            context=DataStoreErrorContext(operation="graph.sanitize_identifier"),
        )
    return s


def sanitize_graph_labels(labels: Iterable[str] | None) -> tuple[GraphLabel, ...]:
    """Validate and normalize an iterable of graph labels into a tuple."""
    if not labels:
        return tuple()
    out: list[str] = []
    for lb in labels:
        out.append(sanitize_graph_identifier(str(lb)))
    # stable ordering, but preserve user order if already unique-ish
    return tuple(out)


def sanitize_graph_rel_type(rel_type: str) -> GraphRelType:
    """Validate a relationship type for safe helpers."""
    return sanitize_graph_identifier(rel_type)


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
# Graph resource references
# =============================================================================


@dataclass(frozen=True, slots=True)
class GraphNodeRef:
    """
    Provider-agnostic reference to a graph node.

    - provider_id is the data store provider id (e.g., "neo4j", "neptune", "janusgraph")
    - id is an opaque node identifier (string). It might be:
        * internal node id
        * application key (uuid)
        * RDF IRI (for RDF backends)
    - labels are optional and informational
    """

    provider_id: str
    id: str

    labels: tuple[GraphLabel, ...] = field(default_factory=tuple)
    identity: DataStoreIdentity | None = None

    uri: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def canonical(self) -> str:
        base = f"{self.provider_id}:{GRAPH_SERVICE}:node:{self.id}"
        if self.identity and self.identity.database:
            return f"{self.provider_id}:{self.identity.database}:{GRAPH_SERVICE}:node:{self.id}"
        return base

    def redacted_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "id": self.id,
            "labels": list(self.labels),
            "identity": self.identity.redacted_dict() if self.identity else None,
            "uri": redact_uri(self.uri) if self.uri else None,
            "meta": redact_mapping(self.meta),
        }


@dataclass(frozen=True, slots=True)
class GraphEdgeRef:
    """
    Provider-agnostic reference to a graph edge/relationship.

    - type is optional but useful for property graphs.
    - src_id / dst_id are optional; some providers use an opaque edge id only.
    """

    provider_id: str
    id: str

    type: GraphRelType | None = None
    src_id: str | None = None
    dst_id: str | None = None

    identity: DataStoreIdentity | None = None

    uri: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def canonical(self) -> str:
        base = f"{self.provider_id}:{GRAPH_SERVICE}:edge:{self.id}"
        if self.identity and self.identity.database:
            return f"{self.provider_id}:{self.identity.database}:{GRAPH_SERVICE}:edge:{self.id}"
        return base

    def redacted_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "id": self.id,
            "type": self.type,
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "identity": self.identity.redacted_dict() if self.identity else None,
            "uri": redact_uri(self.uri) if self.uri else None,
            "meta": redact_mapping(self.meta),
        }


def graph_node_resource_ref(node: GraphNodeRef) -> DataStoreResourceRef:
    """
    Convert GraphNodeRef -> DataStoreResourceRef for generic systems that track resources.

    kind="node"
    """
    return DataStoreResourceRef(
        provider_id=node.provider_id,
        service=GRAPH_SERVICE,
        kind="node",
        id=node.id,
        identity=node.identity,
        uri=node.uri,
        meta={"labels": list(node.labels), **(dict(node.meta) if node.meta else {})},
    )


def graph_edge_resource_ref(edge: GraphEdgeRef) -> DataStoreResourceRef:
    """
    Convert GraphEdgeRef -> DataStoreResourceRef.

    kind="edge"
    """
    meta: dict[str, Any] = dict(edge.meta) if edge.meta else {}
    if edge.type:
        meta.setdefault("type", edge.type)
    if edge.src_id:
        meta.setdefault("src_id", edge.src_id)
    if edge.dst_id:
        meta.setdefault("dst_id", edge.dst_id)

    return DataStoreResourceRef(
        provider_id=edge.provider_id,
        service=GRAPH_SERVICE,
        kind="edge",
        id=edge.id,
        identity=edge.identity,
        uri=edge.uri,
        meta=meta,
    )


# =============================================================================
# Graph query + results
# =============================================================================


@dataclass(frozen=True, slots=True)
class GraphQuery:
    """
    Provider-agnostic graph query.

    SAFETY:
      - text is suppressed from repr() and is never included in redacted_dict()
      - use graph_query_summary() for log-safe details
    """

    language: GraphQueryLanguage
    text: str = field(repr=False)

    # Parameters are commonly used (Cypher params, Gremlin bindings, SPARQL bindings).
    params: Mapping[str, Any] = field(default_factory=dict)

    # Hint for governance / safety checks upstream
    read_only: bool = True

    # Caller hints; provider may ignore or map differently
    timeout_s: float | None = None
    max_records: int | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        lang = normalize_graph_language(self.language)
        object.__setattr__(self, "language", lang)

        t = "" if self.text is None else str(self.text)
        if "\x00" in t:
            raise DataStoreValidationError(
                "graph query text contains NUL",
                details={"language": lang},
                context=DataStoreErrorContext(operation="graph.query.validate"),
            )

        # Avoid absurd accidental payloads
        if len(t) > 2_000_000:
            raise DataStoreValidationError(
                "graph query text too large",
                details={"language": lang, "query_len": len(t), "max": 2_000_000},
                context=DataStoreErrorContext(operation="graph.query.validate"),
            )

        if self.max_records is not None:
            try:
                mr = int(self.max_records)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "max_records must be an integer",
                    details={"max_records": redact_value(str(self.max_records))},
                    context=DataStoreErrorContext(operation="graph.query.validate"),
                ) from exc
            if mr <= 0:
                raise DataStoreValidationError(
                    "max_records must be > 0",
                    details={"max_records": mr},
                    context=DataStoreErrorContext(operation="graph.query.validate"),
                )
            object.__setattr__(self, "max_records", mr)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=DataStoreErrorContext(operation="graph.query.validate"),
                ) from exc
            if ts <= 0:
                raise DataStoreValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=DataStoreErrorContext(operation="graph.query.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

    def fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable hash fingerprint of the query (language + text).
        Safe for logs/correlation. Never returns the raw query.
        """
        payload = f"{self.language}\n{self.text}"
        return hash_stable(payload, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return graph_query_summary(self)


@dataclass(frozen=True, slots=True)
class GraphQueryResult:
    """
    Provider-agnostic result container.

    SAFETY:
      - records are suppressed from repr()
      - redacted_dict returns only counts/field names and safe stats

    records: list[dict[str, Any]] for typical "rows" results
    For path/graph results, providers may return richer shapes in records.
    """

    language: GraphQueryLanguage
    query_fingerprint: str

    records: Sequence[Mapping[str, Any]] = field(default_factory=tuple, repr=False)

    # Provider-defined stats: e.g. {"nodes_created": 1, "relationships_created": 2, ...}
    # Must be log-safe (no raw values that are secrets/PII).
    stats: Mapping[str, Any] = field(default_factory=dict)

    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return graph_result_summary(self)


# =============================================================================
# Optional capability protocols for graph-capable connectors
# =============================================================================


@runtime_checkable
class GraphQueryRunner(Protocol):
    """
    Optional capability: run graph queries (read-only or mixed).

    Implementations SHOULD:
      - accept GraphQuery
      - apply provider-specific timeouts/bindings
      - raise DataStoreError subclasses on failure (from connectors/data_stores/__init__.py)
      - never log raw query text
    """

    def run_query(
        self,
        query: GraphQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> GraphQueryResult: ...


@runtime_checkable
class GraphMutationRunner(Protocol):
    """
    Optional capability: run graph write/mutation queries.

    This separates intent: some deployments want extra governance around writes.
    """

    def run_write(
        self,
        query: GraphQuery,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> GraphQueryResult: ...


# =============================================================================
# Log-safe summaries
# =============================================================================


def _value_shape(v: Any) -> dict[str, Any]:
    """
    Summarize a parameter value without leaking it.
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
        return {
            "type": "str",
            "len": len(v),
            "hash": hash_stable(v),
        }
    if isinstance(v, (bytes, bytearray)):
        return {
            "type": "bytes",
            "len": len(v),
            "hash": hash_stable(v.hex()[:512]),  # avoid huge; hash a prefix
        }
    if isinstance(v, Mapping):
        return {
            "type": "object",
            "keys": len(v),
        }
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        return {
            "type": "array",
            "len": len(v),
        }
    return {"type": type(v).__name__}


def summarize_graph_params(params: Mapping[str, Any] | None, *, max_keys: int = 50) -> dict[str, Any]:
    """
    Return a log-safe summary of query parameters.

    - No raw values are returned.
    - Keys are preserved (keys can still be sensitive; keep your param naming clean).
    - Caps number of keys to prevent log spam.
    """
    if not params:
        return {"count": 0, "items": {}}
    if not isinstance(params, Mapping):
        return {"count": 1, "items": {"<non_mapping>": {"type": type(params).__name__}}}

    items: dict[str, Any] = {}
    count = 0
    for k, v in params.items():
        if count >= max_keys:
            items["…"] = {"truncated": True}
            break
        kk = str(k)
        # Defensive: prevent weird control characters in keys
        if "\x00" in kk or "\r" in kk or "\n" in kk:
            kk = "<invalid_key>"
        items[kk] = _value_shape(v)
        count += 1
    return {"count": len(params), "items": items}


def graph_query_summary(query: GraphQuery, *, salt: str = "francis") -> dict[str, Any]:
    """
    Log-safe summary of a GraphQuery.

    - Does not include raw query text.
    - Includes fingerprint and length to correlate issues.
    """
    if not isinstance(query, GraphQuery):
        raise DataStoreValidationError(
            "graph_query_summary expects a GraphQuery instance",
            details={"type": type(query).__name__},
            context=DataStoreErrorContext(operation="graph.query.summary"),
        )

    qtext = "" if query.text is None else str(query.text)
    return {
        "language": query.language,
        "query_len": len(qtext),
        "query_fingerprint": query.fingerprint(salt=salt),
        "read_only": bool(query.read_only),
        "timeout_s": query.timeout_s,
        "max_records": query.max_records,
        "params": summarize_graph_params(query.params),
        "meta": redact_mapping(query.meta),
    }


def graph_result_summary(result: GraphQueryResult) -> dict[str, Any]:
    """
    Log-safe summary of a GraphQueryResult.

    - Does not include row values.
    - Includes record count and union of top-level field names (best-effort).
    """
    if not isinstance(result, GraphQueryResult):
        return {"type": type(result).__name__}

    record_count = len(result.records or ())
    fields: set[str] = set()

    # Best-effort field discovery (avoid walking huge result sets)
    sample_n = min(record_count, 10)
    for i in range(sample_n):
        try:
            rec = result.records[i]  # type: ignore[index]
            if isinstance(rec, Mapping):
                for k in rec.keys():
                    fields.add(str(k))
        except Exception:
            continue

    # Stats are assumed safe; still redact typical secret-like keys.
    stats_safe = redact_mapping(result.stats)

    return {
        "language": result.language,
        "query_fingerprint": result.query_fingerprint,
        "record_count": record_count,
        "sampled_fields": sorted(fields)[:100],
        "stats": stats_safe,
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }
