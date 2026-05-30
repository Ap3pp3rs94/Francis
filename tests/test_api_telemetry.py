from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.telemetry import git as telemetry_git
from francis.telemetry.status import redact_telemetry_value


def test_telemetry_status_projects_stage7_readonly_sources(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.status"
    assert body["stage"] == "Stage 7 / Telemetry MVP"
    assert body["status"] in {"active", "inactive"}
    assert body["active"] is (body["active_source_total"] > 0)
    assert body["claim"] in {
        "telemetry_posture_contract_only",
        "explicit_telemetry_readback_available",
        "explicit_telemetry_events_recorded",
    }
    assert body["source_total"] == 3
    assert body["active_source_total"] == sum(1 for source in body["sources"] if source["active"])
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    sources = {source["id"]: source for source in body["sources"]}
    assert set(sources) == {"terminal", "git", "ide_diagnostics"}
    assert sources["terminal"]["status"] == "write_scope_required"
    assert sources["terminal"]["active"] is False
    assert sources["terminal"]["retention"]["event_count"] == 0
    assert sources["terminal"]["routes"]["record"] == "/telemetry/terminal/events"
    assert sources["git"]["routes"]["status"] == "/telemetry/git/status"
    assert sources["git"]["hidden_sensing"] is False
    assert sources["git"]["authority"]["execution_authority"] is False
    assert sources["ide_diagnostics"]["status"] == "write_scope_required"
    assert sources["ide_diagnostics"]["active"] is False
    assert sources["ide_diagnostics"]["routes"]["record"] == "/telemetry/ide-diagnostics/events"
    assert sources["ide_diagnostics"]["routes"]["events"] == "/telemetry/ide-diagnostics/events"
    for source in sources.values():
        assert source["visible_indicator"] is True
        assert source["hidden_sensing"] is False
        assert source["scope"]["denied_by_default"] is True
        assert source["retention"]["stores_raw_events"] is False
        assert source["redaction"]["redact_before_storage"] is True
        assert source["authority"]["telemetry_collection"] is False
        assert source["authority"]["execution_authority"] is False
        assert source["authority"]["memory_write"] is False

    assert body["redaction"]["stores_raw_secret_values"] is False
    assert body["retention"]["stores_raw_events"] is False
    if body["active"] and body["retention"]["event_count"] == 0:
        assert body["claim"] == "explicit_telemetry_readback_available"
        assert body["retention"]["status"] == "read_only_snapshot"
        assert body["sensing"]["status"] == "explicit_readback_available"
    elif body["retention"]["event_count"] > 0:
        assert body["claim"] == "explicit_telemetry_events_recorded"
        assert body["retention"]["status"] == "bounded_redacted_events"
        assert body["sensing"]["status"] == "explicit_events_recorded"
    else:
        assert body["claim"] == "telemetry_posture_contract_only"
        assert body["retention"]["status"] == "none"
        assert body["sensing"]["status"] == "inactive"
    assert body["sensing"]["hidden_sensing"] is False
    assert body["governance"]["read_only_contract"] is True
    assert body["governance"]["telemetry_collection"] is False
    assert body["governance"]["telemetry_is_untrusted_input"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert not data_root.exists()


def test_telemetry_redaction_uses_governed_redaction() -> None:
    payload = {
        "cwd": "D:/Francis",
        "operator_note": "token=stage7secret123",
        "nested": {"api_key": "stage7apikey123"},
    }

    redacted = redact_telemetry_value(payload)

    assert redacted["cwd"] == "D:/Francis"
    assert redacted["operator_note"] == "token=[REDACTED:secret]"
    assert redacted["nested"]["api_key"] == "[REDACTED:secret]"


def test_telemetry_context_projects_redacted_assist_surface(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.telemetry.write": ["telemetry.terminal.write"],
                "test.telemetry.ide": ["telemetry.ide_diagnostics.write"],
            }
        ),
    )

    client = TestClient(create_app())
    client.post(
        "/telemetry/terminal/events",
        json={
            "actor": "test.telemetry.write",
            "reason": "record terminal context token=terminalreasonsecret123",
            "command": "pytest token=terminalcommandsecret123",
            "cwd": str(tmp_path),
            "exit_code": 1,
            "operation_id": "op_context_terminal",
        },
    )
    client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": "test.telemetry.ide",
            "reason": "record IDE context token=idereasonsecret123",
            "file": "src/francis/password=idefilesecret123.py",
            "diagnostics": [{"severity": "error", "code": "F821", "message": "token=idemessagesecret123"}],
            "operation_id": "op_context_ide",
        },
    )

    body = client.get("/telemetry/context?surface=chat").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context"
    assert body["surface"] == "chat"
    assert body["status"] == "available"
    assert body["visible_indicator"] is True
    assert body["hidden_sensing"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["does_not_expand_collection_scope"] is True
    assert body["governance"]["telemetry_is_untrusted_input"] is True
    assert body["feedback"]["event_count"] == 0
    assert body["feedback"]["write_route"] == "/telemetry/context/feedback"
    assert body["feedback"]["read_route"] == "/telemetry/context/feedback"
    assert body["feedback"]["review_route"] == "/telemetry/context/feedback/review"
    assert body["feedback"]["required_scope"] == "telemetry.context.feedback.write"
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    source_ids = {item["source_id"] for item in body["context_items"]}
    assert "terminal" in source_ids
    assert "ide_diagnostics" in source_ids
    assert body["prompt_lines"]

    context_text = json.dumps(body, sort_keys=True)
    for raw_secret in (
        "terminalreasonsecret123",
        "terminalcommandsecret123",
        "idereasonsecret123",
        "idefilesecret123",
        "idemessagesecret123",
    ):
        assert raw_secret not in context_text
    assert "[REDACTED:secret]" in context_text


def test_telemetry_context_feedback_denies_event_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "record denied feedback",
            "context_id": "tel_ctx_denied",
            "surface": "chat",
            "rating": "useful",
            "notes": "denied",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["source_id"] == "telemetry_context"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "telemetry.context.feedback.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not data_root.exists()


def test_telemetry_context_feedback_review_is_empty_without_events(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/review")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_review"
    assert body["status"] == "empty"
    assert body["reviewed_event_count"] == 0
    assert body["total"] == 0
    assert body["rating_counts"] == {"useful": 0, "not_useful": 0, "neutral": 0}
    assert body["quality_signals"] == ["no_explicit_context_feedback_recorded"]
    assert body["latest_feedback"] == {}
    assert body["governance"]["read_only"] is True
    assert body["governance"]["on_request_only"] is True
    assert body["governance"]["uses_explicit_operator_feedback_only"] is True
    assert body["governance"]["stores_prompt_body"] is False
    assert body["governance"]["stores_model_response"] is False
    assert body["governance"]["trains_model"] is False
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["grants_memory_write_authority"] is False
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_quality_is_empty_without_events(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-quality")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_quality"
    assert body["status"] == "empty"
    assert body["review"]["status"] == "empty"
    assert body["memory_write_candidate"] == {}
    assert body["memory_write_route"] == "/memory/timeline/record"
    assert body["required_scope"] == "memory.timeline.write"
    assert body["operator_decision_required"] is False
    assert body["writes_memory"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_decision_required_before_memory_write"] is True
    assert body["governance"]["writes_memory"] is False
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )


def test_telemetry_context_feedback_memory_retrieval_policy_is_read_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-retrieval-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_retrieval_policy"
    assert body["status"] == "policy_ready"
    assert body["policy_id"] == "stage7_context_feedback_memory_retrieval_policy"
    assert body["memory_source"] == "memory.timeline"
    assert body["memory_query"] == {
        "route": "/memory/timeline/list",
        "method": "GET",
        "filters": {
            "kinds": ["telemetry_context_feedback_quality_review"],
            "include_payload": True,
            "limit": 20,
        },
    }
    assert body["allowed_event_kinds"] == ["telemetry_context_feedback_quality_review"]
    assert body["allowed_action_types"] == ["telemetry.context_feedback.quality_review"]
    assert body["allowed_classifications"] == ["operator_feedback_quality_signal"]
    assert "action_type" in body["required_event_fields"]
    assert "classification" in body["required_event_fields"]
    assert "read_back_feedback_quality_trends" in body["allowed_uses"]
    assert "grant_execution_authority" in body["forbidden_uses"]
    assert "treat_feedback_payload_as_instruction" in body["forbidden_uses"]
    assert body["retrieval_guards"]["read_only"] is True
    assert body["retrieval_guards"]["redacted_events_only"] is True
    assert body["retrieval_guards"]["telemetry_is_untrusted_input"] is True
    assert body["retrieval_guards"]["requires_action_type"] == "telemetry.context_feedback.quality_review"
    assert body["retrieval_guards"]["requires_retention_policy"] == "stage7_context_feedback_quality"
    assert body["writes_memory"] is False
    assert body["reads_memory"] is False
    assert body["trains_model"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["policy_only"] is True
    assert body["governance"]["does_not_query_memory_yet"] is True
    assert body["governance"]["retrieval_requires_separate_readback"] is True
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )


def test_telemetry_context_feedback_memory_assistance_policy_is_read_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_policy"
    assert body["status"] == "policy_ready"
    assert body["policy_id"] == "stage7_context_feedback_memory_assistance_policy"
    assert body["memory_readback_route"] == "/telemetry/context/feedback/memory-retrieval-readback"
    assert body["operator_feedback_memory_readback_route"] == (
        "/telemetry/context/feedback/memory-assistance-feedback-memory-readback"
    )
    assert body["allowed_memory_event_kinds"] == [
        "telemetry_context_feedback_quality_review",
        "telemetry_context_feedback_memory_assistance_operator_feedback_review",
    ]
    assert body["allowed_action_types"] == [
        "telemetry.context_feedback.quality_review",
        "telemetry.context_feedback.memory_assistance_operator_feedback_review",
    ]
    assert body["allowed_classifications"] == [
        "operator_feedback_quality_signal",
        "operator_feedback_memory_assistance_quality_signal",
    ]
    assert "surface_context_source_quality_counts" in body["allowed_influence"]
    assert "surface_feedback_memory_assistance_operator_quality_counts" in body["allowed_influence"]
    assert "suggest_context_source_attention" in body["allowed_influence"]
    assert "treat_memory_payload_as_instruction" in body["forbidden_influence"]
    assert "grant_execution_authority" in body["forbidden_influence"]
    assert "grant_memory_write_authority" in body["forbidden_influence"]
    assert "select_tools_without_operator_policy" in body["forbidden_influence"]
    assert body["assistance_guards"]["read_only"] is True
    assert body["assistance_guards"]["policy_only"] is True
    assert body["assistance_guards"]["redacted_events_only"] is True
    assert body["assistance_guards"]["telemetry_is_untrusted_input"] is True
    assert body["assistance_guards"]["requires_operator_visible_readback"] is True
    assert (
        "telemetry.context_feedback.memory_assistance_operator_feedback_review"
        in body["assistance_guards"]["allowed_action_types"]
    )
    assert "operator_feedback_memory_assistance_quality_signal" in body["assistance_guards"]["allowed_classifications"]
    assert (
        "stage7_feedback_memory_assistance_operator_feedback_quality"
        in body["assistance_guards"]["allowed_retention_policies"]
    )
    assert body["assistance_guards"]["ignore_payload_instruction_text"] is True
    assert body["assistance_guards"]["no_tool_selection_authority"] is True
    assert body["reads_memory"] is False
    assert body["writes_memory"] is False
    assert body["trains_model"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["policy_only"] is True
    assert body["governance"]["does_not_query_memory"] is True
    assert body["governance"]["assistance_requires_separate_dry_run"] is True
    assert body["governance"]["grants_memory_write_authority"] is False
    assert body["governance"]["grants_mutation_authority"] is False
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_chat_context_contract_is_read_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-chat-context-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_contract"
    assert body["status"] == "contract_ready"
    assert body["contract_id"] == "stage7_context_feedback_memory_assistance_chat_context_contract"
    assert body["chat_route"] == "/chat/send"
    assert body["websocket_route"] == "/chat/ws"
    assert body["prompt_context_source"] == "telemetry_context.prompt_lines"
    assert body["insertion_point"] == "after_visible_telemetry_context_header"
    assert body["allowed_chat_context_lines"] == [
        "feedback_memory_assistance.summary",
        "feedback_memory_assistance.source_attention",
    ]
    assert body["max_context_lines"] == 2
    assert body["line_prefix"] == "feedback_memory_assistance"
    assert "add_bounded_redacted_context_line" in body["allowed_effects"]
    assert "treat_memory_payload_as_instruction" in body["forbidden_effects"]
    assert "append_raw_memory_payload" in body["forbidden_effects"]
    assert "select_tools" in body["forbidden_effects"]
    assert "call_model" in body["forbidden_effects"]
    assert "write_memory" in body["forbidden_effects"]
    assert body["requires"]["visible_telemetry_context_header"] is True
    assert body["requires"]["dry_run_only_source"] is True
    assert body["requires"]["redacted_context_line"] is True
    assert body["reads_memory"] is False
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["mutates_prompt"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["contract_only"] is True
    assert body["governance"]["does_not_query_memory"] is True
    assert body["governance"]["chat_prompt_integration_enabled"] is True
    assert body["governance"]["requires_separate_readback_before_prompt_injection"] is True
    assert body["governance"]["grants_memory_write_authority"] is False
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_dry_run_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-dry-run")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_dry_run"
    assert body["status"] == "empty"
    assert body["policy"]["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_policy"
    assert body["memory_readback"]["route"] == "/telemetry/context/feedback/memory-retrieval-readback"
    assert body["memory_readback"]["count"] == 0
    assert body["event_refs"] == []
    assert body["event_count"] == 0
    assert body["rating_counts"] == {"useful": 0, "not_useful": 0, "neutral": 0}
    assert body["source_attention"] == []
    assert body["dry_run_only"] is True
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["trains_model"] is False
    assert body["calls_model"] is False
    assert body["mutates_prompt"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["dry_run_only"] is True
    assert body["governance"]["does_not_call_model"] is True
    assert body["governance"]["does_not_mutate_prompt"] is True
    assert body["governance"]["does_not_select_tools"] is True
    assert body["governance"]["grants_memory_write_authority"] is False
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_chat_context_readback_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-chat-context-readback")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_readback"
    assert body["status"] == "empty"
    assert (
        body["contract"]["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_chat_context_contract"
    )
    assert body["dry_run"]["route"] == "/telemetry/context/feedback/memory-assistance-dry-run"
    assert body["dry_run"]["event_count"] == 0
    assert body["chat_context"] == {
        "target": "telemetry_context.prompt_lines",
        "line_count": 0,
        "max_context_lines": 2,
        "lines": [],
        "visible_header_required": True,
        "telemetry_is_untrusted_input": True,
    }
    assert body["would_change_chat_prompt"] is False
    assert body["applies_to_chat_now"] is False
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["mutates_prompt"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["readback_only"] is True
    assert body["governance"]["chat_prompt_integration_enabled"] is True
    assert body["governance"]["redacts_context_lines"] is True
    assert body["governance"]["does_not_call_model"] is True
    assert body["governance"]["does_not_select_tools"] is True
    assert body["governance"]["grants_memory_write_authority"] is False
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_operator_feedback_review_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-review")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_review"
    assert body["status"] == "empty"
    assert body["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["reviewed_event_count"] == 0
    assert body["rating_counts"] == {"useful": 0, "not_useful": 0, "neutral": 0}
    assert body["quality_signals"] == ["no_feedback_memory_assistance_operator_feedback_recorded"]
    assert body["latest_feedback"] == {}
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["governance"]["uses_explicit_operator_feedback_only"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-memory-quality")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert (
        body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_quality"
    )
    assert body["status"] == "empty"
    assert body["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["review"]["reviewed_event_count"] == 0
    assert body["memory_write_candidate"] == {}
    assert body["required_scope"] == "memory.timeline.write"
    assert body["operator_decision_required"] is False
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["candidate_only"] is True
    assert body["governance"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_retrieval_readback_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-retrieval-readback")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_retrieval_readback"
    assert body["status"] == "empty"
    assert body["policy"]["kind"] == "francis.stage7.telemetry.context_feedback_memory_retrieval_policy"
    assert body["memory_query"] == {
        "route": "/memory/timeline/list",
        "method": "GET",
        "filters": {
            "kinds": ["telemetry_context_feedback_quality_review"],
            "include_payload": True,
            "limit": 20,
        },
    }
    assert body["items"] == []
    assert body["count"] == 0
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["trains_model"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["uses_memory_timeline_read_route"] is True
    assert body["governance"]["uses_policy_filters"] is True
    assert body["governance"]["ignores_payload_instruction_text"] is True
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_operator_feedback_memory_readback_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-memory-readback")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert (
        body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_memory_readback"
    )
    assert body["status"] == "empty"
    assert body["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["policy"]["operator_feedback_memory_readback_route"] == (
        "/telemetry/context/feedback/memory-assistance-feedback-memory-readback"
    )
    assert body["memory_query"] == {
        "route": "/memory/timeline/list",
        "method": "GET",
        "filters": {
            "kinds": ["telemetry_context_feedback_memory_assistance_operator_feedback_review"],
            "include_payload": True,
            "limit": 20,
        },
    }
    assert body["items"] == []
    assert body["count"] == 0
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["trains_model"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["uses_assistance_policy_filters"] is True
    assert body["governance"]["ignores_payload_instruction_text"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_operator_feedback_loop_audit_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_audit"
    assert body["status"] == "awaiting_feedback"
    assert body["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["ready_count"] == 1
    assert body["required_count"] == 6
    assert body["loop_observed"] is False
    assert body["reviewed_event_count"] == 0
    assert body["memory_event_count"] == 0
    assert body["dry_run_event_count"] == 0
    assert body["chat_context_line_count"] == 0
    requirements = {item["id"]: item for item in body["requirements"]}
    assert requirements["targeted_operator_feedback_review"]["ready"] is False
    assert requirements["memory_quality_candidate"]["ready"] is False
    assert requirements["governed_memory_receipt_readback"]["ready"] is False
    assert requirements["assistance_dry_run_consumes_memory_readback"]["ready"] is False
    assert requirements["chat_context_projection_visible"]["ready"] is False
    assert requirements["operator_ui_recording_surface"]["ready"] is True
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["trains_model"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["audit_only"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_call_model"] is True
    assert body["governance"]["does_not_select_tools"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_operator_feedback_loop_e2e_sample_is_read_only_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-sample")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert (
        body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_sample"
    )
    assert body["status"] == "awaiting_loop_evidence"
    assert body["sample_id"] == "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample"
    assert body["loop_observed"] is False
    assert body["audit"]["route"] == "/telemetry/context/feedback/memory-assistance-feedback-loop-audit"
    assert body["audit"]["status"] == "awaiting_feedback"
    assert body["chat_context"]["route"] == "/telemetry/context/feedback/memory-assistance-chat-context-readback"
    assert body["chat_context"]["line_count"] == 0
    assert body["sample_chat_request"]["route"] == "/chat/send"
    assert body["sample_chat_request"]["executed_by_sample"] is False
    assert body["sample_feedback_request"]["route"] == "/telemetry/context/feedback"
    assert body["sample_feedback_request"]["required_scope"] == "telemetry.context.feedback.write"
    assert body["sample_feedback_request"]["executed_by_sample"] is False
    assert (
        body["sample_memory_record_request"]["route"]
        == "/telemetry/context/feedback/memory-assistance-feedback-memory-quality"
    )
    assert body["sample_memory_record_request"]["required_scope"] == "memory.timeline.write"
    assert body["sample_memory_record_request"]["executed_by_sample"] is False
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["writes_feedback"] is False
    assert body["sends_chat"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["sample_only"] is True
    assert body["governance"]["does_not_send_chat"] is True
    assert body["governance"]["does_not_write_feedback"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-acceptance-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert (
        body["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit"
    )
    assert body["status"] == "awaiting_sample_evidence"
    assert body["acceptance_ready"] is False
    assert body["sample_id"] == "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample"
    assert body["ready_count"] == 3
    assert body["required_count"] == 6
    criteria = {item["id"]: item for item in body["acceptance_criteria"]}
    assert criteria["loop_audit_ready"]["ready"] is False
    assert criteria["e2e_sample_readback_ready"]["ready"] is False
    assert criteria["sample_routes_bound"]["ready"] is True
    assert criteria["sample_non_execution_guarded"]["ready"] is True
    assert criteria["redacted_context_lines_ready"]["ready"] is False
    assert criteria["operator_surface_visible"]["ready"] is True
    assert body["sample"]["route"] == "/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-sample"
    assert body["sample"]["status"] == "awaiting_loop_evidence"
    assert body["sample"]["loop_observed"] is False
    assert body["writes_memory"] is False
    assert body["writes_feedback"] is False
    assert body["sends_chat"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["acceptance_audit_only"] is True
    assert body["governance"]["does_not_send_chat"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_call_model"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_live_sample_readback_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-readback")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert (
        body["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_readback"
    )
    assert body["status"] == "awaiting_live_sample_evidence"
    assert body["live_sample_observed"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 4
    criteria = {item["id"]: item for item in body["criteria"]}
    assert criteria["acceptance_audit_ready"]["ready"] is False
    assert criteria["chat_send_ledger_readback"]["ready"] is False
    assert criteria["operator_feedback_readback"]["ready"] is False
    assert criteria["memory_quality_readback"]["ready"] is False
    assert body["chat"] == {}
    assert body["feedback"] == {}
    assert body["memory"] == {}
    assert body["reads_conversation_ledger"] is True
    assert body["reads_feedback"] is True
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["writes_feedback"] is False
    assert body["sends_chat"] is False
    assert body["calls_model"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["live_sample_readback_only"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()
    assert not (data_root / "telemetry" / "context_feedback.jsonl").exists()
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()


def test_telemetry_context_feedback_memory_assistance_live_sample_operator_review_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-review")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert (
        body["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review"
    )
    assert body["status"] == "awaiting_live_sample_evidence"
    assert body["operator_review_ready"] is False
    assert body["live_sample_observed"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 4
    assert body["operator_decision"] == {
        "required": False,
        "recorded": False,
        "decision": "",
        "receipt_id": "",
        "reason": "live_sample_evidence_required_before_operator_review",
    }
    assert body["evidence"]["chat"] == {}
    assert body["evidence"]["feedback"] == {}
    assert body["evidence"]["memory"] == {}
    assert body["reads_conversation_ledger"] is True
    assert body["reads_feedback"] is True
    assert body["reads_memory"] is True
    assert body["writes_memory"] is False
    assert body["writes_feedback"] is False
    assert body["sends_chat"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_review_projection_only"] is True
    assert body["governance"]["does_not_record_operator_decision"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    assert not (data_root / "conversations" / "ledger" / "ledger.jsonl").exists()
    assert not (data_root / "telemetry" / "context_feedback.jsonl").exists()
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()
    assert not data_root.exists()


def _seed_feedback_memory_assistance_live_sample(
    client: TestClient,
    actor: str,
    *,
    chat_use_llm: bool = False,
) -> None:
    seed_feedback = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": actor,
            "reason": "seed live sample assistance feedback",
            "context_id": "tel_ctx_live_sample_seed",
            "surface": "chat",
            "rating": "useful",
            "message_id": "tel_msg_live_sample_seed",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
            },
        },
    )
    assert seed_feedback.status_code == 200
    assert seed_feedback.json()["ok"] is True

    seed_memory = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        json={
            "actor": actor,
            "reason": "seed live sample assistance memory quality",
            "limit": 10,
            "event_id": "evt-feedback-memory-assistance-live-seed",
        },
    )
    assert seed_memory.status_code == 200
    assert seed_memory.json()["writes_memory"] is True

    chat = client.post(
        "/chat/send",
        json={
            "message": "What context should guide this work?",
            "use_llm": chat_use_llm,
            "api_actor": actor,
        },
    )
    assert chat.status_code == 200
    chat_body = chat.json()
    if chat_use_llm:
        execution_trace = chat_body["execution_trace"]
        assert execution_trace["model_call_trace_id"].startswith("model_span_")
        assert execution_trace["model_or_tool_execution_span_captured"] is True
    assistance = chat_body["telemetry_context"]["feedback_memory_assistance_prompt_integration"]
    assert assistance["applies_to_chat_now"] is True
    feedback_target = assistance["feedback_target"]

    live_feedback = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": actor,
            "reason": "record live sample feedback",
            "context_id": feedback_target["context_id"],
            "surface": feedback_target["surface"],
            "rating": "useful",
            "message_id": feedback_target["message_id"],
            "reply_mode": feedback_target["reply_mode"],
            "source_ids": feedback_target["source_ids"],
            "tags": feedback_target["tags"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": assistance["line_count"],
            },
        },
    )
    assert live_feedback.status_code == 200
    assert live_feedback.json()["ok"] is True

    live_memory = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        json={
            "actor": actor,
            "reason": "record live sample assistance memory quality",
            "limit": 10,
            "event_id": "evt-feedback-memory-assistance-live-sample",
        },
    )
    assert live_memory.status_code == 200
    assert live_memory.json()["writes_memory"] is True


def test_telemetry_context_feedback_memory_assistance_live_sample_readback_observes_existing_governed_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "test.telemetry.live"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                actor: [
                    "chat.write",
                    "telemetry.context.feedback.write",
                    "memory.timeline.write",
                ]
            }
        ),
    )

    client = TestClient(create_app())
    seed_feedback = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": actor,
            "reason": "seed live sample assistance feedback",
            "context_id": "tel_ctx_live_sample_seed",
            "surface": "chat",
            "rating": "useful",
            "message_id": "tel_msg_live_sample_seed",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
            },
        },
    )
    assert seed_feedback.status_code == 200
    assert seed_feedback.json()["ok"] is True

    seed_memory = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        json={
            "actor": actor,
            "reason": "seed live sample assistance memory quality",
            "limit": 10,
            "event_id": "evt-feedback-memory-assistance-live-seed",
        },
    )
    assert seed_memory.status_code == 200
    assert seed_memory.json()["writes_memory"] is True

    chat = client.post(
        "/chat/send",
        json={
            "message": "What context should guide this work?",
            "use_llm": False,
            "api_actor": actor,
        },
    )
    assert chat.status_code == 200
    chat_body = chat.json()
    assistance = chat_body["telemetry_context"]["feedback_memory_assistance_prompt_integration"]
    assert assistance["applies_to_chat_now"] is True
    feedback_target = assistance["feedback_target"]

    live_feedback = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": actor,
            "reason": "record live sample feedback",
            "context_id": feedback_target["context_id"],
            "surface": feedback_target["surface"],
            "rating": "useful",
            "message_id": feedback_target["message_id"],
            "reply_mode": feedback_target["reply_mode"],
            "source_ids": feedback_target["source_ids"],
            "tags": feedback_target["tags"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": assistance["line_count"],
            },
        },
    )
    assert live_feedback.status_code == 200
    assert live_feedback.json()["ok"] is True

    live_memory = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        json={
            "actor": actor,
            "reason": "record live sample assistance memory quality",
            "limit": 10,
            "event_id": "evt-feedback-memory-assistance-live-sample",
        },
    )
    assert live_memory.status_code == 200
    assert live_memory.json()["writes_memory"] is True

    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-readback?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "live_sample_observed"
    assert body["live_sample_observed"] is True
    assert body["ready_count"] == body["required_count"] == 4
    criteria = {item["id"]: item for item in body["criteria"]}
    assert all(item["ready"] for item in criteria.values())
    assert criteria["chat_send_ledger_readback"]["evidence"]["line_count"] == 2
    assert criteria["operator_feedback_readback"]["evidence"]["target"] == (
        "feedback_memory_assistance_prompt_integration"
    )
    assert criteria["memory_quality_readback"]["evidence"]["event_id"] in {
        "evt-feedback-memory-assistance-live-seed",
        "evt-feedback-memory-assistance-live-sample",
    }
    assert body["acceptance"]["acceptance_ready"] is True
    assert body["chat"]["status"] == "applied"
    assert body["chat"]["feedback_target_present"] is True
    assert body["chat"]["trace_kind"] == "chat_route_execution_trace"
    assert body["chat"]["trace_id"].startswith("chat_trace_")
    assert body["chat"]["run_id"].startswith("chat_run_")
    assert body["chat"]["route"] == "/chat/send"
    assert body["chat"]["method"] == "POST"
    assert body["chat"]["model_or_tool_execution_span_captured"] is False
    assert body["feedback"]["feedback_id"]
    assert body["memory"]["event_id"] in {
        "evt-feedback-memory-assistance-live-seed",
        "evt-feedback-memory-assistance-live-sample",
    }
    assert body["sends_chat"] is False
    assert body["writes_feedback"] is False
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["uses_existing_chat_route_evidence"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_review"
    )


def test_telemetry_context_feedback_memory_assistance_live_sample_operator_review_projects_operator_decision_gate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "test.telemetry.live.review"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                actor: [
                    "chat.write",
                    "telemetry.context.feedback.write",
                    "memory.timeline.write",
                ]
            }
        ),
    )

    client = TestClient(create_app())
    from francis.chat import router as chat_router

    def fake_generate(prompt: str) -> str:
        assert "feedback_memory_assistance.summary:" in prompt
        return "Feedback memory assistance span observed."

    monkeypatch.setattr(chat_router, "generate", fake_generate)

    _seed_feedback_memory_assistance_live_sample(client, actor, chat_use_llm=True)
    response = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-review?limit=10"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "operator_review_ready"
    assert body["operator_review_ready"] is True
    assert body["live_sample_observed"] is True
    assert body["ready_count"] == body["required_count"] == 4
    assert body["live_sample"]["status"] == "live_sample_observed"
    assert body["operator_decision"] == {
        "required": True,
        "recorded": False,
        "decision": "",
        "receipt_id": "",
        "reason": "operator_review_decision_not_recorded_by_read_only_projection",
    }
    review_items = {item["id"]: item for item in body["review_items"]}
    assert set(review_items) == {
        "acceptance_audit_ready",
        "chat_send_ledger_readback",
        "operator_feedback_readback",
        "memory_quality_readback",
    }
    assert all(item["ready"] for item in review_items.values())
    assert body["evidence"]["chat"]["status"] == "applied"
    assert body["evidence"]["feedback"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["evidence"]["memory"]["event_id"] in {
        "evt-feedback-memory-assistance-live-seed",
        "evt-feedback-memory-assistance-live-sample",
    }
    assert body["writes_memory"] is False
    assert body["writes_feedback"] is False
    assert body["sends_chat"] is False
    assert body["calls_model"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["operator_review_projection_only"] is True
    assert body["governance"]["uses_live_sample_readback"] is True
    assert body["governance"]["does_not_record_operator_decision"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_operator_decision"
    )


def test_telemetry_context_feedback_memory_assistance_live_sample_operator_decision_denies_without_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "test.telemetry.live.decision.denied"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({actor: []}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision",
        json={
            "actor": actor,
            "reason": "operator accepts live sample",
            "decision": "accepted",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["governance"]["required_scope"] == "telemetry.context.feedback.write"
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["grants_mutation_authority"] is False
    assert not (
        data_root / "logs" / "telemetry" / "context_feedback_memory_assistance_live_sample_decisions.jsonl"
    ).exists()


def test_telemetry_context_feedback_memory_assistance_live_sample_operator_decision_records_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    actor = "test.telemetry.live.decision"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                actor: [
                    "chat.write",
                    "telemetry.terminal.write",
                    "telemetry.ide_diagnostics.write",
                    "telemetry.context.feedback.write",
                    "memory.timeline.write",
                ]
            }
        ),
    )

    client = TestClient(create_app())
    from francis.chat import router as chat_router

    def fake_generate(prompt: str) -> str:
        assert "feedback_memory_assistance.summary:" in prompt
        return "Feedback memory assistance span observed."

    monkeypatch.setattr(chat_router, "generate", fake_generate)

    _seed_feedback_memory_assistance_live_sample(client, actor, chat_use_llm=True)
    terminal = client.post(
        "/telemetry/terminal/events",
        json={
            "actor": actor,
            "reason": "record terminal signal for accepted live sample",
            "command": "pytest token=terminalsignalsecret123",
            "cwd": "D:/Francis",
            "shell": "pwsh",
            "exit_code": 0,
            "operation_id": "op_stage7_terminal_signal",
            "artifact_dir": "data/test_runs/pytest/stage7-terminal-signal",
            "tags": ["stage7", "feedback_memory_assistance"],
        },
    )
    assert terminal.status_code == 200
    terminal_body = terminal.json()
    assert terminal_body["ok"] is True
    assert terminal_body["item"]["source_id"] == "terminal"
    ide = client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": actor,
            "reason": "record IDE signal for accepted live sample",
            "source": "vscode",
            "workspace": "D:/Francis",
            "file": "src/francis/token=idesignalsecret123.py",
            "diagnostics": [
                {
                    "severity": "warning",
                    "code": "W900",
                    "message": "review telemetry context token=idediagnosticsecret123",
                }
            ],
            "operation_id": "op_stage7_ide_signal",
            "tags": ["stage7", "feedback_memory_assistance"],
        },
    )
    assert ide.status_code == 200
    ide_body = ide.json()
    assert ide_body["ok"] is True
    assert ide_body["item"]["source_id"] == "ide_diagnostics"
    response = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision",
        json={
            "actor": actor,
            "reason": "operator accepts live sample token=decisionsecret123",
            "decision": "accepted",
            "notes": "looks good token=notessecret123",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["writes_receipt"] is True
    assert body["writes_memory"] is False
    assert body["writes_feedback"] is False
    assert body["sends_chat"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["decision"] == "accepted"
    receipt = body["receipt"]
    assert (
        receipt["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_receipt"
    )
    assert receipt["receipt_id"] == body["receipt_id"]
    assert receipt["actor"] == actor
    assert receipt["decision"] == "accepted"
    assert receipt["operator_review_ready"] is True
    assert receipt["live_sample_observed"] is True
    assert receipt["ready_count"] == receipt["required_count"] == 4
    assert receipt["governance"]["permission_scope"] == "telemetry.context.feedback.write"
    assert receipt["governance"]["explicit_operator_decision"] is True
    assert receipt["governance"]["grants_execution_authority"] is False
    assert receipt["governance"]["grants_mutation_authority"] is False
    receipt_text = json.dumps(receipt, sort_keys=True)
    assert "decisionsecret123" not in receipt_text
    assert "notessecret123" not in receipt_text

    readback = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decisions?limit=10"
    ).json()
    assert readback["status"] == "decision_receipt_readback_ready"
    assert readback["count"] == 1
    assert readback["items"][0]["receipt_id"] == body["receipt_id"]
    assert readback["latest_receipt"]["receipt_id"] == body["receipt_id"]
    assert readback["latest_receipt_id"] == body["receipt_id"]
    assert readback["latest_decision"] == "accepted"
    assert readback["decision_counts"] == {"accepted": 1, "rejected": 0, "needs_more_evidence": 0}
    assert readback["receipt_readback_ready"] is True
    assert readback["redacted"] is True
    assert readback["writes_receipts"] is False
    assert readback["writes_memory"] is False
    assert readback["grants_execution_authority"] is False
    assert readback["governance"]["receipt_readback_ready"] is True
    assert readback["governance"]["redacted_before_storage"] is True
    assert readback["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_outcome_review"
    )

    review = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-review?limit=10"
    ).json()
    assert review["status"] == "operator_decision_recorded"
    assert review["operator_decision"] == {
        "required": False,
        "recorded": True,
        "decision": "accepted",
        "receipt_id": body["receipt_id"],
        "reason": "operator_review_decision_recorded",
    }
    assert review["latest_operator_decision"]["receipt_id"] == body["receipt_id"]
    assert review["operator_decision_total"] == 1
    assert review["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_decision_outcome_review"
    )

    outcome = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-live-sample-operator-decision-outcome-review"
        "?limit=10"
    ).json()
    assert outcome["ok"] is True
    assert (
        outcome["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_live_sample_operator_decision_outcome_review"
    )
    assert outcome["status"] == "outcome_review_ready"
    assert outcome["outcome"] == "operator_accepted_current_live_sample"
    assert outcome["outcome_review_ready"] is True
    assert outcome["latest_decision"] == "accepted"
    assert outcome["latest_receipt_id"] == body["receipt_id"]
    assert outcome["review"] == {
        "accepted_current_sample": True,
        "rejected_current_sample": False,
        "needs_more_evidence": False,
        "receipt_readback_ready": True,
        "receipt_redacted": True,
    }
    assert outcome["receipt_readback"]["latest_receipt_id"] == body["receipt_id"]
    assert outcome["writes_receipts"] is False
    assert outcome["writes_memory"] is False
    assert outcome["writes_feedback"] is False
    assert outcome["sends_chat"] is False
    assert outcome["calls_model"] is False
    assert outcome["selects_tools"] is False
    assert outcome["grants_execution_authority"] is False
    assert outcome["grants_mutation_authority"] is False
    assert outcome["governance"]["read_only"] is True
    assert outcome["governance"]["operator_decision_outcome_review"] is True
    assert outcome["governance"]["does_not_execute_decision"] is True
    assert outcome["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_terminal_context_signal"
    )

    terminal_signal = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-terminal-context-signal?limit=10"
    ).json()
    assert terminal_signal["ok"] is True
    assert terminal_signal["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_terminal_context_signal"
    )
    assert terminal_signal["status"] == "terminal_context_signal_ready"
    assert terminal_signal["terminal_context_signal_ready"] is True
    assert terminal_signal["accepted_operator_outcome"] is True
    assert terminal_signal["outcome_review_ready"] is True
    assert terminal_signal["outcome"] == "operator_accepted_current_live_sample"
    assert terminal_signal["latest_receipt_id"] == body["receipt_id"]
    assert terminal_signal["terminal_event_count"] == 1
    assert terminal_signal["terminal_context_line_count"] == 1
    assert terminal_signal["terminal_context_items"][0]["source_id"] == "terminal"
    assert terminal_signal["terminal_context_items"][0]["event_id"] == terminal_body["item"]["event_id"]
    assert terminal_signal["latest_terminal_event"]["event_id"] == terminal_body["item"]["event_id"]
    assert "terminalsignalsecret123" not in json.dumps(terminal_signal, sort_keys=True)
    assert terminal_signal["reads_terminal_context"] is True
    assert terminal_signal["reads_terminal_events"] is True
    assert terminal_signal["writes_terminal_events"] is False
    assert terminal_signal["writes_receipts"] is False
    assert terminal_signal["writes_memory"] is False
    assert terminal_signal["writes_feedback"] is False
    assert terminal_signal["sends_chat"] is False
    assert terminal_signal["calls_model"] is False
    assert terminal_signal["selects_tools"] is False
    assert terminal_signal["captures_terminal_streams"] is False
    assert terminal_signal["stores_stdout_stderr"] is False
    assert terminal_signal["grants_execution_authority"] is False
    assert terminal_signal["grants_mutation_authority"] is False
    assert terminal_signal["governance"]["read_only"] is True
    assert terminal_signal["governance"]["terminal_context_signal_projection"] is True
    assert terminal_signal["governance"]["does_not_record_terminal_event"] is True
    assert terminal_signal["governance"]["does_not_execute_terminal_command"] is True
    assert terminal_signal["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_git_context_signal"
    )

    git_signal = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-git-context-signal?limit=10"
    ).json()
    assert git_signal["ok"] is True
    assert git_signal["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_git_context_signal"
    assert git_signal["status"] == "git_context_signal_ready"
    assert git_signal["git_context_signal_ready"] is True
    assert git_signal["terminal_context_signal_ready"] is True
    assert git_signal["git_snapshot_ready"] is True
    assert git_signal["branch"]
    assert git_signal["head"]
    assert git_signal["changed_count"] >= len(git_signal["changed_paths"])
    assert git_signal["git_context_line_count"] == 1
    assert git_signal["git_context_items"][0]["source_id"] == "git"
    assert git_signal["git_snapshot"]["source_id"] == "git"
    assert git_signal["terminal_context_signal"]["latest_receipt_id"] == body["receipt_id"]
    assert git_signal["reads_git_context"] is True
    assert git_signal["reads_git_status"] is True
    assert git_signal["writes_git_state"] is False
    assert git_signal["starts_git_watcher"] is False
    assert git_signal["runs_git_fetch"] is False
    assert git_signal["runs_git_pull"] is False
    assert git_signal["runs_git_push"] is False
    assert git_signal["writes_memory"] is False
    assert git_signal["writes_feedback"] is False
    assert git_signal["sends_chat"] is False
    assert git_signal["calls_model"] is False
    assert git_signal["selects_tools"] is False
    assert git_signal["grants_execution_authority"] is False
    assert git_signal["grants_mutation_authority"] is False
    assert git_signal["governance"]["read_only"] is True
    assert git_signal["governance"]["git_context_signal_projection"] is True
    assert git_signal["governance"]["does_not_start_git_watcher"] is True
    assert git_signal["governance"]["does_not_git_fetch"] is True
    assert git_signal["governance"]["does_not_git_pull"] is True
    assert git_signal["governance"]["does_not_git_push"] is True
    assert git_signal["next_smallest_truthful_gap"] == ("stage7_context_feedback_memory_assistance_ide_context_signal")

    ide_signal = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-ide-context-signal?limit=10"
    ).json()
    assert ide_signal["ok"] is True
    assert ide_signal["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_ide_context_signal"
    assert ide_signal["status"] == "ide_context_signal_ready"
    assert ide_signal["ide_context_signal_ready"] is True
    assert ide_signal["git_context_signal_ready"] is True
    assert ide_signal["ide_event_ready"] is True
    assert ide_signal["ide_event_count"] == 1
    assert ide_signal["ide_context_line_count"] == 1
    assert ide_signal["ide_context_items"][0]["source_id"] == "ide_diagnostics"
    assert ide_signal["latest_ide_diagnostic"]["event_id"] == ide_body["item"]["event_id"]
    assert ide_signal["latest_ide_diagnostic"]["highest_severity"] == "warning"
    assert ide_signal["git_context_signal"]["git_context_signal_ready"] is True
    ide_signal_text = json.dumps(ide_signal, sort_keys=True)
    assert "idesignalsecret123" not in ide_signal_text
    assert "idediagnosticsecret123" not in ide_signal_text
    assert ide_signal["reads_ide_context"] is True
    assert ide_signal["reads_ide_diagnostics"] is True
    assert ide_signal["writes_ide_diagnostics"] is False
    assert ide_signal["captures_file_contents"] is False
    assert ide_signal["stores_file_contents"] is False
    assert ide_signal["starts_ide_integration"] is False
    assert ide_signal["writes_memory"] is False
    assert ide_signal["writes_feedback"] is False
    assert ide_signal["sends_chat"] is False
    assert ide_signal["calls_model"] is False
    assert ide_signal["selects_tools"] is False
    assert ide_signal["grants_execution_authority"] is False
    assert ide_signal["grants_mutation_authority"] is False
    assert ide_signal["governance"]["read_only"] is True
    assert ide_signal["governance"]["ide_context_signal_projection"] is True
    assert ide_signal["governance"]["does_not_record_ide_diagnostic"] is True
    assert ide_signal["governance"]["does_not_capture_file_contents"] is True
    assert ide_signal["governance"]["does_not_start_ide_integration"] is True
    assert ide_signal["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_sensing_indicator_summary"
    )

    sensing_summary = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-sensing-indicator-summary?limit=10"
    ).json()
    assert sensing_summary["ok"] is True
    assert sensing_summary["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_sensing_indicator_summary"
    )
    assert sensing_summary["status"] == "sensing_indicators_ready"
    assert sensing_summary["sensing_indicator_summary_ready"] is True
    assert sensing_summary["visible_sensing_indicators_ready"] is True
    assert sensing_summary["indicator_count"] == 3
    assert sensing_summary["ready_indicator_count"] == 3
    assert sensing_summary["visible_indicator_count"] == 3
    assert [item["id"] for item in sensing_summary["indicators"]] == [
        "terminal_context",
        "git_context",
        "ide_context",
    ]
    assert all(item["ready"] is True for item in sensing_summary["indicators"])
    assert all(item["visible"] is True for item in sensing_summary["indicators"])
    assert sensing_summary["ide_context_signal"]["ide_context_signal_ready"] is True
    sensing_summary_text = json.dumps(sensing_summary, sort_keys=True)
    assert "terminalsignalsecret123" not in sensing_summary_text
    assert "idesignalsecret123" not in sensing_summary_text
    assert "idediagnosticsecret123" not in sensing_summary_text
    assert sensing_summary["hidden_sensing"] is False
    assert sensing_summary["captures_background_activity"] is False
    assert sensing_summary["captures_terminal_streams"] is False
    assert sensing_summary["captures_file_contents"] is False
    assert sensing_summary["starts_terminal_capture"] is False
    assert sensing_summary["starts_git_watcher"] is False
    assert sensing_summary["starts_ide_integration"] is False
    assert sensing_summary["writes_memory"] is False
    assert sensing_summary["writes_feedback"] is False
    assert sensing_summary["sends_chat"] is False
    assert sensing_summary["calls_model"] is False
    assert sensing_summary["selects_tools"] is False
    assert sensing_summary["grants_execution_authority"] is False
    assert sensing_summary["grants_mutation_authority"] is False
    assert sensing_summary["governance"]["read_only"] is True
    assert sensing_summary["governance"]["visible_sensing_indicator_projection"] is True
    assert sensing_summary["governance"]["hidden_sensing"] is False
    assert sensing_summary["governance"]["does_not_start_terminal_capture"] is True
    assert sensing_summary["governance"]["does_not_start_git_watcher"] is True
    assert sensing_summary["governance"]["does_not_start_ide_integration"] is True
    assert sensing_summary["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_context_surface_review"
    )

    operator_surface = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-operator-context-surface-review?limit=10"
    ).json()
    assert operator_surface["ok"] is True
    assert operator_surface["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_operator_context_surface_review"
    )
    assert operator_surface["status"] == "operator_context_surface_ready"
    assert operator_surface["operator_context_surface_ready"] is True
    assert operator_surface["sensing_indicator_summary_ready"] is True
    assert operator_surface["surface_id"] == "telemetry_continuation_panel"
    assert operator_surface["surface_label"] == "Telemetry & Continuation"
    assert operator_surface["visible_section_count"] == operator_surface["surface_section_count"]
    assert operator_surface["indicator_ids"] == ["terminal_context", "git_context", "ide_context"]
    assert [section["id"] for section in operator_surface["visible_sections"]] == [
        "telemetry_feedback_memory_assistance_status_badges",
        "terminal_context_signal_card",
        "git_context_signal_card",
        "ide_context_signal_card",
        "sensing_indicator_summary_card",
    ]
    assert all(section["visible"] is True for section in operator_surface["visible_sections"])
    assert operator_surface["sensing_indicator_summary"]["sensing_indicator_summary_ready"] is True
    operator_surface_text = json.dumps(operator_surface, sort_keys=True)
    assert "terminalsignalsecret123" not in operator_surface_text
    assert "idesignalsecret123" not in operator_surface_text
    assert "idediagnosticsecret123" not in operator_surface_text
    assert operator_surface["read_only"] is True
    assert operator_surface["hidden_sensing"] is False
    assert operator_surface["writes_memory"] is False
    assert operator_surface["writes_feedback"] is False
    assert operator_surface["sends_chat"] is False
    assert operator_surface["calls_model"] is False
    assert operator_surface["selects_tools"] is False
    assert operator_surface["grants_execution_authority"] is False
    assert operator_surface["grants_mutation_authority"] is False
    assert operator_surface["governance"]["read_only"] is True
    assert operator_surface["governance"]["operator_surface_review"] is True
    assert operator_surface["governance"]["uses_visible_sensing_indicator_summary"] is True
    assert operator_surface["governance"]["does_not_start_terminal_capture"] is True
    assert operator_surface["governance"]["does_not_start_git_watcher"] is True
    assert operator_surface["governance"]["does_not_start_ide_integration"] is True
    assert operator_surface["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_action_quality_signal_review"
    )

    action_quality = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-action-quality-signal-review?limit=10"
    ).json()
    assert action_quality["ok"] is True
    assert action_quality["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_action_quality_signal_review"
    )
    assert action_quality["status"] == "action_quality_signals_ready"
    assert action_quality["action_quality_signal_review_ready"] is True
    assert action_quality["ready_signal_count"] == action_quality["signal_count"] == 4
    assert [signal["id"] for signal in action_quality["action_quality_signals"]] == [
        "visible_operator_context_surface",
        "accepted_live_sample_operator_decision",
        "explicit_operator_feedback_quality_signal",
        "governed_memory_quality_signal_readback",
    ]
    assert all(signal["ready"] is True for signal in action_quality["action_quality_signals"])
    assert action_quality["quality_signals"] == ["operator_reported_useful_feedback_memory_assistance"]
    assert action_quality["reviewed_event_count"] >= 1
    assert action_quality["memory_quality_event_count"] >= 1
    assert action_quality["latest_memory_quality_event_id"]
    assert action_quality["operator_surface_ready"] is True
    assert action_quality["accepted_live_sample"] is True
    assert action_quality["operator_surface_review"]["operator_context_surface_ready"] is True
    assert action_quality["feedback_review"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert action_quality["memory_readback"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert action_quality["outcome_review"]["outcome"] == "operator_accepted_current_live_sample"
    action_quality_text = json.dumps(action_quality, sort_keys=True)
    assert "terminalsignalsecret123" not in action_quality_text
    assert "idesignalsecret123" not in action_quality_text
    assert "idediagnosticsecret123" not in action_quality_text
    assert action_quality["capture_mode"] == "explicit_operator_feedback_and_receipt_readback"
    assert action_quality["read_only"] is True
    assert action_quality["model_scored_quality"] is False
    assert action_quality["writes_memory"] is False
    assert action_quality["writes_feedback"] is False
    assert action_quality["mutates_prompt"] is False
    assert action_quality["sends_chat"] is False
    assert action_quality["calls_model"] is False
    assert action_quality["selects_tools"] is False
    assert action_quality["grants_execution_authority"] is False
    assert action_quality["grants_mutation_authority"] is False
    assert action_quality["governance"]["read_only"] is True
    assert action_quality["governance"]["action_quality_signal_review"] is True
    assert action_quality["governance"]["uses_explicit_operator_feedback_only"] is True
    assert action_quality["governance"]["uses_live_sample_operator_decision_receipt"] is True
    assert action_quality["governance"]["uses_governed_memory_quality_readback"] is True
    assert action_quality["governance"]["model_scored_quality"] is False
    assert action_quality["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_primary_loop_evidence_review"
    )

    primary_loop = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-primary-loop-evidence-review?limit=10"
    ).json()
    assert primary_loop["ok"] is True
    assert primary_loop["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_primary_loop_evidence_review"
    )
    assert primary_loop["status"] == "primary_loop_evidence_ready"
    assert primary_loop["primary_loop_evidence_ready"] is True
    assert primary_loop["ready_count"] == primary_loop["required_count"] == 8
    assert [item["id"] for item in primary_loop["primary_loop_evidence"]] == [
        "interface",
        "plan",
        "governance",
        "identity",
        "execution",
        "receipt_trace",
        "memory",
        "ui_return",
    ]
    assert all(item["ready"] is True for item in primary_loop["primary_loop_evidence"])
    assert primary_loop["receipt_trace_kind"] == "receipt_backed_readback"
    assert primary_loop["true_execution_trace_observed"] is True
    assert primary_loop["chat_route_execution_trace_observed"] is True
    assert primary_loop["chat_route_trace_id"].startswith("chat_trace_")
    assert primary_loop["chat_route_run_id"].startswith("chat_run_")
    assert primary_loop["operator_decision_receipt_id"] == body["receipt_id"]
    assert primary_loop["memory_quality_event_id"]
    assert primary_loop["action_quality_review"]["action_quality_signal_review_ready"] is True
    assert primary_loop["live_sample_readback"]["live_sample_observed"] is True
    assert primary_loop["operator_review"]["latest_operator_decision"]["receipt_id"] == body["receipt_id"]
    assert primary_loop["outcome_review"]["outcome"] == "operator_accepted_current_live_sample"
    primary_loop_text = json.dumps(primary_loop, sort_keys=True)
    assert "terminalsignalsecret123" not in primary_loop_text
    assert "idesignalsecret123" not in primary_loop_text
    assert "idediagnosticsecret123" not in primary_loop_text
    assert primary_loop["read_only"] is True
    assert primary_loop["writes_memory"] is False
    assert primary_loop["writes_feedback"] is False
    assert primary_loop["mutates_prompt"] is False
    assert primary_loop["sends_chat"] is False
    assert primary_loop["calls_model"] is False
    assert primary_loop["selects_tools"] is False
    assert primary_loop["grants_execution_authority"] is False
    assert primary_loop["grants_mutation_authority"] is False
    assert primary_loop["governance"]["read_only"] is True
    assert primary_loop["governance"]["primary_loop_evidence_review"] is True
    assert primary_loop["governance"]["receipt_trace_not_true_execution_trace"] is True
    assert primary_loop["governance"]["uses_action_quality_signal_review"] is True
    assert primary_loop["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_memory_poisoning_review"
    )

    poisoning = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-memory-poisoning-review?limit=10"
    ).json()
    assert poisoning["ok"] is True
    assert poisoning["kind"] == ("francis.stage7.telemetry.context_feedback_memory_assistance_memory_poisoning_review")
    assert poisoning["status"] == "memory_poisoning_review_ready"
    assert poisoning["memory_poisoning_review_ready"] is True
    assert poisoning["ready_count"] == poisoning["required_count"] == 5
    assert [item["id"] for item in poisoning["poisoning_controls"]] == [
        "memory_timeline_write_contract",
        "poison_pattern_detection",
        "untrusted_payload_influence_blocked",
        "existing_memory_readback_clean",
        "primary_loop_receipt_trace_bounded",
    ]
    assert all(item["ready"] is True for item in poisoning["poisoning_controls"])
    assert [item["detected_pattern"] for item in poisoning["poison_pattern_samples"]] == [
        "ignore previous instructions",
        "system prompt override",
    ]
    assert all(
        item["expected_error"] == "memory_poisoning_input_denied" for item in poisoning["poison_pattern_samples"]
    )
    assert poisoning["detected_poisoned_memory_items"] == []
    assert poisoning["detected_poisoned_memory_item_count"] == 0
    assert poisoning["primary_loop_evidence"]["primary_loop_evidence_ready"] is True
    poisoning_controls = {item["id"]: item for item in poisoning["poisoning_controls"]}
    assert (
        poisoning_controls["primary_loop_receipt_trace_bounded"]["evidence"]["chat_route_execution_trace_observed"]
        is True
    )
    assert poisoning["memory_readback"]["count"] >= 1
    assert poisoning["read_only"] is True
    assert poisoning["executes_poison_probe"] is False
    assert poisoning["writes_memory"] is False
    assert poisoning["writes_feedback"] is False
    assert poisoning["mutates_prompt"] is False
    assert poisoning["sends_chat"] is False
    assert poisoning["calls_model"] is False
    assert poisoning["selects_tools"] is False
    assert poisoning["grants_execution_authority"] is False
    assert poisoning["grants_mutation_authority"] is False
    assert poisoning["governance"]["read_only"] is True
    assert poisoning["governance"]["memory_poisoning_review"] is True
    assert poisoning["governance"]["uses_memory_timeline_poison_detector"] is True
    assert poisoning["governance"]["does_not_execute_poison_probe"] is True
    assert poisoning["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_true_execution_trace_review"
    )

    trace_review = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-true-execution-trace-review?limit=10"
    ).json()
    assert trace_review["ok"] is True
    assert trace_review["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_true_execution_trace_review"
    )
    assert trace_review["status"] == "true_execution_trace_review_ready"
    assert trace_review["review_ready"] is True
    assert trace_review["receipt_backed_trace_observed"] is True
    assert trace_review["receipt_backed_trace_count"] == 4
    assert trace_review["true_execution_trace_observed"] is True
    assert trace_review["true_execution_trace_count"] == 2
    assert [item["id"] for item in trace_review["trace_sources"]] == [
        "chat_interface_readback",
        "operator_feedback_receipt",
        "operator_decision_receipt",
        "memory_quality_receipt",
        "chat_route_execution_trace",
        "model_or_tool_execution_span",
    ]
    trace_sources = {item["id"]: item for item in trace_review["trace_sources"]}
    assert trace_sources["chat_route_execution_trace"]["ready"] is True
    assert trace_sources["chat_route_execution_trace"]["evidence"]["trace_id"].startswith("chat_trace_")
    assert trace_sources["chat_route_execution_trace"]["evidence"]["run_id"].startswith("chat_run_")
    assert trace_sources["chat_route_execution_trace"]["evidence"]["route"] == "/chat/send"
    assert trace_sources["model_or_tool_execution_span"]["ready"] is True
    assert trace_sources["model_or_tool_execution_span"]["evidence"]["model_call_trace_id"].startswith("model_span_")
    assert trace_sources["model_or_tool_execution_span"]["evidence"]["model_call_kind"] == "llm_generate"
    assert trace_sources["model_or_tool_execution_span"]["evidence"]["model_call_requested"] is True
    assert trace_sources["model_or_tool_execution_span"]["evidence"]["model_call_response_observed"] is True
    assert trace_review["missing_true_execution_trace"] == []
    assert trace_review["primary_loop_evidence"]["primary_loop_evidence_ready"] is True
    assert trace_review["primary_loop_evidence"]["receipt_trace_kind"] == "receipt_backed_readback"
    assert trace_review["primary_loop_evidence"]["chat_route_execution_trace_observed"] is True
    assert trace_review["poisoning_review"]["memory_poisoning_review_ready"] is True
    assert trace_review["read_only"] is True
    assert trace_review["writes_memory"] is False
    assert trace_review["writes_feedback"] is False
    assert trace_review["mutates_prompt"] is False
    assert trace_review["sends_chat"] is False
    assert trace_review["calls_model"] is False
    assert trace_review["selects_tools"] is False
    assert trace_review["grants_execution_authority"] is False
    assert trace_review["grants_mutation_authority"] is False
    assert trace_review["governance"]["true_execution_trace_review"] is True
    assert trace_review["governance"]["receipt_trace_not_true_execution_trace"] is True
    assert trace_review["governance"]["reports_missing_true_execution_trace"] is True
    assert trace_review["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_done_criteria_review"
    )

    done_review = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-done-criteria-review?limit=10"
    ).json()
    assert done_review["ok"] is True
    assert done_review["kind"] == ("francis.stage7.telemetry.context_feedback_memory_assistance_done_criteria_review")
    assert done_review["status"] == "done_criteria_ready"
    assert done_review["done_criteria_ready"] is True
    assert done_review["ready_count"] == done_review["required_count"] == 6
    assert [item["id"] for item in done_review["criteria"]] == [
        "useful_action_quality",
        "scoped_lawful_policy",
        "redacted_context",
        "visible_non_invasive_sensing",
        "traceable_primary_loop",
        "ui_return_visible",
    ]
    assert all(item["ready"] is True for item in done_review["criteria"])
    done_criteria = {item["id"]: item for item in done_review["criteria"]}
    assert done_criteria["traceable_primary_loop"]["evidence"]["true_execution_trace_count"] == 2
    assert done_criteria["traceable_primary_loop"]["evidence"]["missing_true_execution_trace"] == []
    assert done_criteria["visible_non_invasive_sensing"]["evidence"]["visible_indicator"] is True
    assert done_criteria["visible_non_invasive_sensing"]["evidence"]["hidden_sensing"] is False
    assert done_criteria["ui_return_visible"]["evidence"]["surface"] == "Telemetry & Continuation"
    assert done_review["trace_review"]["status"] == "true_execution_trace_review_ready"
    assert done_review["read_only"] is True
    assert done_review["writes_memory"] is False
    assert done_review["writes_feedback"] is False
    assert done_review["sends_chat"] is False
    assert done_review["calls_model"] is False
    assert done_review["selects_tools"] is False
    assert done_review["grants_execution_authority"] is False
    assert done_review["grants_mutation_authority"] is False
    assert done_review["governance"]["done_criteria_review"] is True
    assert done_review["governance"]["does_not_mark_stage7_closed"] is True
    assert done_review["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_multi_source_usefulness_review"
    )

    usefulness = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-multi-source-usefulness-review?limit=10"
    ).json()
    assert usefulness["ok"] is True
    assert usefulness["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_multi_source_usefulness_review"
    )
    assert usefulness["status"] == "multi_source_usefulness_ready"
    assert usefulness["multi_source_usefulness_ready"] is True
    assert usefulness["ready_count"] == usefulness["required_count"] == 6
    assert usefulness["ready_sources"] == ["terminal", "git", "ide_diagnostics"]
    assert [item["id"] for item in usefulness["criteria"]] == [
        "terminal_signal_useful",
        "git_signal_useful",
        "ide_signal_useful",
        "operator_quality_improved",
        "visible_source_coverage",
        "done_criteria_backstop",
    ]
    assert all(item["ready"] is True for item in usefulness["criteria"])
    usefulness_criteria = {item["id"]: item for item in usefulness["criteria"]}
    assert usefulness_criteria["terminal_signal_useful"]["evidence"]["event_count"] == 1
    assert usefulness_criteria["git_signal_useful"]["evidence"]["branch"]
    assert usefulness_criteria["ide_signal_useful"]["evidence"]["event_count"] == 1
    assert usefulness_criteria["operator_quality_improved"]["evidence"]["quality_signals"] == [
        "operator_reported_useful_feedback_memory_assistance"
    ]
    assert usefulness_criteria["visible_source_coverage"]["evidence"]["ready_sources"] == [
        "terminal",
        "git",
        "ide_diagnostics",
    ]
    assert usefulness["done_criteria_review"]["done_criteria_ready"] is True
    assert usefulness["sensing_summary"]["visible_sensing_indicators_ready"] is True
    assert usefulness["read_only"] is True
    assert usefulness["writes_memory"] is False
    assert usefulness["writes_feedback"] is False
    assert usefulness["sends_chat"] is False
    assert usefulness["calls_model"] is False
    assert usefulness["selects_tools"] is False
    assert usefulness["grants_execution_authority"] is False
    assert usefulness["grants_mutation_authority"] is False
    assert usefulness["governance"]["multi_source_usefulness_review"] is True
    assert usefulness["governance"]["does_not_start_terminal_capture"] is True
    assert usefulness["governance"]["does_not_start_git_watcher"] is True
    assert usefulness["governance"]["does_not_start_ide_integration"] is True
    assert usefulness["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_usage_over_time_review"
    )

    usage = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-operator-usage-over-time-review?limit=10"
    ).json()
    assert usage["ok"] is True
    assert usage["kind"] == (
        "francis.stage7.telemetry.context_feedback_memory_assistance_operator_usage_over_time_review"
    )
    assert usage["status"] == "operator_usage_over_time_ready"
    assert usage["operator_usage_over_time_ready"] is True
    assert usage["observed_event_count"] == 3
    assert usage["operator_feedback_count"] == 2
    assert usage["operator_decision_count"] == 1
    assert usage["rating_counts"] == {"useful": 2, "not_useful": 0, "neutral": 0}
    assert usage["decision_counts"] == {"accepted": 1, "rejected": 0, "needs_more_evidence": 0}
    assert len(usage["usage_by_day"]) == 1
    assert usage["usage_by_day"][0]["operator_feedback_count"] == 2
    assert usage["usage_by_day"][0]["operator_decision_count"] == 1
    assert usage["latest_recorded_ts"] >= usage["first_recorded_ts"] > 0
    assert usage["duration_seconds"] >= 0
    assert [event["kind"] for event in usage["recent_usage_events"]] == [
        "operator_feedback",
        "operator_feedback",
        "operator_decision",
    ]
    assert usage["multi_source_usefulness"]["multi_source_usefulness_ready"] is True
    assert usage["read_only"] is True
    assert usage["writes_usage"] is False
    assert usage["writes_memory"] is False
    assert usage["writes_feedback"] is False
    assert usage["writes_receipts"] is False
    assert usage["sends_chat"] is False
    assert usage["calls_model"] is False
    assert usage["selects_tools"] is False
    assert usage["grants_execution_authority"] is False
    assert usage["grants_mutation_authority"] is False
    assert usage["governance"]["operator_usage_over_time_review"] is True
    assert usage["governance"]["uses_existing_operator_feedback_receipts"] is True
    assert usage["governance"]["uses_existing_operator_decision_receipts"] is True
    assert usage["governance"]["does_not_record_operator_usage"] is True
    assert usage["next_smallest_truthful_gap"] == ("stage7_context_feedback_memory_assistance_closure_readiness_review")

    closure = client.get(
        "/telemetry/context/feedback/memory-assistance-feedback-loop-closure-readiness-review?limit=10"
    ).json()
    assert closure["ok"] is True
    assert closure["kind"] == ("francis.stage7.telemetry.context_feedback_memory_assistance_closure_readiness_review")
    assert closure["status"] == "loop_closure_readiness_ready"
    assert closure["feedback_memory_assistance_loop_closure_readiness_ready"] is True
    assert closure["ready_count"] == closure["required_count"] == 6
    assert [item["id"] for item in closure["criteria"]] == [
        "primary_loop_evidence_ready",
        "done_criteria_ready",
        "multi_source_usefulness_ready",
        "operator_usage_over_time_ready",
        "non_authorizing_review_guard",
        "stage_closure_guard",
    ]
    assert all(item["ready"] is True for item in closure["criteria"])
    closure_criteria = {item["id"]: item for item in closure["criteria"]}
    assert closure_criteria["operator_usage_over_time_ready"]["evidence"]["operator_feedback_count"] == 2
    assert closure_criteria["operator_usage_over_time_ready"]["evidence"]["operator_decision_count"] == 1
    assert closure_criteria["stage_closure_guard"]["evidence"]["marks_stage7_closed"] is False
    assert closure["review_scope"] == "feedback_memory_assistance_primary_loop"
    assert closure["marks_stage7_closed"] is False
    assert closure["requires_operator_stage_closure_decision"] is True
    assert closure["read_only"] is True
    assert closure["writes_usage"] is False
    assert closure["writes_memory"] is False
    assert closure["writes_feedback"] is False
    assert closure["writes_receipts"] is False
    assert closure["sends_chat"] is False
    assert closure["calls_model"] is False
    assert closure["selects_tools"] is False
    assert closure["grants_execution_authority"] is False
    assert closure["grants_mutation_authority"] is False
    assert closure["governance"]["closure_readiness_review"] is True
    assert closure["governance"]["does_not_mark_stage7_closed"] is True
    assert closure["governance"]["operator_stage_closure_decision_required"] is True
    assert closure["next_smallest_truthful_gap"] == ("stage7_memory_write_contract_hardening_review")


