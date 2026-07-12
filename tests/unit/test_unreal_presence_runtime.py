from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from francis.unreal_presence_runtime import unreal_presence_runtime_readback


NOW = "2026-07-10T18:10:00+00:00"


def _selection(tmp_path: Path) -> dict[str, object]:
    return {
        "status": "operator_selection_confirmed",
        "valid": True,
        "project": {"path": str(tmp_path / "FrancisPresence.uproject")},
    }


def _status() -> dict[str, object]:
    return {
        "kind": "francis.grounded_presence.unreal_runtime_status",
        "schema_version": "francis.grounded_presence.unreal_runtime_status.v1",
        "schema_path": "schemas/grounded_presence_unreal_runtime_status.schema.json",
        "observed_at": NOW,
        "process_id": os.getpid(),
        "adapter_id": "unreal_presence_1",
        "session_id": "francis_unreal_stage1_v1",
        "endpoint_id": "francis.grounded_presence.unreal_presence_1",
        "authentication_key_id": "francis_presence_local_v1",
        "transport": {
            "status": "render_applied",
            "configured": True,
            "pipe_connected": False,
            "accepted_message_count": 1,
            "rejected_message_count": 0,
            "duplicate_message_count": 0,
            "last_error": "",
        },
        "render": {
            "status": "applied",
            "envelope_id": "gpe_0123456789abcdef0123456789abcdef",
            "sequence": 1,
            "received_at": NOW,
            "rendered_at": NOW,
            "presence_state": "handoff",
            "headline": "Grounded state rendered.",
            "authenticated": True,
            "runtime_observed": True,
        },
        "intent": {
            "last_sequence": 1,
            "last_kind": "request_context_refresh",
            "last_event_id": "gpi_0123456789abcdef0123456789abcdef",
            "sent_count": 1,
            "last_write_succeeded": True,
        },
        "technology": {
            "engine": "Unreal Engine",
            "engine_version": "5.8",
            "active_stack": ["cpp_runtime_module", "slate_operator_surface", "lumen_dynamic_gi"],
        },
        "authority": {
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
        "stores_presence_payload": False,
    }


def _write_status(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "runtime_status.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_runtime_status_schema_accepts_renderer_readback() -> None:
    schema_path = Path(__file__).parents[2] / "schemas" / "grounded_presence_unreal_runtime_status.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(_status())


def test_runtime_readback_requires_confirmed_selection(tmp_path: Path) -> None:
    readback = unreal_presence_runtime_readback(selection={"valid": False}, environ={}, now=NOW)

    assert readback["status"] == "selection_required"
    assert readback["observed"] is False
    assert readback["grants_execution_authority"] is False


def test_runtime_readback_reports_missing_status_without_inventing_runtime(tmp_path: Path) -> None:
    readback = unreal_presence_runtime_readback(selection=_selection(tmp_path), environ={}, now=NOW)

    assert readback["status"] == "runtime_not_observed"
    assert readback["observed"] is False
    assert readback["validation"]["reasons"] == ["runtime_status_missing"]


def test_runtime_readback_accepts_fresh_live_authenticated_render(tmp_path: Path) -> None:
    status_path = _write_status(tmp_path, _status())
    readback = unreal_presence_runtime_readback(
        selection=_selection(tmp_path),
        environ={
            "FRANCIS_UNREAL_PRESENCE_STATUS_PATH": str(status_path),
            "FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID": "francis_presence_local_v1",
        },
        now=NOW,
    )

    assert readback["status"] == "runtime_observed"
    assert readback["observed"] is True
    assert readback["fresh"] is True
    assert readback["process_alive"] is True
    assert readback["runtime"]["render"]["status"] == "applied"
    assert readback["stores_presence_payload"] is False


def test_runtime_readback_rejects_stale_or_authority_expanding_status(tmp_path: Path) -> None:
    stale = _status()
    stale["observed_at"] = "2026-07-10T18:00:00+00:00"
    status_path = _write_status(tmp_path, stale)
    stale_readback = unreal_presence_runtime_readback(
        selection=_selection(tmp_path),
        environ={"FRANCIS_UNREAL_PRESENCE_STATUS_PATH": str(status_path)},
        now=NOW,
    )
    assert stale_readback["status"] == "runtime_stale"
    assert stale_readback["observed"] is False

    expanded = deepcopy(_status())
    expanded["authority"]["grants_execution_authority"] = True
    _write_status(tmp_path, expanded)
    expanded_readback = unreal_presence_runtime_readback(
        selection=_selection(tmp_path),
        environ={"FRANCIS_UNREAL_PRESENCE_STATUS_PATH": str(status_path)},
        now=NOW,
    )
    assert expanded_readback["observed"] is False
    assert "runtime_authority_invalid" in expanded_readback["validation"]["reasons"]
