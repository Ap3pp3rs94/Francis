from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from francis.trust.calculator import evaluate, normalize_risk_tier

_RISK_ORDER: dict[str, int] = {
    "readonly": 0,
    "low": 1,
    "normal": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
    "safety_critical": 6,
}


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _normalize_texts(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set)):
        items = list(values)
    else:
        return ()
    normalized: list[str] = []
    for item in items:
        text = _safe_str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class AuthorityBoundary:
    allowed_paths: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    max_risk_tier: str = "normal"
    approvals_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_paths": list(self.allowed_paths),
            "allowed_actions": list(self.allowed_actions),
            "max_risk_tier": self.max_risk_tier,
            "approvals_required": self.approvals_required,
        }


def normalize_boundary(payload: dict[str, Any] | None) -> AuthorityBoundary:
    obj = payload or {}
    allowed_paths = _normalize_texts(obj.get("allowed_paths") or obj.get("paths"))
    allowed_actions = _normalize_texts(obj.get("allowed_actions") or obj.get("actions"))
    max_risk_tier = normalize_risk_tier(_safe_str(obj.get("max_risk_tier") or obj.get("risk_tier")) or "normal")
    approvals_required = bool(obj.get("approvals_required") or obj.get("require_approval"))
    return AuthorityBoundary(
        allowed_paths=allowed_paths,
        allowed_actions=allowed_actions,
        max_risk_tier=max_risk_tier,
        approvals_required=approvals_required,
    )


def path_within_boundary(path: str | Path, allowed_paths: tuple[str, ...]) -> bool:
    if not allowed_paths:
        return True
    target = Path(path).expanduser().resolve()
    for root in allowed_paths:
        try:
            allowed_root = Path(root).expanduser().resolve()
        except Exception:
            continue
        try:
            target.relative_to(allowed_root)
            return True
        except Exception:
            continue
    return False


def action_allowed(action: str, allowed_actions: tuple[str, ...]) -> bool:
    if not allowed_actions:
        return True
    raw = action.strip().lower()
    return raw in {item.lower() for item in allowed_actions}


def _risk_within_boundary(requested_risk: str, boundary_risk: str) -> bool:
    return _RISK_ORDER[normalize_risk_tier(requested_risk)] <= _RISK_ORDER[normalize_risk_tier(boundary_risk)]


def evaluate_request(
    action_request: dict[str, Any],
    authority_model: dict[str, Any] | None,
    *,
    trust_level: int,
) -> dict[str, Any]:
    boundary = normalize_boundary(authority_model)
    action = _safe_str(action_request.get("action") or action_request.get("capability")).strip()
    risk_tier = normalize_risk_tier(_safe_str(action_request.get("risk_tier")))
    scope = action_request.get("scope")
    scope_path = scope.get("path") if isinstance(scope, dict) else ""
    requested_path = _safe_str(action_request.get("path") or scope_path).strip()

    issues: list[str] = []
    if action and not action_allowed(action, boundary.allowed_actions):
        issues.append("action_outside_boundary")
    if requested_path and not path_within_boundary(requested_path, boundary.allowed_paths):
        issues.append("path_outside_boundary")

    decision = evaluate(
        trust_level,
        risk_tier,
        policy_requires_approval=boundary.approvals_required,
    )
    if not decision.allowed:
        issues.append("trust_threshold_not_met")
    if boundary.max_risk_tier and not _risk_within_boundary(risk_tier, boundary.max_risk_tier):
        issues.append("risk_tier_outside_boundary")

    return {
        "ok": not issues,
        "issues": issues,
        "action": action,
        "path": requested_path or None,
        "boundary": boundary.to_dict(),
        "decision": decision.to_dict(),
    }
