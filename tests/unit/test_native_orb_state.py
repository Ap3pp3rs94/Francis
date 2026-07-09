from __future__ import annotations

import json
from pathlib import Path

from francis.input_actuator.orb_operator import submit_orb_intent
from francis.world_state.native_orb import build_native_orb_state_snapshot


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_native_orb_state_snapshot_is_read_only_contract() -> None:
    snapshot = build_native_orb_state_snapshot(
        {
            "state": "idle",
            "feedback_state": "idle",
            "read_only": True,
            "virtual_pointer": {"available": False},
            "grants_execution_authority": False,
        },
        generated_at="2026-07-09T00:00:00+00:00",
    )

    assert snapshot["kind"] == "francis.native_orb.state_snapshot"
    assert snapshot["schema_version"] == "francis.native_orb.state_snapshot.v1"
    assert snapshot["runtime_contract"] == {
        "native_runtime": "cpp",
        "status": "contract_ready",
        "implemented": False,
        "active_renderer": False,
        "body_renderer_only": True,
        "authority_layer": "francis_core",
        "francis_core_remains_authority": True,
    }
    assert snapshot["visual_lock"]["source"] == "docs/operations/ORB_VISUAL_LOCK.md"
    assert snapshot["visual_lock"]["parity_required"] is True
    assert snapshot["visual_lock"]["redesign_allowed"] is False
    assert snapshot["render_state"]["posture"] == "ambient_rest"
    assert snapshot["authority"]["read_only"] is True
    assert snapshot["authority"]["render_only"] is True
    assert snapshot["authority"]["native_runtime_authority"] is False
    assert snapshot["authority"]["grants_execution_authority"] is False
    assert snapshot["authority"]["grants_input_authority"] is False
    assert snapshot["authority"]["grants_desktop_bridge_authority"] is False
    assert snapshot["authority"]["can_move_user_os_cursor"] is False
    assert snapshot["authority"]["can_click"] is False
    assert snapshot["authority"]["can_drag"] is False
    assert snapshot["authority"]["can_type"] is False
    assert snapshot["ipc"]["event_channel"] == "not_implemented"
    assert snapshot["ipc"]["accepts_mutation_events"] is False
    assert snapshot["event_contract"]["emits_intent_events"] is False
    assert "no_cpp_renderer_implemented" in snapshot["limitations"]


def test_native_orb_state_snapshot_surfaces_virtual_pointer_without_user_cursor() -> None:
    snapshot = build_native_orb_state_snapshot(
        {
            "feedback_state": "moving",
            "read_only": True,
            "virtual_pointer": {
                "available": True,
                "pointer_id": "francis.orb.primary_virtual_pointer",
                "mode": "orb_pointer",
                "x": 33,
                "y": 44,
                "controls_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
            },
        },
        generated_at="2026-07-09T00:00:00+00:00",
    )

    assert snapshot["render_state"]["posture"] == "active_feedback"
    assert snapshot["virtual_pointer"]["available"] is True
    assert snapshot["virtual_pointer"]["x"] == 33
    assert snapshot["virtual_pointer"]["y"] == 44
    assert snapshot["virtual_pointer"]["presentation_only"] is True
    assert snapshot["virtual_pointer"]["controls_user_os_cursor"] is False
    assert snapshot["virtual_pointer"]["user_mouse_taken"] is False
    assert snapshot["virtual_pointer"]["physical_input_performed"] is False
    assert snapshot["authority"]["unsafe_source_flags_denied"] is False


def test_native_orb_state_snapshot_denies_unsafe_source_flags() -> None:
    snapshot = build_native_orb_state_snapshot(
        {
            "feedback_state": "complete",
            "read_only": True,
            "uses_user_os_cursor": True,
            "user_mouse_taken": True,
            "physical_input_performed": True,
            "grants_execution_authority": True,
            "virtual_pointer": {
                "available": True,
                "x": 100,
                "y": 200,
                "desktop_effect_performed": True,
            },
        },
        generated_at="2026-07-09T00:00:00+00:00",
    )

    assert snapshot["virtual_pointer"]["controls_user_os_cursor"] is False
    assert snapshot["virtual_pointer"]["user_mouse_taken"] is False
    assert snapshot["virtual_pointer"]["physical_input_performed"] is False
    assert snapshot["virtual_pointer"]["desktop_effect_performed"] is False
    assert snapshot["authority"]["grants_execution_authority"] is False
    assert snapshot["authority"]["grants_input_authority"] is False
    assert snapshot["authority"]["unsafe_source_flags_denied"] is True
    assert snapshot["authority"]["unsafe_source_flags_observed"] == {
        "uses_user_os_cursor": True,
        "user_mouse_taken": True,
        "physical_input_performed": True,
        "grants_execution_authority": True,
        "desktop_effect_performed": True,
    }


def test_native_orb_state_snapshot_reads_operator_state_without_creating_dirs(tmp_path: Path, monkeypatch) -> None:
    state_root = tmp_path / "orb_operator"
    monkeypatch.setenv("FRANCIS_ORB_OPERATOR_STATE_DIR", str(state_root))

    snapshot = build_native_orb_state_snapshot(generated_at="2026-07-09T00:00:00+00:00")

    assert snapshot["source"]["operator_state_read_only"] is True
    assert snapshot["virtual_pointer"]["available"] is False
    assert snapshot["authority"]["native_runtime_authority"] is False
    assert not state_root.exists()


def test_native_orb_state_snapshot_can_project_existing_virtual_pointer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_ORB_OPERATOR_STATE_DIR", str(tmp_path / "orb_operator"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", raising=False)
    monkeypatch.delenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", raising=False)

    submit_orb_intent({"mode": "orb_pointer", "intent": {"kind": "move_to", "x": 55, "y": 66}})
    snapshot = build_native_orb_state_snapshot(generated_at="2026-07-09T00:00:00+00:00")

    assert snapshot["virtual_pointer"]["available"] is True
    assert snapshot["virtual_pointer"]["x"] == 55
    assert snapshot["virtual_pointer"]["y"] == 66
    assert snapshot["authority"]["can_move_user_os_cursor"] is False


def test_native_orb_state_schema_fixture_matches_required_contract() -> None:
    root = _repo_root()
    schema = json.loads((root / "schemas" / "native_orb_state_snapshot.schema.json").read_text(encoding="utf-8"))
    fixture = json.loads((root / "schemas" / "native_orb_state_snapshot.fixture.json").read_text(encoding="utf-8"))

    assert schema["properties"]["runtime_contract"]["properties"]["native_runtime"]["const"] == "cpp"
    assert schema["properties"]["runtime_contract"]["properties"]["implemented"]["const"] is False
    assert schema["properties"]["authority"]["properties"]["native_runtime_authority"]["const"] is False
    assert schema["properties"]["authority"]["properties"]["can_click"]["const"] is False
    assert schema["properties"]["authority"]["properties"]["can_drag"]["const"] is False
    assert schema["properties"]["authority"]["properties"]["can_type"]["const"] is False
    assert schema["properties"]["ipc"]["properties"]["accepts_mutation_events"]["const"] is False
    assert set(schema["required"]).issubset(fixture)
    assert fixture == build_native_orb_state_snapshot(
        {
            "feedback_state": "idle",
            "read_only": True,
            "virtual_pointer": {"available": False},
            "grants_execution_authority": False,
        },
        generated_at="2026-07-09T00:00:00+00:00",
    )
