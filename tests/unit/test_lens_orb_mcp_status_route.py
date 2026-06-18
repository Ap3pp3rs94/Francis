from __future__ import annotations

import json
from pathlib import Path


def test_lens_mcp_status_route_exposes_read_only_body_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/mcp/status?actor=test.lens.mcp.status&receipt_limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert body["status"] in {"ready", "degraded"}
    assert body["mcp"]["tool_count"] >= 18
    assert "missing_tools" in body["mcp"]
    assert "missing_required_tools" in body["mcp"]
    assert body["resident"] is False
    assert body["routes"]["mcp_observe"] == "/lens/mcp/observe"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["raw_input"] is False
    assert body["governance"]["screenshots"] is False
    assert body["governance"]["ocr"] is False
    assert "traceback" not in json.dumps(body, sort_keys=True).lower()


def test_lens_orb_mcp_status_alias_route_is_available(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/orb/mcp-status?actor=test.lens.orb")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens_orb.mcp_status_bridge"
    assert body["routes"]["mcp_status"] == "/lens/mcp/status"
    assert body["routes"]["mcp_observe"] == "/lens/mcp/observe"


def test_lens_command_palette_monitor_route_projects_voice_bridge_proof(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    status_path = data_root / "runtime" / "lens-command-palette-monitor" / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "lens.command_palette.monitor",
                "status": "healthy",
                "mode": "run",
                "monitor_pid": 1234,
                "monitor_process_alive": True,
                "anomaly_count": 0,
                "anomalies": [],
                "checks": [
                    {
                        "id": "voice_overlay_readback",
                        "passed": True,
                        "status": "readback_ready",
                        "evidence": "scripts/lens-overlay-window.ps1 -Mode Status",
                    }
                ],
                "bridge": {
                    "ok": True,
                    "readback_ready": True,
                    "local_open_available": True,
                    "route": "/?francis_lens=command_palette",
                    "local_surface": "chat_ui.command_palette",
                    "command_total": 2,
                },
                "voice_monitor": {
                    "enabled": True,
                    "ok": True,
                    "selected_provider": "ElevenLabs",
                    "selected_voice": "Emma",
                    "voice_label": "Emma",
                    "voice_identity_ok": True,
                    "overlay_ready": True,
                    "overlay_voice_status": "listening",
                    "voice_status": "listening",
                    "recent_receipt_count": 1,
                    "latest_receipt_id": "chatgpt-voice-recorded-ui",
                    "latest_receipt_actor": "chat_ui.voice",
                    "latest_receipt_source": "chat_ui.voice",
                    "latest_receipt_client_origin": "francis_chat_ui_browser_voice",
                    "latest_receipt_ingress_transport": "http_api",
                    "latest_receipt_counts_as_chatgpt_mcp_proof": False,
                    "latest_receipt_proof_rejection_reason": "latest_receipt_not_chatgpt_voice_origin",
                    "transcript": "do not expose this transcript",
                    "chatgpt_mcp_proof": {
                        "status": "awaiting_chatgpt_mcp_tool_call",
                        "proof_observed": False,
                        "chatgpt_source_receipt_count": 0,
                        "mcp_server_receipt_count": 0,
                        "latest_fresh_usable_mcp_server_receipt_id": "",
                        "next_operator_step": "trigger_chatgpt_voice_app_turn_and_confirm_mcp_tool_receipt",
                        "transcript": "do not expose this proof transcript",
                    },
                },
                "chatgpt_connector_monitor": {
                    "enabled": True,
                    "ok": True,
                    "status": "ready_for_chatgpt_connector",
                    "connector_url_present": True,
                    "connector_url_host": "francis-voice-178175.loca.lt",
                    "connector_url_source": "localtunnel",
                    "connector_shape_valid": True,
                    "connector_usable_for_chatgpt": True,
                    "expected_tool_present": True,
                    "known_localtunnel": True,
                    "persistent_candidate": False,
                    "persistent_ingress_status": "localtunnel_fallback_replace_needed",
                    "blockers": ["localtunnel_url_is_not_persistent_ingress"],
                },
                "chatgpt_persistent_ingress_plan_monitor": {
                    "enabled": True,
                    "ok": True,
                    "status": "localtunnel_fallback_replace_needed",
                    "blockers": ["localtunnel_url_is_not_persistent_ingress"],
                    "recommended_provider_order": ["cloudflared_named_tunnel"],
                    "next_operator_steps": ["choose_or_install_a_persistent_https_ingress_provider"],
                    "governance_safe": True,
                },
            }
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/command-palette/monitor")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens.command_palette.monitor_readback"
    assert body["status"] == "healthy"
    assert body["monitor_process_alive"] is True
    assert body["bridge"]["route"] == "/?francis_lens=command_palette"
    assert body["voice_monitor"]["selected_voice"] == "Emma"
    assert body["voice_monitor"]["latest_receipt_actor"] == "chat_ui.voice"
    assert body["voice_monitor"]["latest_receipt_ingress_transport"] == "http_api"
    assert body["voice_monitor"]["latest_receipt_counts_as_chatgpt_mcp_proof"] is False
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["status"] == "awaiting_chatgpt_mcp_tool_call"
    assert body["chatgpt_connector_monitor"]["known_localtunnel"] is True
    assert body["chatgpt_persistent_ingress_plan_monitor"]["governance_safe"] is True
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["captures_audio"] is False
    assert "do not expose this transcript" not in json.dumps(body, sort_keys=True)


def test_lens_command_palette_monitor_route_reports_missing_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/command-palette/monitor")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "francis.lens.command_palette.monitor_readback"
    assert body["ok"] is False
    assert body["status"] == "missing"
    assert body["monitor_process_alive"] is False
    assert body["voice_monitor"]["chatgpt_mcp_proof"]["proof_observed"] is False
    assert body["governance"]["execution_authority"] is False
