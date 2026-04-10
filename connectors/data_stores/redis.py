"""
===============================================================================
Francis 2.0 — Data Store Connectors (Redis Utilities)
Path: connectors/data_stores/redis.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *Redis-specific but dependency-free* primitives and helpers
used by Redis-capable data store connectors.

It is intentionally driver neutral:
  - No redis-py / aioredis imports here.
  - Standard library only.

It provides:
  - Stable Redis-ish types:
      * RedisKey (str|bytes) helpers + log-safe hashing
      * RedisCommand / RedisCommandResult (safe-by-default models)
  - Optional capability Protocols for Redis connectors:
      * RedisCommandRunner (run_command)
      * RedisPipelineRunner (run_pipeline)
  - Safe validation + log hygiene:
      * conservative key validation for helper paths
      * command fingerprinting (stable hash; never logs raw args/values)
      * argument/value summaries that avoid leaking PII/secrets
  - DataStoreResourceRef helpers:
      * keys: kind="key", id="db<idx>#<hash>" (default) to avoid leaking key names

DESIGN NOTES
------------
Redis is multi-modal (KV, hashes, sets, streams). This file does NOT attempt to
model every data structure. It focuses on:
  - a safe command representation
  - deterministic logging without exposing keys/values

SAFETY & OBSERVABILITY
----------------------
- Keys and values are treated as potentially sensitive. Do not log them.
- This module only emits hashes, lengths, and types in summaries.
- DataStoreResourceRef.id is NOT auto-redacted, so key refs default to hashed ids.

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
    "REDIS_PROVIDER_ID",
    "REDIS_CATEGORY",
    "REDIS_SERVICE",
    # Key + command helpers
    "RedisKey",
    "normalize_redis_db_index",
    "validate_redis_key",
    "key_fingerprint",
    "hash_stable",
    # Resource refs
    "redis_key_resource_ref",
    # Command models
    "RedisCommand",
    "RedisCommandResult",
    # Optional capability protocols
    "RedisCommandRunner",
    "RedisPipelineRunner",
    # Read-only heuristic
    "normalize_redis_command_name",
    "is_probably_read_only_redis_command",
    # Log-safe summaries
    "summarize_redis_arg",
    "summarize_redis_args",
    "redis_command_summary",
    "redis_result_summary",
]


# =============================================================================
# Constants
# =============================================================================

REDIS_PROVIDER_ID = "redis"
REDIS_CATEGORY = "cache"
REDIS_SERVICE = "cache"


# =============================================================================
# Stable hashing for correlation (no raw keys/values in logs)
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
# Redis keys: validation + fingerprinting
# =============================================================================

RedisKey = str | bytes

# Conservative key guardrails for helper paths:
# - disallow NUL/CR/LF
# - cap size to avoid accidental huge logs/payloads
_MAX_KEY_BYTES = 1024


def normalize_redis_db_index(db: int | str | None) -> int | None:
    """
    Normalize a Redis database index.

    Returns:
      - None if db is None
      - int >= 0 otherwise
    """
    if db is None:
        return None
    try:
        i = int(db)
    except Exception as exc:  # noqa: BLE001
        raise DataStoreValidationError(
            "redis db index must be an integer",
            details={"db": redact_value(str(db))},
            context=DataStoreErrorContext(operation="redis.normalize_db"),
        ) from exc
    if i < 0:
        raise DataStoreValidationError(
            "redis db index cannot be negative",
            details={"db": i},
            context=DataStoreErrorContext(operation="redis.normalize_db"),
        )
    return i


def _key_to_bytes(key: RedisKey) -> bytes:
    if isinstance(key, bytes):
        return key
    if key is None:
        return b""
    return str(key).encode("utf-8", errors="strict")


def validate_redis_key(key: RedisKey) -> None:
    """
    Validate a Redis key for safe helper usage.

    Notes:
      - Redis allows binary keys; we support bytes keys as-is.
      - For safety/observability we disallow NUL/CR/LF and cap size.
      - Provider connectors can relax this if needed, but must keep logs safe.
    """
    b = _key_to_bytes(key)
    if not b:
        raise DataStoreValidationError(
            "redis key is required",
            details={"field": "key"},
            context=DataStoreErrorContext(operation="redis.key.validate"),
        )
    if len(b) > _MAX_KEY_BYTES:
        raise DataStoreValidationError(
            "redis key too large for safe helper usage",
            details={"key_bytes": len(b), "max_bytes": _MAX_KEY_BYTES},
            context=DataStoreErrorContext(operation="redis.key.validate"),
        )
    if b"\x00" in b or b"\r" in b or b"\n" in b:
        raise DataStoreValidationError(
            "redis key contains illegal control bytes",
            context=DataStoreErrorContext(operation="redis.key.validate"),
        )


def key_fingerprint(key: RedisKey, *, salt: str = "francis") -> str:
    """
    Return a stable fingerprint for a key without exposing it.

    - For bytes keys, hashes the bytes hex (capped) to avoid huge cost.
    - For str keys, hashes the string.
    """
    b = _key_to_bytes(key)
    # Hash a capped representation to avoid heavy compute.
    rep = b.hex()[:2048]
    return hash_stable(rep, salt=salt)


def redis_key_resource_ref(
    *,
    key: RedisKey,
    db: int | str | None = None,
    provider_id: str = REDIS_PROVIDER_ID,
    identity: DataStoreIdentity | None = None,
    uri: str | None = None,
    meta: Mapping[str, Any] | None = None,
    include_raw_key: bool = False,
) -> DataStoreResourceRef:
    """
    Create a DataStoreResourceRef for a Redis key.

    IMPORTANT:
    DataStoreResourceRef.id is not automatically redacted. Redis keys can be PII.
    So by default we store a hashed key fingerprint.

    id format:
      - include_raw_key=False (default): "db<idx>#<hash>" or "key#<hash>" if db is None
      - include_raw_key=True:            "db<idx>/<raw_key>" (NOT RECOMMENDED unless you never log refs)

    kind="key"
    """
    validate_redis_key(key)
    dbi = normalize_redis_db_index(db)

    if include_raw_key:
        # WARNING: raw key in id; do not log this ref.
        raw = key.decode("utf-8", errors="replace") if isinstance(key, bytes) else str(key)
        rid = f"db{dbi}/{raw}" if dbi is not None else f"key/{raw}"
    else:
        kid = key_fingerprint(key)
        rid = f"db{dbi}#{kid}" if dbi is not None else f"key#{kid}"

    m: dict[str, Any] = dict(meta) if meta else {}
    if dbi is not None:
        m.setdefault("db", dbi)

    return DataStoreResourceRef(
        provider_id=provider_id,
        service=REDIS_SERVICE,
        kind="key",
        id=rid,
        identity=identity,
        uri=uri,
        meta=m,
    )


# =============================================================================
# Commands: normalization + read-only heuristic
# =============================================================================

_CMD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9:_\-]{0,63}$")

# A small, practical read-only set (not exhaustive).
_READ_ONLY_CMDS = {
    "get",
    "mget",
    "strlen",
    "exists",  # arguably neutral but safe to treat read-only
    "ttl",
    "pttl",
    "type",
    "keys",
    "scan",
    "hget",
    "hmget",
    "hlen",
    "hkeys",
    "hvals",
    "hgetall",
    "llen",
    "lrange",
    "scard",
    "smembers",
    "sismember",
    "zcard",
    "zrange",
    "zrevrange",
    "zscore",
    "xinfo",
    "xrange",
    "xrevrange",
    "xread",
    "ping",
    "echo",
    "info",
    "role",
    "client",
    "time",
}

# A small, practical write-ish set (not exhaustive).
_WRITE_CMDS = {
    "set",
    "setex",
    "psetex",
    "mset",
    "del",
    "unlink",
    "expire",
    "pexpire",
    "persist",
    "incr",
    "decr",
    "incrby",
    "decrby",
    "append",
    "hset",
    "hmset",
    "hdel",
    "hincrby",
    "lpush",
    "rpush",
    "lpop",
    "rpop",
    "lset",
    "ltrim",
    "sadd",
    "srem",
    "spop",
    "zadd",
    "zrem",
    "zincrby",
    "xadd",
    "xdel",
    "xtrim",
    "xgroup",
    "xack",
    "publish",
    "flushdb",
    "flushall",
    "eval",
    "evalsha",  # can mutate
}


def normalize_redis_command_name(command: str) -> str:
    """
    Normalize and validate a Redis command name.

    - lowercases
    - conservative validation to avoid control chars / weird logging
    """
    c = (command or "").strip()
    if not c:
        raise DataStoreValidationError(
            "redis command is required",
            details={"field": "command"},
            context=DataStoreErrorContext(operation="redis.command.normalize"),
        )
    if "\x00" in c or "\r" in c or "\n" in c:
        raise DataStoreValidationError(
            "redis command contains illegal control characters",
            details={"command": redact_value(c)},
            context=DataStoreErrorContext(operation="redis.command.normalize"),
        )
    if not _CMD_RE.match(c):
        raise DataStoreValidationError(
            "redis command name has invalid format (conservative rule)",
            details={"command": redact_value(c), "expected": _CMD_RE.pattern},
            context=DataStoreErrorContext(operation="redis.command.normalize"),
        )
    return c.lower()


def is_probably_read_only_redis_command(command: str) -> bool:
    """
    Best-effort heuristic: determine if a Redis command is *probably* read-only.

    Not a security boundary. Governance should enforce write permissions elsewhere.
    """
    cmd = normalize_redis_command_name(command)
    if cmd in _WRITE_CMDS:
        return False
    if cmd in _READ_ONLY_CMDS:
        return True

    # Unknown: be conservative (treat as not read-only).
    return False


# =============================================================================
# Args summarization (no raw values)
# =============================================================================


def summarize_redis_arg(v: Any) -> dict[str, Any]:
    """
    Summarize an argument without revealing it.

    Intended for keys/values/args used in commands.
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
        # Don't log raw strings; hash+len only.
        return {"type": "str", "len": len(v), "hash": hash_stable(v)}

    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
        return {"type": "bytes", "len": len(b), "hash": hash_stable(b[:256].hex())}

    if isinstance(v, Mapping):
        return {"type": "object", "keys": len(v)}

    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        return {"type": "array", "len": len(v)}

    # fallback
    try:
        s = str(v)
    except Exception:
        s = type(v).__name__
    return {
        "type": type(v).__name__,
        "hash": hash_stable(s),
        "len": len(s) if isinstance(s, str) else None,
    }


