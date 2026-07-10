from __future__ import annotations

import hashlib
import json
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


UI_RENDER_PROOF_KIND = "francis.lens.ui_render_proof"
UI_RENDER_PROOF_SCHEMA_VERSION = "francis.lens.ui_render_proof.v1"

_LENS_MARKERS = {
    "lens_heading",
    "status_ready",
    "posture_ready",
    "zero_blockers",
    "policy_safe",
    "receipt_visible",
    "read_only",
}
_CHAT_MARKERS = {
    "agent_relay",
    "active_agents",
    "authority_bounded",
    "live_conversation",
    "technical_receipts",
    "operator_console",
}
_SNAPSHOT_TEXT_MARKERS = (
    "Francis MCP Status",
    "takeover_ready",
    "tool-call-policy-",
    "Agent Relay Controls",
    "Live Conversation",
    "Technical receipt",
)
_CANONICAL_PIDS = (
    "overlay_pid",
    "hotkey_pid",
    "tray_pid",
    "supervisor_pid",
    "resident_host_pid",
    "renderer_pid",
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_repo_artifact(
    repo_root: Path,
    artifact: dict[str, Any],
    artifact_id: str,
    blockers: list[str],
) -> Path | None:
    raw_path = str(artifact.get("path") or "").strip()
    if not raw_path:
        blockers.append(f"{artifact_id}_path_missing")
        return None

    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / path
    try:
        resolved = path.resolve()
        resolved.relative_to(repo_root)
    except (OSError, ValueError):
        blockers.append(f"{artifact_id}_outside_repo")
        return None
    if not resolved.is_file():
        blockers.append(f"{artifact_id}_missing")
        return None

    expected_hash = str(artifact.get("sha256") or "").strip().lower()
    if len(expected_hash) != 64 or _sha256(resolved) != expected_hash:
        blockers.append(f"{artifact_id}_hash_mismatch")
    expected_bytes = _safe_int(artifact.get("bytes"))
    if expected_bytes <= 0 or resolved.stat().st_size != expected_bytes:
        blockers.append(f"{artifact_id}_size_mismatch")
    return resolved


def _validate_png(
    path: Path | None,
    artifact: dict[str, Any],
    artifact_id: str,
    blockers: list[str],
) -> None:
    if path is None:
        return
    try:
        header = path.read_bytes()[:24]
        valid_header = header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR"
        width, height = struct.unpack(">II", header[16:24]) if valid_header else (0, 0)
    except (OSError, struct.error):
        width, height = 0, 0
    if width <= 0 or height <= 0:
        blockers.append(f"{artifact_id}_invalid_png")
        return
    if width != _safe_int(artifact.get("width")) or height != _safe_int(artifact.get("height")):
        blockers.append(f"{artifact_id}_dimensions_mismatch")


def _required_markers(
    surface: dict[str, Any],
    required: set[str],
    surface_id: str,
    blockers: list[str],
) -> None:
    markers = _as_dict(surface.get("markers"))
    for marker in sorted(required):
        if markers.get(marker) is not True:
            blockers.append(f"{surface_id}_marker_missing:{marker}")


def validate_lens_ui_render_proof(
    proof_path: str | Path,
    *,
    repo_root: str | Path,
    expected_repo_head: str = "",
    max_age_seconds: int = 900,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    candidate = Path(proof_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    path = candidate.resolve()
    blockers: list[str] = []
    if not path.is_file():
        blockers.append("ui_render_proof_missing")
        payload: dict[str, Any] = {}
    else:
        payload = _read_json(path)
        if not payload:
            blockers.append("ui_render_proof_invalid_json")

    if payload.get("kind") != UI_RENDER_PROOF_KIND:
        blockers.append("ui_render_proof_kind_mismatch")
    if payload.get("schema_version") != UI_RENDER_PROOF_SCHEMA_VERSION:
        blockers.append("ui_render_proof_schema_mismatch")

    created_at = _parse_created_at(payload.get("created_at"))
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    age_seconds: float | None = None
    if created_at is None:
        blockers.append("ui_render_proof_timestamp_invalid")
    else:
        age_seconds = (current_time - created_at).total_seconds()
        if age_seconds < -60:
            blockers.append("ui_render_proof_from_future")
        if age_seconds > max(1, int(max_age_seconds)):
            blockers.append("ui_render_proof_stale")

    repo_head = str(payload.get("repo_head") or "").strip()
    if expected_repo_head and repo_head != expected_repo_head.strip():
        blockers.append("ui_render_proof_head_mismatch")

    page = _as_dict(payload.get("page"))
    parsed_url = urlparse(str(page.get("url") or ""))
    if parsed_url.scheme != "http" or parsed_url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        blockers.append("ui_render_proof_page_not_loopback")
    if parsed_url.path.rstrip("/") != "/diagnostics":
        blockers.append("ui_render_proof_page_path_mismatch")
    if str(page.get("title") or "").strip() != "Francis Console":
        blockers.append("ui_render_proof_page_title_mismatch")
    if _safe_int(page.get("console_error_count")) != 0:
        blockers.append("ui_render_proof_console_errors")

    lens = _as_dict(payload.get("lens"))
    chat = _as_dict(payload.get("chat"))
    if lens.get("rendered") is not True:
        blockers.append("lens_ui_not_rendered")
    if str(lens.get("status") or "") != "ready":
        blockers.append("lens_ui_status_not_ready")
    if str(lens.get("posture") or "") not in {"pilot_ready", "takeover_ready"}:
        blockers.append("lens_ui_posture_not_ready")
    if _safe_int(lens.get("blocker_count")) != 0:
        blockers.append("lens_ui_blockers_present")
    if _safe_int(lens.get("tool_count")) <= 0:
        blockers.append("lens_ui_tool_count_missing")
    if not str(lens.get("latest_receipt_id") or "").strip():
        blockers.append("lens_ui_receipt_missing")
    if lens.get("read_only") is not True:
        blockers.append("lens_ui_read_only_contract_missing")
    if lens.get("execution_authority") is not False or lens.get("mutation_authority") is not False:
        blockers.append("lens_ui_authority_drift")
    if _safe_int(lens.get("text_length")) <= 0:
        blockers.append("lens_ui_text_missing")
    _required_markers(lens, _LENS_MARKERS, "lens_ui", blockers)

    if chat.get("rendered") is not True:
        blockers.append("chat_ui_not_rendered")
    if _safe_int(chat.get("text_length")) <= 0:
        blockers.append("chat_ui_text_missing")
    _required_markers(chat, _CHAT_MARKERS, "chat_ui", blockers)

    artifacts = _as_dict(payload.get("artifacts"))
    lens_artifact = _as_dict(artifacts.get("lens_screenshot"))
    chat_artifact = _as_dict(artifacts.get("chat_screenshot"))
    snapshot_artifact = _as_dict(artifacts.get("snapshot"))
    lens_path = _resolve_repo_artifact(root, lens_artifact, "lens_screenshot", blockers)
    chat_path = _resolve_repo_artifact(root, chat_artifact, "chat_screenshot", blockers)
    snapshot_path = _resolve_repo_artifact(root, snapshot_artifact, "ui_snapshot", blockers)
    _validate_png(lens_path, lens_artifact, "lens_screenshot", blockers)
    _validate_png(chat_path, chat_artifact, "chat_screenshot", blockers)
    if snapshot_path is not None:
        try:
            snapshot_text = snapshot_path.read_text(encoding="utf-8")
        except OSError:
            snapshot_text = ""
        for marker in _SNAPSHOT_TEXT_MARKERS:
            if marker not in snapshot_text:
                blockers.append(f"ui_snapshot_marker_missing:{marker}")

    runtime = _as_dict(payload.get("canonical_runtime"))
    if runtime.get("status") != "ready":
        blockers.append("canonical_runtime_not_ready")
    process_scan_status = str(runtime.get("process_scan_status") or "")
    process_scan_candidate_count = _safe_int(runtime.get("process_scan_candidate_count"))
    if runtime.get("process_scan_checked") is not True:
        blockers.append("canonical_runtime_process_scan_not_checked")
    if process_scan_status not in {"none_observed", "single_canonical_runtime"}:
        blockers.append("canonical_runtime_not_single")
    elif process_scan_status == "none_observed" and process_scan_candidate_count != 0:
        blockers.append("canonical_runtime_process_scan_count_mismatch")
    elif process_scan_status == "single_canonical_runtime" and process_scan_candidate_count <= 0:
        blockers.append("canonical_runtime_process_scan_count_mismatch")
    if _safe_int(runtime.get("competing_count")) != 0:
        blockers.append("canonical_runtime_competitors_present")
    if _safe_int(runtime.get("renderer_process_count")) != 1:
        blockers.append("canonical_renderer_count_mismatch")
    for pid_name in _CANONICAL_PIDS:
        if _safe_int(runtime.get(pid_name)) <= 0:
            blockers.append(f"canonical_runtime_pid_missing:{pid_name}")

    governance = _as_dict(payload.get("governance"))
    required_true = ("browser_read_only", "captured_existing_surface", "no_physical_input")
    for name in required_true:
        if governance.get(name) is not True:
            blockers.append(f"ui_render_governance_missing:{name}")
    required_false = ("grants_execution_authority", "grants_mutation_authority")
    for name in required_false:
        if governance.get(name) is not False:
            blockers.append(f"ui_render_governance_drift:{name}")

    unique_blockers = list(dict.fromkeys(blockers))
    verified = not unique_blockers
    return {
        "ok": verified,
        "status": "render_verified" if verified else "render_unverified",
        "proof_path": str(path),
        "created_at": str(payload.get("created_at") or ""),
        "age_seconds": age_seconds,
        "repo_head": repo_head,
        "chat_render_verified": verified,
        "lens_render_verified": verified,
        "canonical_runtime": runtime,
        "artifacts": artifacts,
        "blockers": unique_blockers,
        "governance": {
            "read_only_validation": True,
            "writes_repo": False,
            "writes_runtime": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


__all__ = [
    "UI_RENDER_PROOF_KIND",
    "UI_RENDER_PROOF_SCHEMA_VERSION",
    "validate_lens_ui_render_proof",
]
