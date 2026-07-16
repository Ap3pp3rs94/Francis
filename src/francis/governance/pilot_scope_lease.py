from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Iterable

__all__ = [
    "PilotLeaseBinding",
    "PilotLeaseCheck",
    "PilotLeaseDecision",
    "PilotLeaseState",
    "PilotScopeLease",
    "PilotScopeLeaseRegistry",
]

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ROUTE_RE = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]{0,239}$")
_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_MAX_LEASE_DURATION_MS = 30 * 60 * 1_000


class PilotLeaseState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SEALED = "sealed"
    CONSUMED = "consumed"


@dataclass(frozen=True, order=True)
class PilotLeaseBinding:
    scope: str
    route: str
    method: str
    action: str

    def normalized(self) -> PilotLeaseBinding:
        return replace(
            self,
            scope=_identifier(self.scope, field_name="scope"),
            route=_route(self.route),
            method=_method(self.method),
            action=_identifier(self.action, field_name="action"),
        )


@dataclass(frozen=True)
class PilotScopeLease:
    lease_id: str
    actor_id: str
    package_id: str
    package_fingerprint: str
    pilot_run_id: str
    bindings: tuple[PilotLeaseBinding, ...]
    issued_at_ms: int
    expires_at_ms: int
    runtime_nonce: str
    operator_decision_fingerprint: str
    state: PilotLeaseState = PilotLeaseState.ACTIVE
    consumed_bindings: frozenset[PilotLeaseBinding] = field(default_factory=frozenset)

    def validated(self) -> PilotScopeLease:
        lease_id = _identifier(self.lease_id, field_name="lease_id")
        actor_id = _identifier(self.actor_id, field_name="actor_id")
        package_id = _identifier(self.package_id, field_name="package_id")
        pilot_run_id = _identifier(self.pilot_run_id, field_name="pilot_run_id")
        runtime_nonce = _identifier(self.runtime_nonce, field_name="runtime_nonce")
        package_fingerprint = _fingerprint(self.package_fingerprint, field_name="package_fingerprint")
        decision_fingerprint = _fingerprint(
            self.operator_decision_fingerprint,
            field_name="operator_decision_fingerprint",
        )
        issued_at_ms = _timestamp(self.issued_at_ms, field_name="issued_at_ms")
        expires_at_ms = _timestamp(self.expires_at_ms, field_name="expires_at_ms")
        if expires_at_ms <= issued_at_ms:
            raise ValueError("lease_expiry_not_after_issuance")
        if expires_at_ms - issued_at_ms > _MAX_LEASE_DURATION_MS:
            raise ValueError("lease_duration_exceeds_maximum")
        if not isinstance(self.state, PilotLeaseState):
            raise ValueError("invalid_lease_state")
        if self.state is not PilotLeaseState.ACTIVE:
            raise ValueError("new_lease_must_be_active")
        if not isinstance(self.bindings, tuple) or not self.bindings:
            raise ValueError("lease_bindings_required")
        if not all(isinstance(binding, PilotLeaseBinding) for binding in self.bindings):
            raise ValueError("invalid_lease_binding")
        bindings = tuple(binding.normalized() for binding in self.bindings)
        if len(set(bindings)) != len(bindings):
            raise ValueError("duplicate_lease_binding")
        if self.consumed_bindings:
            raise ValueError("new_lease_cannot_have_consumed_bindings")
        return replace(
            self,
            lease_id=lease_id,
            actor_id=actor_id,
            package_id=package_id,
            package_fingerprint=package_fingerprint,
            pilot_run_id=pilot_run_id,
            bindings=bindings,
            issued_at_ms=issued_at_ms,
            expires_at_ms=expires_at_ms,
            runtime_nonce=runtime_nonce,
            operator_decision_fingerprint=decision_fingerprint,
        )


@dataclass(frozen=True)
class PilotLeaseCheck:
    lease_id: str
    package_id: str
    package_fingerprint: str
    pilot_run_id: str
    runtime_nonce: str
    operator_decision_fingerprint: str
    scope: str
    route: str
    method: str
    action: str

    def binding(self) -> PilotLeaseBinding:
        return PilotLeaseBinding(self.scope, self.route, self.method, self.action).normalized()


