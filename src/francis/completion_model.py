from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

COMPLETION_MODEL_STATUS_KIND = "francis.completion_model.status"
COMPLETION_LEDGER_RELATIVE_PATH = "docs/operations/COMPLETION_LEDGER.md"
BUILD_MANIFEST_RELATIVE_PATH = "docs/canonical/BUILD_MANIFEST.md"


def completion_model_status_snapshot(
    *,
    ledger_path: Path | None = None,
    build_manifest_path: Path | None = None,
) -> dict[str, Any]:
    root = repo_root()
    resolved_ledger_path = ledger_path or root / COMPLETION_LEDGER_RELATIVE_PATH
    resolved_build_manifest_path = build_manifest_path or root / BUILD_MANIFEST_RELATIVE_PATH
    ledger_text = _read_text(resolved_ledger_path)
    build_manifest_text = _read_text(resolved_build_manifest_path)
    ledger_exists = resolved_ledger_path.is_file()
    build_manifest_exists = resolved_build_manifest_path.is_file()
    latest_ledger_entry = _latest_ledger_entry(ledger_text)
    stage17_status = _stage17_status(ledger_text)
    loop_guard = _loop_guard(
        ledger_exists=ledger_exists,
        build_manifest_exists=build_manifest_exists,
        latest_ledger_entry=latest_ledger_entry,
    )
    next_continue_decision = _next_continue_decision(
        loop_guard=loop_guard,
        latest_ledger_entry=latest_ledger_entry,
        stage17_status=stage17_status,
    )

    return {
        "ok": ledger_exists and build_manifest_exists,
        "kind": COMPLETION_MODEL_STATUS_KIND,
        "status": "ready" if ledger_exists and build_manifest_exists else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only_contract": True,
        "writes_repo": False,
        "writes_data": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "source_documents": {
            "completion_ledger": COMPLETION_LEDGER_RELATIVE_PATH,
            "build_manifest": BUILD_MANIFEST_RELATIVE_PATH,
        },
        "current_phase": _current_phase(ledger_text=ledger_text, build_manifest_text=build_manifest_text),
        "plane_readiness_snapshot": _plane_readiness_snapshot(build_manifest_text),
        "latest_ledger_entry": latest_ledger_entry,
        "stage17_status": stage17_status,
        "completion_percentage_model": _completion_percentage_model(),
        "continue_loop_guard": loop_guard,
        "routes": {
            "status": "/completion-model/status",
        },
        "next_continue_decision": next_continue_decision,
    }


def _next_continue_decision(
    *,
    loop_guard: dict[str, Any],
    latest_ledger_entry: dict[str, Any],
    stage17_status: dict[str, Any],
) -> dict[str, Any]:
    selected_source = "none"
    selected_title = ""
    selected_roadmap_area = ""
    stage17_gap_preferred = False
    next_gap = "name_remaining_truthful_gap_in_ledger"

    if loop_guard["status"] != "ready":
        selected_source = "completion_model_sources"
        next_gap = "restore_completion_model_sources"
    else:
        stage17_entry = stage17_status.get("latest_ledger_entry")
        if (
            stage17_status.get("found") is True
            and stage17_status.get("status") == "open"
            and isinstance(stage17_entry, dict)
            and stage17_entry.get("has_remaining_truthful_gap") is True
        ):
            selected_source = "stage17_latest_ledger_entry"
            selected_title = str(stage17_entry.get("title", ""))
            selected_roadmap_area = str(stage17_entry.get("roadmap_area", ""))
            stage17_gap_preferred = True
            next_gap = str(stage17_entry.get("remaining_truthful_gap", ""))
        elif latest_ledger_entry["has_remaining_truthful_gap"]:
            selected_source = "latest_ledger_entry"
            selected_title = str(latest_ledger_entry["title"])
            selected_roadmap_area = str(latest_ledger_entry["roadmap_area"])
            next_gap = str(latest_ledger_entry["remaining_truthful_gap"])

    return {
        "status": "bounded_slice_required" if loop_guard["status"] == "ready" else "blocked_until_model_sources_exist",
        "rule": (
            "On continue, preserve dirty work, choose one remaining truthful gap, state plan, "
            "implement the smallest coherent change, validate, then update the ledger."
        ),
        "selected_gap_source": selected_source,
        "selected_ledger_title": selected_title,
        "selected_roadmap_area": selected_roadmap_area,
        "stage17_gap_preferred": stage17_gap_preferred,
        "next_smallest_truthful_gap": next_gap,
    }


