from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from francis_brain.apprenticeship import summarize_apprenticeship
from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries
from francis_forge.library import build_capability_provenance, build_promotion_rules, build_quality_standard
from francis_forge.promotion import promote_stage
from francis_policy.tool_policy import approval_policy_for_tool
from francis_policy.rbac import can
from francis_skills.contracts import SkillCall
from francis_skills.executor import SkillExecutor
from services.orchestrator.app.adversarial_guard import assess_untrusted_input, quarantine_untrusted_input
from services.observer.app.main import run_cycle as run_observer_cycle

from services.orchestrator.app.approvals_store import ensure_action_approved, list_requests, pending_count
from services.orchestrator.app.autonomy.action_budget import check_action_budget, load_state as load_budget_state
from services.orchestrator.app.autonomy.decision_engine import build_plan
from services.orchestrator.app.autonomy.event_queue import (
    append_reactor_guardrail_history,
    queue_status as autonomy_queue_status,
    recover_stale_leased_events,
    write_reactor_guardrail_state,
    read_last_dispatch as read_autonomy_last_dispatch,
    read_reactor_guardrail_state as read_autonomy_reactor_guardrail_state,
    read_last_tick as read_autonomy_last_tick,
)
from services.orchestrator.app.autonomy.event_reactor import collect_events
from services.orchestrator.app.autonomy.intent_engine import collect_intents
from services.orchestrator.app.autonomy.trust_calibration import trust_badge
from services.orchestrator.app.control_state import (
    VALID_MODES,
    check_action_allowed,
    load_or_init_control_state,
    set_mode,
)
from services.orchestrator.app.lens_snapshot import build_lens_snapshot
from services.orchestrator.app.routes.control import (
    ControlRemoteApprovalDecisionRequest,
    ControlRemotePanicRequest,
    ControlRemoteResumeRequest,
    ControlRemoteTakeoverConfirmRequest,
    ControlRemoteTakeoverHandbackRequest,
    ControlRemoteTakeoverRequest,
    ControlTakeoverConfirmRequest,
    ControlTakeoverHandbackExportRequest,
    ControlTakeoverHandbackRequest,
    ControlTakeoverRequest,
    append_takeover_activity,
    control_remote_approval_approve,
    control_remote_approval_reject,
    control_remote_approvals,
    control_remote_feed,
    control_remote_panic,
    control_remote_resume,
    control_remote_state,
    control_remote_takeover_confirm,
    control_remote_takeover_handback,
    control_remote_takeover_request,
    control_takeover_activity,
    control_takeover_confirm,
    control_takeover_handback_export,
    control_takeover_handback,
    control_takeover_handback_package,
    control_takeover_session,
    control_takeover_sessions,
    control_takeover_request,
    control_takeover_state,
)
from services.orchestrator.app.routes.autonomy import (
    AutonomyDispatchRequest,
    AutonomyReactorTickRequest,
    autonomy_dispatch_events,
    autonomy_reactor_tick,
)
from services.orchestrator.app.routes.apprenticeship import (
    ApprenticeshipSessionCreateRequest,
    ApprenticeshipSkillizeRequest,
    ApprenticeshipStepRequest,
    apprenticeship_add_step,
    apprenticeship_create_session,
    apprenticeship_generalize,
    apprenticeship_skillize,
)
from services.orchestrator.app.routes.approvals import ApprovalRequestPayload, approval_request
from services.orchestrator.app.routes.forge import forge_proposals
from services.orchestrator.app.routes.missions import execute_mission_tick
from services.orchestrator.app.telemetry_store import status as telemetry_status
from services.worker.app.main import recover_stale_leased_jobs, run_worker_cycle

router = APIRouter(tags=["lens"])

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")
_skill_executor = SkillExecutor.with_defaults(fs=_fs, repo_root=_repo_root)
_repo_drilldown_state_path = "lens/repo_drilldown.json"


class LensExecuteRequest(BaseModel):
    kind: str
    args: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


def _read_jsonl(rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except Exception:
            continue
    return rows


def _mode_allows_medium_high(mode: str) -> tuple[bool, bool]:
    lowered = mode.lower()
    if lowered == "pilot":
        return (True, False)
    if lowered == "away":
        return (True, False)
    return (False, False)


def _append_jsonl(rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    _fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_trace_id(trace_id: str | None, *, fallback_run_id: str) -> str:
    normalized = str(trace_id or "").strip()
    return normalized or fallback_run_id


def _role_from_request(request: Request) -> str:
    return request.headers.get("x-francis-role", "architect").strip().lower()


def _enforce_action_scope(*, app: str, action: str, mutating: bool = True) -> None:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app=app,
        action=action,
        mutating=mutating,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")


def _enforce_rbac(role: str, action: str) -> None:
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"RBAC denied: role={role}, action={action}")


def _record_lens_execution(
    *,
    run_id: str,
    trace_id: str,
    role: str,
    action_kind: str,
    dry_run: bool,
    ok: bool,
    detail: dict[str, Any],
) -> None:
    presentation = detail.get("presentation", {}) if isinstance(detail.get("presentation"), dict) else {}
    tool = detail.get("tool", {}) if isinstance(detail.get("tool"), dict) else {}
    execution_args = detail.get("execution_args", {}) if isinstance(detail.get("execution_args"), dict) else {}
    summary_text = str(presentation.get("summary", "")).strip() or str(detail.get("summary", "")).strip()
    if not summary_text:
        error = detail.get("error")
        if isinstance(error, dict):
            summary_text = str(error.get("message", "")).strip() or str(error.get("policy_reason", "")).strip()
        elif error is not None:
            summary_text = str(error).strip()
    if not summary_text and str(detail.get("status", "")).strip().lower() == "quarantined":
        summary_text = "Suspicious input was quarantined before Lens execution."
    if not summary_text:
        summary_text = f"{action_kind} {'completed' if ok else 'failed'}."

    presentation_cards: list[dict[str, str]] = []
    for row in presentation.get("cards", []) if isinstance(presentation.get("cards"), list) else []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip()
        value = str(row.get("value", "")).strip()
        tone = str(row.get("tone", "low")).strip().lower() or "low"
        if label and value:
            presentation_cards.append({"label": label, "value": value, "tone": tone})

    ledger_summary = {
        "trace_id": trace_id,
        "action_kind": action_kind,
        "dry_run": dry_run,
        "ok": ok,
        "result_status": detail.get("status"),
        "summary_text": summary_text,
    }
    if str(presentation.get("severity", "")).strip():
        ledger_summary["signal"] = str(presentation.get("severity", "")).strip().lower()
    if presentation_cards:
        ledger_summary["presentation_cards"] = presentation_cards[:4]
    if str(tool.get("skill", "")).strip():
        ledger_summary["skill"] = str(tool.get("skill", "")).strip()
    approval_id = (
        str(tool.get("approval_id", "")).strip()
        or str(execution_args.get("approval_id", "")).strip()
        or str(detail.get("approval_id", "")).strip()
    )
    if approval_id:
        ledger_summary["approval_id"] = approval_id
    if execution_args:
        ledger_summary["execution_args"] = execution_args

    takeover_activity = append_takeover_activity(
        run_id=run_id,
        trace_id=trace_id,
        actor=f"lens:{str(role).strip().lower() or 'architect'}",
        kind="lens.action.execute",
        detail={
            "action_kind": action_kind,
            "dry_run": dry_run,
            "ok": ok,
            "result_status": detail.get("status"),
        },
        ok=ok,
    )
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "session_id": takeover_activity.get("session_id") if isinstance(takeover_activity, dict) else None,
        "kind": "lens.action.execute",
        "action_kind": action_kind,
        "dry_run": dry_run,
        "ok": ok,
        "detail": detail,
    }
    _append_jsonl("logs/francis.log.jsonl", receipt)
    _append_jsonl("journals/decisions.jsonl", receipt)
    _ledger.append(
        run_id=run_id,
        kind="lens.action.execute",
        summary=ledger_summary,
    )


def _execute_repo_skill(
    *,
    role: str,
    skill_name: str,
    args: dict[str, Any],
    allow_approval_required: bool = False,
) -> dict[str, Any]:
    _enforce_rbac(role, "tools.run")
    _enforce_action_scope(app="tools", action=f"tools.run.{skill_name}", mutating=False)
    call = SkillCall(name=skill_name, args=args)
    result = _skill_executor.execute(call).to_dict()
    if not bool(result.get("ok", False)):
        raise HTTPException(status_code=500, detail=f"{skill_name} failed: {result.get('error', 'unknown error')}")
    return result


def _write_repo_drilldown_state(
    *,
    run_id: str,
    trace_id: str,
    kind: str,
    tool: dict[str, Any],
    execution_args: dict[str, Any],
    summary: str,
    presentation: dict[str, Any],
) -> None:
    payload = {
        "status": "ok",
        "surface": "repo_drilldown",
        "state": "ready",
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "tool": tool,
        "execution_args": execution_args,
        "summary": summary,
        "presentation": presentation,
    }
    _fs.write_text(_repo_drilldown_state_path, json.dumps(payload, ensure_ascii=False, indent=2))


