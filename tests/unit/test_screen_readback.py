from __future__ import annotations

import json
from pathlib import Path

from francis.screen_readback import tools as screen_tools


def test_screen_readback_status_is_safe_read_only() -> None:
    result = screen_tools.screen_readback_status()

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["capabilities"]["screen_capture"] is False
    assert result["capabilities"]["pixel_access"] is False
    assert result["governance"]["read_only"] is True
    assert result["governance"]["screenshots"] is False
    assert result["governance"]["pixels"] is False


def test_session_readback_reports_takeover_and_receipts_without_content(tmp_path: Path, monkeypatch) -> None:
    mcp_receipts = tmp_path / "mcp" / "receipts"
    input_receipts = tmp_path / "input" / "receipts"
    mcp_receipts.mkdir(parents=True)
    input_receipts.mkdir(parents=True)
    (mcp_receipts / "mcp-demo.json").write_text("{}", encoding="utf-8")
    (input_receipts / "input-demo.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "mcp"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", "1")

    result = screen_tools.session_readback({})

    assert result["ok"] is True
    # No-implicit-takeover guarantee: with no approved stage9 session, the
    # readback must report takeover as inactive/read-only. Takeover only flips
    # active via a real manual-approval flow, never via env or readback.
    assert result["takeover"]["active"] is False
    assert result["takeover"]["session_id"] == ""
    assert result["takeover"]["mode"] == "read_only"
    assert result["input_actuator"]["real_input_enabled"] is True
    assert result["last_receipts"]["content_included"] is False
    assert result["last_receipts"]["mcp_gateway_receipts"] == ["mcp-demo"]
    assert result["last_receipts"]["input_actuator_receipts"] == ["input-demo"]
    assert result["safety"]["screen_capture"] is False
    assert result["safety"]["pixel_access"] is False
    json.dumps(result)


def test_window_title_redaction_uses_hash(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_SCREEN_READBACK_REDACT_TITLES", "1")

    redacted = screen_tools._redact_text("Example Window Title")

    assert redacted["redacted"] is True
    assert redacted["length"] == len("Example Window Title")
    assert isinstance(redacted["sha256_16"], str)
    assert len(redacted["sha256_16"]) == 16