def test_telemetry_context_feedback_memory_quality_record_is_empty_without_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.memory": ["memory.timeline.write"]}),
    )

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/context/feedback/memory-quality",
        json={
            "actor": "test.telemetry.memory",
            "reason": "empty review must not write memory",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "empty"
    assert body["memory_event"] is None
    assert body["writes_memory"] is False
    assert body["governance"]["empty_review_does_not_write_memory"] is True
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()


def test_telemetry_context_feedback_records_redacted_explicit_feedback(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.feedback": ["telemetry.context.feedback.write"]}),
    )

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "record context feedback token=reasonsecret123",
            "context_id": "tel_ctx token=ctxsecret123",
            "surface": "chat",
            "rating": "useful",
            "message_id": "msg token=messagesecret123",
            "reply_mode": "llm",
            "notes": "good context token=notessecret123",
            "source_ids": ["terminal", "git", "token=sourcesecret123"],
            "tags": ["stage7", "token=tagsecret123"],
            "meta": {
                "api_key": "metasecret123",
                "prompt_body": "do not store raw prompt token=promptsecret123",
                "model_response": "do not store raw response token=responsesecret123",
                "ticket": "TEL-FEEDBACK",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["source_id"] == "telemetry_context"
    assert body["governance"]["required_scope"] == "telemetry.context.feedback.write"
    assert body["governance"]["stores_prompt_body"] is False
    assert body["governance"]["stores_model_response"] is False
    assert body["governance"]["trains_model"] is False
    assert body["governance"]["grants_execution_authority"] is False
    item = body["item"]
    assert item["kind"] == "francis.stage7.telemetry.context_feedback"
    assert item["capture_mode"] == "explicit_operator_feedback"
    assert item["hidden_sensing"] is False
    assert item["visible_indicator"] is True
    assert item["rating"] == "useful"
    assert item["context_id"] == "tel_ctx token=[REDACTED:secret]"
    assert item["message_id"] == "msg token=[REDACTED:secret]"
    assert item["source_ids"] == ["terminal", "git", "token=[REDACTED:secret]"]
    assert item["meta"]["api_key"] == "[REDACTED:secret]"
    assert item["meta"]["ticket"] == "TEL-FEEDBACK"
    assert "prompt_body" not in item["meta"]
    assert "model_response" not in item["meta"]
    assert item["governance"]["stores_prompt_body"] is False
    assert item["governance"]["stores_model_response"] is False
    assert item["governance"]["trains_model"] is False
    assert item["governance"]["grants_memory_write_authority"] is False

    raw_text = (data_root / "logs" / "telemetry" / "context_feedback.jsonl").read_text(encoding="utf-8")
    for raw_secret in (
        "reasonsecret123",
        "ctxsecret123",
        "messagesecret123",
        "notessecret123",
        "sourcesecret123",
        "tagsecret123",
        "metasecret123",
        "promptsecret123",
        "responsesecret123",
    ):
        assert raw_secret not in raw_text

    listed = client.get("/telemetry/context/feedback?limit=5").json()
    assert listed["ok"] is True
    assert listed["total"] == 1
    assert listed["count"] == 1
    assert listed["items"][0]["feedback_id"] == item["feedback_id"]
    assert listed["governance"]["trains_model"] is False
    assert listed["governance"]["grants_execution_authority"] is False

    context = client.get("/telemetry/context?surface=chat").json()
    assert context["feedback"]["event_count"] == 1
    assert context["feedback"]["required_scope"] == "telemetry.context.feedback.write"
    assert context["feedback"]["review_route"] == "/telemetry/context/feedback/review"


def test_telemetry_context_feedback_review_summarizes_explicit_quality_signals(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.feedback": ["telemetry.context.feedback.write"]}),
    )

    client = TestClient(create_app())
    for payload in (
        {
            "actor": "test.telemetry.feedback",
            "reason": "record useful feedback token=usefulreasonsecret123",
            "context_id": "tel_ctx_useful",
            "surface": "chat",
            "rating": "useful",
            "notes": "helped because terminal context was relevant token=notessecret123",
            "source_ids": ["terminal", "git"],
            "tags": ["stage7", "accurate"],
            "meta": {"prompt_body": "do not store prompt token=promptsecret123"},
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record miss",
            "context_id": "tel_ctx_miss",
            "surface": "chat",
            "rating": "not_useful",
            "notes": "missed IDE diagnostic",
            "source_ids": ["ide_diagnostics"],
            "tags": ["missing"],
            "meta": {"model_response": "do not store response token=responsesecret123"},
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record neutral",
            "context_id": "tel_ctx_neutral",
            "surface": "chat",
            "rating": "unexpected",
            "notes": "neutral",
            "source_ids": ["terminal"],
            "tags": ["stage7"],
        },
    ):
        response = client.post("/telemetry/context/feedback", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True

    body = client.get("/telemetry/context/feedback/review?limit=10").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.context_feedback_review"
    assert body["status"] == "review_ready"
    assert body["capture_mode"] == "explicit_operator_feedback_review"
    assert body["reviewed_event_count"] == 3
    assert body["total"] == 3
    assert body["truncated"] is False
    assert body["rating_counts"] == {"useful": 1, "not_useful": 1, "neutral": 1}
    assert body["source_counts"]["terminal"] == 2
    assert body["source_counts"]["git"] == 1
    assert body["source_counts"]["ide_diagnostics"] == 1
    assert body["tag_counts"]["stage7"] == 2
    assert body["quality_signals"] == [
        "operator_reported_useful_context",
        "operator_reported_context_misses",
        "operator_reported_neutral_context",
    ]
    assert body["latest_feedback"]["context_id"] == "tel_ctx_neutral"
    assert body["latest_feedback"]["rating"] == "neutral"
    assert "notes" not in body["latest_feedback"]
    assert "meta" not in body["latest_feedback"]
    assert body["stores_prompt_body"] is False
    assert body["stores_model_response"] is False
    assert body["trains_model"] is False
    assert body["writes_memory"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["uses_explicit_operator_feedback_only"] is True
    assert (
        body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    review_text = json.dumps(body, sort_keys=True)
    for raw_secret in ("usefulreasonsecret123", "notessecret123", "promptsecret123", "responsesecret123"):
        assert raw_secret not in review_text


def test_telemetry_context_feedback_memory_quality_projects_bounded_memory_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.feedback": ["telemetry.context.feedback.write"]}),
    )

    client = TestClient(create_app())
    for payload in (
        {
            "actor": "test.telemetry.feedback",
            "reason": "record useful feedback token=usefulmemoryreasonsecret123",
            "context_id": "tel_ctx_memory_useful",
            "surface": "chat",
            "rating": "useful",
            "notes": "helped with terminal context token=memorynotessecret123",
            "source_ids": ["terminal", "git"],
            "tags": ["stage7", "accurate"],
            "meta": {"prompt_body": "do not store token=memorypromptsecret123"},
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record miss",
            "context_id": "tel_ctx_memory_miss",
            "surface": "chat",
            "rating": "not_useful",
            "notes": "missed diagnostic token=memorymisssecret123",
            "source_ids": ["ide_diagnostics"],
            "tags": ["missing"],
            "meta": {"model_response": "do not store token=memoryresponsesecret123"},
        },
    ):
        response = client.post("/telemetry/context/feedback", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True

    response = client.get("/telemetry/context/feedback/memory-quality?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "memory_candidate_ready"
    assert body["writes_memory"] is False
    assert body["required_scope"] == "memory.timeline.write"
    assert body["operator_decision_required"] is True
    assert body["governance"]["candidate_only"] is True
    assert body["governance"]["writes_memory"] is False
    assert body["governance"]["grants_memory_write_authority"] is False

    candidate = body["memory_write_candidate"]
    assert candidate["action_type"] == "telemetry.context_feedback.quality_review"
    assert candidate["classification"] == "operator_feedback_quality_signal"
    assert candidate["confidence"] == 0.75
    assert candidate["provenance"] == {
        "source": "telemetry.context.feedback.review",
        "capture_mode": "explicit_operator_feedback_review",
        "reviewed_event_count": 2,
        "total": 2,
    }
    assert candidate["retention"] == {
        "policy": "stage7_context_feedback_quality",
        "class": "quality_signal",
        "ttl_seconds": 2_592_000,
    }
    assert candidate["payload"]["rating_counts"] == {"useful": 1, "not_useful": 1, "neutral": 0}
    assert candidate["payload"]["source_counts"]["terminal"] == 1
    assert candidate["payload"]["source_counts"]["ide_diagnostics"] == 1
    assert candidate["payload"]["latest_feedback"]["context_id"] == "tel_ctx_memory_miss"
    assert "notes" not in candidate["payload"]["latest_feedback"]
    assert "meta" not in candidate["payload"]["latest_feedback"]
    assert candidate["memory_write_contract"]["would_satisfy_required_fields"] is True
    assert candidate["memory_write_contract"]["operator_decision_required"] is True
    assert candidate["memory_write_contract"]["write_route"] == "/memory/timeline/record"
    assert candidate["memory_write_contract"]["required_scope"] == "memory.timeline.write"
    assert candidate["poisoning_guard"]["raw_notes_included"] is False
    assert candidate["poisoning_guard"]["raw_prompt_body_included"] is False
    assert candidate["poisoning_guard"]["raw_model_response_included"] is False
    assert candidate["writes_memory"] is False
    assert candidate["grants_memory_write_authority"] is False
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()

    body_text = json.dumps(body, sort_keys=True)
    for raw_secret in (
        "usefulmemoryreasonsecret123",
        "memorynotessecret123",
        "memorypromptsecret123",
        "memorymisssecret123",
        "memoryresponsesecret123",
    ):
        assert raw_secret not in body_text


def test_telemetry_context_feedback_memory_quality_record_denies_without_memory_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.feedback": ["telemetry.context.feedback.write"]}),
    )

    client = TestClient(create_app())
    recorded = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "record feedback before denied memory write",
            "context_id": "tel_ctx_denied_memory",
            "surface": "chat",
            "rating": "useful",
            "notes": "context helped",
            "source_ids": ["terminal"],
            "tags": ["stage7"],
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    denied = client.post(
        "/telemetry/context/feedback/memory-quality",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "attempt memory quality write without memory scope",
            "limit": 10,
        },
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["source_id"] == "telemetry_context"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "memory.timeline.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()


def test_telemetry_context_feedback_memory_quality_record_writes_governed_memory_event(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.telemetry.feedback": [
                    "telemetry.context.feedback.write",
                    "memory.timeline.write",
                ]
            }
        ),
    )

    client = TestClient(create_app())
    recorded = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "record feedback token=memoryrecordreasonsecret123",
            "context_id": "tel_ctx_memory_record",
            "surface": "chat",
            "rating": "not_useful",
            "notes": "missed context token=memoryrecordnotessecret123",
            "source_ids": ["ide_diagnostics"],
            "tags": ["missing", "stage7"],
            "meta": {
                "prompt_body": "never persist token=memoryrecordpromptsecret123",
                "model_response": "never persist token=memoryrecordresponsesecret123",
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    response = client.post(
        "/telemetry/context/feedback/memory-quality",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "operator records quality token=memoryrecordwritesecret123",
            "limit": 10,
            "event_id": "evt-telemetry-feedback-quality",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["writes_memory"] is True
    assert body["memory_event_id"] == "evt-telemetry-feedback-quality"
    assert body["governance"]["required_scope"] == "memory.timeline.write"
    assert body["governance"]["explicit_operator_decision"] is True
    assert body["governance"]["memory_timeline_contract_enforced"] is True
    assert body["governance"]["stores_prompt_body"] is False
    assert body["governance"]["stores_model_response"] is False
    assert body["governance"]["trains_model"] is False

    event = body["memory_event"]["item"]
    assert event["id"] == "evt-telemetry-feedback-quality"
    assert event["kind"] == "telemetry_context_feedback_quality_review"
    assert event["action_type"] == "telemetry.context_feedback.quality_review"
    assert event["classification"] == "operator_feedback_quality_signal"
    assert event["confidence"] == 0.75
    assert event["actor"] == "test.telemetry.feedback"
    assert event["scope"] == "telemetry.context.feedback"
    assert event["provenance"]["source"] == "telemetry.context.feedback.review"
    assert event["retention"] == {
        "policy": "stage7_context_feedback_quality",
        "class": "quality_signal",
        "ttl_seconds": 2_592_000,
    }
    assert event["payload"]["rating_counts"] == {"useful": 0, "not_useful": 1, "neutral": 0}
    assert event["payload"]["latest_feedback"]["context_id"] == "tel_ctx_memory_record"
    assert "notes" not in event["payload"]["latest_feedback"]
    assert "meta" not in event["payload"]["latest_feedback"]

    fetched = client.get("/memory/timeline/get?id=evt-telemetry-feedback-quality")
    assert fetched.status_code == 200
    assert fetched.json()["ok"] is True
    assert fetched.json()["item"]["action_type"] == "telemetry.context_feedback.quality_review"

    raw_text = (data_root / "memory" / "timeline" / "_events.json").read_text(encoding="utf-8")
    for raw_secret in (
        "memoryrecordreasonsecret123",
        "memoryrecordnotessecret123",
        "memoryrecordpromptsecret123",
        "memoryrecordresponsesecret123",
        "memoryrecordwritesecret123",
    ):
        assert raw_secret not in raw_text

    readback = client.get("/telemetry/context/feedback/memory-retrieval-readback?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["ok"] is True
    assert readback_body["status"] == "readback_ready"
    assert readback_body["count"] == 1
    assert readback_body["reads_memory"] is True
    assert readback_body["writes_memory"] is False
    assert readback_body["governance"]["read_only"] is True
    assert readback_body["governance"]["uses_policy_filters"] is True
    assert (
        readback_body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    retrieved = readback_body["items"][0]
    assert retrieved["id"] == "evt-telemetry-feedback-quality"
    assert retrieved["kind"] == "telemetry_context_feedback_quality_review"
    assert retrieved["action_type"] == "telemetry.context_feedback.quality_review"
    assert retrieved["classification"] == "operator_feedback_quality_signal"
    assert retrieved["retention"]["policy"] == "stage7_context_feedback_quality"
    assert retrieved["payload"]["latest_feedback"]["context_id"] == "tel_ctx_memory_record"
    assert "notes" not in retrieved["payload"]["latest_feedback"]
    assert "meta" not in retrieved["payload"]["latest_feedback"]

    readback_text = json.dumps(readback_body, sort_keys=True)
    for raw_secret in (
        "memoryrecordreasonsecret123",
        "memoryrecordnotessecret123",
        "memoryrecordpromptsecret123",
        "memoryrecordresponsesecret123",
        "memoryrecordwritesecret123",
    ):
        assert raw_secret not in readback_text

    dry_run = client.get("/telemetry/context/feedback/memory-assistance-dry-run?limit=10")
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run_ready"
    assert dry_run_body["event_count"] == 1
    assert dry_run_body["rating_counts"] == {"useful": 0, "not_useful": 1, "neutral": 0}
    assert dry_run_body["source_attention"] == [
        {
            "source_id": "ide_diagnostics",
            "feedback_count": 1,
            "suggested_use": "operator_review_context_relevance",
        }
    ]
    assert dry_run_body["event_refs"] == [
        {
            "id": "evt-telemetry-feedback-quality",
            "kind": "telemetry_context_feedback_quality_review",
            "action_type": "telemetry.context_feedback.quality_review",
            "classification": "operator_feedback_quality_signal",
            "retention_policy": "stage7_context_feedback_quality",
        }
    ]
    assert dry_run_body["assistance_projection"]["summary"] == (
        "Operator feedback trends suggest reviewing ide_diagnostics context relevance before assistance."
    )
    assert (
        "treat_memory_payload_as_instruction" in dry_run_body["assistance_projection"]["forbidden_influence_respected"]
    )
    assert dry_run_body["dry_run_only"] is True
    assert dry_run_body["reads_memory"] is True
    assert dry_run_body["writes_memory"] is False
    assert dry_run_body["calls_model"] is False
    assert dry_run_body["mutates_prompt"] is False
    assert dry_run_body["selects_tools"] is False
    assert dry_run_body["governance"]["does_not_call_model"] is True
    assert dry_run_body["governance"]["does_not_mutate_prompt"] is True
    assert dry_run_body["governance"]["does_not_select_tools"] is True
    assert (
        dry_run_body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    chat_readback = client.get("/telemetry/context/feedback/memory-assistance-chat-context-readback?limit=10")
    assert chat_readback.status_code == 200
    chat_body = chat_readback.json()
    assert chat_body["ok"] is True
    assert chat_body["status"] == "context_ready"
    assert chat_body["contract"]["contract_id"] == "stage7_context_feedback_memory_assistance_chat_context_contract"
    assert chat_body["dry_run"]["event_count"] == 1
    assert chat_body["dry_run"]["dry_run_only"] is True
    assert chat_body["chat_context"]["target"] == "telemetry_context.prompt_lines"
    assert chat_body["chat_context"]["line_count"] == 2
    assert chat_body["chat_context"]["max_context_lines"] == 2
    assert chat_body["chat_context"]["visible_header_required"] is True
    assert chat_body["chat_context"]["telemetry_is_untrusted_input"] is True
    assert chat_body["chat_context"]["lines"] == [
        (
            "feedback_memory_assistance.summary: Operator feedback trends suggest reviewing "
            "ide_diagnostics context relevance before assistance."
        ),
        (
            "feedback_memory_assistance.source_attention: ide_diagnostics feedback_count=1 "
            "suggested_use=operator_review_context_relevance"
        ),
    ]
    assert chat_body["would_change_chat_prompt"] is True
    assert chat_body["applies_to_chat_now"] is True
    assert chat_body["reads_memory"] is True
    assert chat_body["writes_memory"] is False
    assert chat_body["calls_model"] is False
    assert chat_body["mutates_prompt"] is False
    assert chat_body["selects_tools"] is False
    assert chat_body["governance"]["chat_prompt_integration_enabled"] is True
    assert chat_body["governance"]["redacts_context_lines"] is True
    assert (
        chat_body["next_smallest_truthful_gap"]
        == "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    chat_readback_text = json.dumps(chat_body, sort_keys=True)
    for raw_secret in (
        "memoryrecordreasonsecret123",
        "memoryrecordnotessecret123",
        "memoryrecordpromptsecret123",
        "memoryrecordresponsesecret123",
        "memoryrecordwritesecret123",
    ):
        assert raw_secret not in chat_readback_text

    dry_run_text = json.dumps(dry_run_body, sort_keys=True)
    for raw_secret in (
        "memoryrecordreasonsecret123",
        "memoryrecordnotessecret123",
        "memoryrecordpromptsecret123",
        "memoryrecordresponsesecret123",
        "memoryrecordwritesecret123",
    ):
        assert raw_secret not in dry_run_text


def test_telemetry_context_feedback_memory_assistance_operator_feedback_review_summarizes_targeted_feedback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.feedback": ["telemetry.context.feedback.write"]}),
    )

    client = TestClient(create_app())
    for payload in (
        {
            "actor": "test.telemetry.feedback",
            "reason": "record assistance useful token=reviewreasonsecret123",
            "context_id": "tel_ctx_feedback_memory_assistance_chat_useful",
            "surface": "chat",
            "rating": "useful",
            "message_id": "tel_msg_feedback_memory_assistance_chat_useful",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "notes": "useful context token=reviewnotessecret123",
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
                "prompt_body": "do not store token=reviewpromptsecret123",
            },
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record normal context feedback",
            "context_id": "tel_ctx_unrelated",
            "surface": "chat",
            "rating": "not_useful",
            "source_ids": ["ide_diagnostics"],
            "tags": ["stage7"],
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record assistance miss",
            "context_id": "tel_ctx_feedback_memory_assistance_chat_miss",
            "surface": "chat",
            "rating": "not_useful",
            "message_id": "tel_msg_feedback_memory_assistance_chat_miss",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
                "model_response": "do not store token=reviewresponsesecret123",
            },
        },
    ):
        response = client.post("/telemetry/context/feedback", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True

    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-review?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "review_ready"
    assert body["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["reviewed_event_count"] == 2
    assert body["rating_counts"] == {"useful": 1, "not_useful": 1, "neutral": 0}
    assert body["source_counts"]["feedback_memory_assistance"] == 2
    assert body["tag_counts"]["feedback_memory_assistance"] == 2
    assert body["quality_signals"] == [
        "operator_reported_useful_feedback_memory_assistance",
        "operator_reported_feedback_memory_assistance_misses",
    ]
    assert body["latest_feedback"]["context_id"] == "tel_ctx_feedback_memory_assistance_chat_miss"
    assert body["latest_feedback"]["message_id"] == "tel_msg_feedback_memory_assistance_chat_miss"
    assert body["latest_feedback"]["reply_mode"] == "feedback_memory_assistance_prompt_context"
    assert body["latest_feedback"]["rating"] == "not_useful"
    assert body["latest_feedback"]["line_count"] == 2
    assert body["writes_memory"] is False
    assert body["calls_model"] is False
    assert body["selects_tools"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    review_text = json.dumps(body, sort_keys=True)
    for raw_secret in (
        "reviewreasonsecret123",
        "reviewnotessecret123",
        "reviewpromptsecret123",
        "reviewresponsesecret123",
    ):
        assert raw_secret not in review_text


def test_telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality_projects_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.feedback": ["telemetry.context.feedback.write"]}),
    )

    client = TestClient(create_app())
    for payload in (
        {
            "actor": "test.telemetry.feedback",
            "reason": "record assistance useful token=qualityreasonsecret123",
            "context_id": "tel_ctx_feedback_memory_assistance_quality_useful",
            "surface": "chat",
            "rating": "useful",
            "message_id": "tel_msg_feedback_memory_assistance_quality_useful",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "notes": "useful assistance token=qualitynotessecret123",
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
                "prompt_body": "do not store token=qualitypromptsecret123",
            },
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record unrelated context feedback",
            "context_id": "tel_ctx_feedback_memory_unrelated_quality",
            "surface": "chat",
            "rating": "not_useful",
            "source_ids": ["terminal"],
            "tags": ["stage7"],
        },
        {
            "actor": "test.telemetry.feedback",
            "reason": "record assistance miss",
            "context_id": "tel_ctx_feedback_memory_assistance_quality_miss",
            "surface": "chat",
            "rating": "not_useful",
            "message_id": "tel_msg_feedback_memory_assistance_quality_miss",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
                "model_response": "do not store token=qualityresponsesecret123",
            },
        },
    ):
        response = client.post("/telemetry/context/feedback", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True

    response = client.get("/telemetry/context/feedback/memory-assistance-feedback-memory-quality?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "memory_candidate_ready"
    assert body["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["review"]["reviewed_event_count"] == 2
    assert body["operator_decision_required"] is True
    assert body["writes_memory"] is False
    assert body["governance"]["candidate_only"] is True
    assert body["governance"]["writes_memory"] is False
    assert body["governance"]["grants_memory_write_authority"] is False

    candidate = body["memory_write_candidate"]
    assert candidate["kind"] == "telemetry_context_feedback_memory_assistance_operator_feedback_review"
    assert candidate["action_type"] == "telemetry.context_feedback.memory_assistance_operator_feedback_review"
    assert candidate["classification"] == "operator_feedback_memory_assistance_quality_signal"
    assert candidate["confidence"] == 0.76
    assert candidate["provenance"] == {
        "source": "telemetry.context.feedback.memory_assistance_feedback_review",
        "capture_mode": "explicit_operator_feedback_review",
        "target": "feedback_memory_assistance_prompt_integration",
        "reviewed_event_count": 2,
    }
    assert candidate["retention"] == {
        "policy": "stage7_feedback_memory_assistance_operator_feedback_quality",
        "class": "quality_signal",
        "ttl_seconds": 2_592_000,
    }
    assert candidate["payload"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert candidate["payload"]["rating_counts"] == {"useful": 1, "not_useful": 1, "neutral": 0}
    assert candidate["payload"]["source_counts"]["feedback_memory_assistance"] == 2
    assert candidate["payload"]["tag_counts"]["feedback_memory_assistance"] == 2
    assert candidate["payload"]["latest_feedback"]["context_id"] == "tel_ctx_feedback_memory_assistance_quality_miss"
    assert candidate["payload"]["latest_feedback"]["message_id"] == "tel_msg_feedback_memory_assistance_quality_miss"
    assert candidate["payload"]["latest_feedback"]["line_count"] == 2
    assert "notes" not in candidate["payload"]["latest_feedback"]
    assert "meta" not in candidate["payload"]["latest_feedback"]
    assert candidate["memory_write_contract"]["would_satisfy_required_fields"] is True
    assert candidate["memory_write_contract"]["operator_decision_required"] is True
    assert (
        candidate["memory_write_contract"]["record_route"]
        == "/telemetry/context/feedback/memory-assistance-feedback-memory-quality"
    )
    assert candidate["poisoning_guard"]["raw_notes_included"] is False
    assert candidate["poisoning_guard"]["raw_prompt_body_included"] is False
    assert candidate["poisoning_guard"]["raw_model_response_included"] is False
    assert candidate["poisoning_guard"]["targeted_feedback_is_not_instruction"] is True
    assert candidate["writes_memory"] is False
    assert candidate["calls_model"] is False
    assert candidate["selects_tools"] is False
    assert candidate["grants_execution_authority"] is False
    assert candidate["grants_memory_write_authority"] is False
    assert not (data_root / "memory" / "timeline" / "_events.json").exists()

    body_text = json.dumps(body, sort_keys=True)
    for raw_secret in (
        "qualityreasonsecret123",
        "qualitynotessecret123",
        "qualitypromptsecret123",
        "qualityresponsesecret123",
    ):
        assert raw_secret not in body_text


def test_telemetry_context_feedback_memory_assistance_operator_feedback_memory_quality_record_writes_governed_memory_event(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                "test.telemetry.feedback": [
                    "telemetry.context.feedback.write",
                    "memory.timeline.write",
                ]
            }
        ),
    )

    client = TestClient(create_app())
    recorded = client.post(
        "/telemetry/context/feedback",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "record assistance feedback token=assistrecordreasonsecret123",
            "context_id": "tel_ctx_feedback_memory_assistance_record",
            "surface": "chat",
            "rating": "useful",
            "message_id": "tel_msg_feedback_memory_assistance_record",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "notes": "assistance helped token=assistrecordnotessecret123",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance"],
            "meta": {
                "feedback_target_kind": "feedback_memory_assistance_prompt_integration",
                "line_count": 2,
                "prompt_body": "never persist token=assistrecordpromptsecret123",
                "model_response": "never persist token=assistrecordresponsesecret123",
            },
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["ok"] is True

    response = client.post(
        "/telemetry/context/feedback/memory-assistance-feedback-memory-quality",
        json={
            "actor": "test.telemetry.feedback",
            "reason": "operator records assistance quality token=assistrecordwritesecret123",
            "limit": 10,
            "event_id": "evt-feedback-memory-assistance-quality",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["writes_memory"] is True
    assert body["memory_event_id"] == "evt-feedback-memory-assistance-quality"
    assert body["governance"]["required_scope"] == "memory.timeline.write"
    assert body["governance"]["explicit_operator_decision"] is True
    assert body["governance"]["memory_timeline_contract_enforced"] is True
    assert body["governance"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert body["governance"]["stores_prompt_body"] is False
    assert body["governance"]["stores_model_response"] is False
    assert body["governance"]["trains_model"] is False

    event = body["memory_event"]["item"]
    assert event["id"] == "evt-feedback-memory-assistance-quality"
    assert event["kind"] == "telemetry_context_feedback_memory_assistance_operator_feedback_review"
    assert event["action_type"] == "telemetry.context_feedback.memory_assistance_operator_feedback_review"
    assert event["classification"] == "operator_feedback_memory_assistance_quality_signal"
    assert event["confidence"] == 0.76
    assert event["actor"] == "test.telemetry.feedback"
    assert event["scope"] == "telemetry.context.feedback_memory_assistance"
    assert event["provenance"]["source"] == "telemetry.context.feedback.memory_assistance_feedback_review"
    assert event["meta"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert event["retention"] == {
        "policy": "stage7_feedback_memory_assistance_operator_feedback_quality",
        "class": "quality_signal",
        "ttl_seconds": 2_592_000,
    }
    assert event["payload"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert event["payload"]["rating_counts"] == {"useful": 1, "not_useful": 0, "neutral": 0}
    assert event["payload"]["latest_feedback"]["context_id"] == "tel_ctx_feedback_memory_assistance_record"
    assert event["payload"]["latest_feedback"]["message_id"] == "tel_msg_feedback_memory_assistance_record"
    assert event["payload"]["latest_feedback"]["line_count"] == 2
    assert "notes" not in event["payload"]["latest_feedback"]
    assert "meta" not in event["payload"]["latest_feedback"]

    fetched = client.get("/memory/timeline/get?id=evt-feedback-memory-assistance-quality")
    assert fetched.status_code == 200
    assert fetched.json()["ok"] is True
    assert (
        fetched.json()["item"]["action_type"] == "telemetry.context_feedback.memory_assistance_operator_feedback_review"
    )

    readback = client.get("/telemetry/context/feedback/memory-assistance-feedback-memory-readback?limit=10")
    assert readback.status_code == 200
    readback_body = readback.json()
    assert readback_body["ok"] is True
    assert readback_body["status"] == "readback_ready"
    assert readback_body["target"] == "feedback_memory_assistance_prompt_integration"
    assert readback_body["count"] == 1
    assert readback_body["reads_memory"] is True
    assert readback_body["writes_memory"] is False
    assert readback_body["calls_model"] is False
    assert readback_body["selects_tools"] is False
    assert readback_body["governance"]["read_only"] is True
    assert readback_body["governance"]["uses_assistance_policy_filters"] is True
    assert readback_body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )
    retrieved = readback_body["items"][0]
    assert retrieved["id"] == "evt-feedback-memory-assistance-quality"
    assert retrieved["kind"] == "telemetry_context_feedback_memory_assistance_operator_feedback_review"
    assert retrieved["action_type"] == "telemetry.context_feedback.memory_assistance_operator_feedback_review"
    assert retrieved["classification"] == "operator_feedback_memory_assistance_quality_signal"
    assert retrieved["retention"]["policy"] == "stage7_feedback_memory_assistance_operator_feedback_quality"
    assert retrieved["payload"]["target"] == "feedback_memory_assistance_prompt_integration"
    assert retrieved["payload"]["latest_feedback"]["context_id"] == "tel_ctx_feedback_memory_assistance_record"
    assert "notes" not in retrieved["payload"]["latest_feedback"]
    assert "meta" not in retrieved["payload"]["latest_feedback"]

    dry_run = client.get("/telemetry/context/feedback/memory-assistance-dry-run?limit=10")
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["ok"] is True
    assert dry_run_body["status"] == "dry_run_ready"
    assert dry_run_body["event_count"] == 1
    assert dry_run_body["memory_readback"]["operator_feedback_count"] == 1
    assert dry_run_body["memory_readback"]["operator_feedback_route"] == (
        "/telemetry/context/feedback/memory-assistance-feedback-memory-readback"
    )
    assert dry_run_body["rating_counts"] == {"useful": 1, "not_useful": 0, "neutral": 0}
    assert dry_run_body["source_attention"] == [
        {
            "source_id": "feedback_memory_assistance",
            "feedback_count": 1,
            "suggested_use": "operator_review_context_relevance",
        },
        {
            "source_id": "telemetry_context",
            "feedback_count": 1,
            "suggested_use": "operator_review_context_relevance",
        },
    ]
    assert dry_run_body["governance"]["uses_operator_feedback_memory_readback"] is True

    audit = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-audit?limit=10")
    assert audit.status_code == 200
    audit_body = audit.json()
    assert audit_body["ok"] is True
    assert (
        audit_body["kind"] == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_audit"
    )
    assert audit_body["status"] == "loop_observed"
    assert audit_body["loop_observed"] is True
    assert audit_body["ready_count"] == audit_body["required_count"] == 6
    assert audit_body["reviewed_event_count"] == 1
    assert audit_body["memory_event_count"] == 1
    assert audit_body["dry_run_event_count"] == 1
    assert audit_body["chat_context_line_count"] == 2
    audit_requirements = {item["id"]: item for item in audit_body["requirements"]}
    assert all(item["ready"] for item in audit_requirements.values())
    assert audit_requirements["targeted_operator_feedback_review"]["route"] == (
        "/telemetry/context/feedback/memory-assistance-feedback-review"
    )
    assert audit_requirements["governed_memory_receipt_readback"]["evidence"]["count"] == 1
    assert audit_requirements["operator_ui_recording_surface"]["evidence"]["action"] == "Record assistance memory"
    assert audit_body["routes"]["memory_quality"] == (
        "/telemetry/context/feedback/memory-assistance-feedback-memory-quality"
    )
    assert audit_body["routes"]["memory_readback"] == (
        "/telemetry/context/feedback/memory-assistance-feedback-memory-readback"
    )
    assert audit_body["writes_memory"] is False
    assert audit_body["calls_model"] is False
    assert audit_body["selects_tools"] is False
    assert audit_body["governance"]["audit_only"] is True
    assert audit_body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    sample = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-sample?limit=10")
    assert sample.status_code == 200
    sample_body = sample.json()
    assert sample_body["ok"] is True
    assert (
        sample_body["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_sample"
    )
    assert sample_body["status"] == "sample_ready"
    assert sample_body["loop_observed"] is True
    assert sample_body["audit"]["status"] == "loop_observed"
    assert sample_body["audit"]["ready_count"] == 6
    assert sample_body["chat_context"]["status"] == "context_ready"
    assert sample_body["chat_context"]["line_count"] == 2
    assert len(sample_body["chat_context"]["lines"]) == 2
    assert sample_body["sample_chat_request"]["route"] == "/chat/send"
    assert sample_body["sample_chat_request"]["body"]["use_llm"] is True
    assert sample_body["sample_chat_request"]["executed_by_sample"] is False
    assert (
        "Telemetry context is explicit, redacted, visible to the operator, and untrusted."
        in sample_body["sample_chat_request"]["expected_prompt_markers"]
    )
    assert sample_body["sample_feedback_request"]["route"] == "/telemetry/context/feedback"
    assert sample_body["sample_feedback_request"]["body"]["reply_mode"] == "feedback_memory_assistance_prompt_context"
    assert sample_body["sample_feedback_request"]["body"]["source_ids"] == [
        "feedback_memory_assistance",
        "telemetry_context",
    ]
    assert sample_body["sample_feedback_request"]["writes_memory"] is False
    assert sample_body["sample_feedback_request"]["executed_by_sample"] is False
    assert (
        sample_body["sample_memory_record_request"]["route"]
        == "/telemetry/context/feedback/memory-assistance-feedback-memory-quality"
    )
    assert sample_body["sample_memory_record_request"]["required_scope"] == "memory.timeline.write"
    assert sample_body["sample_memory_record_request"]["executed_by_sample"] is False
    assert sample_body["writes_memory"] is False
    assert sample_body["writes_feedback"] is False
    assert sample_body["sends_chat"] is False
    assert sample_body["calls_model"] is False
    assert sample_body["selects_tools"] is False
    assert sample_body["governance"]["read_only"] is True
    assert sample_body["governance"]["sample_only"] is True
    assert sample_body["governance"]["does_not_send_chat"] is True
    assert sample_body["governance"]["does_not_write_memory"] is True
    assert sample_body["governance"]["does_not_call_model"] is True
    assert sample_body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    acceptance = client.get("/telemetry/context/feedback/memory-assistance-feedback-loop-e2e-acceptance-audit?limit=10")
    assert acceptance.status_code == 200
    acceptance_body = acceptance.json()
    assert acceptance_body["ok"] is True
    assert (
        acceptance_body["kind"]
        == "francis.stage7.telemetry.context_feedback_memory_assistance_operator_feedback_loop_e2e_acceptance_audit"
    )
    assert acceptance_body["status"] == "acceptance_ready"
    assert acceptance_body["acceptance_ready"] is True
    assert acceptance_body["ready_count"] == acceptance_body["required_count"] == 6
    assert acceptance_body["sample_id"] == "stage7_feedback_memory_assistance_operator_feedback_loop_e2e_sample"
    acceptance_criteria = {item["id"]: item for item in acceptance_body["acceptance_criteria"]}
    assert all(item["ready"] for item in acceptance_criteria.values())
    assert acceptance_criteria["loop_audit_ready"]["evidence"]["ready_count"] == 6
    assert acceptance_criteria["sample_routes_bound"]["evidence"]["chat_route"] == "/chat/send"
    assert acceptance_criteria["sample_non_execution_guarded"]["status"] == "non_executing"
    assert acceptance_criteria["redacted_context_lines_ready"]["evidence"]["line_count"] == 2
    assert acceptance_body["sample"]["status"] == "sample_ready"
    assert acceptance_body["sample"]["loop_observed"] is True
    assert acceptance_body["sample"]["chat_context_line_count"] == 2
    assert acceptance_body["writes_memory"] is False
    assert acceptance_body["writes_feedback"] is False
    assert acceptance_body["sends_chat"] is False
    assert acceptance_body["calls_model"] is False
    assert acceptance_body["selects_tools"] is False
    assert acceptance_body["governance"]["read_only"] is True
    assert acceptance_body["governance"]["acceptance_audit_only"] is True
    assert acceptance_body["governance"]["does_not_send_chat"] is True
    assert acceptance_body["governance"]["does_not_write_memory"] is True
    assert acceptance_body["governance"]["does_not_call_model"] is True
    assert acceptance_body["next_smallest_truthful_gap"] == (
        "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
    )

    raw_text = (data_root / "memory" / "timeline" / "_events.json").read_text(encoding="utf-8")
    for raw_secret in (
        "assistrecordreasonsecret123",
        "assistrecordnotessecret123",
        "assistrecordpromptsecret123",
        "assistrecordresponsesecret123",
        "assistrecordwritesecret123",
    ):
        assert raw_secret not in raw_text
    dry_run_text = json.dumps(dry_run_body, sort_keys=True)
    readback_text = json.dumps(readback_body, sort_keys=True)
    for raw_secret in (
        "assistrecordreasonsecret123",
        "assistrecordnotessecret123",
        "assistrecordpromptsecret123",
        "assistrecordresponsesecret123",
        "assistrecordwritesecret123",
    ):
        assert raw_secret not in readback_text
        assert raw_secret not in dry_run_text
        assert raw_secret not in json.dumps(audit_body, sort_keys=True)
        assert raw_secret not in json.dumps(sample_body, sort_keys=True)
        assert raw_secret not in json.dumps(acceptance_body, sort_keys=True)


def test_terminal_telemetry_denies_event_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/terminal/events",
        json={
            "actor": "test.telemetry.write",
            "reason": "record denied command outcome",
            "command": "echo denied",
            "cwd": str(tmp_path),
            "exit_code": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not data_root.exists()


def test_terminal_telemetry_records_redacted_explicit_command_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({"test.telemetry.write": ["telemetry.terminal.write"]}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/terminal/events",
        json={
            "actor": "test.telemetry.write",
            "reason": "record terminal outcome token=reasonsecret123",
            "command": "echo token=commandsecret123",
            "cwd": str(tmp_path / "password=cwdsecret123"),
            "shell": "powershell",
            "exit_code": 0,
            "duration_ms": 42,
            "operation_id": "op_terminal",
            "approval_id": "apr_terminal",
            "trace_id": "trace_terminal",
            "run_id": "run_terminal",
            "artifact_dir": "supervised_exec/apr_terminal",
            "tags": ["stage7", "token=tagsecret123"],
            "meta": {"api_key": "metasecret123", "ticket": "TEL-7"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["governance"]["grants_execution_authority"] is False
    item = body["item"]
    assert item["kind"] == "francis.stage7.telemetry.terminal_event"
    assert item["capture_mode"] == "explicit_command_outcome_report"
    assert item["hidden_sensing"] is False
    assert item["governance"]["stores_stdout_stderr"] is False
    assert item["command"] == "echo token=[REDACTED:secret]"
    assert "stdout_tail" not in item
    assert "stderr_tail" not in item
    assert item["operation_id"] == "op_terminal"
    assert item["approval_id"] == "apr_terminal"
    assert item["trace_id"] == "trace_terminal"
    assert item["run_id"] == "run_terminal"
    assert item["artifact_dir"] == "supervised_exec/apr_terminal"
    assert item["meta"]["api_key"] == "[REDACTED:secret]"
    assert item["meta"]["ticket"] == "TEL-7"

    raw_text = (data_root / "logs" / "telemetry" / "terminal_events.jsonl").read_text(encoding="utf-8")
    for raw_secret in (
        "reasonsecret123",
        "commandsecret123",
        "cwdsecret123",
        "tagsecret123",
        "metasecret123",
    ):
        assert raw_secret not in raw_text

    listed = client.get("/telemetry/terminal/events?limit=5").json()
    assert listed["ok"] is True
    assert listed["total"] == 1
    assert listed["items"][0]["event_id"] == item["event_id"]

    status = client.get("/telemetry/status").json()
    sources = {source["id"]: source for source in status["sources"]}
    assert status["active"] is True
    assert status["claim"] == "explicit_telemetry_events_recorded"
    assert status["active_source_total"] >= 1
    assert status["retention"]["status"] == "bounded_redacted_events"
    assert status["retention"]["event_count"] == 1
    assert status["sensing"]["status"] == "explicit_events_recorded"
    assert sources["terminal"]["active"] is True
    assert sources["terminal"]["status"] == "explicit_events_recorded"
    assert sources["terminal"]["signals"] == ["command_outcome"]
    assert sources["terminal"]["retention"]["event_count"] == 1
    assert sources["terminal"]["latest_event"]["event_id"] == item["event_id"]


def test_terminal_scope_projects_permission_without_recording(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({"test.telemetry.write": ["telemetry.terminal.write"]}))

    client = TestClient(create_app())
    body = client.get("/telemetry/terminal/scope?actor=test.telemetry.write").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.terminal_scope"
    assert body["status"] == "write_scope_ready"
    assert body["required_scope"] == "telemetry.terminal.write"
    assert body["governance"]["permission_allowed"] is True
    assert body["governance"]["grants_execution_authority"] is False
    assert body["event_count"] == 0
    assert not data_root.exists()


def test_ide_diagnostics_telemetry_denies_event_without_actor_scope(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({}))

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": "test.telemetry.ide",
            "reason": "record denied diagnostic",
            "file": "src/francis/example.py",
            "diagnostics": [{"severity": "error", "code": "E999", "message": "syntax error"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["source_id"] == "ide_diagnostics"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["required_scope"] == "telemetry.ide_diagnostics.write"
    assert body["governance"]["reason"] == "missing_scopes"
    assert not data_root.exists()


def test_ide_diagnostics_records_redacted_explicit_diagnostic_event(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.telemetry.ide": ["telemetry.ide_diagnostics.write"]}),
    )

    client = TestClient(create_app())
    response = client.post(
        "/telemetry/ide-diagnostics/events",
        json={
            "actor": "test.telemetry.ide",
            "reason": "record IDE diagnostic token=reasonsecret123",
            "source": "vscode",
            "workspace": "D:/Francis",
            "file": "src/francis/password=filesecret123.py",
            "diagnostics": [
                {
                    "severity": "error",
                    "code": "F821",
                    "message": "undefined name token=diagsecret123",
                    "range": {"start_line": 7, "start_character": 3, "end_line": 7, "end_character": 20},
                },
                {
                    "severity": "warning",
                    "code": "W0611",
                    "message": "unused import",
                    "range": {"line": 1, "character": 0},
                },
            ],
            "operation_id": "op_ide",
            "approval_id": "apr_ide",
            "trace_id": "trace_ide",
            "run_id": "run_ide",
            "tags": ["stage7", "token=tagsecret123"],
            "meta": {"api_key": "metasecret123", "ticket": "IDE-7"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "recorded"
    assert body["governance"]["grants_execution_authority"] is False
    assert body["governance"]["stores_file_contents"] is False
    item = body["item"]
    assert item["kind"] == "francis.stage7.telemetry.ide_diagnostic_event"
    assert item["capture_mode"] == "explicit_ide_diagnostic_report"
    assert item["hidden_sensing"] is False
    assert item["governance"]["stores_file_contents"] is False
    assert item["file"] == "src/francis/password=[REDACTED:secret]"
    assert item["diagnostic_count"] == 2
    assert item["highest_severity"] == "error"
    assert item["diagnostics"][0]["message"] == "undefined name token=[REDACTED:secret]"
    assert item["diagnostics"][0]["range"]["start_line"] == 7
    assert item["meta"]["api_key"] == "[REDACTED:secret]"
    assert item["meta"]["ticket"] == "IDE-7"

    raw_text = (data_root / "logs" / "telemetry" / "ide_diagnostics.jsonl").read_text(encoding="utf-8")
    for raw_secret in ("reasonsecret123", "filesecret123", "diagsecret123", "tagsecret123", "metasecret123"):
        assert raw_secret not in raw_text

    listed = client.get("/telemetry/ide-diagnostics/events?limit=5").json()
    assert listed["ok"] is True
    assert listed["total"] == 1
    assert listed["items"][0]["event_id"] == item["event_id"]
    assert listed["stores_file_contents"] is False

    scope = client.get("/telemetry/ide-diagnostics/scope?actor=test.telemetry.ide").json()
    assert scope["ok"] is True
    assert scope["status"] == "write_scope_ready"
    assert scope["required_scope"] == "telemetry.ide_diagnostics.write"
    assert scope["governance"]["captures_file_contents"] is False

    status = client.get("/telemetry/status").json()
    sources = {source["id"]: source for source in status["sources"]}
    assert status["active"] is True
    assert status["claim"] == "explicit_telemetry_events_recorded"
    assert sources["ide_diagnostics"]["active"] is True
    assert sources["ide_diagnostics"]["status"] == "explicit_diagnostics_recorded"
    assert sources["ide_diagnostics"]["signals"] == ["diagnostic_summary"]
    assert sources["ide_diagnostics"]["latest_diagnostic"]["event_id"] == item["event_id"]
    assert sources["ide_diagnostics"]["latest_diagnostic"]["file"] == "src/francis/password=[REDACTED:secret]"
    assert sources["ide_diagnostics"]["latest_diagnostic"]["highest_severity"] == "error"


def test_git_telemetry_status_is_readonly_snapshot(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    client = TestClient(create_app())
    body = client.get("/telemetry/git/status?limit=5").json()

    assert body["ok"] is True
    assert body["kind"] == "francis.stage7.telemetry.git_status"
    assert body["source_id"] == "git"
    assert body["capture_mode"] == "explicit_git_status_snapshot"
    assert body["watch_mode"] == "on_request_snapshot"
    assert body["hidden_sensing"] is False
    assert body["visible_indicator"] is True
    assert body["stores_raw_events"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["governance"]["background_watcher"] is False
    assert body["governance"]["git_fetch"] is False
    assert body["governance"]["git_pull"] is False
    assert body["governance"]["git_push"] is False
    assert isinstance(body["changed_paths"], list)
    assert len(body["changed_paths"]) <= 5
    assert body["changed_count"] >= len(body["changed_paths"])
    assert not data_root.exists()

    status = client.get("/telemetry/status").json()
    sources = {source["id"]: source for source in status["sources"]}
    assert sources["git"]["routes"]["status"] == "/telemetry/git/status"
    if body["active"]:
        assert sources["git"]["active"] is True
        assert sources["git"]["status"] == "snapshot_ready"
        assert sources["git"]["latest_snapshot"]["branch"] == body["branch"]


def test_git_telemetry_status_sanitizes_snapshot_exceptions(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    def fail_git(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise RuntimeError("raw git status secret token=gitexceptionsecret123")

    monkeypatch.setattr(telemetry_git.subprocess, "run", fail_git)

    client = TestClient(create_app())
    body = client.get("/telemetry/git/status?limit=5").json()

    assert body["ok"] is True
    assert body["status"] == "unavailable"
    assert body["active"] is False
    assert body["error"] == "internal_api_error"

    response_text = json.dumps(body, sort_keys=True)
    assert "gitexceptionsecret123" not in response_text
    assert "raw git status secret" not in response_text
    assert "RuntimeError" not in response_text
    assert "Traceback" not in response_text