@dataclass(frozen=True)
class PilotLeaseDecision:
    allowed: bool
    reason: str
    state: PilotLeaseState | None
    evidence: dict[str, object] = field(default_factory=dict)


class PilotScopeLeaseRegistry:
    """Process-local single-run lease authority.

    The registry deliberately has no persistence loader. A new process starts
    empty, so a prior lease cannot silently rehydrate after restart.
    """

    def __init__(self, leases: Iterable[PilotScopeLease] = ()) -> None:
        self._lock = threading.RLock()
        self._leases: dict[str, PilotScopeLease] = {}
        for lease in leases:
            self.issue(lease)

    def issue(self, lease: PilotScopeLease) -> PilotScopeLease:
        validated = lease.validated()
        with self._lock:
            if validated.lease_id in self._leases:
                raise ValueError("duplicate_lease_id")
            if any(
                current.actor_id == validated.actor_id
                and current.package_id == validated.package_id
                and current.pilot_run_id == validated.pilot_run_id
                and self._effective_state(current, _now_ms()) is PilotLeaseState.ACTIVE
                for current in self._leases.values()
            ):
                raise ValueError("conflicting_active_pilot_lease")
            self._leases[validated.lease_id] = validated
        return validated

    def authorize_and_consume(
        self,
        *,
        actor_id: object,
        check: PilotLeaseCheck,
        now_ms: int | None = None,
    ) -> PilotLeaseDecision:
        now = _now_ms() if now_ms is None else _timestamp(now_ms, field_name="now_ms")
        with self._lock:
            lease = self._leases.get(str(check.lease_id or "").strip())
            if lease is None:
                return _denied("missing_pilot_lease")
            state = self._effective_state(lease, now)
            if state is not PilotLeaseState.ACTIVE:
                return _denied(f"pilot_lease_{state.value}", state=state)
            try:
                binding = check.binding()
            except ValueError:
                return _denied("malformed_pilot_lease_check", state=state)
            mismatch = _binding_mismatch(lease, actor_id=actor_id, check=check, binding=binding)
            if mismatch:
                return _denied(mismatch, state=state)
            if binding in lease.consumed_bindings:
                return _denied("pilot_lease_binding_replayed", state=state)
            next_binding = lease.bindings[len(lease.consumed_bindings)]
            if binding != next_binding:
                return _denied("pilot_lease_binding_out_of_order", state=state)
            consumed = frozenset((*lease.consumed_bindings, binding))
            updated = replace(lease, consumed_bindings=consumed)
            self._leases[lease.lease_id] = updated
            resulting_state = self._effective_state(updated, now)
            return PilotLeaseDecision(
                True,
                "pilot_lease_binding_consumed",
                resulting_state,
                {
                    "lease_bound": True,
                    "binding_consumed": True,
                    "consumed_binding_count": len(consumed),
                    "allowed_binding_count": len(lease.bindings),
                    "lease_state": resulting_state.value,
                },
            )

    def revoke(self, lease_id: str, *, now_ms: int | None = None) -> PilotLeaseDecision:
        now = _now_ms() if now_ms is None else _timestamp(now_ms, field_name="now_ms")
        with self._lock:
            lease = self._leases.get(str(lease_id or "").strip())
            if lease is None:
                return _denied("missing_pilot_lease")
            state = self._effective_state(lease, now)
            if state is not PilotLeaseState.ACTIVE and state is not PilotLeaseState.CONSUMED:
                return _denied(f"pilot_lease_{state.value}", state=state)
            self._leases[lease.lease_id] = replace(lease, state=PilotLeaseState.REVOKED)
            return PilotLeaseDecision(True, "pilot_lease_revoked", PilotLeaseState.REVOKED, {"lease_state": "revoked"})

    def seal(self, lease_id: str, *, now_ms: int | None = None) -> PilotLeaseDecision:
        now = _now_ms() if now_ms is None else _timestamp(now_ms, field_name="now_ms")
        with self._lock:
            lease = self._leases.get(str(lease_id or "").strip())
            if lease is None:
                return _denied("missing_pilot_lease")
            state = self._effective_state(lease, now)
            if state not in {PilotLeaseState.ACTIVE, PilotLeaseState.CONSUMED}:
                return _denied(f"pilot_lease_{state.value}", state=state)
            self._leases[lease.lease_id] = replace(lease, state=PilotLeaseState.SEALED)
            return PilotLeaseDecision(True, "pilot_lease_sealed", PilotLeaseState.SEALED, {"lease_state": "sealed"})

    def state(self, lease_id: str, *, now_ms: int | None = None) -> PilotLeaseState | None:
        now = _now_ms() if now_ms is None else _timestamp(now_ms, field_name="now_ms")
        with self._lock:
            lease = self._leases.get(str(lease_id or "").strip())
            return self._effective_state(lease, now) if lease else None

    @staticmethod
    def _effective_state(lease: PilotScopeLease, now_ms: int) -> PilotLeaseState:
        if lease.state is not PilotLeaseState.ACTIVE:
            return lease.state
        if now_ms < lease.issued_at_ms:
            return PilotLeaseState.PENDING
        if now_ms >= lease.expires_at_ms:
            return PilotLeaseState.EXPIRED
        if len(lease.consumed_bindings) == len(lease.bindings):
            return PilotLeaseState.CONSUMED
        return PilotLeaseState.ACTIVE


