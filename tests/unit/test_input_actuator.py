from __future__ import annotations

from pathlib import Path

from francis.input_actuator.tools import (
    execute_approved_input_action,
    input_receipts_readback,
    input_status,
    propose_input_action,
)


def test_input_status_is_read_only_and_does_not_grant_raw_input(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", raising=False)

    result = input_status()

    assert result["ok"] is True
    assert result["governance"]["read_only"] is True
    assert result["governance"]["raw_mcp_input_authority"] is False
    assert result["data"]["real_input_enabled"] is False


def test_propose_mouse_move_requires_manual_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))

    result = propose_input_action(
        {
            "actor": "test",
            "objective": "move cursor to safe point",
            "kind": "mouse.move",
            "payload": {"x": 10, "y": 20},
        }
    )

    assert result["ok"] is True
    assert result["status"] == "approval_required"
    assert result["data"]["approval_phrase"].startswith("APPROVE INPUT ")
    assert result["governance"]["moves_mouse"] is False


def test_execute_refuses_without_exact_approval_phrase(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    proposal = propose_input_action(
        {
            "actor": "test",
            "objective": "click safely",
            "kind": "mouse.click",
            "payload": {"button": "left", "clicks": 1},
        }
    )

    result = execute_approved_input_action(
        {"proposal_id": proposal["data"]["proposal_id"], "approval_phrase": "APPROVE nope"}
    )

    assert result["ok"] is False
    assert result["status"] == "approval_required"
    assert result["governance"]["moves_mouse"] is False


def test_execute_approved_defaults_to_dry_run_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", raising=False)
    proposal = propose_input_action(
        {
            "actor": "test",
            "objective": "move cursor dry-run",
            "kind": "mouse.move",
            "payload": {"x": 11, "y": 22},
        }
    )

    result = execute_approved_input_action(
        {
            "proposal_id": proposal["data"]["proposal_id"],
            "approval_phrase": proposal["data"]["approval_phrase"],
        }
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["governance"]["dry_run"] is True
    assert result["governance"]["moves_mouse"] is False
    assert Path(result["data"]["receipt_path"]).exists()


def test_real_input_env_without_active_takeover_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", "1")
    proposal = propose_input_action(
        {
            "actor": "test",
            "objective": "blocked physical move",
            "kind": "mouse.move",
            "payload": {"x": 11, "y": 22},
        }
    )

    result = execute_approved_input_action(
        {
            "proposal_id": proposal["data"]["proposal_id"],
            "approval_phrase": proposal["data"]["approval_phrase"],
        }
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_active_takeover_required"
    assert result["governance"]["moves_mouse"] is False


def test_keyboard_type_refuses_sensitive_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))

    try:
        propose_input_action(
            {
                "actor": "test",
                "objective": "type credential",
                "kind": "keyboard.type",
                "payload": {"text": "password is hunter2"},
            }
        )
    except ValueError as exc:
        assert "sensitive" in str(exc)
    else:
        raise AssertionError("expected sensitive text refusal")


def test_keyboard_type_public_action_redacts_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    result = propose_input_action(
        {
            "actor": "test",
            "objective": "type visible label",
            "kind": "keyboard.type",
            "payload": {"text": "hello"},
        }
    )

    preview = result["data"]["action_preview"]
    assert preview["kind"] == "keyboard.type"
    assert preview["text_length"] == 5
    assert "text_sha256" in preview
    assert "hello" not in str(preview)


def test_receipts_readback_missing_is_truthful(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))
    result = input_receipts_readback({"receipt_id": "missing"})

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["governance"]["read_only"] is True


def test_unsupported_action_is_refused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path))

    try:
        propose_input_action(
            {
                "actor": "test",
                "objective": "bad action",
                "kind": "shell.exec",
                "payload": {"command": "whoami"},
            }
        )
    except ValueError as exc:
        assert "unsupported input action" in str(exc)
    else:
        raise AssertionError("expected unsupported action refusal")
