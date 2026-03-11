from __future__ import annotations

from typing import Any

from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.hud.app.views.approval_queue import get_approval_queue_view
from services.hud.app.views.current_work import get_current_work_view
from services.hud.app.views.execution_journal import get_execution_journal_view


def _normalize_usage_action_kind(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    suffix = ".request_approval"
    return raw[: -len(suffix)] if raw.endswith(suffix) else raw


def _severity_rank(severity: object) -> int:
    normalized = str(severity or "").strip().lower()
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized == "low":
        return 1
    return 0


def _max_severity(rows: list[dict[str, str]], fallback: str = "low") -> str:
    highest = fallback
    for row in rows:
        severity = str(row.get("severity", fallback)).strip().lower() or fallback
        if _severity_rank(severity) > _severity_rank(highest):
            highest = severity
    return highest


def _find_chip(actions: dict[str, object], kind: str) -> dict[str, Any] | None:
    chips = actions.get("action_chips", []) if isinstance(actions.get("action_chips"), list) else []
    lowered = str(kind or "").strip().lower()
    for chip in chips:
        if str(chip.get("kind", "")).strip().lower() == lowered:
            return chip
    return None


def _resolve_focus_chip(actions: dict[str, object], focus_kind: str) -> dict[str, Any] | None:
    direct = _find_chip(actions, focus_kind)
    if direct is not None:
        return direct
    if focus_kind == "repo.tests":
        return _find_chip(actions, "repo.tests.request_approval")
    return None


def _find_related_approval(queue: dict[str, object], focus_kind: str) -> dict[str, Any] | None:
    items = queue.get("items", []) if isinstance(queue.get("items"), list) else []
    normalized = _normalize_usage_action_kind(focus_kind)
    for row in items:
        if _normalize_usage_action_kind(row.get("requested_action_kind")) == normalized:
            return row
    return None


def _find_related_receipt(journal: dict[str, object], focus_kind: str) -> dict[str, Any] | None:
    items = journal.get("items", []) if isinstance(journal.get("items"), list) else []
    normalized = _normalize_usage_action_kind(focus_kind)
    for row in items:
        if _normalize_usage_action_kind(row.get("action_kind")) == normalized:
            return row
    return None


def _compact_chip(chip: dict[str, Any] | None) -> dict[str, Any] | None:
    if not chip:
        return None
    return {
        "kind": str(chip.get("kind", "")).strip(),
        "label": str(chip.get("label", "")).strip(),
        "enabled": bool(chip.get("enabled", False)),
        "risk_tier": str(chip.get("risk_tier", "low")).strip() or "low",
        "reason": str(chip.get("reason", "")).strip(),
        "policy_reason": str(chip.get("policy_reason", "")).strip(),
    }


def get_execution_feed_view(
    *,
    snapshot: dict[str, object] | None = None,
    actions: dict[str, object] | None = None,
    current_work: dict[str, object] | None = None,
    approval_queue: dict[str, object] | None = None,
    execution_journal: dict[str, object] | None = None,
    execution: dict[str, Any] | None = None,
) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    if actions is None:
        actions = get_lens_actions(max_actions=8)
    if current_work is None:
        current_work = get_current_work_view(snapshot=snapshot)
    if approval_queue is None:
        approval_queue = get_approval_queue_view(snapshot=snapshot, actions=actions)
    if execution_journal is None:
        execution_journal = get_execution_journal_view(snapshot=snapshot)

    next_action = current_work.get("next_action", {}) if isinstance(current_work.get("next_action"), dict) else {}
    operator_link = current_work.get("operator_link", {}) if isinstance(current_work.get("operator_link"), dict) else {}
    execution_action = execution.get("action", {}) if isinstance(execution, dict) and isinstance(execution.get("action"), dict) else {}
    focus_kind = _normalize_usage_action_kind(execution_action.get("kind") or next_action.get("kind"))
    focus_chip = _resolve_focus_chip(actions, focus_kind)
    related_approval = _find_related_approval(approval_queue, focus_kind)
    related_receipt = _find_related_receipt(execution_journal, focus_kind)
    next_evidence = (
        current_work.get("next_action_evidence", [])
        if isinstance(current_work.get("next_action_evidence"), list)
        else []
    )
    execution_result = execution.get("result", {}) if isinstance(execution, dict) and isinstance(execution.get("result"), dict) else {}
    execution_presentation = (
        execution_result.get("presentation", {})
        if isinstance(execution_result.get("presentation"), dict)
        else {}
    )

    evidence: list[dict[str, str]] = []
    for row in next_evidence:
        if not isinstance(row, dict):
            continue
        evidence.append(
            {
                "kind": str(row.get("kind", "signal")).strip() or "signal",
                "severity": str(row.get("severity", "low")).strip().lower() or "low",
                "detail": str(row.get("detail", "")).strip() or "No detail provided.",
            }
        )
    if related_approval:
        evidence.insert(
            0,
            {
                "kind": "approval",
                "severity": "high",
                "detail": str(related_approval.get("detail_summary") or related_approval.get("summary") or "Approval is pending.").strip(),
            },
        )
    if related_receipt:
        evidence.insert(
            0,
            {
                "kind": "receipt",
                "severity": "medium",
                "detail": str(related_receipt.get("detail_summary") or related_receipt.get("summary") or "Receipt is available.").strip(),
            },
        )
    if execution_presentation:
        for row in execution_presentation.get("evidence", [])[:3]:
            if not isinstance(row, dict):
                continue
            evidence.insert(
                0,
                {
                    "kind": str(row.get("kind", "execution")).strip() or "execution",
                    "severity": str(row.get("severity", "low")).strip().lower() or "low",
                    "detail": str(row.get("detail", "")).strip() or "No execution detail provided.",
                },
            )

    if related_approval:
        state = "approval_pending"
        summary = f"{current_work.get('terminal_summary', 'Terminal anchor unavailable.')} {related_approval.get('id', 'Approval')} is the current gate for {focus_kind or 'the current move'}."
    elif execution_presentation.get("summary"):
        state = "executed"
        summary = str(execution_presentation.get("summary", "")).strip()
    elif related_receipt:
        state = "receipt_grounded"
        summary = str(related_receipt.get("detail_summary") or related_receipt.get("summary") or "Receipt is grounding the current move.").strip()
    elif focus_chip:
        state = "ready"
        summary = str(operator_link.get("summary", "")).strip() or (
            f"{current_work.get('terminal_summary', 'Terminal anchor unavailable.')} "
            f"Execution feed is tracking {focus_kind or 'the current move'}."
        )
    else:
        state = str(operator_link.get("state", "")).strip() or "idle"
        summary = str(operator_link.get("summary", "")).strip() or str(
            current_work.get("terminal_summary", "Terminal anchor unavailable.")
        ).strip()

    severity = _max_severity(evidence, fallback=str(current_work.get("next_action_signal", {}).get("severity", "low")))
    active_run = execution_journal.get("active_run", {}) if isinstance(execution_journal.get("active_run"), dict) else {}

    return {
        "status": "ok",
        "surface": "execution_feed",
        "state": state,
        "focus_action_kind": focus_kind,
        "summary": summary,
        "severity": severity,
        "evidence": evidence[:6],
        "detail": {
            "next_action": next_action,
            "focus_chip": _compact_chip(focus_chip),
            "related_approval": related_approval,
            "related_receipt": related_receipt,
            "active_run": active_run,
            "operator_link": operator_link,
            "execution": execution if isinstance(execution, dict) else None,
        },
    }
