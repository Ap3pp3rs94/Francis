from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from francis.credentials.scope_checker import ScopeChecker
from francis.governance.redaction import redact_secret_text

logger = logging.getLogger(__name__)

__all__ = ["ApiPermissionDecision", "ApiPermissionGate"]


@dataclass(frozen=True)
class ApiPermissionDecision:
    allowed: bool
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redacted_text(value: object) -> str:
    return redact_secret_text(_safe_text(value).strip())


def _scope_list(value: Iterable[str] | None) -> tuple[list[str], bool]:
    if value is None or isinstance(value, (str, bytes)):
        return [], False
    try:
        raw_scopes = list(value)
    except TypeError:
        return [], False

    scopes: list[str] = []
    for raw_scope in raw_scopes:
        scope = _safe_text(raw_scope).strip()
        if scope:
            scopes.append(scope)
    return scopes, True


class ApiPermissionGate:
    def __init__(self, actor_scopes: Mapping[str, Iterable[str]] | None = None) -> None:
        self._actor_scopes: dict[str, tuple[str, ...]] = {}
        for raw_actor, raw_scopes in (actor_scopes or {}).items():
            actor_id = _safe_text(raw_actor).strip()
            scopes, valid = _scope_list(raw_scopes)
            if actor_id and valid:
                self._actor_scopes[actor_id] = tuple(scopes)

    @classmethod
    def from_env(cls, env_var: str = "FRANCIS_API_ACTOR_SCOPES") -> "ApiPermissionGate":
        raw = _safe_text(os.getenv(env_var)).strip()
        if not raw:
            return cls()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("invalid API actor-scope policy JSON")
            return cls()
        if not isinstance(parsed, dict):
            logger.warning("API actor-scope policy must be a JSON object")
            return cls()
        return cls(parsed)

    def check(
        self,
        *,
        actor_id: object,
        required_scopes: Iterable[str] | None,
        route: object = "",
        method: object = "",
        actor_scopes: Iterable[str] | None = None,
    ) -> ApiPermissionDecision:
        """Evaluate a privileged API action without leaking scope names."""
        actor = _safe_text(actor_id).strip()
        evidence: dict[str, Any] = {
            "actor_present": bool(actor),
            "route": _redacted_text(route),
            "method": _redacted_text(method).upper(),
        }

        required, valid_required = _scope_list(required_scopes)
        evidence["required_scope_count"] = len(required)
        if not valid_required:
            return ApiPermissionDecision(False, "invalid_required_scopes", evidence)
        if not required:
            return ApiPermissionDecision(False, "empty_required_scopes", evidence)
        if not actor:
            return ApiPermissionDecision(False, "missing_actor", evidence)

        if actor_scopes is None:
            resolved_scopes = list(self._actor_scopes.get(actor, ()))
            valid_actor_scopes = True
        else:
            resolved_scopes, valid_actor_scopes = _scope_list(actor_scopes)

        evidence["actor_scope_count"] = len(resolved_scopes)
        if not valid_actor_scopes:
            logger.warning("check expected iterable actor scopes")
            return ApiPermissionDecision(False, "invalid_actor_scopes", evidence)
        if not resolved_scopes:
            return ApiPermissionDecision(
                False,
                "missing_scopes",
                {**evidence, "scope_decision": {"missing_scope_count": len(required)}},
            )

        scope_decision = ScopeChecker(resolved_scopes).check(required)
        decision_evidence = {
            key: value
            for key, value in scope_decision.evidence.items()
            if key in {"requested_scope_count", "allowed_scope_count", "missing_scope_count"}
        }
        return ApiPermissionDecision(
            scope_decision.allowed,
            scope_decision.reason,
            {**evidence, "scope_decision": decision_evidence},
        )