def _read_text(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""


def _current_phase(*, ledger_text: str, build_manifest_text: str) -> str:
    from_ledger = _first_match(ledger_text, r"Francis is in `(?P<phase>Phase \d+)`", "phase")
    if from_ledger:
        return from_ledger
    return _first_match(build_manifest_text, r"\((?P<phase>Phase \d+)\)", "phase")


def _plane_readiness_snapshot(build_manifest_text: str) -> list[dict[str, str]]:
    return [
        {"plane": match.group("plane").strip(), "status": match.group("status").strip()}
        for match in re.finditer(r"(?m)^- `(?P<plane>P\d+_[A-Z_]+)`:\s*(?P<status>[^\r\n]+)$", build_manifest_text)
    ]


def _latest_ledger_entry(ledger_text: str) -> dict[str, Any]:
    body = ledger_text
    update_rule_index = body.find("\n## 6. Update rule")
    if update_rule_index >= 0:
        body = body[:update_rule_index]
    matches = list(re.finditer(r"(?m)^### (?P<title>.+)$", body))
    if not matches:
        return {
            "found": False,
            "title": "",
            "roadmap_area": "",
            "remaining_truthful_gap": "",
            "has_remaining_truthful_gap": False,
        }
    latest = matches[-1]
    entry_text = body[latest.start() :].strip()
    remaining_gap = _first_match(entry_text, r"(?s)Remaining truthful gap:\s*(?P<gap>.+)$", "gap")
    return {
        "found": True,
        "title": latest.group("title").strip(),
        "roadmap_area": _labeled_paragraph(entry_text, "Roadmap area"),
        "remaining_truthful_gap": _limit_text(remaining_gap, max_length=700),
        "has_remaining_truthful_gap": bool(remaining_gap.strip()),
    }


def _stage17_status(ledger_text: str) -> dict[str, Any]:
    body = ledger_text
    update_rule_index = body.find("\n## 6. Update rule")
    if update_rule_index >= 0:
        body = body[:update_rule_index]

    matches = list(re.finditer(r"(?m)^### (?P<title>.+)$", body))
    latest_stage17_entry: dict[str, Any] | None = None
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        entry_text = body[match.start() : next_start].strip()
        title = match.group("title").strip()
        roadmap_area = _labeled_paragraph(entry_text, "Roadmap area")
        if not _is_stage17_ledger_entry(title=title, roadmap_area=roadmap_area):
            continue
        remaining_gap = _first_match(entry_text, r"(?s)Remaining truthful gap:\s*(?P<gap>.+)$", "gap")
        latest_stage17_entry = {
            "found": True,
            "title": title,
            "roadmap_area": roadmap_area,
            "remaining_truthful_gap": _limit_text(remaining_gap, max_length=700),
            "has_remaining_truthful_gap": bool(remaining_gap.strip()),
        }

    if latest_stage17_entry is None:
        return {
            "found": False,
            "status": "unknown",
            "readback_scope": "latest_stage17_ledger_entry",
            "read_only_contract": True,
            "writes_repo": False,
            "writes_data": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "latest_ledger_entry": {
                "found": False,
                "title": "",
                "roadmap_area": "",
                "remaining_truthful_gap": "",
                "has_remaining_truthful_gap": False,
            },
            "next_smallest_truthful_gap": "name_stage17_remaining_truthful_gap_in_ledger",
        }

    status = "open" if _text_says_stage17_open(str(latest_stage17_entry["remaining_truthful_gap"])) else "review"
    return {
        "found": True,
        "status": status,
        "readback_scope": "latest_stage17_ledger_entry",
        "read_only_contract": True,
        "writes_repo": False,
        "writes_data": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "latest_ledger_entry": latest_stage17_entry,
        "next_smallest_truthful_gap": "select_from_latest_stage17_remaining_truthful_gap"
        if latest_stage17_entry["has_remaining_truthful_gap"]
        else "name_stage17_remaining_truthful_gap_in_ledger",
    }


def _is_stage17_ledger_entry(*, title: str, roadmap_area: str) -> bool:
    title_key = title.casefold()
    roadmap_key = roadmap_area.casefold()
    title_is_stage17_slice = title_key.startswith("stage 17 ") or " - stage 17 " in title_key
    return title_is_stage17_slice or roadmap_key.startswith("stage 17 /")


def _text_says_stage17_open(text: str) -> bool:
    key = text.casefold()
    return "stage 17 remains open" in key or "stage 17 still needs" in key


def _loop_guard(
    *,
    ledger_exists: bool,
    build_manifest_exists: bool,
    latest_ledger_entry: dict[str, Any],
) -> dict[str, Any]:
    checklist = [
        {
            "id": "ledger_read",
            "status": "ready" if ledger_exists else "blocked",
            "required_before_continue": True,
            "evidence": COMPLETION_LEDGER_RELATIVE_PATH,
        },
        {
            "id": "build_manifest_read",
            "status": "ready" if build_manifest_exists else "blocked",
            "required_before_continue": True,
            "evidence": BUILD_MANIFEST_RELATIVE_PATH,
        },
        {
            "id": "latest_validated_slice_identified",
            "status": "ready" if latest_ledger_entry["found"] else "blocked",
            "required_before_continue": True,
            "evidence": str(latest_ledger_entry["title"]),
        },
        {
            "id": "remaining_gap_named",
            "status": "ready" if latest_ledger_entry["has_remaining_truthful_gap"] else "needs_review",
            "required_before_continue": True,
            "evidence": str(latest_ledger_entry["remaining_truthful_gap"]),
        },
        {
            "id": "percentage_movement_guard",
            "status": "enforced",
            "required_before_continue": True,
            "evidence": "percentages require baseline, validated gate movement, and remaining blockers",
        },
        {
            "id": "single_bounded_slice_guard",
            "status": "enforced",
            "required_before_continue": True,
            "evidence": "continue should pick one roadmap-aligned slice, validate it, then ledger it",
        },
    ]
    blocked_count = sum(1 for item in checklist if item["status"] == "blocked")
    return {
        "status": "ready" if blocked_count == 0 else "blocked",
        "blocked_count": blocked_count,
        "checklist": checklist,
    }


def _completion_percentage_model() -> dict[str, Any]:
    return {
        "status": "evidence_gated",
        "numeric_baseline_declared_here": False,
        "overall_project_percent": None,
        "current_build_phase_percent": None,
        "current_task_percent": None,
        "movement_allowed_by_this_readback": False,
        "required_to_move": [
            "known_baseline_source",
            "validated_repo_evidence",
            "ledger_backed_gate_or_milestone_change",
            "explicit_remaining_blockers",
        ],
        "rule": (
            "Do not move overall Francis or build-phase percentages from effort, elapsed time, "
            "runtime-only success, or documentation-only changes."
        ),
    }


def _first_match(text: str, pattern: str, group_name: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(group_name).strip()


def _labeled_paragraph(text: str, label: str) -> str:
    prefix = f"{label}:".casefold()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.casefold().startswith(prefix):
            continue
        parts = [stripped[len(prefix) :].strip()]
        for continuation in lines[index + 1 :]:
            if not continuation.strip():
                break
            parts.append(continuation.strip())
        return _limit_text(" ".join(part for part in parts if part), max_length=700)
    return ""


def _limit_text(text: str, *, max_length: int) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[:max_length].strip() + "..."
