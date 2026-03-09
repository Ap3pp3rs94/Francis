from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.redaction import redact
from francis_core.workspace_fs import WorkspaceFS

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore\b.{0,48}\b(previous|prior|all)\b.{0,48}\b(instructions?|prompts?|rules?)\b", re.IGNORECASE),
    re.compile(r"\b(system prompt|developer message|hidden instructions?)\b", re.IGNORECASE),
    re.compile(r"\b(act as|pretend to be)\b.{0,32}\b(system|developer|root|admin)\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
)
POLICY_BYPASS_PATTERNS = (
    re.compile(r"\b(bypass|override|disable|ignore)\b.{0,40}\b(approval|policy|rbac|guardrail|kill switch|scope)\b", re.IGNORECASE),
    re.compile(r"\bwithout approval\b", re.IGNORECASE),
    re.compile(r"\boutside\b.{0,24}\b(scope|policy)\b", re.IGNORECASE),
    re.compile(r"\b(escalate privileges?|grant yourself access)\b", re.IGNORECASE),
)
DESTRUCTIVE_PATTERNS = (
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bdel\s+/[a-z]+\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:\b", re.IGNORECASE),
    re.compile(r"\bpowershell\s+-enc\b", re.IGNORECASE),
)
PATH_ESCAPE_PATTERN = re.compile(r"(^|[\\/])\.\.([\\/]|$)")
ABSOLUTE_WINDOWS_PATH_PATTERN = re.compile(r"^[a-z]:[\\/]", re.IGNORECASE)
ABSOLUTE_POSIX_PATH_PATTERN = re.compile(r"^/")
PATH_FIELD_NAMES = {"path", "target"}


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


def _payload_excerpt(payload: Any, *, limit: int = 360) -> str:
    serialized = redact(json.dumps(payload, ensure_ascii=False, default=str))
    return serialized[:limit]


def _iter_string_fields(value: Any, *, path: str = "payload") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, str):
        rows.append((path, value))
        return rows
    if isinstance(value, Mapping):
        for key, item in value.items():
            rows.extend(_iter_string_fields(item, path=f"{path}.{key}"))
        return rows
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            rows.extend(_iter_string_fields(item, path=f"{path}[{index}]"))
    return rows


def assess_untrusted_input(
    *,
    surface: str,
    action: str,
    payload: Any,
    inspect_paths: bool = False,
) -> dict[str, Any]:
    markers: list[dict[str, str]] = []
    for field_path, value in _iter_string_fields(payload):
        normalized = " ".join(str(value).split())
        if not normalized:
            continue
        for category, patterns in (
            ("prompt_injection", PROMPT_INJECTION_PATTERNS),
            ("policy_bypass", POLICY_BYPASS_PATTERNS),
            ("destructive_command", DESTRUCTIVE_PATTERNS),
        ):
            for pattern in patterns:
                match = pattern.search(normalized)
                if match is None:
                    continue
                markers.append(
                    {
                        "category": category,
                        "path": field_path,
                        "evidence": redact(match.group(0))[:160],
                    }
                )
                break
        if inspect_paths:
            field_name = field_path.rsplit(".", 1)[-1]
            if "[" in field_name:
                field_name = field_name.split("[", 1)[0]
            if field_name not in PATH_FIELD_NAMES:
                continue
            path_value = normalized.strip()
            if PATH_ESCAPE_PATTERN.search(path_value) or ABSOLUTE_WINDOWS_PATH_PATTERN.search(path_value) or ABSOLUTE_POSIX_PATH_PATTERN.search(path_value):
                markers.append(
                    {
                        "category": "filesystem_escape",
                        "path": field_path,
                        "evidence": redact(path_value)[:160],
                    }
                )

    categories = sorted({marker["category"] for marker in markers})
    severity = "high" if any(category in {"filesystem_escape", "destructive_command", "policy_bypass"} for category in categories) else "medium"
    return {
        "surface": surface,
        "action": action,
        "quarantined": bool(markers),
        "severity": severity,
        "categories": categories,
        "markers": markers[:12],
        "message": (
            f"Suspicious untrusted input quarantined on {surface}:{action}."
            if markers
            else ""
        ),
    }


def quarantine_untrusted_input(
    fs: WorkspaceFS,
    *,
    run_id: str,
    trace_id: str,
    surface: str,
    action: str,
    payload: Any,
    assessment: dict[str, Any],
    ledger_rel_path: str = "runs/run_ledger.jsonl",
) -> dict[str, Any]:
    quarantine_id = str(uuid4())
    ts = utc_now_iso()
    summary = {
        "quarantine_id": quarantine_id,
        "surface": surface,
        "action": action,
        "severity": assessment.get("severity", "medium"),
        "categories": list(assessment.get("categories", [])),
        "markers": list(assessment.get("markers", [])),
        "payload_excerpt": _payload_excerpt(payload),
    }
    log_row = {
        "id": quarantine_id,
        "ts": ts,
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": "security.quarantine",
        **summary,
    }
    decision_row = {
        "id": str(uuid4()),
        "ts": ts,
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": "security.quarantine",
        "headline": assessment.get("message") or "Suspicious untrusted input quarantined.",
        **summary,
    }
    incident_row = {
        "id": str(uuid4()),
        "ts": ts,
        "run_id": run_id,
        "severity": assessment.get("severity", "medium"),
        "kind": "security.untrusted_input",
        "message": assessment.get("message") or "Suspicious untrusted input quarantined.",
        "evidence": summary,
        "status": "open",
    }

    _append_jsonl(fs, "security/quarantine.jsonl", log_row)
    _append_jsonl(fs, "logs/francis.log.jsonl", log_row)
    _append_jsonl(fs, "journals/decisions.jsonl", decision_row)
    _append_jsonl(fs, "incidents/incidents.jsonl", incident_row)
    RunLedger(fs, rel_path=ledger_rel_path).append(
        run_id=run_id,
        kind="security.quarantine",
        summary={
            "trace_id": trace_id,
            "surface": surface,
            "action": action,
            "severity": assessment.get("severity", "medium"),
            "categories": list(assessment.get("categories", [])),
            "quarantine_id": quarantine_id,
        },
    )
    return {
        "id": quarantine_id,
        "ts": ts,
        "status": "quarantined",
        "surface": surface,
        "action": action,
        "severity": assessment.get("severity", "medium"),
        "categories": list(assessment.get("categories", [])),
        "markers": list(assessment.get("markers", [])),
    }