def summarize_redis_args(args: Sequence[Any] | None, *, max_items: int = 50) -> dict[str, Any]:
    """
    Summarize a command args list without exposing values.
    """
    if not args:
        return {"count": 0, "sample": []}

    n = len(args)
    sample_n = min(n, max_items)
    sample = []
    for i in range(sample_n):
        try:
            sample.append(summarize_redis_arg(args[i]))
        except Exception:
            sample.append({"type": "error"})
    return {"count": n, "sample": sample, "truncated": n > sample_n}


# =============================================================================
# Command models + results
# =============================================================================


@dataclass(frozen=True, slots=True)
class RedisCommand:
    """
    Provider-agnostic Redis command model.

    SAFETY:
      - args are suppressed from repr()
      - summaries never include raw args (keys/values)
    """

    command: str
    args: Sequence[Any] = field(default_factory=tuple, repr=False)

    # Optional db index hint; connector may ignore if using separate clients/pools
    db: int | None = None

    # Governance hint; default derived from command heuristic if not provided
    read_only: bool | None = None

    # Hints; connector may ignore or map to driver options
    timeout_s: float | None = None

    # Optional URI for context; redacted in summaries
    uri: str | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cmd = normalize_redis_command_name(self.command)
        object.__setattr__(self, "command", cmd)

        if self.db is not None:
            object.__setattr__(self, "db", normalize_redis_db_index(self.db))

        if self.read_only is None:
            object.__setattr__(self, "read_only", bool(is_probably_read_only_redis_command(cmd)))

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise DataStoreValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=DataStoreErrorContext(operation="redis.command.validate"),
                ) from exc
            if ts <= 0:
                raise DataStoreValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=DataStoreErrorContext(operation="redis.command.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

    def fingerprint(self, *, salt: str = "francis") -> str:
        """
        Stable fingerprint of the command name + argument *shapes* (not values).
        """
        payload = {
            "cmd": self.command,
            "db": self.db,
            "args": summarize_redis_args(self.args),
            "read_only": bool(self.read_only),
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return redis_command_summary(self)


@dataclass(frozen=True, slots=True)
class RedisCommandResult:
    """
    Provider-agnostic command result container.

    SAFETY:
      - value is suppressed from repr()
      - summaries do not include raw values
    """

    command_fingerprint: str
    command: str

    value: Any = field(default=None, repr=False)

    # Provider-defined stats; must be log-safe. Still passed through redact_mapping.
    # Examples: {"duration_ms": 2, "node": "cluster-1:7000", "retries": 1}
    stats: Mapping[str, Any] = field(default_factory=dict)

    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return redis_result_summary(self)


# =============================================================================
# Optional capability protocols
# =============================================================================


@runtime_checkable
class RedisCommandRunner(Protocol):
    """
    Optional capability: run a single Redis command.

    Implementations SHOULD:
      - accept RedisCommand
      - raise DataStoreError subclasses on failure (from connectors/data_stores/__init__.py)
      - never log raw keys/values/args
    """

    def run_command(
        self,
        cmd: RedisCommand,
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> RedisCommandResult: ...


@runtime_checkable
class RedisPipelineRunner(Protocol):
    """
    Optional capability: run a list of Redis commands (pipeline).

    Connectors can map this to driver pipeline/transaction.
    """

    def run_pipeline(
        self,
        cmds: Sequence[RedisCommand],
        *,
        identity: DataStoreIdentity | None = None,
        timeout_s: float | None = None,
    ) -> Sequence[RedisCommandResult]: ...


# =============================================================================
# Log-safe summaries
# =============================================================================


def redis_command_summary(cmd: RedisCommand, *, salt: str = "francis") -> dict[str, Any]:
    """
    Log-safe summary of a RedisCommand.

    - excludes raw args (keys/values)
    - includes fingerprint + arg shapes
    """
    if not isinstance(cmd, RedisCommand):
        raise DataStoreValidationError(
            "redis_command_summary expects RedisCommand",
            details={"type": type(cmd).__name__},
            context=DataStoreErrorContext(operation="redis.command.summary"),
        )

    return {
        "command": cmd.command,
        "db": cmd.db,
        "read_only": bool(cmd.read_only),
        "timeout_s": cmd.timeout_s,
        "args": summarize_redis_args(cmd.args),
        "fingerprint": cmd.fingerprint(salt=salt),
        "uri": redact_uri(cmd.uri) if cmd.uri else None,
        "meta": redact_mapping(cmd.meta),
    }


def redis_result_summary(result: RedisCommandResult) -> dict[str, Any]:
    """
    Log-safe summary of a RedisCommandResult.

    - excludes raw result values
    - includes a value shape summary only
    """
    if not isinstance(result, RedisCommandResult):
        return {"type": type(result).__name__}

    value_shape = summarize_redis_arg(result.value)

    return {
        "command": result.command,
        "command_fingerprint": result.command_fingerprint,
        "value_shape": value_shape,
        "stats": redact_mapping(result.stats),
        "ts": result.ts,
        "meta": redact_mapping(result.meta),
    }