def _binding_mismatch(
    lease: PilotScopeLease,
    *,
    actor_id: object,
    check: PilotLeaseCheck,
    binding: PilotLeaseBinding,
) -> str:
    if str(actor_id or "").strip() != lease.actor_id:
        return "pilot_lease_actor_mismatch"
    comparisons = (
        (check.package_id, lease.package_id, "package"),
        (check.package_fingerprint, lease.package_fingerprint, "package_fingerprint"),
        (check.pilot_run_id, lease.pilot_run_id, "run"),
        (check.runtime_nonce, lease.runtime_nonce, "runtime_nonce"),
        (check.operator_decision_fingerprint, lease.operator_decision_fingerprint, "operator_decision"),
    )
    for observed, expected, label in comparisons:
        if str(observed or "").strip() != expected:
            return f"pilot_lease_{label}_mismatch"
    if binding not in lease.bindings:
        same_scope = any(candidate.scope == binding.scope for candidate in lease.bindings)
        if not same_scope:
            return "pilot_lease_scope_mismatch"
        same_route = any(candidate.route == binding.route for candidate in lease.bindings)
        if not same_route:
            return "pilot_lease_route_mismatch"
        same_method = any(
            candidate.route == binding.route and candidate.method == binding.method for candidate in lease.bindings
        )
        if not same_method:
            return "pilot_lease_method_mismatch"
        return "pilot_lease_action_mismatch"
    return ""


def _denied(reason: str, *, state: PilotLeaseState | None = None) -> PilotLeaseDecision:
    evidence: dict[str, object] = {"lease_bound": state is not None}
    if state is not None:
        evidence["lease_state"] = state.value
    return PilotLeaseDecision(False, reason, state, evidence)


def _identifier(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not _ID_RE.fullmatch(text):
        raise ValueError(f"invalid_{field_name}")
    return text


def _fingerprint(value: object, *, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"invalid_{field_name}")
    return text


def _route(value: object) -> str:
    text = str(value or "").strip()
    if not _ROUTE_RE.fullmatch(text) or "//" in text or "/../" in f"{text}/":
        raise ValueError("invalid_route")
    return text


def _method(value: object) -> str:
    text = str(value or "").strip().upper()
    if text not in _METHODS:
        raise ValueError("invalid_method")
    return text


def _timestamp(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"invalid_{field_name}")
    return value


def _now_ms() -> int:
    return time.time_ns() // 1_000_000
