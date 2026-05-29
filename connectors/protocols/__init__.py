from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True, init=False)
class ProtocolErrorContext:
    protocol_id: str
    operation: str
    request_id: str
    details: dict[str, Any]

    def __init__(
        self,
        protocol_id: str,
        operation: str = "",
        request_id: str = "",
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        object.__setattr__(self, "protocol_id", protocol_id)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "request_id", request_id)
        merged = dict(details or {})
        merged.update(extra)
        object.__setattr__(self, "details", merged)


class ProtocolError(Exception):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        context: ProtocolErrorContext | None = None,
        code: str = "",
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.context = context
        self.code = code
        self.__cause__ = cause


class ProtocolAuthError(ProtocolError):
    pass


class ProtocolNetworkError(ProtocolError):
    pass


class ProtocolPermissionError(ProtocolError):
    pass


class ProtocolRateLimitError(ProtocolError):
    pass


class ProtocolSerializationError(ProtocolError):
    pass


class ProtocolTimeoutError(ProtocolError):
    pass


class ProtocolUnavailableError(ProtocolError):
    pass


class ProtocolUnsupportedError(ProtocolError):
    pass


class ProtocolValidationError(ProtocolError):
    pass


@dataclass(frozen=True, slots=True)
class ProtocolBackoffPolicy:
    max_attempts: int = 1
    base_delay_s: float = 0.1
    max_delay_s: float = 2.0
    jitter_s: float = 0.05


@dataclass(frozen=True, slots=True)
class ProtocolConnectorInfo:
    protocol_id: str
    name: str
    version: str | None = None
    description: str = ""
    capabilities: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProtocolEndpoint:
    uri: str = ""
    address: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return {"uri": redact_uri(self.uri), "address": redact_value(self.address), "meta": redact_mapping(self.meta)}


@dataclass(frozen=True, slots=True)
class ProtocolIdentity:
    principal: str = ""
    credentials: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProtocolHealth:
    ok: bool
    degraded: bool = False
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProtocolRequest:
    operation: str
    payload: Any = None
    endpoint: ProtocolEndpoint | None = None
    identity: ProtocolIdentity | None = None
    headers: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    timeout_s: float | None = None
    idempotent: bool | None = None


@dataclass(slots=True, init=False)
class ProtocolResponse:
    ok: bool
    payload: Any
    status: str
    details: dict[str, Any]

    def __init__(
        self,
        ok: bool,
        payload: Any = None,
        status: str = "",
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        self.ok = bool(ok)
        self.payload = payload
        self.status = status
        self.details = details or {}
        for key, value in extra.items():
            setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


def compute_backoff_s(
    policy_or_attempt: ProtocolBackoffPolicy | int,
    policy: ProtocolBackoffPolicy | None = None,
    *,
    attempt: int | None = None,
) -> float:
    active_policy = policy_or_attempt if isinstance(policy_or_attempt, ProtocolBackoffPolicy) else policy
    if active_policy is None:
        active_policy = ProtocolBackoffPolicy()
    if attempt is not None:
        bounded_attempt = max(0, int(attempt))
    else:
        bounded_attempt = max(0, int(policy_or_attempt)) if isinstance(policy_or_attempt, int) else 0
    delay = min(float(active_policy.max_delay_s), float(active_policy.base_delay_s) * (2**bounded_attempt))
    jitter = random.uniform(0.0, max(0.0, float(active_policy.jitter_s))) if active_policy.jitter_s > 0 else 0.0
    return max(0.0, delay + jitter)


def redact_value(value: Any) -> str:
    text = "" if value is None else str(value)
    if len(text) <= 8:
        return "[REDACTED]" if text else ""
    return f"{text[:4]}...[REDACTED]"


def redact_uri(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.split("@", 1)[-1] if "@" in text else text


def redact_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, item in (value or {}).items():
        lowered = str(key).lower()
        if any(secret_key in lowered for secret_key in ("authorization", "cookie", "token", "secret", "password")):
            out[str(key)] = "[REDACTED]"
        else:
            out[str(key)] = item
    return out
