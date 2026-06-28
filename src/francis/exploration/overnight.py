from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from francis.governance.policy_engine import DECISION_ALLOWED, ToolCallPolicyRequest, evaluate_tool_call_policy
from francis.governance.redaction import redact_governed_value
from francis.kernel.paths import data_dir as francis_data_dir
from francis.kernel.paths import repo_root as francis_repo_root
from francis.telemetry.git import git_status_snapshot

RECEIPT_KIND = "francis.exploration.overnight.receipt"
SUMMARY_KIND = "francis.exploration.overnight.summary"
STATUS_KIND = "francis.exploration.overnight.status"
DEFAULT_DURATION_HOURS = 8.0
DEFAULT_INTERVAL_MINUTES = 20.0
DEFAULT_MAX_FINDINGS = 40
DEFAULT_MAX_SCAN_FILES = 900
MAX_SCAN_FILE_BYTES = 220_000
MAX_CYCLES = 200
ACTOR = "francis.overnight_explorer"

SCAN_ROOTS = (
    "docs",
    "src/francis",
    "tests",
    "scripts",
    "apps/chat_ui/src",
)
SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}
TEXT_SUFFIXES = {
    ".css",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
FINDING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("truth_gap", re.compile(r"\bnext_smallest_truthful_gap\b|remaining\s+truthful\s+gap", re.IGNORECASE)),
    ("blocked", re.compile(r"\bblocked\b|\bblocker\b|\brequires operator\b", re.IGNORECASE)),
    ("unsupported", re.compile(r"\bunsupported\b|\bunavailable\b|\bnot\s+yet\b", re.IGNORECASE)),
    ("todo", re.compile(r"\bTODO\b|\bFIXME\b", re.IGNORECASE)),
    ("fake_state_guard", re.compile(r"\bfake\b|\bmock-only\b|\bdemo-only\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class OvernightExplorerConfig:
    repo_root: Path
    data_root: Path
    actor: str = ACTOR
    session_id: str = ""
    duration_hours: float = DEFAULT_DURATION_HOURS
    interval_minutes: float = DEFAULT_INTERVAL_MINUTES
    max_findings: int = DEFAULT_MAX_FINDINGS
    max_scan_files: int = DEFAULT_MAX_SCAN_FILES
    max_cycles: int = MAX_CYCLES


def make_config(
    *,
    repo_root: str | Path | None = None,
    data_root: str | Path | None = None,
    actor: str = ACTOR,
    session_id: str = "",
    duration_hours: float = DEFAULT_DURATION_HOURS,
    interval_minutes: float = DEFAULT_INTERVAL_MINUTES,
    max_findings: int = DEFAULT_MAX_FINDINGS,
    max_scan_files: int = DEFAULT_MAX_SCAN_FILES,
    max_cycles: int = MAX_CYCLES,
) -> OvernightExplorerConfig:
    root = Path(repo_root).expanduser().resolve() if repo_root is not None else francis_repo_root()
    data = Path(data_root).expanduser().resolve() if data_root is not None else francis_data_dir()
    return OvernightExplorerConfig(
        repo_root=root,
        data_root=data,
        actor=_clean_token(actor) or ACTOR,
        session_id=_clean_token(session_id),
        duration_hours=_bounded_float(duration_hours, DEFAULT_DURATION_HOURS, minimum=0.01),
        interval_minutes=_bounded_float(interval_minutes, DEFAULT_INTERVAL_MINUTES, minimum=0.01),
        max_findings=_bounded_int(max_findings, DEFAULT_MAX_FINDINGS, minimum=1, maximum=250),
        max_scan_files=_bounded_int(max_scan_files, DEFAULT_MAX_SCAN_FILES, minimum=10, maximum=5000),
        max_cycles=_bounded_int(max_cycles, MAX_CYCLES, minimum=1, maximum=1000),
    )


def runtime_root(data_root: str | Path | None = None) -> Path:
    root = Path(data_root).expanduser().resolve() if data_root is not None else francis_data_dir()
    return root / "runtime" / "overnight_explorer"


def stop_flag_path(data_root: str | Path | None = None) -> Path:
    return runtime_root(data_root) / "stop.flag"


def latest_path(data_root: str | Path | None = None) -> Path:
    return runtime_root(data_root) / "latest.json"


def write_stop_flag(data_root: str | Path | None = None, *, reason: str = "operator_stop") -> dict[str, Any]:
    path = stop_flag_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "francis.exploration.overnight.stop",
        "created_at": _utc_now(),
        "reason": _clean_token(reason) or "operator_stop",
        "governance": _governance_base(),
    }
    _write_json(path, payload)
    return {"ok": True, "status": "stop_requested", "stop_flag_path": str(path)}


def clear_stop_flag(data_root: str | Path | None = None) -> dict[str, Any]:
    path = stop_flag_path(data_root)
    existed = path.exists()
    if existed:
        path.unlink()
    return {"ok": True, "status": "cleared" if existed else "not_present", "stop_flag_path": str(path)}


def read_status(data_root: str | Path | None = None) -> dict[str, Any]:
    root = runtime_root(data_root)
    latest = latest_path(data_root)
    latest_payload = _read_json(latest) if latest.exists() else {}
    receipt_count = len(list((root / "receipts").glob("*.json"))) if (root / "receipts").exists() else 0
    return {
        "ok": True,
        "kind": STATUS_KIND,
        "status": "ready" if latest_payload else "no_runs",
        "runtime_root": str(root),
        "stop_flag_path": str(stop_flag_path(data_root)),
        "stop_requested": stop_flag_path(data_root).exists(),
        "receipt_count": receipt_count,
        "latest": latest_payload,
        "governance": _governance_base(),
    }


def run_once(config: OvernightExplorerConfig | None = None) -> dict[str, Any]:
    cfg = config or make_config()
    session_id = cfg.session_id or _new_session_id("overnight")
    root = runtime_root(cfg.data_root)
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    (root / "summaries").mkdir(parents=True, exist_ok=True)
    (root / "policy_receipts").mkdir(parents=True, exist_ok=True)

    cycle_id = f"cycle-{_timestamp_slug()}"
    policy = evaluate_tool_call_policy(
        ToolCallPolicyRequest(
            actor=cfg.actor,
            surface="overnight_explorer",
            tool_name="overnight_explore.read_substrate",
            requested_authority="readback",
            arguments={
                "repo_root": str(cfg.repo_root),
                "data_root": str(cfg.data_root),
                "allowed_write_scope": str(root),
                "desktop_input": False,
                "network": False,
            },
            reason="bounded overnight substrate exploration",
            trace_id=cycle_id,
        ),
        write_receipt=True,
        receipt_root=root / "policy_receipts",
    )

    observations: dict[str, Any] = {}
    status = "blocked"
    if policy.decision == DECISION_ALLOWED:
        observations = _collect_observations(cfg)
        status = "complete"

    learning_notes = _learning_notes(observations, status=status)
    receipt = {
        "ok": status == "complete",
        "kind": RECEIPT_KIND,
        "status": status,
        "created_at": _utc_now(),
        "session_id": session_id,
        "cycle_id": cycle_id,
        "actor": cfg.actor,
        "requested_intent": {
            "verb": "explore_and_learn_read_only",
            "scope": "francis_substrate",
            "repo_root": str(cfg.repo_root),
        },
        "governance": {
            **_governance_base(),
            "policy_decision": policy.decision,
            "policy_id": policy.policy_id,
            "policy_receipt_path": policy.receipt_path,
        },
        "policy_decision": policy.to_dict(),
        "observations": observations,
        "learning_notes": learning_notes,
    }
    receipt = redact_governed_value(receipt)
    receipt_id = _stable_id(receipt, prefix="overnight-explore")
    receipt_path = root / "receipts" / f"{receipt_id}.json"
    receipt["receipt_id"] = receipt_id
    receipt["receipt_path"] = str(receipt_path)
    _write_json(receipt_path, receipt)
    _write_json(latest_path(cfg.data_root), _latest_projection(receipt))
    return receipt


def run_loop(config: OvernightExplorerConfig | None = None, *, stream: bool = False) -> dict[str, Any]:
    cfg = config or make_config()
    session_id = cfg.session_id or _new_session_id("overnight")
    root = runtime_root(cfg.data_root)
    root.mkdir(parents=True, exist_ok=True)
    stop_path = stop_flag_path(cfg.data_root)
    started_at = _utc_now()
    deadline = time.monotonic() + cfg.duration_hours * 3600
    interval_seconds = cfg.interval_minutes * 60
    cycles: list[dict[str, Any]] = []
    status = "complete"
    if stream:
        _stream_event(
            "started",
            {
                "session_id": session_id,
                "started_at": started_at,
                "duration_hours_requested": cfg.duration_hours,
                "interval_minutes": cfg.interval_minutes,
                "max_cycles": cfg.max_cycles,
                "governance": _governance_base(),
            },
        )

    while len(cycles) < cfg.max_cycles:
        if stop_path.exists():
            status = "stopped"
            break
        if time.monotonic() > deadline:
            break

        receipt = run_once(
            OvernightExplorerConfig(
                repo_root=cfg.repo_root,
                data_root=cfg.data_root,
                actor=cfg.actor,
                session_id=session_id,
                duration_hours=cfg.duration_hours,
                interval_minutes=cfg.interval_minutes,
                max_findings=cfg.max_findings,
                max_scan_files=cfg.max_scan_files,
                max_cycles=cfg.max_cycles,
            )
        )
        cycle = _cycle_projection(receipt)
        cycles.append(cycle)
        if stream:
            _stream_event("cycle_complete", {"session_id": session_id, "cycle": cycle})
        if len(cycles) >= cfg.max_cycles:
            break

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        _sleep_with_stop_poll(stop_path, seconds=min(interval_seconds, remaining))

    if len(cycles) >= cfg.max_cycles:
        status = "max_cycles_reached"
    if stop_path.exists() and status != "max_cycles_reached":
        status = "stopped"

    summary = {
        "ok": True,
        "kind": SUMMARY_KIND,
        "status": status,
        "session_id": session_id,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "duration_hours_requested": cfg.duration_hours,
        "interval_minutes": cfg.interval_minutes,
        "cycles_completed": len(cycles),
        "runtime_root": str(root),
        "stop_flag_path": str(stop_path),
        "cycles": cycles,
        "governance": _governance_base(),
    }
    summary = redact_governed_value(summary)
    summary_id = _stable_id(summary, prefix="overnight-summary")
    summary_path = root / "summaries" / f"{summary_id}.json"
    summary["summary_id"] = summary_id
    summary["summary_path"] = str(summary_path)
    _write_json(summary_path, summary)
    _write_json(latest_path(cfg.data_root), summary)
    if stream:
        _stream_event("finished", {"session_id": session_id, "summary": summary})
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="francis overnight-explore")
    parser.add_argument("--repo-root", default="", help="Francis repo root. Defaults to the detected source checkout.")
    parser.add_argument("--data-dir", default="", help="Francis data directory. Defaults to FRANCIS_DATA_DIR or data/.")
    parser.add_argument("--actor", default=ACTOR, help="Actor recorded in receipts.")
    parser.add_argument("--duration-hours", type=float, default=DEFAULT_DURATION_HOURS)
    parser.add_argument("--interval-minutes", type=float, default=DEFAULT_INTERVAL_MINUTES)
    parser.add_argument("--max-findings", type=int, default=DEFAULT_MAX_FINDINGS)
    parser.add_argument("--max-scan-files", type=int, default=DEFAULT_MAX_SCAN_FILES)
    parser.add_argument("--max-cycles", type=int, default=MAX_CYCLES)
    parser.add_argument("--once", action="store_true", help="Run one read-only exploration cycle and exit.")
    parser.add_argument("--stream", action="store_true", help="Print visible lifecycle and per-cycle events.")
    parser.add_argument("--status", action="store_true", help="Print latest overnight explorer status.")
    parser.add_argument("--stop", action="store_true", help="Request a running overnight explorer to stop.")
    parser.add_argument("--clear-stop-flag", action="store_true", help="Remove a stale stop flag before running.")
    args = parser.parse_args(argv)

    data_root = Path(args.data_dir).expanduser().resolve() if args.data_dir else francis_data_dir()
    if args.stop:
        _print_json(write_stop_flag(data_root))
        return 0
    if args.status:
        _print_json(read_status(data_root))
        return 0
    if args.clear_stop_flag:
        clear_stop_flag(data_root)

    cfg = make_config(
        repo_root=args.repo_root or None,
        data_root=data_root,
        actor=args.actor,
        duration_hours=args.duration_hours,
        interval_minutes=args.interval_minutes,
        max_findings=args.max_findings,
        max_scan_files=args.max_scan_files,
        max_cycles=args.max_cycles,
    )
    result = run_once(cfg) if args.once else run_loop(cfg, stream=bool(args.stream))
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def _collect_observations(cfg: OvernightExplorerConfig) -> dict[str, Any]:
    return {
        "repo": {
            "root": str(cfg.repo_root),
            "git": _git_status(cfg.repo_root),
            "recent_commits": _git_lines(cfg.repo_root, ["log", "-5", "--pretty=format:%h %ad %s", "--date=short"]),
            "posture": _posture_lines(cfg.repo_root),
            "file_counts": _file_counts(cfg),
        },
        "runtime": _runtime_snapshot(cfg),
        "findings": _findings(cfg),
        "scope": {
            "scan_roots": list(SCAN_ROOTS),
            "max_scan_files": cfg.max_scan_files,
            "max_file_bytes": MAX_SCAN_FILE_BYTES,
            "stores_raw_transcripts": False,
            "reads_conversation_transcripts": False,
        },
    }


def _git_status(root: Path) -> dict[str, Any]:
    try:
        return git_status_snapshot(cwd=root, limit=30)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        return {"ok": False, "status": "unavailable", "error": _safe_str(exc), "governance": _governance_base()}


def _git_lines(root: Path, args: list[str]) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    if completed.returncode != 0:
        return []
    lines = completed.stdout.splitlines()
    return [_safe_line(line) for line in lines[:10]]


def _posture_lines(root: Path) -> dict[str, Any]:
    ledger = root / "docs" / "operations" / "COMPLETION_LEDGER.md"
    build_order = root / "docs" / "BUILD_ORDER.md"
    manifest = root / "docs" / "canonical" / "BUILD_MANIFEST.md"
    return {
        "ledger": _matching_lines(
            ledger,
            (
                "Francis is in",
                "strongest current posture",
                "P9_OBSERVABILITY",
                "P3_GOVERNANCE",
                "P8_MEMORY",
            ),
            max_lines=12,
        ),
        "build_order": _matching_lines(build_order, ("Current priority", "observability", "governance", "memory"), 12),
        "manifest": _matching_lines(manifest, ("Phase 2", "Current Build Posture", "Plane readiness"), 12),
    }


def _file_counts(cfg: OvernightExplorerConfig) -> dict[str, Any]:
    counts_by_root: dict[str, int] = {}
    counts_by_suffix: dict[str, int] = {}
    scanned = 0
    skipped_large = 0
    for path in _iter_scan_files(cfg.repo_root, cfg.max_scan_files):
        scanned += 1
        rel = _relative(path, cfg.repo_root)
        top = rel.split("/", 1)[0]
        suffix = path.suffix.lower() or "[none]"
        counts_by_root[top] = counts_by_root.get(top, 0) + 1
        counts_by_suffix[suffix] = counts_by_suffix.get(suffix, 0) + 1
        try:
            if path.stat().st_size > MAX_SCAN_FILE_BYTES:
                skipped_large += 1
        except OSError:
            continue
    return {
        "scanned_files": scanned,
        "skipped_large_files": skipped_large,
        "by_root": dict(sorted(counts_by_root.items())),
        "by_suffix": dict(sorted(counts_by_suffix.items())),
    }


def _runtime_snapshot(cfg: OvernightExplorerConfig) -> dict[str, Any]:
    data_root = cfg.data_root
    runtime = data_root / "runtime"
    dirs = _directory_summaries(runtime, limit=40)
    overlay = _read_json_shallow(cfg.repo_root / "config" / "runtime" / "lens" / "overlay.json")
    control_mode = _read_json_shallow(runtime / "control_mode.json")
    return {
        "data_root": str(data_root),
        "runtime_root": str(runtime),
        "runtime_dirs": dirs,
        "overlay_config": overlay,
        "control_mode": control_mode,
    }


def _directory_summaries(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(path.iterdir(), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
        if len(items) >= limit:
            break
        try:
            stat = child.stat()
        except OSError:
            continue
        items.append(
            {
                "name": child.name,
                "kind": "dir" if child.is_dir() else "file",
                "last_modified_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "size_bytes": stat.st_size if child.is_file() else 0,
            }
        )
    return items


def _findings(cfg: OvernightExplorerConfig) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen_per_file: dict[str, int] = {}
    for path in _iter_scan_files(cfg.repo_root, cfg.max_scan_files):
        if len(findings) >= cfg.max_findings:
            break
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_FILE_BYTES:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = _relative(path, cfg.repo_root)
        for line_number, line in enumerate(lines, start=1):
            if len(findings) >= cfg.max_findings:
                break
            if seen_per_file.get(rel, 0) >= 3:
                break
            for marker, pattern in FINDING_PATTERNS:
                if pattern.search(line):
                    seen_per_file[rel] = seen_per_file.get(rel, 0) + 1
                    findings.append(
                        {
                            "marker": marker,
                            "path": rel,
                            "line": line_number,
                            "text": _safe_line(line),
                        }
                    )
                    break
    return findings


def _learning_notes(observations: dict[str, Any], *, status: str) -> dict[str, Any]:
    repo = observations.get("repo") if isinstance(observations, dict) else {}
    runtime = observations.get("runtime") if isinstance(observations, dict) else {}
    findings = observations.get("findings") if isinstance(observations, dict) else []
    git = repo.get("git") if isinstance(repo, dict) else {}
    file_counts = repo.get("file_counts") if isinstance(repo, dict) else {}
    runtime_dirs = runtime.get("runtime_dirs") if isinstance(runtime, dict) else []
    finding_markers: dict[str, int] = {}
    if isinstance(findings, list):
        for item in findings:
            if isinstance(item, dict):
                marker = _safe_str(item.get("marker")) or "unknown"
                finding_markers[marker] = finding_markers.get(marker, 0) + 1

    return {
        "status": status,
        "summary": "Read-only substrate exploration completed." if status == "complete" else "Exploration blocked by policy.",
        "learned": {
            "git_dirty": bool(git.get("dirty")) if isinstance(git, dict) else False,
            "tracked_changed_count": git.get("changed_count", 0) if isinstance(git, dict) else 0,
            "scanned_files": file_counts.get("scanned_files", 0) if isinstance(file_counts, dict) else 0,
            "runtime_surface_count": len(runtime_dirs) if isinstance(runtime_dirs, list) else 0,
            "finding_markers": dict(sorted(finding_markers.items())),
        },
        "candidate_next_questions": _candidate_questions(findings if isinstance(findings, list) else []),
        "overnight_limits": [
            "no desktop input",
            "no network fetch",
            "no repository mutation",
            "no raw transcript ingestion",
            "writes only overnight explorer receipts and summaries",
        ],
    }


def _candidate_questions(findings: list[Any]) -> list[str]:
    questions: list[str] = []
    for item in findings[:6]:
        if not isinstance(item, dict):
            continue
        marker = _safe_str(item.get("marker"))
        path = _safe_str(item.get("path"))
        line = _safe_str(item.get("line"))
        if marker and path:
            questions.append(f"Review {marker} at {path}:{line} for a bounded follow-up task.")
    if not questions:
        questions.append("Compare the latest receipt summary against the completion ledger before granting more authority.")
    return questions


def _iter_scan_files(root: Path, max_files: int) -> list[Path]:
    files: list[Path] = []
    for rel_root in SCAN_ROOTS:
        base = root / rel_root
        if not base.exists():
            continue
        if base.is_file():
            files.append(base)
            continue
        for path in base.rglob("*"):
            if len(files) >= max_files:
                return files
            if not path.is_file():
                continue
            parts = set(path.relative_to(root).parts)
            if parts & SKIPPED_DIRS:
                continue
            files.append(path)
    return files


def _matching_lines(path: Path, needles: tuple[str, ...], max_lines: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    matches: list[dict[str, Any]] = []
    lowered_needles = tuple(needle.lower() for needle in needles)
    for line_number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        lower = text.lower()
        if any(needle in lower for needle in lowered_needles):
            matches.append({"line": line_number, "text": _safe_line(text)})
            if len(matches) >= max_lines:
                break
    return matches


def _read_json_shallow(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"status": "missing", "path": str(path)}
    try:
        if path.stat().st_size > 64_000:
            return {"status": "skipped_large", "path": str(path)}
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unavailable", "path": str(path)}
    if not isinstance(payload, dict):
        return {"status": "non_object", "path": str(path)}
    return {
        "status": "read",
        "path": str(path),
        "keys": sorted(_safe_str(key) for key in payload.keys())[:40],
        "summary": redact_governed_value({key: payload.get(key) for key in sorted(payload)[:20]}),
    }


def _latest_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    notes = receipt.get("learning_notes") if isinstance(receipt, dict) else {}
    learned = notes.get("learned") if isinstance(notes, dict) else {}
    return {
        "ok": bool(receipt.get("ok")),
        "kind": STATUS_KIND,
        "status": receipt.get("status", ""),
        "session_id": receipt.get("session_id", ""),
        "cycle_id": receipt.get("cycle_id", ""),
        "created_at": receipt.get("created_at", ""),
        "receipt_id": receipt.get("receipt_id", ""),
        "receipt_path": receipt.get("receipt_path", ""),
        "learned": learned if isinstance(learned, dict) else {},
        "governance": receipt.get("governance", {}),
    }


def _cycle_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    latest = _latest_projection(receipt)
    return {
        "status": latest.get("status", ""),
        "cycle_id": latest.get("cycle_id", ""),
        "created_at": latest.get("created_at", ""),
        "receipt_path": latest.get("receipt_path", ""),
        "learned": latest.get("learned", {}),
    }


def _stream_event(event: str, payload: dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "kind": "francis.exploration.overnight.stream",
                "event": event,
                "created_at": _utc_now(),
                **payload,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )


def _governance_base() -> dict[str, Any]:
    return {
        "local_first": True,
        "read_only": True,
        "desktop_input": False,
        "keyboard_input": False,
        "mouse_input": False,
        "network_access": False,
        "git_fetch": False,
        "git_pull": False,
        "git_push": False,
        "repository_mutation": False,
        "execution_authority": False,
        "mutation_authority_granted": False,
        "writes_memory": False,
        "writes_raw_transcripts": False,
        "allowed_write_scope": "data/runtime/overnight_explorer",
    }


def _sleep_with_stop_poll(stop_path: Path, *, seconds: float) -> None:
    end = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < end:
        if stop_path.exists():
            return
        time.sleep(min(5.0, max(0.0, end - time.monotonic())))


def _stable_id(payload: dict[str, Any], *, prefix: str) -> str:
    basis = {key: value for key, value in payload.items() if key not in {"receipt_id", "receipt_path", "summary_id"}}
    digest = hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _new_session_id(prefix: str) -> str:
    return f"{prefix}-{_timestamp_slug()}-{hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]}"


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _safe_line(value: Any) -> str:
    text = _safe_str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return _safe_str(redact_governed_value(text))[:260]


def _clean_token(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_str(value).strip())


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _bounded_float(value: Any, default: float, *, minimum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    if parsed < minimum:
        return default
    return parsed


def _bounded_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < minimum:
        return default
    return min(parsed, maximum)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