def _compact_text_summary(value: object, max_length: int = 220) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _first_meaningful_line(*values: object) -> str:
    for value in values:
        for raw_line in str(value or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered in {"traceback", "stack trace"}:
                continue
            if lowered.startswith("line "):
                continue
            if lowered.startswith("collected ") and lowered.endswith(" items"):
                continue
            return line
    return ""


def _meaningful_lines(*values: object, max_lines: int = 6) -> list[str]:
    rows: list[str] = []
    for value in values:
        for raw_line in str(value or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            rows.append(line)
            if len(rows) >= max_lines:
                return rows
    return rows


def _build_repo_presentation(
    *,
    kind: str,
    execution_args: dict[str, Any],
    result: dict[str, Any],
    summary: str,
) -> dict[str, Any]:
    output = result.get("output", {}) if isinstance(result.get("output"), dict) else {}
    stdout = str(output.get("stdout", "")).strip()
    stderr = str(output.get("stderr", "")).strip()
    meaningful = _meaningful_lines(stdout, stderr, max_lines=6)
    presentation_summary = _compact_text_summary(summary, 260) or f"{kind} completed."
    severity = "medium"
    evidence: list[dict[str, str]] = []
    stats: dict[str, Any] = {}
    cards: list[dict[str, str]] = []

    if kind == "repo.status":
        combined = f"{stdout}\n{stderr}".lower()
        clean = "nothing to commit" in combined or "working tree clean" in combined
        severity = "low" if clean else "medium"
        evidence_rows = meaningful or ["Repository status returned no significant lines."]
        evidence = [
            {"kind": "status", "severity": severity, "detail": row}
            for row in evidence_rows[:4]
        ]
        stats = {
            "dirty": not clean,
            "line_count": len(meaningful),
        }
        cards = [
            {"label": "State", "value": "dirty" if not clean else "clean", "tone": severity},
            {"label": "Visible Lines", "value": str(len(meaningful)), "tone": "low"},
        ]
        if not presentation_summary or presentation_summary == "Repository status returned no output.":
            presentation_summary = evidence_rows[0]

    elif kind == "repo.diff":
        file_count = len(re.findall(r"^diff --git ", stdout, flags=re.MULTILINE))
        hunk_count = len(re.findall(r"^@@", stdout, flags=re.MULTILINE))
        added = len(re.findall(r"^\+(?!\+\+)", stdout, flags=re.MULTILINE))
        removed = len(re.findall(r"^-(?!--)", stdout, flags=re.MULTILINE))
        severity = "medium" if any((file_count, hunk_count, added, removed)) else "low"
        evidence = [
            {
                "kind": "diff",
                "severity": severity,
                "detail": f"{file_count} file diff(s) surfaced. {hunk_count} hunk(s), {added} addition(s), {removed} removal(s).",
            }
        ]
        evidence.extend(
            {"kind": "diff", "severity": severity, "detail": row}
            for row in meaningful[:3]
        )
        stats = {
            "file_count": file_count,
            "hunk_count": hunk_count,
            "added": added,
            "removed": removed,
        }
        cards = [
            {"label": "Files", "value": str(file_count), "tone": severity},
            {"label": "Hunks", "value": str(hunk_count), "tone": "medium"},
            {"label": "Additions", "value": str(added), "tone": "low"},
            {"label": "Removals", "value": str(removed), "tone": "medium"},
        ]
        if not presentation_summary or presentation_summary == "No tracked diff output was returned.":
            presentation_summary = evidence[0]["detail"]

    elif kind == "repo.lint":
        issue_count = len(re.findall(r"^[^:\r\n]+:\d+:\d+:", stdout, flags=re.MULTILINE))
        combined = f"{stdout}\n{stderr}".lower()
        passed = "all checks passed" in combined or "0 errors" in combined
        severity = "low" if passed and issue_count == 0 else "high" if issue_count or "failed" in combined or "error" in combined else "medium"
        if issue_count:
            evidence.append(
                {
                    "kind": "lint",
                    "severity": severity,
                    "detail": f"{issue_count} lint issue(s) detected.",
                }
            )
            evidence.extend(
                {"kind": "lint", "severity": severity, "detail": row}
                for row in meaningful[:3]
            )
        else:
            pass_line = _first_meaningful_line(stdout, stderr) or "Ruff completed without visible issues."
            evidence.append({"kind": "lint", "severity": severity, "detail": pass_line})
        stats = {"issue_count": issue_count}
        cards = [
            {"label": "Issues", "value": str(issue_count), "tone": severity},
            {"label": "Target", "value": str(execution_args.get("target", ".")).strip() or ".", "tone": "low"},
        ]
        if not presentation_summary or presentation_summary == "Ruff completed without stdout.":
            presentation_summary = evidence[0]["detail"]

    elif kind == "repo.tests":
        combined = f"{stdout}\n{stderr}"
        lane = str(execution_args.get("lane", "fast")).strip().lower() or "fast"
        passed_match = re.search(r"(\d+)\s+passed", combined, flags=re.IGNORECASE)
        failed_match = re.search(r"(\d+)\s+failed", combined, flags=re.IGNORECASE)
        skipped_match = re.search(r"(\d+)\s+(?:skipped|deselected)", combined, flags=re.IGNORECASE)
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        lowered = combined.lower()
        severity = "high" if failed > 0 or "error" in lowered else "low" if passed > 0 and failed == 0 else "medium"
        evidence.append(
            {
                "kind": "tests",
                "severity": severity,
                "detail": f"Lane {lane} executed.",
            }
        )
        if passed or failed or skipped:
            evidence.append(
                {
                    "kind": "tests",
                    "severity": severity,
                    "detail": f"{passed} passed | {failed} failed" + (f" | {skipped} skipped/deselected" if skipped else ""),
                }
            )
        evidence.extend(
            {"kind": "tests", "severity": severity, "detail": row}
            for row in meaningful[:3]
        )
        stats = {
            "lane": lane,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }
        cards = [
            {"label": "Lane", "value": lane, "tone": "low"},
            {"label": "Passed", "value": str(passed), "tone": "low"},
            {"label": "Failed", "value": str(failed), "tone": "high" if failed else "low"},
            {"label": "Skipped", "value": str(skipped), "tone": "medium" if skipped else "low"},
        ]
        if not presentation_summary or presentation_summary == "repo.tests completed without stdout.":
            presentation_summary = evidence[1]["detail"] if len(evidence) > 1 else evidence[0]["detail"]

    else:
        evidence = [
            {"kind": "context", "severity": severity, "detail": _first_meaningful_line(stdout, stderr, summary) or f"{kind} completed."}
        ]

    return {
        "kind": kind,
        "summary": presentation_summary,
        "severity": severity,
        "cards": cards,
        "evidence": evidence[:4],
        "detail": {
            "kind": kind,
            "execution_args": execution_args,
            "stats": stats,
            "raw_excerpt": {
                "stdout": _compact_text_summary(stdout, 1200),
                "stderr": _compact_text_summary(stderr, 800),
            },
        },
    }


def _find_forge_promote_approval(stage_id: str) -> dict[str, Any] | None:
    requests = list_requests(_fs, action="forge.promote", limit=100)
    for row in reversed(requests):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("stage_id", "")).strip() != stage_id:
            continue
        return row
    return None


def _build_capability_presentation(
    *,
    entry: dict[str, Any],
    approval_id: str = "",
) -> dict[str, Any]:
    status = str(entry.get("status", "")).strip().lower() or "staged"
    name = str(entry.get("name", "Capability pack")).strip() or "Capability pack"
    version = str(entry.get("version", "")).strip() or "0.1.0"
    risk_tier = str(entry.get("risk_tier", "low")).strip().lower() or "low"
    validation = entry.get("validation", {}) if isinstance(entry.get("validation"), dict) else {}
    diff_summary = entry.get("diff_summary", {}) if isinstance(entry.get("diff_summary"), dict) else {}
    tool_pack = entry.get("tool_pack", {}) if isinstance(entry.get("tool_pack"), dict) else {}
    quality_standard = build_quality_standard(entry)
    promotion_rules = build_promotion_rules(entry, approval_status="approved" if approval_id else "")
    provenance = build_capability_provenance(entry, approval_status="approved" if approval_id else "")
    summary = (
        f"{name} {version} is active in the governed capability library."
        if status == "active"
        else f"{name} {version} remains staged and is not yet active."
    )
    cards = [
        {"label": "Status", "value": status, "tone": "low" if status == "active" else "medium"},
        {"label": "Version", "value": version, "tone": "low"},
        {"label": "Risk", "value": risk_tier, "tone": "medium" if risk_tier in {"medium", "high", "critical"} else "low"},
        {
            "label": "Validation",
            "value": "passed" if bool(validation.get("ok")) else "needs review",
            "tone": "low" if bool(validation.get("ok")) else "high",
        },
        {
            "label": "Quality",
            "value": str(quality_standard.get("score", "")).strip() or "0/0",
            "tone": "low" if bool(quality_standard.get("ok")) else "high",
        },
        {
            "label": "Files",
            "value": str(int(diff_summary.get("file_count", 0) or 0)),
            "tone": "low" if int(diff_summary.get("file_count", 0) or 0) > 0 else "medium",
        },
        {
            "label": "Provenance",
            "value": str(provenance.get("label", "Internal")).strip() or "Internal",
            "tone": str(provenance.get("tone", "low")).strip() or "low",
        },
        {
            "label": "Review",
            "value": str(provenance.get("review_label", "self-governed")).strip() or "self-governed",
            "tone": (
                "low"
                if str(provenance.get("review_state", "")).strip() in {"approved", "internal"}
                else "high"
                if str(provenance.get("review_state", "")).strip() in {"quarantined", "revoked", "rejected"}
                else "medium"
            ),
        },
    ]
    if str(tool_pack.get("skill_name", "")).strip():
        cards.append(
            {
                "label": "Tool Pack",
                "value": str(tool_pack.get("skill_name", "")).strip(),
                "tone": "low",
            }
        )
    if approval_id:
        cards.append({"label": "Approval", "value": approval_id, "tone": "low"})
    evidence = [
        {
            "kind": "capability",
            "severity": "low" if status == "active" else "medium",
            "detail": summary,
        },
        {
            "kind": "validation",
            "severity": "low" if bool(validation.get("ok")) else "high",
            "detail": (
                "Validation passed for the staged capability."
                if bool(validation.get("ok"))
                else "Validation still needs review before the capability should be trusted."
            ),
        },
    ]
    if int(diff_summary.get("file_count", 0) or 0) > 0:
        evidence.append(
            {
                "kind": "diff",
                "severity": "low",
                "detail": f"{int(diff_summary.get('file_count', 0) or 0)} file(s) are attached to the capability pack.",
            }
        )
    if str(tool_pack.get("skill_name", "")).strip():
        evidence.append(
            {
                "kind": "tool_pack",
                "severity": "low",
                "detail": f"Registered tool-pack skill {str(tool_pack.get('skill_name', '')).strip()}.",
            }
        )
    evidence.append(
        {
            "kind": "provenance",
            "severity": str(provenance.get("tone", "low")).strip() or "low",
            "detail": str(provenance.get("summary", "")).strip()
            or "Capability provenance is not available.",
        }
    )
    return {
        "kind": "forge.promote",
        "summary": summary,
        "severity": (
            "high"
            if str(provenance.get("tone", "")).strip() == "high"
            else "low"
            if status == "active"
            else "medium"
        ),
        "cards": cards[:8],
        "evidence": evidence[:5],
        "detail": {
            "entry": entry,
            "approval_id": approval_id,
            "status": status,
            "quality_standard": quality_standard,
            "promotion_rules": promotion_rules,
            "provenance": provenance,
        },
    }


def _usage_action_chip(
    *,
    kind: str,
    label: str,
    enabled: bool,
    reason: str,
    risk_tier: str = "low",
    trust_badge: str = "Likely",
    args: dict[str, Any] | None = None,
    policy_reason: str = "",
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    chip = {
        "kind": kind,
        "label": label,
        "enabled": bool(enabled),
        "reason": reason,
        "policy_reason": policy_reason,
        "risk_tier": risk_tier,
        "trust_badge": trust_badge,
        "requires_confirmation": requires_confirmation,
    }
    hinted = _with_execute_hint(chip)
    if args:
        hinted.setdefault("execute_via", {}).setdefault("payload", {}).setdefault("args", {}).update(args)
    return hinted


def _check_usage_scope(app: str, action: str, *, mutating: bool = False) -> tuple[bool, str]:
    allowed, reason, _state = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app=app,
        action=action,
        mutating=mutating,
    )
    return (allowed, reason)


def _usage_tool_approval_signature(*, skill_name: str, args: dict[str, Any]) -> str:
    normalized = json.dumps(
        {"skill": str(skill_name).strip().lower(), "args": args},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _usage_tool_approval_metadata(*, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface": "lens.usage",
        "skill": str(skill_name).strip().lower(),
        "args": args,
        "signature": _usage_tool_approval_signature(skill_name=skill_name, args=args),
    }


def _find_usage_tool_approval(*, skill_name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    signature = _usage_tool_approval_signature(skill_name=skill_name, args=args)
    requests = list_requests(_fs, action=f"tools.{skill_name}", limit=50)
    for row in reversed(requests):
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("signature", "")).strip() != signature:
            continue
        return row
    return None


def _request_usage_tool_approval(
    *,
    request: Request,
    skill_name: str,
    args: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    payload = ApprovalRequestPayload(
        action=f"tools.{skill_name}",
        reason=reason,
        metadata=_usage_tool_approval_metadata(skill_name=skill_name, args=args),
    )
    return approval_request(request, payload)


def _execute_lens_action(
    *,
    request: Request,
    kind: str,
    args: dict[str, Any],
    dry_run: bool,
    run_id: str,
    trace_id: str,
    role: str,
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip().lower()

    if normalized_kind == "control.panic":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
        reason = str(args.get("reason", "")).strip() or "lens.action.panic"
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
                "after": {"mode": before.get("mode"), "kill_switch": True},
                "reason": reason,
            }
        after = set_mode(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            mode=str(before.get("mode", "pilot")).strip().lower(),
            kill_switch=True,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
            "after": {"mode": after.get("mode"), "kill_switch": after.get("kill_switch")},
            "reason": reason,
        }

    if normalized_kind == "control.resume":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        before = load_or_init_control_state(_fs, _repo_root, _workspace_root)
        requested_mode = str(args.get("mode", before.get("mode", "pilot"))).strip().lower()
        if requested_mode not in VALID_MODES:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {requested_mode}")
        reason = str(args.get("reason", "")).strip() or "lens.action.resume"
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
                "after": {"mode": requested_mode, "kill_switch": False},
                "reason": reason,
            }
        after = set_mode(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            mode=requested_mode,
            kill_switch=False,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "before": {"mode": before.get("mode"), "kill_switch": before.get("kill_switch")},
            "after": {"mode": after.get("mode"), "kill_switch": after.get("kill_switch")},
            "reason": reason,
        }

    if normalized_kind == "control.takeover.request":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        objective = str(args.get("objective", "")).strip()
        if not objective:
            raise HTTPException(status_code=400, detail="objective is required for control.takeover.request")
        reason = str(args.get("reason", "")).strip()
        repos = [str(item) for item in args.get("repos", []) if isinstance(item, str) and str(item).strip()]
        workspaces = [
            str(item) for item in args.get("workspaces", []) if isinstance(item, str) and str(item).strip()
        ]
        apps = [str(item) for item in args.get("apps", []) if isinstance(item, str) and str(item).strip()]
        payload = {
            "objective": objective,
            "reason": reason,
            "repos": repos if repos else None,
            "workspaces": workspaces if workspaces else None,
            "apps": apps if apps else None,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": payload}
        summary = control_takeover_request(
            request,
            payload=ControlTakeoverRequest(
                objective=objective,
                reason=reason,
                repos=repos if repos else None,
                workspaces=workspaces if workspaces else None,
                apps=apps if apps else None,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "control.takeover.confirm":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        confirm = bool(args.get("confirm", True))
        reason = str(args.get("reason", "")).strip()
        mode = str(args.get("mode", "pilot")).strip().lower() or "pilot"
        execution_args = {
            "confirm": confirm,
            "reason": reason,
            "mode": mode,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_confirm(
            request,
            payload=ControlTakeoverConfirmRequest(
                confirm=confirm,
                reason=reason,
                mode=mode,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "control.takeover.handback":
        _enforce_action_scope(app="control", action="control.mode", mutating=False)
        summary_text = str(args.get("summary", "")).strip()
        verification = args.get("verification", {})
        pending_approvals = max(0, int(args.get("pending_approvals", 0)))
        mode = args.get("mode", "assist")
        reason = str(args.get("reason", "")).strip()
        execution_args = {
            "summary": summary_text,
            "verification": verification if isinstance(verification, dict) else {},
            "pending_approvals": pending_approvals,
            "mode": mode,
            "reason": reason,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_handback(
            request,
            payload=ControlTakeoverHandbackRequest(
                summary=summary_text,
                verification=verification if isinstance(verification, dict) else {},
                pending_approvals=pending_approvals,
                mode=str(mode).strip().lower() if isinstance(mode, str) and str(mode).strip() else None,
                reason=reason,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "control.takeover.activity":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(500, int(args.get("limit", 100))))
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"limit": limit, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_activity(limit=limit, session_id=session_id)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.handback.package":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(500, int(args.get("limit", 200))))
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"limit": limit, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_handback_package(limit=limit, session_id=session_id)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.handback.export":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(5000, int(args.get("limit", 300))))
        session_id = str(args.get("session_id", "")).strip() or None
        reason = str(args.get("reason", "")).strip()
        execution_args = {"limit": limit, "session_id": session_id, "reason": reason}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_handback_export(
            request,
            payload=ControlTakeoverHandbackExportRequest(
                session_id=session_id,
                limit=limit,
                reason=reason,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.sessions":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        limit = max(1, min(200, int(args.get("limit", 20))))
        execution_args = {"limit": limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_sessions(limit=limit)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.takeover.session":
        _enforce_action_scope(app="control", action="control.takeover.read", mutating=False)
        session_id = str(args.get("session_id", "")).strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for control.takeover.session")
        limit = max(1, min(500, int(args.get("limit", 200))))
        execution_args = {"session_id": session_id, "limit": limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_takeover_session(session_id=session_id, limit=limit)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.state":
        _enforce_action_scope(app="control", action="control.remote.read", mutating=False)
        _enforce_rbac(role, "control.remote.read")
        _enforce_rbac(role, "approvals.read")
        approval_limit = max(1, min(100, int(args.get("approval_limit", 10))))
        session_limit = max(1, min(50, int(args.get("session_limit", 5))))
        execution_args = {"approval_limit": approval_limit, "session_limit": session_limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_state(request, approval_limit=approval_limit, session_limit=session_limit)
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.approvals":
        _enforce_action_scope(app="control", action="control.remote.read", mutating=False)
        _enforce_rbac(role, "control.remote.read")
        _enforce_rbac(role, "approvals.read")
        status = str(args.get("status", "pending")).strip().lower() or "pending"
        action_filter = str(args.get("action", "")).strip() or None
        limit = max(1, min(200, int(args.get("limit", 50))))
        execution_args = {"status": status, "action": action_filter, "limit": limit}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_approvals(
            request,
            status=status,
            action=action_filter,
            limit=limit,
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.feed":
        _enforce_action_scope(app="control", action="control.remote.read", mutating=False)
        _enforce_rbac(role, "control.remote.read")
        _enforce_rbac(role, "approvals.read")
        limit = max(1, min(1000, int(args.get("limit", 100))))
        cursor = str(args.get("cursor", "")).strip() or None
        session_id = str(args.get("session_id", "")).strip() or None
        source = str(args.get("source", "")).strip().lower() or None
        kind = str(args.get("kind", "")).strip() or None
        kind_prefix = str(args.get("kind_prefix", "")).strip() or None
        risk_tier = str(args.get("risk_tier", "")).strip().lower() or None
        execution_args = {
            "limit": limit,
            "cursor": cursor,
            "session_id": session_id,
            "source": source,
            "kind": kind,
            "kind_prefix": kind_prefix,
            "risk_tier": risk_tier,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_feed(
            request,
            limit=limit,
            cursor=cursor,
            session_id=session_id,
            source=source,
            kind=kind,
            kind_prefix=kind_prefix,
            risk_tier=risk_tier,
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.panic":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        reason = str(args.get("reason", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"reason": reason, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_panic(
            request,
            payload=ControlRemotePanicRequest(reason=reason, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.resume":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        reason = str(args.get("reason", "")).strip()
        mode = str(args.get("mode", "pilot")).strip().lower()
        if mode not in VALID_MODES:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"reason": reason, "mode": mode, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_resume(
            request,
            payload=ControlRemoteResumeRequest(reason=reason, mode=mode, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.takeover.request":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        objective = str(args.get("objective", "")).strip()
        if not objective:
            raise HTTPException(status_code=400, detail="objective is required for control.remote.takeover.request")
        reason = str(args.get("reason", "")).strip()
        repos = [str(item) for item in args.get("repos", []) if isinstance(item, str) and str(item).strip()]
        workspaces = [
            str(item) for item in args.get("workspaces", []) if isinstance(item, str) and str(item).strip()
        ]
        apps = [str(item) for item in args.get("apps", []) if isinstance(item, str) and str(item).strip()]
        execution_args = {
            "objective": objective,
            "reason": reason,
            "repos": repos if repos else None,
            "workspaces": workspaces if workspaces else None,
            "apps": apps if apps else None,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_takeover_request(
            request,
            payload=ControlRemoteTakeoverRequest(
                objective=objective,
                reason=reason,
                repos=repos if repos else None,
                workspaces=workspaces if workspaces else None,
                apps=apps if apps else None,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.takeover.confirm":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        confirm = bool(args.get("confirm", True))
        reason = str(args.get("reason", "")).strip()
        mode = str(args.get("mode", "pilot")).strip().lower() or "pilot"
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {
            "confirm": confirm,
            "reason": reason,
            "mode": mode,
            "session_id": session_id,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_takeover_confirm(
            request,
            payload=ControlRemoteTakeoverConfirmRequest(
                confirm=confirm,
                reason=reason,
                mode=mode,
                session_id=session_id,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.takeover.handback":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        summary_text = str(args.get("summary", "")).strip()
        verification = args.get("verification", {})
        pending_approvals = max(0, int(args.get("pending_approvals", 0)))
        mode = args.get("mode", "assist")
        reason = str(args.get("reason", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {
            "summary": summary_text,
            "verification": verification if isinstance(verification, dict) else {},
            "pending_approvals": pending_approvals,
            "mode": mode,
            "reason": reason,
            "session_id": session_id,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_takeover_handback(
            request,
            payload=ControlRemoteTakeoverHandbackRequest(
                summary=summary_text,
                verification=verification if isinstance(verification, dict) else {},
                pending_approvals=pending_approvals,
                mode=str(mode).strip().lower() if isinstance(mode, str) and str(mode).strip() else None,
                reason=reason,
                session_id=session_id,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.approval.approve":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        _enforce_rbac(role, "approvals.decide")
        approval_id = str(args.get("approval_id", "")).strip()
        if not approval_id:
            raise HTTPException(status_code=400, detail="approval_id is required for control.remote.approval.approve")
        note = str(args.get("note", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"approval_id": approval_id, "note": note, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_approval_approve(
            approval_id=approval_id,
            request=request,
            payload=ControlRemoteApprovalDecisionRequest(note=note, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "control.remote.approval.reject":
        _enforce_action_scope(app="control", action="control.remote.write", mutating=False)
        _enforce_rbac(role, "control.remote.write")
        _enforce_rbac(role, "approvals.decide")
        approval_id = str(args.get("approval_id", "")).strip()
        if not approval_id:
            raise HTTPException(status_code=400, detail="approval_id is required for control.remote.approval.reject")
        note = str(args.get("note", "")).strip()
        session_id = str(args.get("session_id", "")).strip() or None
        execution_args = {"approval_id": approval_id, "note": note, "session_id": session_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = control_remote_approval_reject(
            approval_id=approval_id,
            request=request,
            payload=ControlRemoteApprovalDecisionRequest(note=note, session_id=session_id),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "worker.cycle":
        _enforce_rbac(role, "worker.cycle")
        _enforce_action_scope(app="worker", action="worker.cycle")
        max_jobs = max(1, min(500, int(args.get("max_jobs", 20))))
        max_runtime_seconds = max(1, min(600, int(args.get("max_runtime_seconds", 60))))
        allowlist = {
            str(item).strip().lower()
            for item in args.get("action_allowlist", [])
            if isinstance(item, str) and str(item).strip()
        }
        execution_args = {
            "max_jobs": max_jobs,
            "max_runtime_seconds": max_runtime_seconds,
            "action_allowlist": sorted(allowlist) if allowlist else None,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = run_worker_cycle(
            run_id=f"{run_id}:lens-worker:{uuid4()}",
            trace_id=trace_id,
            max_jobs=max_jobs,
            max_runtime_seconds=max_runtime_seconds,
            action_allowlist=allowlist if allowlist else None,
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "worker.recover_leases":
        _enforce_rbac(role, "worker.cycle")
        _enforce_action_scope(app="worker", action="worker.recover")
        action_classes = {
            str(item).strip().lower()
            for item in args.get("action_classes", [])
            if isinstance(item, str) and str(item).strip()
        }
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {"action_classes": sorted(action_classes) if action_classes else None},
            }
        summary = recover_stale_leased_jobs(
            run_id=f"{run_id}:lens-worker-recover:{uuid4()}",
            trace_id=trace_id,
            action_classes=action_classes if action_classes else None,
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "autonomy.recover":
        _enforce_rbac(role, "autonomy.recover")
        _enforce_action_scope(app="autonomy", action="autonomy.recover")
        lease_ttl_seconds = max(15, min(3600, int(args.get("lease_ttl_seconds", 300))))
        max_recover = max(1, min(1000, int(args.get("max_recover", 100))))
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {
                    "lease_ttl_seconds": lease_ttl_seconds,
                    "max_recover": max_recover,
                },
            }
        recovery = recover_stale_leased_events(
            _fs,
            run_id=f"{run_id}:lens-autonomy-recover:{uuid4()}",
            lease_ttl_seconds=lease_ttl_seconds,
            max_recover=max_recover,
        )
        return {"status": "ok", "kind": normalized_kind, "recovery": recovery}

    if normalized_kind == "autonomy.dispatch":
        _enforce_rbac(role, "autonomy.dispatch")
        _enforce_action_scope(app="autonomy", action="autonomy.dispatch")
        max_events = max(1, min(100, int(args.get("max_events", 5))))
        max_actions = max(0, min(10, int(args.get("max_actions", 2))))
        max_runtime_seconds = max(1, min(120, int(args.get("max_runtime_seconds", 10))))
        max_dispatch_actions = max(0, min(200, int(args.get("max_dispatch_actions", 10))))
        max_dispatch_runtime_seconds = max(1, min(600, int(args.get("max_dispatch_runtime_seconds", 30))))
        max_attempts = max(1, min(20, int(args.get("max_attempts", 3))))
        retry_backoff_seconds = max(0, min(3600, int(args.get("retry_backoff_seconds", 60))))
        lease_ttl_seconds = max(15, min(3600, int(args.get("lease_ttl_seconds", 300))))
        recover_stale_leases = bool(args.get("recover_stale_leases", True))
        allow_medium = bool(args.get("allow_medium", False))
        allow_high = bool(args.get("allow_high", False))
        stop_on_critical = bool(args.get("stop_on_critical", True))
        execution_args = {
            "max_events": max_events,
            "max_actions": max_actions,
            "max_runtime_seconds": max_runtime_seconds,
            "max_dispatch_actions": max_dispatch_actions,
            "max_dispatch_runtime_seconds": max_dispatch_runtime_seconds,
            "max_attempts": max_attempts,
            "retry_backoff_seconds": retry_backoff_seconds,
            "lease_ttl_seconds": lease_ttl_seconds,
            "recover_stale_leases": recover_stale_leases,
            "allow_medium": allow_medium,
            "allow_high": allow_high,
            "stop_on_critical": stop_on_critical,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = autonomy_dispatch_events(
            request,
            payload=AutonomyDispatchRequest(
                max_events=max_events,
                max_actions=max_actions,
                max_runtime_seconds=max_runtime_seconds,
                max_dispatch_actions=max_dispatch_actions,
                max_dispatch_runtime_seconds=max_dispatch_runtime_seconds,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                lease_ttl_seconds=lease_ttl_seconds,
                recover_stale_leases=recover_stale_leases,
                allow_medium=allow_medium,
                allow_high=allow_high,
                stop_on_critical=stop_on_critical,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "autonomy.reactor.tick":
        _enforce_rbac(role, "autonomy.enqueue")
        _enforce_rbac(role, "autonomy.dispatch")
        _enforce_action_scope(app="autonomy", action="autonomy.enqueue")
        _enforce_action_scope(app="autonomy", action="autonomy.dispatch")
        max_collect_events = max(1, min(100, int(args.get("max_collect_events", 20))))
        max_events = max(1, min(100, int(args.get("max_events", 5))))
        max_actions = max(0, min(10, int(args.get("max_actions", 2))))
        max_runtime_seconds = max(1, min(120, int(args.get("max_runtime_seconds", 10))))
        max_dispatch_actions = max(0, min(200, int(args.get("max_dispatch_actions", 10))))
        max_dispatch_runtime_seconds = max(1, min(600, int(args.get("max_dispatch_runtime_seconds", 30))))
        max_attempts = max(1, min(20, int(args.get("max_attempts", 3))))
        retry_backoff_seconds = max(0, min(3600, int(args.get("retry_backoff_seconds", 60))))
        retry_pressure_threshold = max(0, min(500, int(args.get("retry_pressure_threshold", 5))))
        retry_pressure_consecutive_ticks = max(1, min(50, int(args.get("retry_pressure_consecutive_ticks", 3))))
        retry_pressure_cooldown_ticks = max(1, min(50, int(args.get("retry_pressure_cooldown_ticks", 2))))
        lease_ttl_seconds = max(15, min(3600, int(args.get("lease_ttl_seconds", 300))))
        recover_stale_leases = bool(args.get("recover_stale_leases", True))
        allow_medium = bool(args.get("allow_medium", False))
        allow_high = bool(args.get("allow_high", False))
        stop_on_critical = bool(args.get("stop_on_critical", True))
        include_types = [
            str(item).strip()
            for item in args.get("include_types", [])
            if isinstance(item, str) and str(item).strip()
        ]
        execution_args = {
            "max_collect_events": max_collect_events,
            "include_types": include_types,
            "max_events": max_events,
            "max_actions": max_actions,
            "max_runtime_seconds": max_runtime_seconds,
            "max_dispatch_actions": max_dispatch_actions,
            "max_dispatch_runtime_seconds": max_dispatch_runtime_seconds,
            "max_attempts": max_attempts,
            "retry_backoff_seconds": retry_backoff_seconds,
            "retry_pressure_threshold": retry_pressure_threshold,
            "retry_pressure_consecutive_ticks": retry_pressure_consecutive_ticks,
            "retry_pressure_cooldown_ticks": retry_pressure_cooldown_ticks,
            "lease_ttl_seconds": lease_ttl_seconds,
            "recover_stale_leases": recover_stale_leases,
            "allow_medium": allow_medium,
            "allow_high": allow_high,
            "stop_on_critical": stop_on_critical,
        }
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        summary = autonomy_reactor_tick(
            request,
            payload=AutonomyReactorTickRequest(
                max_collect_events=max_collect_events,
                include_types=include_types,
                max_events=max_events,
                max_actions=max_actions,
                max_runtime_seconds=max_runtime_seconds,
                max_dispatch_actions=max_dispatch_actions,
                max_dispatch_runtime_seconds=max_dispatch_runtime_seconds,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                retry_pressure_threshold=retry_pressure_threshold,
                retry_pressure_consecutive_ticks=retry_pressure_consecutive_ticks,
                retry_pressure_cooldown_ticks=retry_pressure_cooldown_ticks,
                lease_ttl_seconds=lease_ttl_seconds,
                recover_stale_leases=recover_stale_leases,
                allow_medium=allow_medium,
                allow_high=allow_high,
                stop_on_critical=stop_on_critical,
            ),
        )
        return {"status": "ok", "kind": normalized_kind, "execution_args": execution_args, "summary": summary}

    if normalized_kind == "repo.status":
        result = _execute_repo_skill(role=role, skill_name="repo.status", args={})
        output = result.get("output", {}) if isinstance(result.get("output"), dict) else {}
        summary = str(output.get("stdout", "")).strip() or "Repository status returned no output."
        tool = {"skill": "repo.status"}
        presentation = _build_repo_presentation(
            kind=normalized_kind,
            execution_args={},
            result=result,
            summary=summary,
        )
        _write_repo_drilldown_state(
            run_id=run_id,
            trace_id=trace_id,
            kind=normalized_kind,
            tool=tool,
            execution_args={},
            summary=summary,
            presentation=presentation,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "tool": tool,
            "summary": summary,
            "presentation": presentation,
            "result": result,
        }

    if normalized_kind == "repo.diff":
        path_arg = str(args.get("path", "")).strip()
        max_chars = max(200, min(40000, int(args.get("max_chars", 12000))))
        execution_args = {"path": path_arg, "max_chars": max_chars}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        result = _execute_repo_skill(
            role=role,
            skill_name="repo.diff",
            args={"path": path_arg, "max_chars": max_chars},
        )
        output = result.get("output", {}) if isinstance(result.get("output"), dict) else {}
        summary = str(output.get("stdout", "")).strip() or "No tracked diff output was returned."
        tool = {"skill": "repo.diff"}
        presentation = _build_repo_presentation(
            kind=normalized_kind,
            execution_args=execution_args,
            result=result,
            summary=summary,
        )
        _write_repo_drilldown_state(
            run_id=run_id,
            trace_id=trace_id,
            kind=normalized_kind,
            tool=tool,
            execution_args=execution_args,
            summary=summary,
            presentation=presentation,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "tool": tool,
            "execution_args": execution_args,
            "summary": summary,
            "presentation": presentation,
            "result": result,
        }

    if normalized_kind == "repo.lint":
        target = str(args.get("target", ".")).strip() or "."
        execution_args = {"target": target}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        result = _execute_repo_skill(role=role, skill_name="repo.lint", args={"target": target})
        output = result.get("output", {}) if isinstance(result.get("output"), dict) else {}
        summary = str(output.get("stdout", "")).strip() or "Ruff completed without stdout."
        tool = {"skill": "repo.lint"}
        presentation = _build_repo_presentation(
            kind=normalized_kind,
            execution_args=execution_args,
            result=result,
            summary=summary,
        )
        _write_repo_drilldown_state(
            run_id=run_id,
            trace_id=trace_id,
            kind=normalized_kind,
            tool=tool,
            execution_args=execution_args,
            summary=summary,
            presentation=presentation,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "tool": tool,
            "execution_args": execution_args,
            "summary": summary,
            "presentation": presentation,
            "result": result,
        }

    if normalized_kind == "repo.tests.request_approval":
        lane = str(args.get("lane", "fast")).strip().lower() or "fast"
        target = str(args.get("target", "")).strip()
        tool_args = {"lane": lane}
        if target:
            tool_args["target"] = target
        execution_args = dict(tool_args)
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        _enforce_rbac(role, "approvals.request")
        _enforce_action_scope(app="approvals", action="approvals.request", mutating=False)
        approval_response = _request_usage_tool_approval(
            request=request,
            skill_name="repo.tests",
            args=tool_args,
            reason="Lens requested approval for repo.tests from the usage loop.",
        )
        approval = approval_response.get("approval", {}) if isinstance(approval_response.get("approval"), dict) else {}
        return {
            "status": "ok",
            "kind": normalized_kind,
            "execution_args": execution_args,
            "approval": approval,
            "summary": (
                f"Approval {str(approval.get('id', '')).strip() or 'pending'} requested for repo.tests."
            ),
        }

    if normalized_kind == "repo.tests":
        lane = str(args.get("lane", "fast")).strip().lower() or "fast"
        target = str(args.get("target", "")).strip()
        approval_id = str(args.get("approval_id", "")).strip() or None
        execution_args = {"lane": lane, "approval_id": approval_id or ""}
        if target:
            execution_args["target"] = target
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        _enforce_rbac(role, "tools.run")
        _enforce_action_scope(app="tools", action="tools.run.repo.tests", mutating=False)
        policy = approval_policy_for_tool(
            skill_name="repo.tests",
            risk_tier="low",
            mutating=False,
            source="builtin",
            declared_requires_approval=True,
        )
        tool_args = {"lane": lane}
        if target:
            tool_args["target"] = target
        approved, approval_detail = ensure_action_approved(
            _fs,
            run_id=run_id,
            action="tools.repo.tests",
            requested_by=role,
            reason="Lens requested repo.tests execution from the usage loop.",
            approval_required=True,
            approval_id=approval_id,
            metadata=_usage_tool_approval_metadata(skill_name="repo.tests", args=tool_args),
        )
        if not approved:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Action requires approval: tools.repo.tests",
                    "policy_reason": policy.reason,
                    **approval_detail,
                },
            )
        result = _skill_executor.execute(SkillCall(name="repo.tests", args=tool_args)).to_dict()
        if not bool(result.get("ok", False)):
            raise HTTPException(status_code=500, detail=f"repo.tests failed: {result.get('error', 'unknown error')}")
        output = result.get("output", {}) if isinstance(result.get("output"), dict) else {}
        summary = str(output.get("stdout", "")).strip() or "repo.tests completed without stdout."
        tool = {"skill": "repo.tests", "approval_id": approval_id}
        presentation = _build_repo_presentation(
            kind=normalized_kind,
            execution_args=execution_args,
            result=result,
            summary=summary,
        )
        _write_repo_drilldown_state(
            run_id=run_id,
            trace_id=trace_id,
            kind=normalized_kind,
            tool=tool,
            execution_args=execution_args,
            summary=summary,
            presentation=presentation,
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "tool": tool,
            "execution_args": execution_args,
            "summary": summary,
            "presentation": presentation,
            "result": result,
        }

    if normalized_kind == "forge.promote.request_approval":
        stage_id = str(args.get("stage_id", "")).strip()
        if not stage_id:
            raise HTTPException(status_code=400, detail="stage_id is required for forge.promote.request_approval")
        execution_args = {"stage_id": stage_id}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        _enforce_rbac(role, "approvals.request")
        _enforce_action_scope(app="approvals", action="approvals.request", mutating=False)
        existing = _find_forge_promote_approval(stage_id)
        existing_status = str((existing or {}).get("status", "")).strip().lower()
        if existing is not None and existing_status in {"pending", "approved"}:
            approval = existing
        else:
            approval_response = approval_request(
                request,
                ApprovalRequestPayload(
                    action="forge.promote",
                    reason=f"Lens requested approval to promote staged capability {stage_id}.",
                    metadata={
                        "path": f"/forge/promote/{stage_id}",
                        "stage_id": stage_id,
                        "action_kind": "forge.promote",
                        "source": "lens.capability_library",
                    },
                ),
            )
            approval = (
                approval_response.get("approval", {})
                if isinstance(approval_response.get("approval"), dict)
                else {}
            )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "execution_args": execution_args,
            "approval": approval,
            "summary": (
                f"Approval {str(approval.get('id', '')).strip() or 'pending'} is queued for forge.promote."
            ),
        }

    if normalized_kind == "forge.promote":
        _enforce_rbac(role, "forge.promote")
        _enforce_action_scope(app="forge", action="forge.promote", mutating=True)
        stage_id = str(args.get("stage_id", "")).strip()
        if not stage_id:
            raise HTTPException(status_code=400, detail="stage_id is required for forge.promote")
        approval_id = str(args.get("approval_id", "")).strip() or None
        execution_args = {"stage_id": stage_id, "approval_id": approval_id or ""}
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": execution_args}
        approved, approval_detail = ensure_action_approved(
            _fs,
            run_id=run_id,
            action="forge.promote",
            requested_by=role,
            reason=f"Promote staged capability: {stage_id}",
            approval_id=approval_id,
            metadata={
                "path": f"/forge/promote/{stage_id}",
                "stage_id": stage_id,
                "action_kind": "forge.promote",
                "source": "lens.capability_library",
            },
        )
        if not approved:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Action requires approval: forge.promote",
                    **approval_detail,
                },
            )
        actual_approval_id = approval_id or str(approval_detail.get("approval_request_id", "")).strip() or None
        catalog_entries = [row for row in list_entries(_fs) if isinstance(row, dict)]
        staged_entry = next((row for row in catalog_entries if str(row.get("id", "")).strip() == stage_id), None)
        if staged_entry is None:
            raise HTTPException(status_code=404, detail=f"Stage not found: {stage_id}")
        promotion_rules = build_promotion_rules(staged_entry, approval_status="approved")
        for rule in promotion_rules.get("rules", []) if isinstance(promotion_rules.get("rules"), list) else []:
            if not isinstance(rule, dict):
                continue
            if bool(rule.get("ok")):
                continue
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Capability is not promotion-ready",
                    "stage_id": stage_id,
                    "rule": str(rule.get("kind", "")).strip() or "promotion_rule",
                    "reason": str(rule.get("detail", "")).strip() or "Promotion rules are not satisfied.",
                    "promotion_rules": promotion_rules,
                },
            )
        try:
            promoted = promote_stage(_fs, stage_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if promoted is None:
            raise HTTPException(status_code=404, detail=f"Stage not found: {stage_id}")
        _ledger.append(
            run_id=run_id,
            kind="forge.promote",
            summary={
                "stage_id": stage_id,
                "status": promoted.get("status"),
                "approval_id": actual_approval_id,
            },
        )
        presentation = _build_capability_presentation(
            entry=promoted,
            approval_id=actual_approval_id or "",
        )
        tool_pack_registered = isinstance(promoted.get("tool_pack"), dict) and bool(
            promoted["tool_pack"].get("skill_name")
        )
        return {
            "status": "ok",
            "kind": normalized_kind,
            "tool": {"skill": "forge.promote", "approval_id": actual_approval_id},
            "execution_args": execution_args,
            "summary": str(presentation.get("summary", "")).strip(),
            "presentation": presentation,
            "entry": promoted,
            "tool_pack_registered": tool_pack_registered,
            "tool_pack_skill": promoted.get("tool_pack", {}).get("skill_name") if tool_pack_registered else None,
        }

    if normalized_kind == "observer.scan":
        _enforce_action_scope(app="observer", action="observer.scan")
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind}
        summary = run_observer_cycle(
            run_id=f"{run_id}:lens-observer:{uuid4()}",
            repo_root=_repo_root,
            workspace_root=_workspace_root,
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "mission.tick":
        _enforce_rbac(role, "missions.tick")
        _enforce_action_scope(app="missions", action="missions.tick")
        mission_id = str(args.get("mission_id", "")).strip()
        if not mission_id:
            raise HTTPException(status_code=400, detail="mission_id is required for mission.tick")
        force_fail = bool(args.get("force_fail", False))
        reason = str(args.get("reason", "")).strip()
        idempotency_key = str(args.get("idempotency_key", "")).strip() or None
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {
                    "mission_id": mission_id,
                    "force_fail": force_fail,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                },
            }
        summary = execute_mission_tick(
            mission_id=mission_id,
            run_id=f"{run_id}:lens-mission:{uuid4()}",
            trace_id=trace_id,
            role=role,
            force_fail=force_fail,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "forge.propose":
        _enforce_rbac(role, "forge.propose")
        _enforce_action_scope(app="forge", action="forge.propose", mutating=False)
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind}
        summary = forge_proposals(request)
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "apprenticeship.generalize":
        _enforce_rbac(role, "apprenticeship.generalize")
        _enforce_action_scope(app="apprenticeship", action="apprenticeship.generalize", mutating=True)
        session_id = str(args.get("session_id", "")).strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for apprenticeship.generalize")
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": {"session_id": session_id}}
        summary = apprenticeship_generalize(request, session_id=session_id)
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "apprenticeship.session.create":
        _enforce_rbac(role, "apprenticeship.write")
        _enforce_action_scope(app="apprenticeship", action="apprenticeship.write", mutating=True)
        title = str(args.get("title", "")).strip()
        if not title:
            raise HTTPException(status_code=400, detail="title is required for apprenticeship.session.create")
        create_payload = ApprenticeshipSessionCreateRequest(
            title=title,
            objective=str(args.get("objective", "")).strip(),
            mission_id=str(args.get("mission_id", "")).strip() or None,
            tags=[str(tag).strip() for tag in args.get("tags", []) if isinstance(tag, str) and str(tag).strip()],
        )
        if dry_run:
            return {"status": "dry_run", "kind": normalized_kind, "execution_args": create_payload.model_dump()}
        summary = apprenticeship_create_session(request, payload=create_payload)
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "apprenticeship.step.record":
        _enforce_rbac(role, "apprenticeship.write")
        _enforce_action_scope(app="apprenticeship", action="apprenticeship.write", mutating=True)
        session_id = str(args.get("session_id", "")).strip()
        action_value = str(args.get("action", "")).strip()
        intent_value = str(args.get("intent", "")).strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for apprenticeship.step.record")
        if not action_value:
            raise HTTPException(status_code=400, detail="action is required for apprenticeship.step.record")
        if not intent_value:
            raise HTTPException(status_code=400, detail="intent is required for apprenticeship.step.record")
        step_payload = ApprenticeshipStepRequest(
            kind=str(args.get("step_kind", "command")).strip() or "command",
            action=action_value,
            intent=intent_value,
            artifact_path=str(args.get("artifact_path", "")).strip(),
            notes=str(args.get("notes", "")).strip(),
            inputs=args.get("inputs", {}) if isinstance(args.get("inputs"), dict) else {},
            outputs=args.get("outputs", {}) if isinstance(args.get("outputs"), dict) else {},
        )
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {"session_id": session_id, **step_payload.model_dump()},
            }
        summary = apprenticeship_add_step(request, session_id=session_id, payload=step_payload)
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "apprenticeship.skillize":
        _enforce_rbac(role, "apprenticeship.skillize")
        _enforce_action_scope(app="apprenticeship", action="apprenticeship.skillize", mutating=True)
        session_id = str(args.get("session_id", "")).strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for apprenticeship.skillize")
        skillize_payload = ApprenticeshipSkillizeRequest(
            name=str(args.get("name", "")).strip() or None,
            description=str(args.get("description", "")).strip() or None,
            rationale=str(args.get("rationale", "")).strip() or None,
            tags=[str(tag) for tag in args.get("tags", []) if isinstance(tag, str)],
            risk_tier=str(args.get("risk_tier", "low")).strip().lower() or "low",
        )
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "execution_args": {"session_id": session_id, **skillize_payload.model_dump()},
            }
        summary = apprenticeship_skillize(request, session_id=session_id, payload=skillize_payload)
        return {"status": "ok", "kind": normalized_kind, "summary": summary}

    if normalized_kind == "autonomy.reactor.guardrail.reset":
        _enforce_rbac(role, "autonomy.guardrail.reset")
        _enforce_action_scope(app="autonomy", action="autonomy.guardrail.reset")
        reason = str(args.get("reason", "")).strip() or "lens.guardrail.reset"
        before = read_autonomy_reactor_guardrail_state(_fs)
        if dry_run:
            return {
                "status": "dry_run",
                "kind": normalized_kind,
                "reason": reason,
                "before": before,
                "after": {
                    **before,
                    "consecutive_retry_pressure_ticks": 0,
                    "cooldown_remaining_ticks": 0,
                    "last_reason": reason,
                },
            }
        after = write_reactor_guardrail_state(
            _fs,
            payload={
                **before,
                "consecutive_retry_pressure_ticks": 0,
                "cooldown_remaining_ticks": 0,
                "last_reason": reason,
            },
        )
        receipt = {
            "id": str(uuid4()),
            "ts": utc_now_iso(),
            "run_id": run_id,
            "trace_id": trace_id,
            "kind": "autonomy.reactor.guardrail.reset",
            "reason": reason,
            "before": before,
            "after": after,
        }
        append_reactor_guardrail_history(_fs, payload=receipt)
        return {"status": "ok", "kind": normalized_kind, "receipt": receipt}

    raise HTTPException(status_code=400, detail=f"Unsupported lens action kind: {normalized_kind}")


def _with_execute_hint(chip: dict[str, Any]) -> dict[str, Any]:
    kind = str(chip.get("kind", "")).strip()
    hinted = {
        **chip,
        "execute_via": {
            "endpoint": "/lens/actions/execute",
            "method": "POST",
            "payload": {"kind": kind, "args": {}},
        },
    }
    if kind == "mission.tick":
        hinted["execute_via"]["payload"]["args"] = {"mission_id": "<required>"}
    elif kind == "repo.tests":
        hinted["execute_via"]["payload"]["args"] = {"lane": "fast", "approval_id": ""}
    elif kind == "repo.tests.request_approval":
        hinted["execute_via"]["payload"]["args"] = {"lane": "fast"}
    elif kind == "apprenticeship.generalize":
        hinted["execute_via"]["payload"]["args"] = {"session_id": "<required>"}
    elif kind == "apprenticeship.skillize":
        hinted["execute_via"]["payload"]["args"] = {
            "session_id": "<required>",
            "name": "",
            "description": "",
            "rationale": "",
            "tags": [],
            "risk_tier": "low",
        }
    elif kind == "control.takeover.request":
        hinted["execute_via"]["payload"]["args"] = {"objective": "<required>", "reason": ""}
    elif kind == "control.takeover.confirm":
        hinted["execute_via"]["payload"]["args"] = {"confirm": True, "mode": "pilot", "reason": ""}
    elif kind == "control.takeover.handback":
        hinted["execute_via"]["payload"]["args"] = {
            "summary": "",
            "verification": {},
            "pending_approvals": 0,
            "mode": "assist",
            "reason": "",
        }
    elif kind == "control.takeover.activity":
        hinted["execute_via"]["payload"]["args"] = {"limit": 50, "session_id": ""}
    elif kind == "control.takeover.handback.package":
        hinted["execute_via"]["payload"]["args"] = {"limit": 120, "session_id": ""}
    elif kind == "control.takeover.handback.export":
        hinted["execute_via"]["payload"]["args"] = {"limit": 300, "session_id": "", "reason": ""}
    elif kind == "control.takeover.sessions":
        hinted["execute_via"]["payload"]["args"] = {"limit": 20}
    elif kind == "control.takeover.session":
        hinted["execute_via"]["payload"]["args"] = {"session_id": "<required>", "limit": 200}
    elif kind == "control.remote.state":
        hinted["execute_via"]["payload"]["args"] = {"approval_limit": 10, "session_limit": 5}
    elif kind == "control.remote.approvals":
        hinted["execute_via"]["payload"]["args"] = {"status": "pending", "limit": 50}
    elif kind == "control.remote.feed":
        hinted["execute_via"]["payload"]["args"] = {
            "limit": 100,
            "cursor": "",
            "session_id": "",
            "source": "",
            "kind": "",
            "kind_prefix": "",
            "risk_tier": "",
        }
    elif kind == "control.remote.panic":
        hinted["execute_via"]["payload"]["args"] = {"reason": "", "session_id": ""}
    elif kind == "control.remote.resume":
        hinted["execute_via"]["payload"]["args"] = {"reason": "", "mode": "pilot", "session_id": ""}
    elif kind == "control.remote.takeover.request":
        hinted["execute_via"]["payload"]["args"] = {"objective": "<required>", "reason": ""}
    elif kind == "control.remote.takeover.confirm":
        hinted["execute_via"]["payload"]["args"] = {"confirm": True, "mode": "pilot", "reason": "", "session_id": ""}
    elif kind == "control.remote.takeover.handback":
        hinted["execute_via"]["payload"]["args"] = {
            "summary": "",
            "verification": {},
            "pending_approvals": 0,
            "mode": "assist",
            "reason": "",
            "session_id": "",
        }
    elif kind == "control.remote.approval.approve":
        hinted["execute_via"]["payload"]["args"] = {"approval_id": "<required>", "note": "", "session_id": ""}
    elif kind == "control.remote.approval.reject":
        hinted["execute_via"]["payload"]["args"] = {"approval_id": "<required>", "note": "", "session_id": ""}
    return hinted


@router.get("/lens/state")
def lens_state(request: Request) -> dict:
    allowed, reason, control = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="lens",
        action="lens.state",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    event_state = collect_events(_fs)
    intent_state = collect_intents(_fs)
    telemetry = telemetry_status(_fs)
    lens_snapshot = build_lens_snapshot(_workspace_root)
    current_work = lens_snapshot.get("current_work", {}) if isinstance(lens_snapshot.get("current_work"), dict) else {}
    next_best_action = (
        lens_snapshot.get("next_best_action", {})
        if isinstance(lens_snapshot.get("next_best_action"), dict)
        else {}
    )
    autonomy_queue = autonomy_queue_status(_fs, limit=200)
    autonomy_last_dispatch = read_autonomy_last_dispatch(_fs)
    autonomy_last_tick = read_autonomy_last_tick(_fs)
    autonomy_guardrail = read_autonomy_reactor_guardrail_state(_fs)
    dispatch_verification = (
        autonomy_last_dispatch.get("verification", {})
        if isinstance(autonomy_last_dispatch.get("verification"), dict)
        else {}
    )
    tick_verification = (
        autonomy_last_tick.get("verification", {})
        if isinstance(autonomy_last_tick.get("verification"), dict)
        else {}
    )
    last_dispatch_config = (
        autonomy_last_dispatch.get("config", {}) if isinstance(autonomy_last_dispatch, dict) else {}
    )
    halted_reason = str(autonomy_last_dispatch.get("halted_reason", "")).strip()
    dispatch_halted = bool(halted_reason) and halted_reason != "completed"
    dispatch_budget_halt = halted_reason in {"dispatch_action_budget_exceeded", "dispatch_runtime_budget_exceeded"}
    dispatch_critical_halt = halted_reason in {"critical_incident_present", "critical_anomaly"}
    tick_dispatch = autonomy_last_tick.get("dispatch", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_collect = autonomy_last_tick.get("collect", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_halted_reason = str(tick_dispatch.get("halted_reason", "")).strip()
    tick_halted = bool(tick_halted_reason) and tick_halted_reason != "completed"
    guardrail_cooldown_active = int(autonomy_guardrail.get("cooldown_remaining_ticks", 0)) > 0
    manual_reset_available = str(control.get("mode", "observe")).strip().lower() == "pilot"
    autonomy_high_risk_due = sum(
        1
        for row in autonomy_queue.get("queued", [])
        if str(row.get("risk_tier", "")).strip().lower() in {"high", "critical"}
    )
    autonomy_leased_expired_count = int(autonomy_queue.get("leased_expired_count", 0))
    autonomy_retry_pressure = int(autonomy_queue.get("queued_retry_count", 0))
    catalog_entries = list_entries(_fs)
    staged_count = sum(1 for entry in catalog_entries if str(entry.get("status", "")).lower() == "staged")
    pending_approvals = pending_count(_fs) + len(_read_jsonl("queue/deadletter.jsonl")) + staged_count

    mode = str(control.get("mode", "observe")).strip().lower()
    kill_switch = bool(control.get("kill_switch", False))
    takeover_state = control_takeover_state().get("takeover", {})
    takeover_status = str(takeover_state.get("status", "idle")).strip().lower() or "idle"
    takeover_session_id = str(takeover_state.get("session_id") or "").strip() or None
    takeover_last_session_id = str(takeover_state.get("last_session_id") or "").strip() or None
    activity_session_id = takeover_session_id or takeover_last_session_id
    takeover_activity_payload = control_takeover_activity(limit=10, session_id=activity_session_id)
    takeover_recent_activity = takeover_activity_payload.get("activity", [])
    takeover_sessions_payload = control_takeover_sessions(limit=3)
    takeover_recent_sessions = takeover_sessions_payload.get("sessions", [])
    try:
        remote_state = control_remote_state(request, approval_limit=10, session_limit=3)
    except HTTPException as exc:
        remote_state = {
            "status": "unavailable",
            "policy_reason": str(getattr(exc, "detail", "remote state unavailable")),
            "remote_actions": [],
            "control": {},
            "takeover": {},
            "approvals": {"pending_count": 0, "pending": []},
            "sessions": {"count": 0, "recent": []},
        }
    handback_package_available = False
    handback_package_summary: dict[str, Any] | None = None
    if takeover_last_session_id:
        try:
            handback_package = control_takeover_handback_package(limit=20, session_id=takeover_last_session_id)
            handback_package_available = True
            handback_package_summary = handback_package.get("summary", {})
        except HTTPException:
            handback_package_available = False
            handback_package_summary = None
    pilot_mode_on = mode == "pilot" and not kill_switch
    pilot_indicator_status = "on" if pilot_mode_on else "paused" if mode == "pilot" and kill_switch else "off"
    pilot_indicator_label = (
        "PILOT MODE ON"
        if pilot_indicator_status == "on"
        else "PILOT MODE PAUSED"
        if pilot_indicator_status == "paused"
        else "PILOT MODE OFF"
    )
    panic_available = not kill_switch
    resume_available = kill_switch

    return {
        "status": "ok",
        "mode": control.get("mode"),
        "kill_switch": control.get("kill_switch"),
        "scope": control.get("scopes", {}),
        "control_surface": {
            "mode": mode,
            "kill_switch": kill_switch,
            "panic_available": panic_available,
            "resume_available": resume_available,
            "mutating_actions_blocked": kill_switch,
            "pilot_mode_on": pilot_mode_on,
            "pilot_indicator": {
                "visible": True,
                "status": pilot_indicator_status,
                "label": pilot_indicator_label,
                "kill_switch_active": kill_switch,
            },
            "takeover": {
                "status": takeover_status,
                "active": takeover_status == "active",
                "pending_confirmation": takeover_status == "requested",
                "session_id": takeover_session_id,
                "last_session_id": takeover_last_session_id,
                "objective": takeover_state.get("objective"),
                "requested_by": takeover_state.get("requested_by"),
                "requested_at": takeover_state.get("requested_at"),
                "confirmed_at": takeover_state.get("confirmed_at"),
                "handed_back_at": takeover_state.get("handed_back_at"),
                "recent_activity": takeover_recent_activity,
                "recent_sessions": takeover_recent_sessions,
                "session_count": int(takeover_sessions_payload.get("count", len(takeover_recent_sessions))),
                "handback_package_available": handback_package_available,
                "handback_package_summary": handback_package_summary,
            },
        },
        "intent_state": intent_state,
        "event_state": event_state,
        "telemetry": {
            "enabled": bool(telemetry.get("enabled", False)),
            "event_count_horizon": int(telemetry.get("event_count_horizon", 0)),
            "active_streams_horizon": list(telemetry.get("active_streams_horizon", [])),
            "last_event_ts": telemetry.get("last_event_ts"),
        },
        "current_work": current_work,
        "next_best_action": next_best_action,
        "remote": remote_state,
        "apprenticeship": summarize_apprenticeship(_fs, limit=5),
        "autonomy_queue": {
            "queued_count": int(autonomy_queue.get("queued_count", 0)),
            "queued_retry_count": autonomy_retry_pressure,
            "leased_count": int(autonomy_queue.get("leased_count", 0)),
            "leased_expired_count": autonomy_leased_expired_count,
            "dispatched_count": int(autonomy_queue.get("dispatched_count", 0)),
            "failed_count": int(autonomy_queue.get("failed_count", 0)),
            "deadletter_count": int(autonomy_queue.get("deadletter_count", 0)),
            "high_risk_due_count": autonomy_high_risk_due,
        },
        "autonomy_dispatch": {
            "last_run_id": autonomy_last_dispatch.get("run_id"),
            "halted_reason": halted_reason or None,
            "halted": dispatch_halted,
            "processed_count": int(autonomy_last_dispatch.get("processed_count", 0)),
            "failed_count": int(autonomy_last_dispatch.get("failed_count", 0)),
            "retried_count": int(autonomy_last_dispatch.get("retried_count", 0)),
            "released_count": int(autonomy_last_dispatch.get("released_count", 0)),
            "dispatch_executed_actions": int(autonomy_last_dispatch.get("dispatch_executed_actions", 0)),
            "max_dispatch_actions": int(last_dispatch_config.get("max_dispatch_actions", 0)),
            "max_dispatch_runtime_seconds": int(last_dispatch_config.get("max_dispatch_runtime_seconds", 0)),
            "max_attempts": int(last_dispatch_config.get("max_attempts", 0)),
            "retry_backoff_seconds": int(last_dispatch_config.get("retry_backoff_seconds", 0)),
            "verification_status": dispatch_verification.get("verification_status"),
            "confidence": dispatch_verification.get("confidence"),
            "can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
            "claim": dispatch_verification.get("claim"),
            "completion_state": autonomy_last_dispatch.get("completion_state"),
            "trust_badge": trust_badge(
                confidence=str(dispatch_verification.get("confidence", "")),
                can_claim_done=bool(dispatch_verification.get("can_claim_done", False)),
            ),
        },
        "autonomy_reactor": {
            "last_run_id": autonomy_last_tick.get("run_id"),
            "last_ts": autonomy_last_tick.get("ts"),
            "halted": tick_halted,
            "halted_reason": tick_halted_reason or None,
            "collect_seen_count": int(tick_collect.get("seen_count", 0)),
            "collect_queued_count": int(tick_collect.get("queued_count", 0)),
            "dispatch_processed_count": int(tick_dispatch.get("processed_count", 0)),
            "dispatch_failed_count": int(tick_dispatch.get("failed_count", 0)),
            "dispatch_retried_count": int(tick_dispatch.get("retried_count", 0)),
            "dispatch_released_count": int(tick_dispatch.get("released_count", 0)),
            "verification_status": tick_verification.get("verification_status"),
            "confidence": tick_verification.get("confidence"),
            "can_claim_done": bool(tick_verification.get("can_claim_done", False)),
            "claim": tick_verification.get("claim"),
            "completion_state": autonomy_last_tick.get("completion_state"),
            "trust_badge": trust_badge(
                confidence=str(tick_verification.get("confidence", "")),
                can_claim_done=bool(tick_verification.get("can_claim_done", False)),
            ),
            "guardrail": {
                "tick_count": int(autonomy_guardrail.get("tick_count", 0)),
                "consecutive_retry_pressure_ticks": int(
                    autonomy_guardrail.get("consecutive_retry_pressure_ticks", 0)
                ),
                "cooldown_remaining_ticks": int(autonomy_guardrail.get("cooldown_remaining_ticks", 0)),
                "escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                "last_retry_pressure_count": int(autonomy_guardrail.get("last_retry_pressure_count", 0)),
                "last_reason": autonomy_guardrail.get("last_reason"),
                "manual_reset_available": manual_reset_available,
                "updated_at": autonomy_guardrail.get("updated_at"),
            },
        },
        "pending_approvals": pending_approvals,
        "blockers": {
            "critical_incidents": event_state.get("critical_incident_count", 0),
            "deadletters": event_state.get("deadletter_count", 0),
            "worker_queue_due": event_state.get("worker_queue_due_count", 0),
            "worker_queue_backoff": event_state.get("worker_queue_backoff_count", 0),
            "worker_leased": event_state.get("worker_leased_count", 0),
            "worker_leased_expired": event_state.get("worker_leased_expired_count", 0),
            "worker_cycle_active": event_state.get("worker_cycle_active_count", 0),
            "worker_cycle_max": event_state.get("worker_cycle_max_concurrent", 1),
            "worker_cycle_gate_saturated": event_state.get("worker_cycle_gate_saturated", False),
            "worker_last_lease_lost": event_state.get("worker_last_lease_lost_count", 0),
            "worker_last_lease_conflict": event_state.get("worker_last_lease_conflict_count", 0),
            "autonomy_queue_due": int(autonomy_queue.get("queued_count", 0)),
            "autonomy_queue_high_risk_due": autonomy_high_risk_due,
            "autonomy_queue_retry_pressure": autonomy_retry_pressure,
            "autonomy_queue_leased_expired": autonomy_leased_expired_count,
            "autonomy_dispatch_halted": dispatch_halted,
            "autonomy_dispatch_halted_reason": halted_reason or None,
            "autonomy_dispatch_budget_halt": dispatch_budget_halt,
            "autonomy_dispatch_critical_halt": dispatch_critical_halt,
            "autonomy_dispatch_claim_confidence": dispatch_verification.get("confidence"),
            "autonomy_dispatch_can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
            "autonomy_reactor_halted": tick_halted,
            "autonomy_reactor_halted_reason": tick_halted_reason or None,
            "autonomy_reactor_cooldown_active": guardrail_cooldown_active,
            "autonomy_reactor_claim_confidence": tick_verification.get("confidence"),
            "autonomy_reactor_can_claim_done": bool(tick_verification.get("can_claim_done", False)),
            "pending_approvals": pending_approvals,
        },
    }


@router.get("/lens/actions")
def lens_actions(request: Request, max_actions: int = 6) -> dict:
    allowed, reason, control = check_action_allowed(
        _fs,
        repo_root=_repo_root,
        workspace_root=_workspace_root,
        app="lens",
        action="lens.actions",
        mutating=False,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Control denied: {reason}")

    role = _role_from_request(request)
    event_state = collect_events(_fs)
    intent_state = collect_intents(_fs)
    lens_snapshot = build_lens_snapshot(_workspace_root)
    current_work = lens_snapshot.get("current_work", {}) if isinstance(lens_snapshot.get("current_work"), dict) else {}
    next_best_action = (
        lens_snapshot.get("next_best_action", {})
        if isinstance(lens_snapshot.get("next_best_action"), dict)
        else {}
    )
    autonomy_queue = autonomy_queue_status(_fs, limit=200)
    autonomy_last_dispatch = read_autonomy_last_dispatch(_fs)
    autonomy_last_tick = read_autonomy_last_tick(_fs)
    autonomy_guardrail = read_autonomy_reactor_guardrail_state(_fs)
    dispatch_halted_reason = str(autonomy_last_dispatch.get("halted_reason", "")).strip()
    dispatch_verification = (
        autonomy_last_dispatch.get("verification", {})
        if isinstance(autonomy_last_dispatch.get("verification"), dict)
        else {}
    )
    last_dispatch_config = (
        autonomy_last_dispatch.get("config", {}) if isinstance(autonomy_last_dispatch, dict) else {}
    )
    tick_dispatch = autonomy_last_tick.get("dispatch", {}) if isinstance(autonomy_last_tick, dict) else {}
    tick_verification = (
        autonomy_last_tick.get("verification", {})
        if isinstance(autonomy_last_tick.get("verification"), dict)
        else {}
    )
    tick_halted_reason = str(tick_dispatch.get("halted_reason", "")).strip()
    guardrail_cooldown_remaining = int(autonomy_guardrail.get("cooldown_remaining_ticks", 0))
    guardrail_cooldown_active = guardrail_cooldown_remaining > 0
    autonomy_queued_count = int(autonomy_queue.get("queued_count", 0))
    autonomy_retry_pressure = int(autonomy_queue.get("queued_retry_count", 0))
    autonomy_high_risk_due = sum(
        1
        for row in autonomy_queue.get("queued", [])
        if str(row.get("risk_tier", "")).strip().lower() in {"high", "critical"}
    )
    autonomy_leased_expired_count = int(autonomy_queue.get("leased_expired_count", 0))
    allow_medium, allow_high = _mode_allows_medium_high(str(control.get("mode", "observe")))
    plan = build_plan(
        event_state=event_state,
        intent_state=intent_state,
        max_actions=max_actions,
        allow_medium=allow_medium,
        allow_high=allow_high,
    )
    budget_state = load_budget_state(_fs)
    gated_candidates: list[dict[str, Any]] = []
    for candidate in plan.get("candidate_actions", []):
        if not bool(candidate.get("allowed", False)):
            gated_candidates.append({**candidate})
            continue
        allowed_by_budget, reason, action_key = check_action_budget(candidate, state=budget_state)
        if allowed_by_budget:
            gated_candidates.append({**candidate})
        else:
            gated_candidates.append(
                {
                    **candidate,
                    "allowed": False,
                    "policy_reason": reason,
                    "blocked_by": "action_budget",
                    "action_key": action_key,
                }
            )

    selected_actions = [item for item in gated_candidates if bool(item.get("allowed"))][: max(0, max_actions)]
    blocked_actions = [item for item in gated_candidates if not bool(item.get("allowed"))]

    action_chips = []
    for action in gated_candidates:
        kind = str(action.get("kind", ""))
        label = {
            "observer.scan": "Run Observer Scan",
            "worker.cycle": "Process Worker Queue",
            "worker.recover_leases": "Recover Stale Leases",
            "mission.tick": "Advance Mission",
            "forge.propose": "Generate Forge Proposals",
        }.get(kind, kind)
        chip = {
            "kind": kind,
            "label": label,
            "enabled": bool(action.get("allowed")),
            "reason": action.get("reason", ""),
            "policy_reason": action.get("policy_reason", ""),
            "risk_tier": action.get("risk_tier", "low"),
            "trust_badge": "Likely" if bool(action.get("allowed")) else "Uncertain",
        }
        if kind == "worker.cycle":
            chip["lease_telemetry"] = {
                "renewed_last_cycle": event_state.get("worker_last_lease_renewed_count", 0),
                "lost_last_cycle": event_state.get("worker_last_lease_lost_count", 0),
                "conflicts_last_cycle": event_state.get("worker_last_lease_conflict_count", 0),
                "recovered_last_cycle": event_state.get("worker_last_recovered_count", 0),
                "gate_saturated": event_state.get("worker_cycle_gate_saturated", False),
                "active_cycles": event_state.get("worker_cycle_active_count", 0),
                "max_concurrent_cycles": event_state.get("worker_cycle_max_concurrent", 1),
            }
        if kind == "worker.recover_leases":
            chip["recovery_scope"] = action.get("action_classes", [])
        action_chips.append(_with_execute_hint(chip))

    usage_repo = current_work.get("repo", {}) if isinstance(current_work.get("repo"), dict) else {}
    usage_capabilities = (
        current_work.get("capabilities", {}) if isinstance(current_work.get("capabilities"), dict) else {}
    )
    capability_focus = (
        usage_capabilities.get("focus_entry", {})
        if isinstance(usage_capabilities.get("focus_entry"), dict)
        else {}
    )
    repo_status_allowed, repo_status_scope_reason = _check_usage_scope("tools", "tools.run.repo.status")
    repo_diff_allowed, repo_diff_scope_reason = _check_usage_scope("tools", "tools.run.repo.diff")
    repo_lint_allowed, repo_lint_scope_reason = _check_usage_scope("tools", "tools.run.repo.lint")
    repo_tests_allowed, repo_tests_scope_reason = _check_usage_scope("tools", "tools.run.repo.tests")
    forge_promote_allowed, forge_promote_scope_reason = _check_usage_scope(
        "forge",
        "forge.promote",
        mutating=True,
    )
    approvals_request_allowed, approvals_request_scope_reason = _check_usage_scope(
        "approvals",
        "approvals.request",
        mutating=False,
    )
    repo_tests_args = {"lane": "fast"}
    repo_tests_approval = _find_usage_tool_approval(skill_name="repo.tests", args=repo_tests_args)
    repo_tests_approval_status = (
        str(repo_tests_approval.get("status", "")).strip().lower() if isinstance(repo_tests_approval, dict) else ""
    )
    repo_tests_approval_id = (
        str(repo_tests_approval.get("id", "")).strip() if isinstance(repo_tests_approval, dict) else ""
    )
    usage_chip_defs = [
        {
            "kind": "repo.status",
            "label": "Inspect Repo Status",
            "enabled": repo_status_allowed,
            "reason": str(usage_repo.get("summary", "Read the current git working tree state.")),
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            "args": {},
            "policy_reason": "" if repo_status_allowed else repo_status_scope_reason,
        }
    ]
    if bool(usage_repo.get("dirty", False)):
        usage_chip_defs.append(
            {
                "kind": "repo.diff",
                "label": "Summarize Local Diff",
                "enabled": repo_diff_allowed,
                "reason": (
                    f"{int(usage_repo.get('changed_count', 0))} repo change(s) are present. "
                    "Inspect tracked diffs before the next mutating pass."
                ),
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                "args": {},
                "policy_reason": "" if repo_diff_allowed else repo_diff_scope_reason,
            }
        )
    usage_chip_defs.append(
        {
            "kind": "repo.lint",
            "label": "Run Ruff Check",
            "enabled": repo_lint_allowed,
            "reason": "Run the repo lint gate against the current working tree.",
            "risk_tier": "low",
            "trust_badge": "Likely",
            "args": {"target": "."},
            "policy_reason": "" if repo_lint_allowed else repo_lint_scope_reason,
        }
    )
    if repo_tests_approval_status == "approved" and repo_tests_approval_id:
        usage_chip_defs.append(
            {
                "kind": "repo.tests",
                "label": "Run Fast Checks",
                "enabled": repo_tests_allowed,
                "reason": (
                    f"Approval {repo_tests_approval_id[:8]} is approved. "
                    "Run the fast pytest lane against the current repo state."
                ),
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                "args": {"lane": "fast", "approval_id": repo_tests_approval_id},
                "policy_reason": "" if repo_tests_allowed else repo_tests_scope_reason,
            }
        )
    else:
        pending_policy_reason = (
            f"Approval {repo_tests_approval_id[:8]} is pending."
            if repo_tests_approval_status == "pending" and repo_tests_approval_id
            else (
                "Repository test execution requires approval."
                if repo_tests_allowed
                else repo_tests_scope_reason
            )
        )
        usage_chip_defs.append(
            {
                "kind": "repo.tests",
                "label": "Run Fast Checks",
                "enabled": False,
                "reason": "Run the fast pytest lane against the current repo state.",
                "risk_tier": "low",
                "trust_badge": "Likely",
                "args": {"lane": "fast"},
                "policy_reason": pending_policy_reason,
            }
        )
        if repo_tests_approval_status != "pending":
            request_enabled = approvals_request_allowed and can(role, "approvals.request")
            request_policy_reason = (
                ""
                if request_enabled
                else approvals_request_scope_reason
                if not approvals_request_allowed
                else f"RBAC denied: role={role}, action=approvals.request"
            )
            usage_chip_defs.append(
                {
                    "kind": "repo.tests.request_approval",
                    "label": "Request Fast Checks Approval",
                    "enabled": request_enabled,
                    "reason": (
                        "Queue approval for repo.tests so Francis can run the fast lane from the same operator deck."
                    ),
                    "risk_tier": "low",
                    "trust_badge": "Likely",
                    "args": {"lane": "fast"},
                    "policy_reason": request_policy_reason,
                }
            )
    capability_stage_id = str(capability_focus.get("id", "")).strip()
    capability_status = str(capability_focus.get("status", "")).strip().lower()
    capability_approval_status = str(capability_focus.get("approval_status", "")).strip().lower()
    capability_approval_id = str(capability_focus.get("approval_id", "")).strip()
    if capability_stage_id and capability_status == "staged":
        capability_risk = str(capability_focus.get("risk_tier", "medium")).strip().lower() or "medium"
        capability_reason = str(capability_focus.get("summary", "")).strip() or "Staged capability is ready for governed review."
        if capability_approval_status == "approved" and capability_approval_id:
            usage_chip_defs.append(
                {
                    "kind": "forge.promote",
                    "label": "Promote Capability",
                    "enabled": forge_promote_allowed,
                    "reason": capability_reason,
                    "risk_tier": capability_risk,
                    "trust_badge": "Confirmed",
                    "args": {"stage_id": capability_stage_id, "approval_id": capability_approval_id},
                    "policy_reason": "" if forge_promote_allowed else forge_promote_scope_reason,
                }
            )
        else:
            capability_policy_reason = (
                f"Promotion approval {capability_approval_id} is pending."
                if capability_approval_status == "pending" and capability_approval_id
                else "Promotion approval was rejected and needs a fresh operator decision."
                if capability_approval_status == "rejected"
                else "Capability promotion requires approval."
                if forge_promote_allowed
                else forge_promote_scope_reason
            )
            usage_chip_defs.append(
                {
                    "kind": "forge.promote",
                    "label": "Promote Capability",
                    "enabled": False,
                    "reason": capability_reason,
                    "risk_tier": capability_risk,
                    "trust_badge": "Likely",
                    "args": {"stage_id": capability_stage_id},
                    "policy_reason": capability_policy_reason,
                }
            )
            if capability_approval_status != "pending":
                request_enabled = approvals_request_allowed and can(role, "approvals.request")
                request_policy_reason = (
                    ""
                    if request_enabled
                    else approvals_request_scope_reason
                    if not approvals_request_allowed
                    else f"RBAC denied: role={role}, action=approvals.request"
                )
                usage_chip_defs.append(
                    {
                        "kind": "forge.promote.request_approval",
                        "label": "Request Promotion Approval",
                        "enabled": request_enabled,
                        "reason": capability_reason,
                        "risk_tier": capability_risk,
                        "trust_badge": "Likely",
                        "args": {"stage_id": capability_stage_id},
                        "policy_reason": request_policy_reason,
                    }
                )
    if next_best_action:
        next_kind = str(next_best_action.get("kind", "")).strip().lower()
        if next_kind and not any(str(item.get("kind", "")).strip().lower() == next_kind for item in usage_chip_defs):
            usage_chip_defs.insert(
                0,
                {
                    "kind": next_kind,
                    "label": str(next_best_action.get("label", next_kind)).strip() or next_kind,
                    "enabled": bool(next_best_action.get("enabled", True)),
                    "reason": str(next_best_action.get("reason", "")).strip(),
                    "risk_tier": str(next_best_action.get("risk_tier", "low")).strip().lower() or "low",
                    "trust_badge": str(next_best_action.get("trust_badge", "Likely")).strip() or "Likely",
                    "args": next_best_action.get("args", {}) if isinstance(next_best_action.get("args"), dict) else {},
                    "policy_reason": str(next_best_action.get("policy_reason", "")).strip(),
                },
            )
    existing_usage_kinds = {str(chip.get("kind", "")).strip().lower() for chip in action_chips}
    usage_chips = [
        _usage_action_chip(
            kind=str(item.get("kind", "")).strip().lower(),
            label=str(item.get("label", "")).strip() or str(item.get("kind", "")).strip(),
            enabled=bool(item.get("enabled", False)),
            reason=str(item.get("reason", "")).strip(),
            risk_tier=str(item.get("risk_tier", "low")).strip().lower() or "low",
            trust_badge=str(item.get("trust_badge", "Likely")).strip() or "Likely",
            args=item.get("args", {}) if isinstance(item.get("args"), dict) else {},
            policy_reason=str(item.get("policy_reason", "")).strip(),
            requires_confirmation=bool(item.get("requires_confirmation", False)),
        )
        for item in usage_chip_defs
        if str(item.get("kind", "")).strip().lower() not in existing_usage_kinds
    ]
    action_chips = usage_chips + action_chips

    mode = str(control.get("mode", "observe")).strip().lower()
    kill_switch = bool(control.get("kill_switch", False))
    takeover_state = control_takeover_state().get("takeover", {})
    takeover_status = str(takeover_state.get("status", "idle")).strip().lower() or "idle"
    takeover_session_id = str(takeover_state.get("session_id") or "").strip()
    takeover_last_session_id = str(takeover_state.get("last_session_id") or "").strip()
    takeover_sessions_payload = control_takeover_sessions(limit=5)
    takeover_sessions_rows = takeover_sessions_payload.get("sessions", [])
    latest_handback_posture = next(
        (
            row.get("handback_fabric_posture", {})
            for row in takeover_sessions_rows
            if str(row.get("session_id", "")).strip() == takeover_last_session_id
            and isinstance(row.get("handback_fabric_posture"), dict)
        ),
        {},
    )
    handback_trust_badge = str(latest_handback_posture.get("trust", "Likely")).strip() or "Likely"
    remote_read_allowed = can(role, "control.remote.read") and can(role, "approvals.read")
    remote_write_allowed = can(role, "control.remote.write")
    remote_decide_allowed = remote_write_allowed and can(role, "approvals.decide")
    apprenticeship = summarize_apprenticeship(_fs, limit=3)
    remote_pending_rows: list[dict[str, Any]] = []
    try:
        remote_approvals = control_remote_approvals(request, status="pending", limit=3)
        remote_pending_rows = [
            row for row in remote_approvals.get("approvals", []) if isinstance(row, dict)
        ]
    except HTTPException:
        remote_pending_rows = []
    action_chips.append(
        _with_execute_hint(
            {
            "kind": "control.panic" if not kill_switch else "control.resume",
            "label": "Panic Stop (Kill Switch)" if not kill_switch else "Resume Mutations",
            "enabled": True,
            "reason": (
                "Instantly block all mutating actions."
                if not kill_switch
                else "Kill switch is active; resume mutating actions when ready."
            ),
            "policy_reason": "",
            "risk_tier": "high" if not kill_switch else "medium",
            "trust_badge": "Confirmed",
            "requires_confirmation": True,
            "mode": mode,
            }
        )
    )
    remote_control_chip = _with_execute_hint(
        {
        "kind": "control.remote.panic" if not kill_switch else "control.remote.resume",
        "label": "Remote Panic Stop" if not kill_switch else "Remote Resume Mutations",
        "enabled": remote_write_allowed,
        "reason": (
            "Trigger kill switch through the remote control plane."
            if not kill_switch
            else "Resume mutating actions through the remote control plane."
        ),
        "policy_reason": "" if remote_write_allowed else f"RBAC denied: role={role}, action=control.remote.write",
        "risk_tier": "high" if not kill_switch else "medium",
        "trust_badge": "Confirmed",
        "requires_confirmation": True,
        }
    )
    if takeover_session_id:
        remote_control_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_session_id
    action_chips.append(remote_control_chip)
    action_chips.append(
        _with_execute_hint(
            {
            "kind": "control.remote.state",
            "label": "Remote Snapshot",
            "enabled": remote_read_allowed,
            "reason": "Fetch compact control/takeover/approvals state for remote steering.",
            "policy_reason": "" if remote_read_allowed else f"RBAC denied: role={role}, action=control.remote.read",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
    )
    if remote_pending_rows:
        approvals_chip = _with_execute_hint(
            {
            "kind": "control.remote.approvals",
            "label": "Review Pending Approvals",
            "enabled": remote_read_allowed,
            "reason": f"{len(remote_pending_rows)} pending approval(s) available.",
            "policy_reason": "" if remote_read_allowed else f"RBAC denied: role={role}, action=control.remote.read",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        approvals_chip["execute_via"]["payload"]["args"]["status"] = "pending"
        action_chips.append(approvals_chip)
        remote_feed_chip = _with_execute_hint(
            {
            "kind": "control.remote.feed",
            "label": "Remote Feed",
            "enabled": remote_read_allowed,
            "reason": "Stream recent remote control and takeover events with receipts.",
            "policy_reason": "" if remote_read_allowed else f"RBAC denied: role={role}, action=control.remote.read",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        action_chips.append(remote_feed_chip)
        first_pending_id = str(remote_pending_rows[0].get("id", "")).strip()
        if first_pending_id:
            approve_chip = _with_execute_hint(
                {
                "kind": "control.remote.approval.approve",
                "label": "Approve Top Request",
                "enabled": remote_decide_allowed,
                "reason": f"Approve request {first_pending_id[:8]}... from Lens.",
                "policy_reason": (
                    "" if remote_decide_allowed else f"RBAC denied: role={role}, action=approvals.decide"
                ),
                "risk_tier": "low",
                "trust_badge": "Likely" if remote_decide_allowed else "Uncertain",
                "requires_confirmation": True,
                }
            )
            approve_chip["execute_via"]["payload"]["args"]["approval_id"] = first_pending_id
            action_chips.append(approve_chip)
            reject_chip = _with_execute_hint(
                {
                "kind": "control.remote.approval.reject",
                "label": "Reject Top Request",
                "enabled": remote_decide_allowed,
                "reason": f"Reject request {first_pending_id[:8]}... from Lens.",
                "policy_reason": (
                    "" if remote_decide_allowed else f"RBAC denied: role={role}, action=approvals.decide"
                ),
                "risk_tier": "low",
                "trust_badge": "Likely" if remote_decide_allowed else "Uncertain",
                "requires_confirmation": True,
                }
            )
            reject_chip["execute_via"]["payload"]["args"]["approval_id"] = first_pending_id
            action_chips.append(reject_chip)

    review_ready_sessions = [
        row for row in apprenticeship.get("review_ready", []) if isinstance(row, dict)
    ]
    recording_sessions = [
        row
        for row in apprenticeship.get("recent_sessions", [])
        if isinstance(row, dict)
        and str(row.get("status", "")).strip().lower() == "recording"
        and int(row.get("step_count", 0)) > 0
    ]
    if recording_sessions:
        session = recording_sessions[0]
        allowed_by_scope, scope_reason, _ = check_action_allowed(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            app="apprenticeship",
            action="apprenticeship.generalize",
            mutating=True,
        )
        allowed_by_rbac = can(role, "apprenticeship.generalize")
        enabled = allowed_by_scope and allowed_by_rbac
        policy_reason = ""
        if not enabled:
            policy_reason = scope_reason if not allowed_by_scope else f"RBAC denied: role={role}, action=apprenticeship.generalize"
        chip = _with_execute_hint(
            {
                "kind": "apprenticeship.generalize",
                "label": "Generalize Teaching Session",
                "enabled": enabled,
                "reason": (
                    f"{str(session.get('title', 'Teaching session')).strip()} has "
                    f"{int(session.get('step_count', 0))} demonstrated step(s) ready for review."
                ),
                "policy_reason": policy_reason,
                "risk_tier": "low",
                "trust_badge": "Confirmed" if enabled else "Uncertain",
            }
        )
        chip["execute_via"]["payload"]["args"]["session_id"] = str(session.get("id", "")).strip()
        action_chips.append(chip)

    if review_ready_sessions:
        session = review_ready_sessions[0]
        allowed_by_scope, scope_reason, _ = check_action_allowed(
            _fs,
            repo_root=_repo_root,
            workspace_root=_workspace_root,
            app="apprenticeship",
            action="apprenticeship.skillize",
            mutating=True,
        )
        allowed_by_rbac = can(role, "apprenticeship.skillize")
        enabled = allowed_by_scope and allowed_by_rbac
        policy_reason = ""
        if not enabled:
            policy_reason = scope_reason if not allowed_by_scope else f"RBAC denied: role={role}, action=apprenticeship.skillize"
        chip = _with_execute_hint(
            {
                "kind": "apprenticeship.skillize",
                "label": "Skillize Teaching Session",
                "enabled": enabled,
                "reason": f"{str(session.get('title', 'Teaching session')).strip()} is ready to stage into Forge.",
                "policy_reason": policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if enabled else "Uncertain",
                "requires_confirmation": True,
            }
        )
        chip["execute_via"]["payload"]["args"]["session_id"] = str(session.get("id", "")).strip()
        action_chips.append(chip)
    if takeover_status == "active":
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.takeover.handback",
                "label": "Hand Back Pilot Control",
                "enabled": True,
                "reason": "Takeover is active; return control with summary and receipts.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Likely",
                "requires_confirmation": True,
                }
            )
        )
        remote_handback_chip = _with_execute_hint(
            {
            "kind": "control.remote.takeover.handback",
            "label": "Remote Handback Control",
            "enabled": remote_write_allowed,
            "reason": "Complete takeover handback through the remote command plane.",
            "policy_reason": "" if remote_write_allowed else f"RBAC denied: role={role}, action=control.remote.write",
            "risk_tier": "low",
            "trust_badge": "Likely" if remote_write_allowed else "Uncertain",
            "requires_confirmation": True,
            }
        )
        if takeover_session_id:
            remote_handback_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_session_id
        action_chips.append(remote_handback_chip)
    elif takeover_status == "requested":
        confirmation_enabled = not kill_switch
        confirmation_policy = ""
        if kill_switch:
            confirmation_policy = "kill switch active; resume before confirming takeover"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.takeover.confirm",
                "label": "Confirm Pilot Takeover",
                "enabled": confirmation_enabled,
                "reason": "Takeover request is pending explicit confirmation.",
                "policy_reason": confirmation_policy,
                "risk_tier": "medium",
                "trust_badge": "Likely" if confirmation_enabled else "Uncertain",
                "requires_confirmation": True,
                }
            )
        )
        remote_confirm_chip = _with_execute_hint(
            {
            "kind": "control.remote.takeover.confirm",
            "label": "Remote Confirm Takeover",
            "enabled": confirmation_enabled and remote_write_allowed,
            "reason": "Confirm takeover via remote command plane.",
            "policy_reason": (
                f"RBAC denied: role={role}, action=control.remote.write"
                if not remote_write_allowed
                else confirmation_policy
            ),
            "risk_tier": "medium",
            "trust_badge": "Likely" if confirmation_enabled and remote_write_allowed else "Uncertain",
            "requires_confirmation": True,
            }
        )
        if takeover_session_id:
            remote_confirm_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_session_id
        action_chips.append(remote_confirm_chip)
    else:
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.takeover.request",
                "label": "Request Pilot Takeover",
                "enabled": True,
                "reason": "Start explicit takeover handshake with scoped objective.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                "requires_confirmation": True,
                }
            )
        )
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "control.remote.takeover.request",
                "label": "Remote Request Takeover",
                "enabled": remote_write_allowed,
                "reason": "Start takeover handshake through remote command plane.",
                "policy_reason": "" if remote_write_allowed else f"RBAC denied: role={role}, action=control.remote.write",
                "risk_tier": "low",
                "trust_badge": "Confirmed" if remote_write_allowed else "Uncertain",
                "requires_confirmation": True,
                }
            )
        )

    activity_session_id = takeover_session_id or takeover_last_session_id
    sessions_chip = _with_execute_hint(
        {
        "kind": "control.takeover.sessions",
        "label": "Browse Takeover Sessions",
        "enabled": True,
        "reason": "Inspect recent takeover sessions and handback outcomes.",
        "policy_reason": "",
        "risk_tier": "low",
        "trust_badge": "Confirmed",
        }
    )
    sessions_chip["execute_via"]["payload"]["args"]["limit"] = 20
    action_chips.append(sessions_chip)
    if activity_session_id:
        activity_chip = _with_execute_hint(
            {
            "kind": "control.takeover.activity",
            "label": "View Takeover Activity",
            "enabled": True,
            "reason": "Review the latest takeover session action feed.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        activity_chip["execute_via"]["payload"]["args"]["session_id"] = activity_session_id
        action_chips.append(activity_chip)
        session_chip = _with_execute_hint(
            {
            "kind": "control.takeover.session",
            "label": "Open Current Session",
            "enabled": True,
            "reason": "Load full session timeline, receipts, and exports.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": "Confirmed",
            }
        )
        session_chip["execute_via"]["payload"]["args"]["session_id"] = activity_session_id
        action_chips.append(session_chip)
    elif takeover_sessions_rows:
        latest_session_id = str(takeover_sessions_rows[0].get("session_id", "")).strip()
        if latest_session_id:
            latest_chip = _with_execute_hint(
                {
                "kind": "control.takeover.session",
                "label": "Open Latest Session",
                "enabled": True,
                "reason": "Review the latest session timeline and receipts.",
                "policy_reason": "",
                "risk_tier": "low",
                "trust_badge": "Confirmed",
                }
            )
            latest_chip["execute_via"]["payload"]["args"]["session_id"] = latest_session_id
            action_chips.append(latest_chip)
    if takeover_last_session_id:
        package_chip = _with_execute_hint(
            {
            "kind": "control.takeover.handback.package",
            "label": "Open Handback Package",
            "enabled": True,
            "reason": "Load the latest handback receipts bundle for review.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": handback_trust_badge,
            }
        )
        package_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_last_session_id
        action_chips.append(package_chip)
        export_chip = _with_execute_hint(
            {
            "kind": "control.takeover.handback.export",
            "label": "Export Handback Bundle",
            "enabled": True,
            "reason": "Write a durable handback bundle to workspace/control/handback_exports.",
            "policy_reason": "",
            "risk_tier": "low",
            "trust_badge": handback_trust_badge,
            }
        )
        export_chip["execute_via"]["payload"]["args"]["session_id"] = takeover_last_session_id
        action_chips.append(export_chip)

    if autonomy_queued_count > 0:
        dispatch_enabled = mode in {"pilot", "away"}
        policy_reason = ""
        if not dispatch_enabled:
            policy_reason = f"mutating action autonomy.dispatch not allowed in {mode} mode"
        elif autonomy_high_risk_due > 0:
            policy_reason = "approval required for queued high-risk autonomy events"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.dispatch",
                "label": "Dispatch Autonomy Events",
                "enabled": dispatch_enabled,
                "reason": f"{autonomy_queued_count} queued autonomy event(s)",
                "policy_reason": policy_reason,
                "risk_tier": "medium" if autonomy_high_risk_due == 0 else "high",
                "trust_badge": trust_badge(
                    confidence=str(dispatch_verification.get("confidence", "")),
                    can_claim_done=bool(dispatch_verification.get("can_claim_done", False)),
                ),
                "queue_telemetry": {
                    "queued_count": autonomy_queued_count,
                    "high_risk_due_count": autonomy_high_risk_due,
                    "last_halted_reason": dispatch_halted_reason or None,
                    "last_max_dispatch_actions": int(last_dispatch_config.get("max_dispatch_actions", 0)),
                    "last_max_dispatch_runtime_seconds": int(last_dispatch_config.get("max_dispatch_runtime_seconds", 0)),
                    "last_verification_status": dispatch_verification.get("verification_status"),
                    "last_confidence": dispatch_verification.get("confidence"),
                    "last_can_claim_done": bool(dispatch_verification.get("can_claim_done", False)),
                    "last_completion_state": autonomy_last_dispatch.get("completion_state"),
                },
                }
            )
        )
    if autonomy_leased_expired_count > 0:
        recover_enabled = mode in {"pilot", "away"}
        recover_policy_reason = ""
        if not recover_enabled:
            recover_policy_reason = f"mutating action autonomy.recover not allowed in {mode} mode"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.recover",
                "label": "Recover Stale Autonomy Leases",
                "enabled": recover_enabled,
                "reason": f"{autonomy_leased_expired_count} stale leased autonomy event(s)",
                "policy_reason": recover_policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if recover_enabled else "Uncertain",
                "queue_telemetry": {
                    "leased_expired_count": autonomy_leased_expired_count,
                },
                }
            )
        )
    if tick_halted_reason or autonomy_retry_pressure > 0 or guardrail_cooldown_active:
        tick_enabled = mode in {"pilot", "away"}
        tick_policy_reason = ""
        if not tick_enabled:
            tick_policy_reason = f"mutating action autonomy.reactor.tick not allowed in {mode} mode"
        elif guardrail_cooldown_active:
            tick_policy_reason = (
                "guardrail cooldown active; dispatch will remain suppressed until cooldown clears"
            )
        risk_tier = "high" if tick_halted_reason in {"critical_incident_present", "critical_anomaly"} else "medium"
        reason_parts: list[str] = []
        if tick_halted_reason:
            reason_parts.append(f"last tick halted: {tick_halted_reason}")
        if autonomy_retry_pressure > 0:
            reason_parts.append(f"{autonomy_retry_pressure} queued retry event(s)")
        if guardrail_cooldown_active:
            reason_parts.append(f"cooldown active ({guardrail_cooldown_remaining} tick(s) remaining)")
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.reactor.tick",
                "label": "Run Reactor Tick",
                "enabled": tick_enabled,
                "reason": "; ".join(reason_parts) if reason_parts else "reactor health check",
                "policy_reason": tick_policy_reason,
                "risk_tier": risk_tier,
                "trust_badge": trust_badge(
                    confidence=str(tick_verification.get("confidence", "")),
                    can_claim_done=bool(tick_verification.get("can_claim_done", False)),
                ),
                "queue_telemetry": {
                    "queued_retry_count": autonomy_retry_pressure,
                    "last_tick_halted_reason": tick_halted_reason or None,
                    "guardrail_cooldown_active": guardrail_cooldown_active,
                    "guardrail_cooldown_remaining_ticks": guardrail_cooldown_remaining,
                    "guardrail_escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                    "last_tick_verification_status": tick_verification.get("verification_status"),
                    "last_tick_confidence": tick_verification.get("confidence"),
                    "last_tick_can_claim_done": bool(tick_verification.get("can_claim_done", False)),
                    "last_tick_completion_state": autonomy_last_tick.get("completion_state"),
                    "last_tick_processed_count": int(tick_dispatch.get("processed_count", 0)),
                    "last_tick_failed_count": int(tick_dispatch.get("failed_count", 0)),
                    "last_tick_retried_count": int(tick_dispatch.get("retried_count", 0)),
                    "last_tick_released_count": int(tick_dispatch.get("released_count", 0)),
                },
                }
            )
        )
    if guardrail_cooldown_active:
        reset_enabled = mode == "pilot"
        reset_policy_reason = ""
        if not reset_enabled:
            reset_policy_reason = "manual guardrail reset requires pilot mode"
        action_chips.append(
            _with_execute_hint(
                {
                "kind": "autonomy.reactor.guardrail.reset",
                "label": "Reset Reactor Cooldown",
                "enabled": reset_enabled,
                "reason": f"cooldown active ({guardrail_cooldown_remaining} tick(s) remaining)",
                "policy_reason": reset_policy_reason,
                "risk_tier": "low",
                "trust_badge": "Likely" if reset_enabled else "Uncertain",
                "queue_telemetry": {
                    "guardrail_cooldown_active": guardrail_cooldown_active,
                    "guardrail_cooldown_remaining_ticks": guardrail_cooldown_remaining,
                    "guardrail_escalations_count": int(autonomy_guardrail.get("escalations_count", 0)),
                },
                }
            )
        )

    return {
        "status": "ok",
        "mode": control.get("mode"),
        "current_work": current_work,
        "next_best_action": next_best_action,
        "action_chips": action_chips,
        "selected_actions": selected_actions,
        "blocked_actions": blocked_actions,
    }


@router.post("/lens/actions/execute")
def lens_execute_action(request: Request, payload: LensExecuteRequest) -> dict:
    run_id = str(getattr(request.state, "run_id", uuid4()))
    trace_id = _normalize_trace_id(getattr(request.state, "trace_id", None), fallback_run_id=run_id)
    role = _role_from_request(request)
    kind = str(payload.kind).strip().lower()
    args = payload.args if isinstance(payload.args, dict) else {}
    dry_run = bool(payload.dry_run)
    assessment = assess_untrusted_input(
        surface="lens",
        action=kind or "lens.actions.execute",
        payload={"kind": kind, "args": args},
        inspect_paths=True,
    )
    if assessment["quarantined"]:
        quarantine = quarantine_untrusted_input(
            _fs,
            run_id=run_id,
            trace_id=trace_id,
            surface="lens",
            action=kind or "lens.actions.execute",
            payload={"kind": kind, "args": args},
            assessment=assessment,
        )
        _record_lens_execution(
            run_id=run_id,
            trace_id=trace_id,
            role=role,
            action_kind=kind,
            dry_run=dry_run,
            ok=False,
            detail={"status": "quarantined", "quarantine_id": quarantine["id"], "categories": quarantine["categories"]},
        )
        raise HTTPException(status_code=409, detail={"message": assessment["message"], "quarantine": quarantine})

    try:
        result = _execute_lens_action(
            request=request,
            kind=kind,
            args=args,
            dry_run=dry_run,
            run_id=run_id,
            trace_id=trace_id,
            role=role,
        )
    except HTTPException as exc:
        _record_lens_execution(
            run_id=run_id,
            trace_id=trace_id,
            role=role,
            action_kind=kind,
            dry_run=dry_run,
            ok=False,
            detail={"status": "error", "error": exc.detail, "status_code": exc.status_code},
        )
        raise
    except Exception as exc:
        _record_lens_execution(
            run_id=run_id,
            trace_id=trace_id,
            role=role,
            action_kind=kind,
            dry_run=dry_run,
            ok=False,
            detail={"status": "error", "error": str(exc), "status_code": 500},
        )
        raise HTTPException(status_code=500, detail=f"Lens action execution failed: {exc}")

    _record_lens_execution(
        run_id=run_id,
        trace_id=trace_id,
        role=role,
        action_kind=kind,
        dry_run=dry_run,
        ok=True,
        detail={
            "status": str(result.get("status", "ok")),
            "kind": kind,
            "summary": str(result.get("summary", "")).strip(),
            "presentation": result.get("presentation", {}) if isinstance(result.get("presentation"), dict) else {},
            "tool": result.get("tool", {}) if isinstance(result.get("tool"), dict) else {},
            "execution_args": result.get("execution_args", {}) if isinstance(result.get("execution_args"), dict) else {},
        },
    )
    return {
        "status": "ok" if not dry_run else "dry_run",
        "run_id": run_id,
        "trace_id": trace_id,
        "action": {"kind": kind, "dry_run": dry_run, "args": args},
        "result": result,
    }
