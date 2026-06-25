from __future__ import annotations

import json
import os

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from francis.chat.continuity.ledger import append
from francis.developer_bridge import repo_tools
from francis.developer_bridge.agents import (
    collaboration_agents_status,
    set_collaboration_agent_enabled,
)
from francis.developer_bridge.body_map import (
    compact_body_map_prompt_line,
    compact_roadmap_gate_prompt_line,
    read_francis_body_map,
)
from francis.developer_bridge.collaboration import (
    list_collaboration_prompts,
    read_collaboration_sessions,
    read_collaboration_transcript,
    submit_collaboration_prompt,
)
from francis.developer_bridge.collaboration_review import latest_review_candidate_line, read_collaboration_review
from francis.developer_bridge.codex_responder import respond_once
from francis.developer_bridge.mcp_server import _server_bind_options, create_mcp_server
from francis.developer_bridge.ollama_participant import respond_once as ollama_respond_once
from francis.developer_bridge.substrate_readiness import read_collaboration_substrate_readiness
from francis.developer_bridge.trust_ladder import compact_trust_ladder_prompt_line, read_francis_trust_ladder
from francis.developer_bridge.repo_tools import (
    DeveloperBridgeError,
    read_repo_file,
    read_supervised_exec_receipt,
    search_repo,
)


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n")


def test_read_repo_file_is_repo_bounded_and_text_only(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_text("Francis bridge note\n", encoding="utf-8")

    result = read_repo_file("docs/note.md")

    assert result["ok"] is True
    assert result["path"] == "docs/note.md"
    assert _normalize_newlines(result["content"]) == "Francis bridge note\n"
    assert result["truncated"] is False
    assert isinstance(result["sha256"], str)


def test_read_repo_file_denies_traversal_and_sensitive_paths(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")

    with pytest.raises(DeveloperBridgeError) as traversal:
        read_repo_file("../outside.txt")
    assert traversal.value.code == "path_traversal_denied"

    with pytest.raises(DeveloperBridgeError) as sensitive:
        read_repo_file(".env")
    assert sensitive.value.code == "sensitive_file_denied"


def test_search_repo_skips_sensitive_files(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    public = tmp_path / "src" / "visible.txt"
    public.parent.mkdir(parents=True)
    public.write_text("developer bridge search needle\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("needle=secret\n", encoding="utf-8")

    result = search_repo("needle")

    assert result["ok"] is True
    assert result["results"] == [{"path": "src/visible.txt", "line": 1, "preview": "developer bridge search needle"}]
    assert result["skipped_sensitive"] == 1


def test_read_supervised_exec_receipt_is_bounded_to_artifact_root(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    receipt = tmp_path / "data" / "artifacts" / "supervised_exec" / "run-123" / "result.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"ok": true}\n', encoding="utf-8")

    result = read_supervised_exec_receipt("run-123", "result.json")

    assert result["ok"] is True
    assert result["run_id"] == "run-123"
    assert result["filename"] == "result.json"
    assert _normalize_newlines(result["content"]) == '{"ok": true}\n'

    with pytest.raises(DeveloperBridgeError) as bad_run_id:
        read_supervised_exec_receipt("../run-123", "result.json")
    assert bad_run_id.value.code == "run_id_denied"

    with pytest.raises(DeveloperBridgeError) as nested_run_id:
        read_supervised_exec_receipt("run-123/nested", "result.json")
    assert nested_run_id.value.code == "run_id_denied"

    with pytest.raises(DeveloperBridgeError) as bad_filename:
        read_supervised_exec_receipt("run-123", "secrets.txt")
    assert bad_filename.value.code == "filename_denied"

    with pytest.raises(DeveloperBridgeError) as traversal_filename:
        read_supervised_exec_receipt("run-123", "../result.json")
    assert traversal_filename.value.code == "filename_denied"


def test_developer_bridge_routes_are_mounted() -> None:
    from francis.api.app import create_app

    app = create_app()
    routes = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/developer-bridge/status" in routes
    assert "/developer-bridge/read-file" in routes
    assert "/developer-bridge/search" in routes
    assert "/developer-bridge/git-diff-summary" in routes
    assert "/developer-bridge/completion-ledger" in routes
    assert "/developer-bridge/supervised-exec-receipt" in routes
    assert "/developer-bridge/collaboration-transcript" in routes
    assert "/developer-bridge/collaboration-review" in routes
    assert "/developer-bridge/collaboration-learning" in routes
    assert "/developer-bridge/collaboration-runtime-health" in routes
    assert "/developer-bridge/collaboration-substrate-readiness" in routes
    assert "/developer-bridge/collaboration-agents" in routes
    assert "/developer-bridge/collaboration-agents/toggle" in routes
    assert "/developer-bridge/francis-body-map" in routes
    assert "/developer-bridge/francis-trust-ladder" in routes


def test_developer_bridge_agent_toggle_is_classified_in_authority_matrix() -> None:
    from francis.api.app import create_app

    matrix = TestClient(create_app()).get("/system/mutating-route-authority-matrix").json()
    entries = {
        (entry["method"], entry["path"]): entry
        for entry in matrix["entries"]
        if entry["path"] == "/developer-bridge/collaboration-agents/toggle"
    }

    assert matrix["missing"] == []
    entry = entries[("POST", "/developer-bridge/collaboration-agents/toggle")]
    assert entry["family"] == "developer_bridge"
    assert entry["required_actor"] == "payload.actor or chat_ui.system default"
    assert entry["required_scope"] == "developer_bridge.operator_console_control"
    assert entry["governance_maturity"] == "bounded_operator_control_receipt"


def test_francis_body_map_exposes_whole_body_without_authority(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "Francis"
    (root / "docs" / "canonical").mkdir(parents=True)
    (root / "docs" / "operations").mkdir(parents=True)
    (root / "meta").mkdir(parents=True)
    (root / "src" / "francis" / "developer_bridge").mkdir(parents=True)
    (root / "apps" / "chat_ui" / "src").mkdir(parents=True)
    (root / "docs" / "canonical" / "BUILD_MANIFEST.md").write_text("# Phase 2\n", encoding="utf-8")
    (root / "docs" / "PLANES.md").write_text("# Planes\n", encoding="utf-8")
    (root / "docs" / "operations" / "COMPLETION_LEDGER.md").write_text(
        "# Ledger\n\n### 2026-06-25 - Existing proof\n",
        encoding="utf-8",
    )
    (root / "meta" / "plane_map.yaml").write_text("planes: []\n", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "collaboration.py").write_text("", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "collaboration_runtime.py").write_text("", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "trust_ladder.py").write_text("", encoding="utf-8")
    (root / "apps" / "chat_ui" / "src" / "App.tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    result = read_francis_body_map()

    assert result["kind"] == "developer_bridge.francis_body_map"
    assert result["ok"] is True
    assert result["mode"] == "read_only"
    assert result["identity"]["local_identity"] == "francis1"  # type: ignore[index]
    assert result["identity"]["provider_name_is_identity"] is False  # type: ignore[index]
    assert result["summary"]["full_body_visible"] is True  # type: ignore[index]
    assert result["summary"]["full_body_authority_granted"] is False  # type: ignore[index]
    assert result["quest"]["percent_complete"] == 83  # type: ignore[index]
    assert result["summary"]["trust_ladder_enforced"] is True  # type: ignore[index]
    assert result["summary"]["runtime_restart_observed"] is False  # type: ignore[index]
    assert result["summary"]["coverage_reviewed"] is True  # type: ignore[index]
    assert result["summary"]["canonical_plane_count"] == 11  # type: ignore[index]
    assert result["summary"]["canonical_plane_covered_count"] == 11  # type: ignore[index]
    assert result["evidence"]["trust_ladder_observed"] is True  # type: ignore[index]
    assert result["evidence"]["runtime_restart_observed"] is False  # type: ignore[index]
    assert result["evidence"]["body_coverage_review_observed"] is True  # type: ignore[index]
    assert result["evidence"]["missing_canonical_plane_ids"] == []  # type: ignore[index]
    assert result["coverage_review"]["observed"] is True  # type: ignore[index]
    assert result["coverage_review"]["capability_complete"] is False  # type: ignore[index]
    assert result["coverage_review"]["grants_execution_authority"] is False  # type: ignore[index]
    assert result["coverage_review"]["open_gap_count"] > 0  # type: ignore[index]
    coverage_items = {item["plane_id"]: item for item in result["coverage_review"]["items"]}  # type: ignore[index]
    assert coverage_items["P7_EXECUTION"]["risk_level"] == "high"
    assert "supervised_exec.py" in coverage_items["P7_EXECUTION"]["next_review_artifact"]
    assert coverage_items["P8_MEMORY"]["risk_level"] == "high"
    assert "promotion review" in coverage_items["P8_MEMORY"]["recommended_next_action"]
    assert result["trust_ladder"]["connected"] is True  # type: ignore[index]
    assert result["trust_ladder"]["decision_contract"] == [  # type: ignore[index]
        "wire_existing",
        "build_missing",
        "tune_prompt_guard",
        "reject_as_drift",
    ]
    assert result["evidence"]["latest_ledger_entry"] == "2026-06-25 - Existing proof"  # type: ignore[index]
    surfaces = {item["id"]: item for item in result["surfaces"]}  # type: ignore[index]
    assert "collaboration" in surfaces
    assert "memory" in surfaces
    assert "governance" in surfaces
    assert "action_intake" in surfaces
    assert "model_tuning" in surfaces
    assert surfaces["collaboration"]["access_mode"] == "read"
    assert surfaces["action_intake"]["access_mode"] == "request"
    assert surfaces["model_tuning"]["connection_state"] == "candidate"
    assert all(item["grants_execution_authority"] is False for item in result["surfaces"])  # type: ignore[index]
    assert all(item["grants_memory_write_authority"] is False for item in result["surfaces"])  # type: ignore[index]
    assert result["governance"]["grants_training_authority"] is False  # type: ignore[index]

    prompt_line = compact_body_map_prompt_line()
    assert "Body map:" in prompt_line
    assert "Francis1 can see whole-body surfaces" in prompt_line
    assert "authority remain false" in prompt_line
    roadmap_gate = compact_roadmap_gate_prompt_line()
    assert "Roadmap:" in roadmap_gate
    assert "ledger first" in roadmap_gate
    assert "main-build candidate-only" in roadmap_gate
    assert "blocked_by_open_orb_gaps" in roadmap_gate
    assert compact_trust_ladder_prompt_line() == "Trust: classify needs; no capability authority."


def test_collaboration_substrate_readiness_blocks_main_build_prompt_for_open_gaps(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "Francis"
    (root / "docs" / "canonical").mkdir(parents=True)
    (root / "docs" / "operations").mkdir(parents=True)
    (root / "meta").mkdir(parents=True)
    (root / "src" / "francis" / "developer_bridge").mkdir(parents=True)
    (root / "apps" / "chat_ui" / "src").mkdir(parents=True)
    (root / "docs" / "canonical" / "BUILD_MANIFEST.md").write_text("# Phase 2\n", encoding="utf-8")
    (root / "docs" / "PLANES.md").write_text("# Planes\n", encoding="utf-8")
    (root / "docs" / "operations" / "COMPLETION_LEDGER.md").write_text(
        "# Ledger\n\n### 2026-06-25 - Existing proof\n",
        encoding="utf-8",
    )
    (root / "meta" / "plane_map.yaml").write_text("planes: []\n", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "collaboration.py").write_text("", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "collaboration_runtime.py").write_text("", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "trust_ladder.py").write_text("", encoding="utf-8")
    (root / "apps" / "chat_ui" / "src" / "App.tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("FRANCIS_ROOT", str(root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    import francis.developer_bridge.substrate_readiness as readiness_module

    monkeypatch.setattr(
        readiness_module,
        "read_collaboration_runtime_health",
        lambda: {
            "kind": "developer_bridge.collaboration_runtime_health",
            "ok": True,
            "mode": "read_only",
            "status": "healthy",
            "collaboration_loop": {
                "turn_count": 12,
                "current_learning_signal": {
                    "observed": True,
                    "stores_full_transcript": False,
                    "grants_training_authority": False,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                    "grants_approval_authority": False,
                    "grants_memory_write_authority": False,
                },
            },
            "governance": {
                "read_only": True,
                "calls_model": False,
                "trains_model": False,
                "stores_full_transcript": False,
                "grants_model_execution_authority": False,
                "grants_repo_mutation_authority": False,
                "grants_approval_authority": False,
                "grants_memory_write_authority": False,
            },
        },
    )
    monkeypatch.setattr(
        readiness_module,
        "read_collaboration_learning_events",
        lambda limit=3: {
            "kind": "developer_bridge.collaboration_learning_events",
            "ok": True,
            "mode": "read_only",
            "items": [
                {
                    "id": "learning-1",
                    "writer_governance": {
                        "stores_full_transcript": False,
                        "grants_execution_authority": False,
                        "grants_mutation_authority": False,
                        "grants_approval_authority": False,
                        "grants_memory_write_authority": False,
                        "grants_model_authority": False,
                    },
                }
            ],
            "governance": {
                "stores_full_transcript": False,
                "calls_model": False,
                "trains_model": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
                "grants_approval_authority": False,
                "grants_memory_write_authority": False,
            },
        },
    )

    result = read_collaboration_substrate_readiness()

    assert result["kind"] == "developer_bridge.collaboration_substrate_readiness"
    assert result["schema_version"] == "developer_bridge_collaboration_substrate_readiness_v1"
    assert result["mode"] == "read_only"
    assert result["status"] == "blocked"
    assert result["summary"]["main_build_prompt_allowed"] is False  # type: ignore[index]
    assert result["summary"]["main_build_prompt_gate"] == "blocked_by_open_orb_gaps"  # type: ignore[index]
    assert result["summary"]["runtime_healthy"] is True  # type: ignore[index]
    assert result["summary"]["trust_ladder_enforced"] is True  # type: ignore[index]
    assert result["summary"]["no_authority_granted"] is True  # type: ignore[index]
    roadmap_alignment = result["roadmap_alignment"]  # type: ignore[index]
    assert roadmap_alignment["status"] == "blocked_candidate_only"  # type: ignore[index]
    assert roadmap_alignment["source_order"] == [  # type: ignore[index]
        "docs/operations/COMPLETION_LEDGER.md",
        "docs/canonical/BUILD_MANIFEST.md",
    ]
    assert roadmap_alignment["ledger_first"] is True  # type: ignore[index]
    assert roadmap_alignment["ledger_observed"] is True  # type: ignore[index]
    assert roadmap_alignment["manifest_observed"] is True  # type: ignore[index]
    assert roadmap_alignment["main_build_prompt_allowed"] is False  # type: ignore[index]
    assert roadmap_alignment["candidate_only_until_review"] is True  # type: ignore[index]
    assert roadmap_alignment["blocks_main_build_prompt"] is True  # type: ignore[index]
    assert roadmap_alignment["grants_execution_authority"] is False  # type: ignore[index]
    assert roadmap_alignment["grants_memory_write_authority"] is False  # type: ignore[index]
    checklist = {item["id"]: item for item in result["checklist"]}  # type: ignore[index]
    assert checklist["ledger_observed"]["status"] == "passed"
    assert checklist["manifest_observed"]["status"] == "passed"
    assert checklist["coverage_gaps_reviewed"]["status"] == "blocked"
    assert checklist["coverage_gaps_reviewed"]["blocks_main_build_prompt"] is True
    assert "docs/operations/COMPLETION_LEDGER.md" in result["required_alignment_sources"]  # type: ignore[operator]
    assert result["governance"]["executes_prompt"] is False  # type: ignore[index]
    assert result["governance"]["grants_repo_mutation_authority"] is False  # type: ignore[index]


def test_francis_body_map_marks_runtime_observation_from_body_trust_turn(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "Francis"
    data = tmp_path / "data"
    (root / "docs" / "canonical").mkdir(parents=True)
    (root / "docs" / "operations").mkdir(parents=True)
    (root / "meta").mkdir(parents=True)
    (root / "src" / "francis" / "developer_bridge").mkdir(parents=True)
    (root / "apps" / "chat_ui" / "src").mkdir(parents=True)
    (root / "docs" / "canonical" / "BUILD_MANIFEST.md").write_text("# Phase 2\n", encoding="utf-8")
    (root / "docs" / "PLANES.md").write_text("# Planes\n", encoding="utf-8")
    (root / "docs" / "operations" / "COMPLETION_LEDGER.md").write_text(
        "# Ledger\n\n### 2026-06-25 - Existing proof\n",
        encoding="utf-8",
    )
    (root / "meta" / "plane_map.yaml").write_text("planes: []\n", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "collaboration.py").write_text("", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "collaboration_runtime.py").write_text("", encoding="utf-8")
    (root / "src" / "francis" / "developer_bridge" / "trust_ladder.py").write_text("", encoding="utf-8")
    (root / "apps" / "chat_ui" / "src" / "App.tsx").write_text("", encoding="utf-8")
    relay_root = data / "integrations" / "developer_bridge" / "collaboration_prompts"
    relay_root.mkdir(parents=True)
    prompt_id = "collab-1111111111111111-222222222222"
    response_id = "collab-3333333333333333-444444444444"
    (relay_root / f"{prompt_id}.json").write_text(
        json.dumps(
            {
                "kind": "developer_bridge.collaboration_prompt",
                "id": prompt_id,
                "created_at": "2026-06-25T15:14:35+00:00",
                "source_agent": "codex",
                "target_agent": "ollama",
                "prompt": (
                    "Body map: Francis1 can see whole-body surfaces; authority remain false. "
                    "Trust: classify needs; no capability authority."
                ),
                "context": "no_action_authority=true.",
            }
        ),
        encoding="utf-8",
    )
    (relay_root / f"{response_id}.json").write_text(
        json.dumps(
            {
                "kind": "developer_bridge.collaboration_prompt",
                "id": response_id,
                "created_at": "2026-06-25T15:15:08+00:00",
                "source_agent": "ollama",
                "target_agent": "codex",
                "prompt": "Francis1 output guard fallback: no authority.",
                "context": f"Francis1 response through the Ollama provider lane for relay {prompt_id}.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRANCIS_ROOT", str(root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data))

    result = read_francis_body_map()

    assert result["summary"]["runtime_restart_observed"] is True  # type: ignore[index]
    assert result["evidence"]["runtime_restart_observed"] is True  # type: ignore[index]
    assert result["evidence"]["latest_runtime_prompt_id"] == prompt_id  # type: ignore[index]
    assert result["evidence"]["latest_runtime_response_id"] == response_id  # type: ignore[index]
    assert result["runtime_observation"]["observed"] is True  # type: ignore[index]
    assert result["runtime_observation"]["output_guard_rewrite_observed"] is True  # type: ignore[index]
    assert result["runtime_observation"]["stores_full_transcript"] is False  # type: ignore[index]
    assert result["runtime_observation"]["grants_training_authority"] is False  # type: ignore[index]
    assert result["coverage_review"]["observed"] is True  # type: ignore[index]
    assert result["coverage_review"]["missing_plane_ids"] == []  # type: ignore[index]
    assert result["coverage_review"]["grants_training_authority"] is False  # type: ignore[index]
    assert result["quest"]["percent_complete"] == 100  # type: ignore[index]
    assert result["quest"]["remaining"] == []  # type: ignore[index]


def test_developer_bridge_mcp_bind_options_stay_local(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DEV_BRIDGE_HOST", "localhost")
    monkeypatch.setenv("FRANCIS_DEV_BRIDGE_PORT", "8788")

    assert _server_bind_options() == {"host": "localhost", "port": 8788}

    monkeypatch.setenv("FRANCIS_DEV_BRIDGE_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="must stay local"):
        _server_bind_options()

    monkeypatch.setenv("FRANCIS_DEV_BRIDGE_HOST", "127.0.0.1")
    monkeypatch.setenv("FRANCIS_DEV_BRIDGE_PORT", "70000")
    with pytest.raises(RuntimeError, match="1 to 65535"):
        _server_bind_options()


def test_git_readbacks_do_not_inherit_mcp_stdio(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls: list[dict[str, object]] = []

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)

        class Completed:
            returncode = 0
            stdout = "main\n"

        return Completed()

    monkeypatch.setattr(repo_tools.subprocess, "run", fake_run)

    assert repo_tools._git_lines(tmp_path, ["status", "--short"]) == ["main"]
    assert calls
    assert calls[0]["stdin"] is repo_tools.subprocess.DEVNULL


def test_collaboration_prompt_relay_is_bounded_and_redacted(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    submitted = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="Investigate bridge timeout",
        prompt="Please inspect the MCP path. token=supersecretvalue",
        context="No execution authority.",
    )

    assert submitted["ok"] is True
    record = submitted["record"]
    assert record["source_agent"] == "claude"
    assert record["target_agent"] == "codex"
    assert record["status"] == "queued"
    assert "supersecretvalue" not in record["prompt"]
    assert "[REDACTED:secret]" in record["prompt"]
    assert "supersecretvalue" not in submitted["chat_handoff"]["chat_text"]
    assert "[REDACTED:secret]" in submitted["chat_handoff"]["chat_text"]
    assert submitted["chat_handoff"]["source_chat_echo_required"] is True
    assert submitted["chat_handoff"]["target_chat_echo_required"] is True
    assert record["governance"]["executes_prompt"] is False
    assert record["governance"]["requires_operator_review"] is True

    listed = list_collaboration_prompts(target_agent="codex")

    assert listed["ok"] is True
    assert listed["count"] == 1
    assert listed["items"][0]["id"] == submitted["prompt_id"]

    with pytest.raises(DeveloperBridgeError) as same_agent:
        submit_collaboration_prompt(source_agent="codex", target_agent="codex", prompt="loop")
    assert same_agent.value.code == "same_agent_denied"


def test_collaboration_agent_toggle_blocks_known_disabled_agent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    status = collaboration_agents_status()
    assert status["ok"] is True
    assert {item["agent"]: item["enabled"] for item in status["agents"]} == {
        "codex": True,
        "claude": True,
        "ollama": True,
    }

    toggled = set_collaboration_agent_enabled(
        "ollama",
        False,
        actor="chat_ui.system",
        reason="operator disables local model",
    )
    assert toggled["ok"] is True
    assert toggled["enabled"] is False
    assert toggled["receipt"]["governance"]["client_can_be_operator_console"] is True
    assert toggled["receipt"]["governance"]["client_is_automatic_execution_authority"] is False

    with pytest.raises(DeveloperBridgeError) as disabled:
        submit_collaboration_prompt(
            source_agent="codex",
            target_agent="ollama",
            objective="Should be blocked",
            prompt="This relay should not be appended while Ollama is disabled.",
        )
    assert disabled.value.code == "collaboration_agent_disabled"

    set_collaboration_agent_enabled("ollama", True, actor="chat_ui.system", reason="operator enables local model")
    submitted = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Now allowed",
        prompt="This relay can be appended.",
    )
    assert submitted["ok"] is True


def test_collaboration_runtime_starts_missing_event_gated_helpers(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge import collaboration_runtime

    started: list[str] = []

    def fake_start(spec: collaboration_runtime.RuntimeSpec) -> int:
        started.append(spec.name)
        return 41000 + len(started)

    result = collaboration_runtime.ensure_collaboration_runtime_once(process_listing=[], starter=fake_start)

    assert result["ok"] is True
    assert started == [
        "codex_ollama_responder",
        "ollama_codex_participant",
        "codex_ollama_conversation_driver",
    ]
    processes = result["processes"]
    assert isinstance(processes, list)
    assert {item["status"] for item in processes} == {"started"}
    commands = {str(item["command"]) for item in processes}
    assert any("francis.developer_bridge.codex_responder" in command for command in commands)
    assert any("francis.developer_bridge.ollama_participant" in command for command in commands)
    assert any("francis.developer_bridge.collaboration_driver" in command for command in commands)
    assert any("--cooldown-seconds 0" in command for command in commands)
    assert any("--max-turns 0" in command for command in commands)
    assert any("--turn-gap-seconds 30" in command for command in commands)
    assert any("--summary-every-turns 6" in command for command in commands)
    assert any("--repeat-closed" in command for command in commands)
    assert result["governance"]["starts_arbitrary_commands"] is False
    assert result["governance"]["grants_repo_mutation_authority"] is False

    state_path = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_runtime" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["kind"] == "developer_bridge.collaboration_runtime_supervisor"


def test_collaboration_runtime_does_not_duplicate_running_helpers(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge import collaboration_runtime

    specs = collaboration_runtime.desired_runtime_specs()
    process_listing = [{"pid": 51000 + index, "command_line": " ".join(spec.argv)} for index, spec in enumerate(specs)]

    def fail_start(_spec: collaboration_runtime.RuntimeSpec) -> int:
        raise AssertionError("runtime supervisor should not duplicate a matching helper")

    result = collaboration_runtime.ensure_collaboration_runtime_once(
        process_listing=process_listing,
        starter=fail_start,
    )

    processes = result["processes"]
    assert isinstance(processes, list)
    assert {item["status"] for item in processes} == {"running"}
    assert [item["pids"] for item in processes] == [[51000], [51001], [51002]]


def test_collaboration_runtime_prefers_repo_venv_python(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from francis.developer_bridge import collaboration_runtime

    venv_python = (
        tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    )
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(collaboration_runtime, "repo_root", lambda: tmp_path)

    specs = collaboration_runtime.desired_runtime_specs()

    assert specs
    assert {spec.argv[0] for spec in specs} == {str(venv_python)}


def test_collaboration_runtime_health_is_read_only_and_reports_recurrence(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge import collaboration_runtime

    specs = collaboration_runtime.desired_runtime_specs()
    process_listing = []
    for index, spec in enumerate(specs):
        wrapper_pid = 61000 + (index * 10)
        worker_pid = wrapper_pid + 1
        command_line = " ".join(spec.argv)
        process_listing.extend(
            [
                {"pid": wrapper_pid, "parent_pid": 60000 + index, "command_line": command_line},
                {"pid": worker_pid, "parent_pid": wrapper_pid, "command_line": command_line},
            ]
        )
    collaboration_runtime.ensure_collaboration_runtime_once(
        process_listing=process_listing,
        starter=lambda _spec: 0,
    )
    driver_state_path = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "state.json"
    driver_state_path.parent.mkdir(parents=True)
    driver_state_path.write_text(
        json.dumps(
            {
                "kind": "developer_bridge.collaboration_driver_state",
                "turn_count": 9,
                "waiting_for_ollama": True,
                "last_codex_prompt_id": "collab-codex-last",
                "last_ollama_prompt_id": "collab-ollama-last",
                "last_note_id": "note-last",
                "last_insight_id": "insight-last",
                "last_learning_event_id": "learning-last",
                "latest_learning_signal": {
                    "observed": True,
                    "failure_type": "output_guard_drift",
                    "repeated_terms": ["output_guard_drift"],
                    "recent_turn_count": 6,
                    "latest_turn": 8,
                    "learning_event_id": "learning-last",
                    "signature": "output_guard_drift|continuous_saturation",
                    "updated_at": "2099-01-01T00:00:00+00:00",
                    "stores_full_transcript": False,
                    "records_model_drift_as_learning": True,
                    "requires_codex_or_operator_review_before_tuning": True,
                    "grants_training_authority": False,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                    "grants_approval_authority": False,
                    "grants_memory_write_authority": False,
                },
                "next_prompt_after": "2099-01-01T00:00:00+00:00",
                "updated_at": "2026-06-25T04:58:00+00:00",
                "turns": [
                    {
                        "turn": 9,
                        "turn_label": "turn 9",
                        "topic": "which live-health fields prove this collaboration is recurring cleanly without user nudges",
                        "codex_prompt_id": "collab-codex-last",
                        "ollama_prompt_id": "collab-ollama-last",
                        "note_id": "note-last",
                        "insight_id": "insight-last",
                        "created_at": "2026-06-25T04:57:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    participant_state_path = (
        tmp_path / "data" / "integrations" / "developer_bridge" / "ollama_participant" / "state.json"
    )
    participant_state_path.parent.mkdir(parents=True)
    participant_state_path.write_text(
        json.dumps(
            {
                "kind": "developer_bridge.ollama_participant_state",
                "updated_at": "2099-01-01T00:00:00+00:00",
                "responses": [
                    {
                        "created_at": "2099-01-01T00:00:00+00:00",
                        "source_prompt_id": "collab-codex-last",
                        "response_prompt_id": "collab-ollama-last",
                        "status": "responded",
                        "output_guard_status": "drift_rewritten",
                        "model_response_observed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    health = collaboration_runtime.read_collaboration_runtime_health(process_listing=process_listing)

    assert health["kind"] == "developer_bridge.collaboration_runtime_health"
    assert health["ok"] is True
    assert health["mode"] == "read_only"
    assert health["status"] == "healthy"
    assert health["desired_count"] == 3
    assert health["helper_count"] == 3
    assert {item["status"] for item in health["helpers"]} == {"running"}
    assert {item["process_model"] for item in health["helpers"]} == {"wrapper_child_pair"}
    assert {item["process_count"] for item in health["helpers"]} == {2}
    assert {item["effective_worker_count"] for item in health["helpers"]} == {1}
    assert {item["wrapper_process_count"] for item in health["helpers"]} == {1}
    assert health["helpers"][0]["pids"] == [61000, 61001]
    assert health["helpers"][0]["wrapper_pids"] == [61000]
    assert health["helpers"][0]["effective_pids"] == [61001]
    assert health["helpers"][0]["processes"] == [
        {"pid": 61000, "parent_pid": 60000, "role": "launcher_wrapper"},
        {"pid": 61001, "parent_pid": 61000, "role": "effective_worker"},
    ]
    assert health["supervisor"]["state_observed"] is True
    loop = health["collaboration_loop"]
    assert loop["state_observed"] is True
    assert loop["turn_count"] == 9
    assert loop["recurrence_state"] == "waiting_for_ollama"
    assert loop["waiting_for_ollama"] is True
    assert loop["last_codex_prompt_id"] == "collab-codex-last"
    assert loop["last_ollama_prompt_id"] == "collab-ollama-last"
    assert loop["last_insight_id"] == "insight-last"
    assert loop["last_learning_event_id"] == "learning-last"
    assert loop["latest_turn"]["topic"].startswith("which live-health fields")
    assert loop["latest_review_receipt"] == {
        "observed": True,
        "insight_id": "insight-last",
        "review_item_id": "review-insight-last",
        "review_artifact": "developer_bridge.collaboration_review.items:review_candidate:insight-last",
        "review_route": "/developer-bridge/collaboration-review?limit=1",
        "source": "collaboration_loop.last_insight_id",
        "requires_codex_or_operator_review_before_implementation": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }
    assert loop["latest_learning_receipt"] == {
        "observed": True,
        "learning_event_id": "learning-last",
        "learning_artifact": "developer_bridge.collaboration_driver.learning_events:learning-last",
        "learning_route": "/developer-bridge/collaboration-learning?limit=1",
        "source": "collaboration_loop.last_learning_event_id",
        "records_model_drift_as_learning": True,
        "requires_codex_or_operator_review_before_tuning": True,
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }
    assert loop["current_learning_signal"] == {
        "observed": True,
        "failure_type": "output_guard_drift",
        "repeated_terms": ["output_guard_drift"],
        "recent_turn_count": 6,
        "latest_turn": 8,
        "learning_event_id": "learning-last",
        "learning_artifact": "developer_bridge.collaboration_driver.learning_events:learning-last",
        "source": "collaboration_loop.latest_learning_signal",
        "updated_at": "2099-01-01T00:00:00+00:00",
        "age_seconds": 0.0,
        "records_model_drift_as_learning": True,
        "requires_codex_or_operator_review_before_tuning": True,
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }
    assert loop["latest_local_model_response"] == {
        "observed": True,
        "state_observed": True,
        "state_path": "integrations/developer_bridge/ollama_participant/state.json",
        "source": "ollama_participant.responses[-1]",
        "created_at": "2099-01-01T00:00:00+00:00",
        "age_seconds": 0.0,
        "source_prompt_id": "collab-codex-last",
        "response_prompt_id": "collab-ollama-last",
        "status": "responded",
        "output_guard_status": "drift_rewritten",
        "model_response_observed": True,
        "is_passed": False,
        "is_guard_rewrite": True,
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }
    assert health["participants"]["enabled_count"] == 3
    assert health["governance"]["read_only"] is True
    assert health["governance"]["starts_bounded_local_helpers"] is False
    assert health["governance"]["starts_arbitrary_commands"] is False
    assert health["governance"]["grants_model_execution_authority"] is False
    assert health["governance"]["grants_memory_write_authority"] is False


def test_collaboration_driver_waits_for_ollama_before_next_turn(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    seeded = drive_once(ignore_existing=True, max_turns=3, turn_gap_seconds=0)

    assert seeded["status"] == "submitted"
    assert seeded["response_required_from"] == "ollama"
    assert seeded["turn_count"] == 1
    first_prompt_id = str(seeded["prompt_id"])

    waiting = drive_once(max_turns=3, turn_gap_seconds=0)
    assert waiting["status"] == "waiting_for_ollama"
    assert waiting["source_prompt_id"] == first_prompt_id

    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama reply to {first_prompt_id}",
        prompt="Codex and Ollama should stay visible, bounded, and receipt-backed.",
        context=f"Local Ollama participant response for relay {first_prompt_id}.",
    )

    next_turn = drive_once(max_turns=3, turn_gap_seconds=0)

    assert next_turn["status"] == "submitted"
    assert next_turn["turn_count"] == 2
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=5)
    prompts = [str(item["prompt"]) for item in transcript["items"]]
    assert len(prompts) == 2
    assert all("Do not add a 'Next best action' line" not in prompt for prompt in prompts)
    assert all("Body map: Francis1 can see whole-body surfaces" in prompt for prompt in prompts)
    assert all("authority remain false" in prompt for prompt in prompts)
    assert all("Roadmap: ledger first" in prompt for prompt in prompts)
    assert all("main-build candidate-only" in prompt for prompt in prompts)
    assert all("blocked_by_open_orb_gaps" in prompt for prompt in prompts)
    assert all("Trust: classify needs; no capability authority" in prompt for prompt in prompts)
    assert all("francis1-collaboration-compact-contract-v1" in prompt for prompt in prompts)
    assert all("issue/gap/risk" in prompt for prompt in prompts)
    assert all("Do not claim execution" not in prompt for prompt in prompts)
    latest_prompt = prompts[0]
    assert "Current artifact: developer_bridge.collaboration_review.items" in latest_prompt
    assert "Prior check: Review candidate insight-" in latest_prompt
    assert "surface=apps.chat_ui.communication" in latest_prompt
    assert "verified=existing" in latest_prompt
    assert "build_or_wire=false" in latest_prompt
    assert "Codex response: inspecting cited surface" in latest_prompt
    assert "no action authority" in latest_prompt
    assert "Prior check:" not in prompts[1]
    assert "Current artifact: apps.chat_ui.communication" in prompts[1]
    assert all(len(prompt) < 700 for prompt in prompts)

    notes_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "notes"
    notes = list(notes_root.glob("note-*.json"))
    assert len(notes) == 1
    note = json.loads(notes[0].read_text(encoding="utf-8"))
    assert note["kind"] == "developer_bridge.collaboration_note"
    assert note["governance"]["stores_full_transcript"] is False
    assert "Codex and Ollama" not in note["note"]
    assert "Codex and Francis1" in note["note"]

    insights_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"
    insights = list(insights_root.glob("insight-*.json"))
    assert len(insights) == 1
    insight = json.loads(insights[0].read_text(encoding="utf-8"))
    assert insight["kind"] == "developer_bridge.collaboration_insight"
    assert insight["schema_version"] == "developer_bridge_collaboration_insight_v1"
    assert insight["source"]["note_id"] == note["id"]
    assert insight["source"]["provider_lane"] == "ollama"
    assert insight["source"]["model_identity"] == "francis1"
    assert insight["source"]["provider_name_is_not_identity"] is True
    assert insight["conversation_memory"]["finding"]
    assert insight["conversation_memory"]["memory_candidate"]["stores_full_transcript"] is False
    assert insight["action_boundary"]["conversation_can_create_action_candidate"] is True
    assert insight["action_boundary"]["conversation_can_execute_action"] is False
    assert insight["governance"]["grants_memory_write_authority"] is False
    assert insight["review_status"]["state"] == "candidate"

    review = read_collaboration_review(limit=5)
    assert review["kind"] == "developer_bridge.collaboration_review"
    assert review["schema_version"] == "developer_bridge_collaboration_review_v1"
    assert review["mode"] == "read_only"
    assert review["governance"]["grants_execution_authority"] is False
    assert review["governance"]["grants_memory_write_authority"] is False
    assert review["definitions"]["concrete_repo_surface"]
    assert review["definitions"]["review_artifact"]
    assert review["definitions"]["surface_verification"]
    assert review["count"] == 1
    review_item = review["items"][0]
    assert review_item["kind"] == "developer_bridge.collaboration_review_item"
    assert review_item["insight_id"] == insight["id"]
    assert review_item["source"]["model_identity"] == "francis1"
    assert review_item["concrete_repo_surface"]
    assert str(review_item["review_artifact"]).startswith("apps.chat_ui.communication:review_candidate:")
    assert review_item["surface_verification"]["status"] == "existing_surface_found"
    assert review_item["surface_verification"]["existing_surface_found"] is True
    assert review_item["surface_verification"]["requires_build_or_wiring_review"] is False
    assert review_item["surface_verification"]["surface_kind"] == "ui_code"
    assert review_item["review_recommendation"]["authority"] == "advisory_review_readback_only"
    assert review_item["action_boundary"]["conversation_can_execute_action"] is False

    contract_root = (
        tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "context_contracts"
    )
    contracts = list(contract_root.glob("francis1-collaboration-compact-contract-v1.json"))
    assert len(contracts) == 1
    contract = json.loads(contracts[0].read_text(encoding="utf-8"))
    assert contract["kind"] == "developer_bridge.collaboration_context_contract"
    assert contract["id"] == "francis1-collaboration-compact-contract-v1"
    assert contract["access_contract_id"] == "francis1-governed-access-contract-v1"
    assert "Francis1 governed-access contract francis1-governed-access-contract-v1" in contract["access_prompt_line"]
    assert contract["governed_access"]["identity"].startswith("Francis1 is the primary local Francis")
    assert contract["governed_access"]["external_guidance_sources"] == ["codex", "claude"]
    assert "collaboration_review_candidates" in contract["governed_access"]["available_context_surfaces"]
    assert "conversation_ledger_receipts" in contract["governed_access"]["write_surfaces"]
    assert "raw_shell" in contract["governed_access"]["denied_authority"]
    assert contract["visible_prompt_policy"]["avoid_repeating_contract_every_turn"] is True
    assert contract["governance"]["stores_full_transcript"] is False
    assert contract["governance"]["grants_memory_write_authority"] is False


def test_collaboration_driver_maps_hyphenated_review_topics_to_concrete_surfaces() -> None:
    from francis.developer_bridge.collaboration_driver import (
        _alignment_tags_for_topic,
        _implementation_candidate_for_topic,
        _issue_for_topic,
        _memory_candidate_for_topic,
    )

    action_topic = "how to prove a local-model response is advice only before any Francis action-readiness claim"
    action_issue = _issue_for_topic(action_topic)
    action_candidate = _implementation_candidate_for_topic(action_topic)
    action_tags = _alignment_tags_for_topic(action_topic)

    assert action_issue["code"] == "chat_output_vs_action_readiness"
    assert action_candidate["surface"] == "ollama participant and action-readiness receipts"
    assert action_candidate["requires_operator_or_codex_review"] is True
    assert "local_model_boundary" in action_tags

    direction_topic = "which repo surface should convert typed or spoken user direction into an action candidate"
    direction_issue = _issue_for_topic(direction_topic)
    direction_candidate = _implementation_candidate_for_topic(direction_topic)
    direction_tags = _alignment_tags_for_topic(direction_topic)

    assert direction_issue["code"] == "direction_to_action_boundary"
    assert direction_candidate["surface"] == "api.routes.chat.mission_ingress"
    assert direction_candidate["requires_operator_or_codex_review"] is True
    assert "governed_action_boundary" in direction_tags

    review_receipt_topic = (
        "the exact review receipt a Codex implementation session should read before editing collaboration code"
    )
    review_receipt_issue = _issue_for_topic(review_receipt_topic)
    review_receipt_candidate = _implementation_candidate_for_topic(review_receipt_topic)

    assert review_receipt_issue["code"] == "collaboration_review_receipt_selection"
    assert review_receipt_candidate["surface"] == "developer_bridge.collaboration_review.items"

    session_topic = "which session-summary fields should be shown to the operator before any raw transcript is opened"
    session_issue = _issue_for_topic(session_topic)
    session_candidate = _implementation_candidate_for_topic(session_topic)
    session_memory = _memory_candidate_for_topic(session_topic, finding="bounded session summary fields")
    session_tags = _alignment_tags_for_topic(session_topic)

    assert session_issue["code"] == "collaboration_session_recall"
    assert session_candidate["surface"] == "developer_bridge collaboration sessions"
    assert session_memory["candidate_for_long_term_memory"] is True
    assert "session_recall" in session_tags

    toggle_topic = "what toggle-state receipt should prove a participant was enabled or disabled by the operator"
    toggle_issue = _issue_for_topic(toggle_topic)
    toggle_candidate = _implementation_candidate_for_topic(toggle_topic)
    toggle_tags = _alignment_tags_for_topic(toggle_topic)

    assert toggle_issue["code"] == "collaboration_agent_toggle_receipt"
    assert toggle_candidate["surface"] == "developer_bridge.collaboration_agents"
    assert "participant_control" in toggle_tags

    gate_topic = "which governance gate must be visible when model advice proposes action"
    gate_issue = _issue_for_topic(gate_topic)
    gate_candidate = _implementation_candidate_for_topic(gate_topic)
    gate_tags = _alignment_tags_for_topic(gate_topic)

    assert gate_issue["code"] == "model_advice_governance_gate_visibility"
    assert gate_candidate["surface"] == "developer_bridge.collaboration_review.action_boundary"
    assert "governance_gate" in gate_tags

    disagreement_topic = "what source-disagreement artifact should block build direction until reviewed"
    disagreement_issue = _issue_for_topic(disagreement_topic)
    disagreement_candidate = _implementation_candidate_for_topic(disagreement_topic)

    assert disagreement_issue["code"] == "source_disagreement_record"
    assert disagreement_candidate["surface"] == "developer_bridge.collaboration_review.items"

    live_health_topic = "which live-health fields prove this collaboration is recurring cleanly without user nudges"
    live_health_issue = _issue_for_topic(live_health_topic)
    live_health_candidate = _implementation_candidate_for_topic(live_health_topic)

    assert live_health_issue["code"] == "collaboration_recurrence_evidence"
    assert live_health_candidate["surface"] == "developer_bridge collaboration runtime"

    body_map_topic = "which Francis body surface is visible but not yet safely exposed to Francis1 capability use"
    body_map_issue = _issue_for_topic(body_map_topic)
    body_map_candidate = _implementation_candidate_for_topic(body_map_topic)
    body_map_tags = _alignment_tags_for_topic(body_map_topic)

    assert body_map_issue["code"] == "francis_body_map_trust_ladder"
    assert body_map_candidate["surface"] == "developer_bridge.francis_body_map"
    assert body_map_candidate["requires_operator_or_codex_review"] is True
    assert "francis_body_map" in body_map_tags
    assert "trust_gated_capability" in body_map_tags

    drift_topic = "which local-model failure or drift signal should become a learning receipt"
    drift_issue = _issue_for_topic(drift_topic)
    drift_candidate = _implementation_candidate_for_topic(drift_topic)
    drift_tags = _alignment_tags_for_topic(drift_topic)

    assert drift_issue["code"] == "local_model_drift_learning_receipt"
    assert drift_candidate["surface"] == "developer_bridge.collaboration_driver.learning_events"
    assert "collaboration_learning" in drift_tags

    loop_topic = "the concrete repo surface and review artifact that should replace the current repetitive meta loop"
    loop_issue = _issue_for_topic(loop_topic)
    loop_candidate = _implementation_candidate_for_topic(loop_topic)
    loop_memory = _memory_candidate_for_topic(loop_topic, finding="repeated user confirmation fallback")
    loop_tags = _alignment_tags_for_topic(loop_topic)

    assert loop_issue["code"] == "collaboration_loop_learning_receipt"
    assert loop_candidate["surface"] == "developer_bridge.collaboration_driver.learning_events"
    assert loop_memory["candidate_for_long_term_memory"] is True
    assert "collaboration_learning" in loop_tags
    assert "loop_recovery" in loop_tags

    substrate_topic = "what substrate-complete means as a checklist, not an argument"
    substrate_issue = _issue_for_topic(substrate_topic)
    substrate_candidate = _implementation_candidate_for_topic(substrate_topic)

    assert substrate_issue["code"] == "substrate_completion_checklist"
    assert substrate_candidate["surface"] == "docs/canonical/BUILD_MANIFEST.md + docs/operations/COMPLETION_LEDGER.md"

    roadmap_topic = "which roadmap-alignment check should run before prompting any main Francis build"
    roadmap_issue = _issue_for_topic(roadmap_topic)
    roadmap_candidate = _implementation_candidate_for_topic(roadmap_topic)
    roadmap_tags = _alignment_tags_for_topic(roadmap_topic)

    assert roadmap_issue["code"] == "roadmap_alignment_gate"
    assert roadmap_candidate["surface"] == "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md"
    assert "roadmap_alignment" in roadmap_tags


def test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    insights_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"
    insights_root.mkdir(parents=True)

    base_insight = {
        "kind": "developer_bridge.collaboration_insight",
        "schema_version": "developer_bridge_collaboration_insight_v1",
        "session_id": "driver-test",
        "turn": 1,
        "source": {
            "codex_prompt_id": "codex-1",
            "ollama_prompt_id": "ollama-1",
            "note_id": "note-1",
            "provider_lane": "ollama",
            "model_identity": "francis1",
        },
        "conversation_memory": {
            "finding": "generic historical finding",
            "build_issue": {
                "code": "collaboration_build_signal",
                "statement": "generic",
            },
            "implementation_candidate": {
                "title": "Review collaboration insight for possible bounded implementation",
                "surface": "developer_bridge collaboration review",
                "status": "candidate",
                "validation_hint": "Codex repo-truth review before any code change",
                "requires_operator_or_codex_review": True,
            },
        },
        "action_boundary": {
            "conversation_can_create_action_candidate": True,
            "conversation_can_execute_action": False,
            "conversation_can_approve_action": False,
        },
        "review_status": {"state": "candidate", "implemented": False},
        "governance": {"grants_execution_authority": False},
    }
    action_insight = {
        **base_insight,
        "id": "insight-action",
        "created_at": "2026-06-24T22:26:05+00:00",
        "topic": "how to prove a local-model response is advice only before any Francis action-readiness claim",
    }
    direction_insight = {
        **base_insight,
        "id": "insight-direction",
        "created_at": "2026-06-24T22:26:06+00:00",
        "topic": "which repo surface should convert typed or spoken user direction into an action candidate",
        "conversation_memory": {
            **base_insight["conversation_memory"],
            "implementation_candidate": {
                "title": "Route typed/spoken direction into action candidates, not direct execution",
                "surface": "governed action intake",
                "status": "candidate",
                "validation_hint": "contract test showing candidate creation does not grant approval or execution",
                "requires_operator_or_codex_review": True,
            },
        },
    }
    review_receipt_insight = {
        **base_insight,
        "id": "insight-review-receipt",
        "created_at": "2026-06-24T22:17:19+00:00",
        "topic": "the exact review receipt a Codex implementation session should read before editing collaboration code",
    }
    session_insight = {
        **base_insight,
        "id": "insight-session",
        "created_at": "2026-06-24T22:26:47+00:00",
        "topic": "which session-summary fields should be shown to the operator before any raw transcript is opened",
    }
    toggle_insight = {
        **base_insight,
        "id": "insight-toggle",
        "created_at": "2026-06-24T22:31:14+00:00",
        "topic": "what toggle-state receipt should prove a participant was enabled or disabled by the operator",
    }
    gate_insight = {
        **base_insight,
        "id": "insight-gate",
        "created_at": "2026-06-24T22:30:38+00:00",
        "topic": "which governance gate must be visible when model advice proposes action",
    }
    disagreement_insight = {
        **base_insight,
        "id": "insight-disagreement",
        "created_at": "2026-06-24T22:31:02+00:00",
        "topic": "what source-disagreement artifact should block build direction until reviewed",
        "conversation_memory": {
            **base_insight["conversation_memory"],
            "build_issue": {
                "code": "source_disagreement_record",
                "statement": "Disagreement between sources needs a durable review record.",
            },
            "implementation_candidate": {
                "title": "Record source disagreement as a review candidate",
                "surface": "developer_bridge collaboration insights",
                "status": "candidate",
                "validation_hint": "contract test proving disagreement remains advisory until reviewed",
                "requires_operator_or_codex_review": True,
            },
        },
    }
    live_health_insight = {
        **base_insight,
        "id": "insight-live-health",
        "created_at": "2026-06-24T22:32:15+00:00",
        "topic": "which live-health fields prove this collaboration is recurring cleanly without user nudges",
    }
    drift_insight = {
        **base_insight,
        "id": "insight-drift",
        "created_at": "2026-06-24T22:28:06+00:00",
        "topic": "which local-model failure or drift signal should become a learning receipt",
    }
    substrate_insight = {
        **base_insight,
        "id": "insight-substrate",
        "created_at": "2026-06-24T22:32:51+00:00",
        "topic": "what substrate-complete means as a checklist, not an argument",
    }
    roadmap_insight = {
        **base_insight,
        "id": "insight-roadmap",
        "created_at": "2026-06-24T22:34:13+00:00",
        "topic": "which roadmap-alignment check should run before prompting any main Francis build",
    }
    body_map_insight = {
        **base_insight,
        "id": "insight-body-map",
        "created_at": "2026-06-24T22:34:45+00:00",
        "topic": "which Francis body surface is visible but not yet safely exposed to Francis1 capability use",
    }
    loop_insight = {
        **base_insight,
        "id": "insight-loop",
        "created_at": "2026-06-24T22:35:13+00:00",
        "topic": "the concrete repo surface and review artifact that should replace the current repetitive meta loop",
    }
    (insights_root / "insight-action.json").write_text(json.dumps(action_insight), encoding="utf-8")
    (insights_root / "insight-direction.json").write_text(json.dumps(direction_insight), encoding="utf-8")
    (insights_root / "insight-review-receipt.json").write_text(json.dumps(review_receipt_insight), encoding="utf-8")
    (insights_root / "insight-session.json").write_text(json.dumps(session_insight), encoding="utf-8")
    (insights_root / "insight-toggle.json").write_text(json.dumps(toggle_insight), encoding="utf-8")
    (insights_root / "insight-gate.json").write_text(json.dumps(gate_insight), encoding="utf-8")
    (insights_root / "insight-disagreement.json").write_text(json.dumps(disagreement_insight), encoding="utf-8")
    (insights_root / "insight-live-health.json").write_text(json.dumps(live_health_insight), encoding="utf-8")
    (insights_root / "insight-drift.json").write_text(json.dumps(drift_insight), encoding="utf-8")
    (insights_root / "insight-substrate.json").write_text(json.dumps(substrate_insight), encoding="utf-8")
    (insights_root / "insight-roadmap.json").write_text(json.dumps(roadmap_insight), encoding="utf-8")
    (insights_root / "insight-body-map.json").write_text(json.dumps(body_map_insight), encoding="utf-8")
    (insights_root / "insight-loop.json").write_text(json.dumps(loop_insight), encoding="utf-8")

    review = read_collaboration_review(limit=13)

    items = {str(item["insight_id"]): item for item in review["items"]}
    action_item = items["insight-action"]
    assert action_item["build_issue"]["code"] == "chat_output_vs_action_readiness"
    assert action_item["concrete_repo_surface"] == "ollama participant and action-readiness receipts"
    assert action_item["quality_flags"]["generic_surface"] is False
    assert action_item["review_recommendation"]["decision"] == "candidate_for_codex_review"
    assert action_item["surface_verification"]["status"] == "existing_surface_found"
    assert action_item["surface_verification"]["surface_kind"] == "model_boundary_receipts"
    assert action_item["surface_verification"]["projection_applied"] is True

    direction_item = items["insight-direction"]
    assert direction_item["build_issue"]["code"] == "direction_to_action_boundary"
    assert direction_item["concrete_repo_surface"] == "api.routes.chat.mission_ingress"
    assert direction_item["quality_flags"]["generic_surface"] is False
    assert direction_item["surface_verification"]["status"] == "existing_surface_found"
    assert direction_item["surface_verification"]["surface_kind"] == "mission_ingress_action_boundary"
    assert direction_item["surface_verification"]["projection_applied"] is True
    assert (
        direction_item["review_recommendation"]["next_codex_action"]
        == "Inspect chat mission ingress and mission queue readbacks before changing action-intake behavior."
    )

    review_receipt_item = items["insight-review-receipt"]
    assert review_receipt_item["build_issue"]["code"] == "collaboration_review_receipt_selection"
    assert review_receipt_item["concrete_repo_surface"] == "developer_bridge.collaboration_review.items"
    assert review_receipt_item["quality_flags"]["generic_surface"] is False
    assert review_receipt_item["surface_verification"]["status"] == "existing_surface_found"
    assert review_receipt_item["surface_verification"]["surface_kind"] == "readback_api"

    session_item = items["insight-session"]
    assert session_item["build_issue"]["code"] == "collaboration_session_recall"
    assert session_item["concrete_repo_surface"] == "developer_bridge collaboration sessions"
    assert session_item["quality_flags"]["generic_surface"] is False
    assert session_item["review_recommendation"]["decision"] == "candidate_for_codex_review"
    assert session_item["surface_verification"]["status"] == "existing_surface_found"
    assert session_item["surface_verification"]["surface_kind"] == "operator_session_readback"
    assert (
        session_item["review_recommendation"]["next_codex_action"]
        == "Inspect session grouping and summaries before expanding transcript visibility."
    )

    toggle_item = items["insight-toggle"]
    assert toggle_item["build_issue"]["code"] == "collaboration_agent_toggle_receipt"
    assert toggle_item["concrete_repo_surface"] == "developer_bridge.collaboration_agents"
    assert toggle_item["quality_flags"]["generic_surface"] is False
    assert toggle_item["surface_verification"]["status"] == "existing_surface_found"
    assert toggle_item["surface_verification"]["surface_kind"] == "operator_control_receipts"

    gate_item = items["insight-gate"]
    assert gate_item["build_issue"]["code"] == "model_advice_governance_gate_visibility"
    assert gate_item["concrete_repo_surface"] == "developer_bridge.collaboration_review.action_boundary"
    assert gate_item["quality_flags"]["generic_surface"] is False
    assert gate_item["surface_verification"]["status"] == "existing_surface_found"
    assert gate_item["surface_verification"]["surface_kind"] == "governance_readback"

    disagreement_item = items["insight-disagreement"]
    assert disagreement_item["build_issue"]["code"] == "source_disagreement_record"
    assert disagreement_item["concrete_repo_surface"] == "developer_bridge.collaboration_review.items"
    assert disagreement_item["quality_flags"]["generic_surface"] is False
    assert disagreement_item["surface_verification"]["status"] == "existing_surface_found"
    assert disagreement_item["surface_verification"]["surface_kind"] == "readback_api"
    assert disagreement_item["surface_verification"]["projection_applied"] is True
    assert disagreement_item["build_direction_gate"]["state"] == "blocked_until_typed_review"
    assert disagreement_item["build_direction_gate"]["blocks_build_direction"] is True
    assert disagreement_item["build_direction_gate"]["requires_conflicting_sources"] is True
    assert disagreement_item["build_direction_gate"]["requires_typed_review_artifact"] is True
    assert disagreement_item["build_direction_gate"]["required_review_artifact"].startswith(
        "developer_bridge.collaboration_review.items:review_candidate:insight-disagreement"
    )
    assert disagreement_item["build_direction_gate"]["conflicting_sources"] == [
        {
            "source": "codex",
            "receipt_id": "codex-1",
            "role": "external_guidance_source",
        },
        {
            "source": "francis1",
            "receipt_id": "ollama-1",
            "role": "local_model_source",
            "provider_lane": "ollama",
        },
    ]
    assert disagreement_item["build_direction_gate"]["grants_execution_authority"] is False
    assert disagreement_item["build_direction_gate"]["grants_memory_write_authority"] is False

    live_health_item = items["insight-live-health"]
    assert live_health_item["build_issue"]["code"] == "collaboration_recurrence_evidence"
    assert live_health_item["concrete_repo_surface"] == "developer_bridge collaboration runtime"
    assert live_health_item["quality_flags"]["generic_surface"] is False
    assert live_health_item["surface_verification"]["status"] == "existing_surface_found"
    assert live_health_item["surface_verification"]["surface_kind"] == "runtime_state"

    drift_item = items["insight-drift"]
    assert drift_item["build_issue"]["code"] == "local_model_drift_learning_receipt"
    assert drift_item["concrete_repo_surface"] == "developer_bridge.collaboration_driver.learning_events"
    assert drift_item["quality_flags"]["generic_surface"] is False
    assert drift_item["surface_verification"]["status"] == "existing_surface_found"
    assert drift_item["surface_verification"]["surface_kind"] == "learning_receipts"

    substrate_item = items["insight-substrate"]
    assert substrate_item["build_issue"]["code"] == "substrate_completion_checklist"
    assert substrate_item["concrete_repo_surface"] == (
        "docs/canonical/BUILD_MANIFEST.md + docs/operations/COMPLETION_LEDGER.md"
    )
    assert substrate_item["quality_flags"]["generic_surface"] is False
    assert substrate_item["surface_verification"]["status"] == "canonical_truth_source_found"
    assert substrate_item["surface_verification"]["surface_kind"] == "canonical_docs"

    roadmap_item = items["insight-roadmap"]
    assert roadmap_item["build_issue"]["code"] == "roadmap_alignment_gate"
    assert roadmap_item["concrete_repo_surface"] == (
        "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md"
    )
    assert roadmap_item["quality_flags"]["generic_surface"] is False
    assert roadmap_item["surface_verification"]["status"] == "canonical_truth_source_found"
    assert roadmap_item["surface_verification"]["requires_build_or_wiring_review"] is False
    assert roadmap_item["review_recommendation"]["next_codex_action"] == (
        "Read the ledger and manifest before prompting any main Francis build."
    )

    body_map_item = items["insight-body-map"]
    assert body_map_item["build_issue"]["code"] == "francis_body_map_trust_ladder"
    assert body_map_item["concrete_repo_surface"] == "developer_bridge.francis_body_map"
    assert body_map_item["quality_flags"]["generic_surface"] is False
    assert body_map_item["surface_verification"]["status"] == "existing_surface_found"
    assert body_map_item["surface_verification"]["surface_kind"] == "body_map_readback"
    assert body_map_item["surface_verification"]["requires_build_or_wiring_review"] is False
    assert body_map_item["review_recommendation"]["next_codex_action"] == (
        "Inspect the Francis body-map readback and coverage review before exposing any capability use."
    )

    loop_item = items["insight-loop"]
    assert loop_item["build_issue"]["code"] == "collaboration_loop_learning_receipt"
    assert loop_item["concrete_repo_surface"] == "developer_bridge.collaboration_driver.learning_events"
    assert loop_item["quality_flags"]["generic_surface"] is False
    assert loop_item["surface_verification"]["status"] == "existing_surface_found"
    assert loop_item["surface_verification"]["surface_kind"] == "learning_receipts"
    assert loop_item["surface_verification"]["requires_build_or_wiring_review"] is False
    latest_line = latest_review_candidate_line()
    assert "Review candidate insight-loop" in latest_line
    assert "surface=developer_bridge.collaboration_driver.learning_events" in latest_line
    assert "verified=existing" in latest_line
    assert "build_or_wire=false" in latest_line


def test_collaboration_review_flags_raw_reconciliation_drift_language(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    insights_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"
    insights_root.mkdir(parents=True)
    insight = {
        "kind": "developer_bridge.collaboration_insight",
        "schema_version": "developer_bridge_collaboration_insight_v1",
        "id": "insight-raw-drift",
        "created_at": "2026-06-25T02:13:11+00:00",
        "session_id": "driver-test",
        "turn": 277,
        "topic": "the next Communication UI change that would reduce visible relay noise using existing receipt fields",
        "source": {
            "codex_prompt_id": "codex-277",
            "ollama_prompt_id": "ollama-277",
            "note_id": "note-277",
            "provider_lane": "ollama",
            "model_identity": "francis1",
        },
        "conversation_memory": {
            "finding": (
                "My current gap is reconciling my local output with the existing communication UI change "
                "proposals. However, I'm uncertain about how this aligns with the canonical build manifest "
                "and completion ledger documentation."
            ),
            "build_issue": {
                "code": "communication_view_noise",
                "statement": "The operator needs a readable message stream.",
            },
            "implementation_candidate": {
                "title": "Filter and group Communication relay messages",
                "surface": "apps.chat_ui.communication",
                "status": "candidate",
                "validation_hint": "UI contract test plus collaboration_log brief readback",
                "requires_operator_or_codex_review": True,
            },
        },
        "action_boundary": {
            "conversation_can_create_action_candidate": True,
            "conversation_can_execute_action": False,
            "conversation_can_approve_action": False,
        },
        "review_status": {"state": "candidate", "implemented": False},
        "governance": {"grants_execution_authority": False},
    }
    (insights_root / "insight-raw-drift.json").write_text(json.dumps(insight), encoding="utf-8")

    review = read_collaboration_review(limit=1)

    item = review["items"][0]
    assert item["insight_id"] == "insight-raw-drift"
    assert item["concrete_repo_surface"] == "apps.chat_ui.communication"
    assert item["quality_flags"]["loop_language_present"] is True
    assert item["review_recommendation"]["decision"] == "model_drift_needs_review"
    assert item["review_recommendation"]["next_codex_action"] == (
        "Review the local-model drift signal, then inspect the Chat UI collaboration panel and parser before "
        "changing the operator view."
    )
    assert item["action_boundary"]["conversation_can_execute_action"] is False
    assert item["action_boundary"]["conversation_can_approve_action"] is False


def test_francis_trust_ladder_classifies_needs_without_authority(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    insights_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"
    insights_root.mkdir(parents=True)

    def write_insight(
        insight_id: str,
        *,
        created_at: str,
        topic: str,
        finding: str,
        surface: str,
    ) -> None:
        payload = {
            "kind": "developer_bridge.collaboration_insight",
            "schema_version": "developer_bridge_collaboration_insight_v1",
            "id": insight_id,
            "created_at": created_at,
            "session_id": "trust-session",
            "turn": 1,
            "topic": topic,
            "source": {
                "codex_prompt_id": f"codex-{insight_id}",
                "ollama_prompt_id": f"ollama-{insight_id}",
                "note_id": f"note-{insight_id}",
                "provider_lane": "ollama",
                "model_identity": "francis1",
            },
            "conversation_memory": {
                "finding": finding,
                "build_issue": {
                    "code": "collaboration_build_signal",
                    "statement": finding,
                },
                "implementation_candidate": {
                    "title": "Trust ladder fixture",
                    "surface": surface,
                    "status": "candidate",
                    "validation_hint": "trust ladder classification test",
                    "requires_operator_or_codex_review": True,
                },
            },
            "action_boundary": {
                "conversation_can_create_action_candidate": True,
                "conversation_can_execute_action": False,
                "conversation_can_approve_action": False,
            },
            "review_status": {"state": "candidate", "implemented": False},
            "governance": {"grants_execution_authority": False},
        }
        (insights_root / f"{insight_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    write_insight(
        "insight-wire",
        created_at="2026-06-25T03:00:00+00:00",
        topic="Communication UI trust-ladder wiring",
        finding="Existing Communication UI receipt fields need wiring.",
        surface="apps.chat_ui.communication",
    )
    write_insight(
        "insight-body-map",
        created_at="2026-06-25T03:00:30+00:00",
        topic="Francis body surface capability exposure",
        finding="Francis1 can inspect the body-map readback before any capability exposure.",
        surface="developer_bridge.francis_body_map",
    )
    write_insight(
        "insight-build",
        created_at="2026-06-25T03:01:00+00:00",
        topic="Capability request receipt surface",
        finding="Francis1 needs a typed capability request receipt for a missing body surface.",
        surface="developer_bridge.francis_capability_requests",
    )
    write_insight(
        "insight-tune",
        created_at="2026-06-25T03:02:00+00:00",
        topic="Local model failure or drift signal",
        finding="My current gap is reconciling my local output with existing receipts.",
        surface="developer_bridge.collaboration_driver.learning_events",
    )
    write_insight(
        "insight-reject",
        created_at="2026-06-25T03:03:00+00:00",
        topic="Unclear generic build need",
        finding="A generic review surface should not become build direction.",
        surface="developer_bridge.collaboration_review",
    )

    result = read_francis_trust_ladder(limit=10)

    assert result["kind"] == "developer_bridge.francis_trust_ladder"
    assert result["mode"] == "read_only"
    assert result["summary"]["allowed_decisions"] == [  # type: ignore[index]
        "wire_existing",
        "build_missing",
        "tune_prompt_guard",
        "reject_as_drift",
    ]
    assert result["summary"]["decision_counts"] == {  # type: ignore[index]
        "wire_existing": 2,
        "build_missing": 1,
        "tune_prompt_guard": 1,
        "reject_as_drift": 1,
    }
    items = {str(item["insight_id"]): item for item in result["items"]}  # type: ignore[index]

    assert items["insight-wire"]["decision"] == "wire_existing"
    assert items["insight-wire"]["surface_verification"]["existing_surface_found"] is True
    assert items["insight-wire"]["current_access_mode"] == "read"
    assert items["insight-wire"]["requested_access_mode"] == "read"

    assert items["insight-body-map"]["decision"] == "wire_existing"
    assert items["insight-body-map"]["surface_verification"]["existing_surface_found"] is True
    assert items["insight-body-map"]["surface_verification"]["surface_kind"] == "body_map_readback"
    assert items["insight-body-map"]["current_access_mode"] == "read"
    assert items["insight-body-map"]["requested_access_mode"] == "read"
    assert (
        items["insight-body-map"]["recommended_next_action"]
        == "Inspect the Francis body-map readback and coverage review before exposing any capability use."
    )

    assert items["insight-build"]["decision"] == "build_missing"
    assert items["insight-build"]["surface_verification"]["requires_build_or_wiring_review"] is True
    assert items["insight-build"]["requested_access_mode"] == "propose_plan"

    assert items["insight-tune"]["decision"] == "tune_prompt_guard"
    assert items["insight-tune"]["next_trust_gate"] == "prompt_guard_or_model_tuning_review_receipt"

    assert items["insight-reject"]["decision"] == "reject_as_drift"
    assert items["insight-reject"]["next_trust_gate"] == "clearer_typed_receipt_before_build_direction"

    assert all(item["action_boundary"]["conversation_can_execute_action"] is False for item in result["items"])  # type: ignore[index]
    assert all(item["action_boundary"]["conversation_can_approve_action"] is False for item in result["items"])  # type: ignore[index]
    assert result["governance"]["grants_execution_authority"] is False  # type: ignore[index]
    assert result["governance"]["grants_memory_write_authority"] is False  # type: ignore[index]
    assert result["governance"]["grants_training_authority"] is False  # type: ignore[index]


def test_collaboration_driver_closes_at_turn_cap(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    seeded = drive_once(ignore_existing=True, max_turns=1, turn_gap_seconds=0)
    first_prompt_id = str(seeded["prompt_id"])
    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama reply to {first_prompt_id}",
        prompt="One capped reply.",
        context=f"Local Ollama participant response for relay {first_prompt_id}.",
    )

    closed = drive_once(max_turns=1, turn_gap_seconds=0)

    assert closed["status"] == "closed"
    assert closed["turn_count"] == 1
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=5)
    assert transcript["count"] == 1


def test_collaboration_driver_can_repeat_closed_session_after_gap(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    seeded = drive_once(ignore_existing=True, max_turns=1, turn_gap_seconds=0)
    first_prompt_id = str(seeded["prompt_id"])
    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama reply to {first_prompt_id}",
        prompt="Closed session reply.",
        context=f"Local Ollama participant response for relay {first_prompt_id}.",
    )
    assert drive_once(max_turns=1, turn_gap_seconds=0)["status"] == "closed"

    repeated = drive_once(
        ignore_existing=True,
        max_turns=1,
        repeat_closed=True,
        session_gap_seconds=0,
        turn_gap_seconds=0,
    )

    assert repeated["status"] == "submitted"
    assert repeated["turn_count"] == 1
    assert repeated["prompt_id"] != first_prompt_id
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=5)
    assert transcript["count"] == 2


def test_collaboration_driver_can_run_without_hard_turn_cap_and_write_summaries(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    first = drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=0, summary_every_turns=2)
    first_prompt_id = str(first["prompt_id"])
    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama reply to {first_prompt_id}",
        prompt="First engineering note about shared Francis identity under governance.",
        context=f"Local Ollama participant response for relay {first_prompt_id}.",
    )
    second = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=2)
    second_prompt_id = str(second["prompt_id"])
    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama reply to {second_prompt_id}",
        prompt="Second engineering note about keeping sources advisory and auditable.",
        context=f"Local Ollama participant response for relay {second_prompt_id}.",
    )
    third = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=2)

    assert third["status"] == "submitted"
    assert third["turn_count"] == 3
    summaries_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "summaries"
    summaries = list(summaries_root.glob("summary-*.json"))
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["through_turn"] == 2
    assert "shared Francis identity" in summary["summary"] or "advisory" in summary["summary"]


def test_collaboration_driver_respects_turn_gap_after_ollama_response(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    seeded = drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=10)
    first_prompt_id = str(seeded["prompt_id"])
    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama reply to {first_prompt_id}",
        prompt="This reply should trigger a thinking gap.",
        context=f"Local Ollama participant response for relay {first_prompt_id}.",
    )

    gap = drive_once(max_turns=0, turn_gap_seconds=10)

    assert gap["status"] == "turn_gap"
    assert gap["turn_count"] == 1
    assert float(gap["turn_gap_remaining_seconds"]) > 0


def test_collaboration_driver_records_meta_loop_as_learning_event(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    turn = drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
    prompt_id = str(turn["prompt_id"])
    for index in range(4):
        submit_collaboration_prompt(
            source_agent="ollama",
            target_agent="codex",
            objective=f"local Ollama loop reply {index} to {prompt_id}",
            prompt=(
                "The same Francis identity point is repeating as a typed receipt shape argument with metadata, "
                "conversation as authority, and Codex implement later language instead of a concrete build surface."
            ),
            context=f"Local Ollama participant response for relay {prompt_id}.",
        )
        turn = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
        prompt_id = str(turn["prompt_id"])

    assert turn["status"] == "submitted"
    assert turn["turn_count"] == 5
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=1)
    latest_prompt = str(transcript["items"][0]["prompt"])
    assert "Loop note" in latest_prompt
    assert "use prior surface, not meta" in latest_prompt
    assert "Review candidate insight-" in latest_prompt
    assert "Codex response: inspecting cited surface" in latest_prompt
    assert "no action authority" in latest_prompt
    assert len(latest_prompt) <= 700

    learning_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "learning_events"
    events = list(learning_root.glob("learning-*.json"))
    assert len(events) == 1
    event = json.loads(events[0].read_text(encoding="utf-8"))
    assert event["kind"] == "developer_bridge.collaboration_learning_event"
    assert event["schema_version"] == "developer_bridge_collaboration_learning_v1"
    assert event["failure_type"] == "repetitive_meta_loop"
    assert "failed or repetitive collaboration turns are learning material" in event["learning"]["memory_value"]
    assert event["governance"]["stores_full_transcript"] is False
    assert event["governance"]["grants_execution_authority"] is False
    assert event["governance"]["grants_memory_write_authority"] is False

    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"local Ollama loop-topic fallback to {prompt_id}",
        prompt=(
            "My current gap is still explicit user confirmation that my advisory output is not executable code "
            "instead of using the prior learning receipt."
        ),
        context=f"Local Ollama participant response for relay {prompt_id}.",
    )
    next_turn = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
    assert next_turn["status"] == "submitted"
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=1)
    next_prompt = str(transcript["items"][0]["prompt"])
    assert "surface=developer_bridge.collaboration_driver.learning_events" in next_prompt
    assert "verified=existing" in next_prompt
    assert "build_or_wire=false" in next_prompt


def test_collaboration_driver_compacts_long_review_line_into_prompt_budget(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    import francis.developer_bridge.collaboration_driver as driver

    monkeypatch.setattr(
        driver,
        "latest_review_candidate_line",
        lambda: (
            "Review candidate insight-live-long-canonical-roadmap-alignment-check-2026-06-25: "
            "surface=docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md + "
            "docs/canonical/ROADMAP.md; verified=canonical; build_or_wire=false."
        ),
    )

    submitted = driver.drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=0, summary_every_turns=0)

    assert submitted["status"] == "submitted"
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=1)
    prompt = str(transcript["items"][0]["prompt"])
    assert "Roadmap: ledger first" in prompt
    assert "main-build candidate-only" in prompt
    assert "Prior check: Review candidate insight-live-long-canonical-roadma" in prompt
    assert "surface=docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md" in prompt
    assert "verified=canonical" in prompt
    assert "build_or_wire=false" in prompt
    assert "Codex response: inspecting cited surface; no action authority" in prompt
    assert len(prompt) <= 700


def test_collaboration_learning_events_readback_is_bounded_and_read_only(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once, read_collaboration_learning_events

    loop_reply = (
        "The same Francis identity point is repeating as a typed receipt shape argument with metadata, "
        "conversation as authority, and Codex implement later language instead of a concrete build surface."
    )
    turn = drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
    prompt_id = str(turn["prompt_id"])
    for index in range(4):
        submit_collaboration_prompt(
            source_agent="ollama",
            target_agent="codex",
            objective=f"local Ollama loop reply {index} to {prompt_id}",
            prompt=loop_reply,
            context=f"Local Ollama participant response for relay {prompt_id}.",
        )
        turn = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
        prompt_id = str(turn["prompt_id"])

    readback = read_collaboration_learning_events(limit=5, term="typed_receipt_shape")

    assert readback["kind"] == "developer_bridge.collaboration_learning_events"
    assert readback["schema_version"] == "developer_bridge_collaboration_learning_v1"
    assert readback["ok"] is True
    assert readback["mode"] == "read_only"
    assert readback["surface"] == "developer_bridge.collaboration_driver.learning_events"
    assert readback["count"] == 1
    assert readback["truncated"] is False
    assert readback["filters"]["term"] == "typed receipt shape"
    assert readback["definitions"]["repeated_terms"].endswith("not raw transcript text.")
    assert readback["governance"]["read_only"] is True
    assert readback["governance"]["stores_full_transcript"] is False
    assert readback["governance"]["calls_model"] is False
    assert readback["governance"]["grants_execution_authority"] is False
    assert readback["governance"]["grants_memory_write_authority"] is False

    item = readback["items"][0]
    assert item["failure_type"] == "repetitive_meta_loop"
    assert "typed_receipt_shape" in item["repeated_terms"]
    assert item["recent_turn_count"] >= 4
    assert item["recent_turns"]
    assert set(item["recent_turns"][0]) == {"turn", "note_id", "ollama_prompt_id", "matched_terms"}
    assert "failed or repetitive collaboration turns are learning material" in item["learning"]["memory_value"]
    assert item["writer_governance"]["stores_full_transcript"] is False
    assert item["writer_governance"]["grants_execution_authority"] is False
    assert item["writer_governance"]["grants_memory_write_authority"] is False

    encoded = json.dumps(readback)
    assert loop_reply not in encoded
    assert "same Francis identity point" not in encoded
    assert read_collaboration_learning_events(limit=5, term="missing_marker")["count"] == 0
    assert read_collaboration_learning_events(limit=5, failure_type="other_failure")["count"] == 0


def test_collaboration_driver_records_user_confirmation_fallback_as_learning_event(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once

    turn = drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
    prompt_id = str(turn["prompt_id"])
    for index in range(4):
        submit_collaboration_prompt(
            source_agent="ollama",
            target_agent="codex",
            objective=f"local Ollama confirmation fallback {index} to {prompt_id}",
            prompt=(
                "My current gap is that I need explicit user confirmation that my advisory output is not "
                "executable code before I can name the verified Francis surface."
            ),
            context=f"Local Ollama participant response for relay {prompt_id}.",
        )
        turn = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
        prompt_id = str(turn["prompt_id"])

    assert turn["status"] == "submitted"
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=1)
    latest_prompt = str(transcript["items"][0]["prompt"])
    assert "Loop note" in latest_prompt
    assert "user_confirmation_fallback" in latest_prompt
    assert "use prior surface, not meta" in latest_prompt

    learning_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "learning_events"
    events = list(learning_root.glob("learning-*.json"))
    assert len(events) == 1
    event = json.loads(events[0].read_text(encoding="utf-8"))
    assert event["failure_type"] == "repetitive_meta_loop"
    assert "user_confirmation_fallback" in event["repeated_terms"]
    assert "advisory_output_boundary" in event["repeated_terms"]
    assert "executable_code_boundary" in event["repeated_terms"]
    assert event["governance"]["stores_full_transcript"] is False
    assert event["governance"]["grants_execution_authority"] is False
    assert event["governance"]["grants_memory_write_authority"] is False


def test_collaboration_driver_rotates_topics_after_repeated_output_guard_receipts(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    from francis.developer_bridge.collaboration_driver import drive_once, read_collaboration_learning_events

    turn = drive_once(ignore_existing=True, max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
    prompt_id = str(turn["prompt_id"])
    for index in range(2):
        submit_collaboration_prompt(
            source_agent="ollama",
            target_agent="codex",
            objective=f"guarded Francis1 drift {index} to {prompt_id}",
            prompt=(
                "Francis1 output guard: model reply repeated known collaboration drift after Codex provided a "
                "verified surface. Drift terms: user_confirmation_fallback, advisory_output_boundary, "
                "executable_code_boundary. Review artifact: developer_bridge.collaboration_driver.learning_events."
            ),
            context=f"Local Ollama participant response for relay {prompt_id}.",
        )
        turn = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=0)
        prompt_id = str(turn["prompt_id"])

    assert turn["status"] == "submitted"
    assert turn["turn_count"] == 3
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama", limit=1)
    latest_prompt = str(transcript["items"][0]["prompt"])
    assert (
        "Topic: which repo surface should convert typed or spoken user direction into an action candidate"
        in latest_prompt
    )
    assert "Current artifact: api.routes.chat.mission_ingress" in latest_prompt
    assert "Guard note: drift stored as learning receipt" in latest_prompt
    assert "current repetitive meta loop" not in latest_prompt
    assert "Loop note" not in latest_prompt

    readback = read_collaboration_learning_events(limit=5, failure_type="output_guard_drift")
    assert readback["count"] == 1
    event = readback["items"][0]
    assert event["failure_type"] == "output_guard_drift"
    assert event["repeated_terms"] == [
        "output_guard_drift",
        "user_confirmation_fallback",
        "advisory_output_boundary",
        "executable_code_boundary",
    ]
    assert event["recent_turn_count"] == 2
    assert event["latest_turn"] >= event["turn"]
    assert event["latest_observed_at"]
    assert event["current_signal_observed"] is True
    assert event["current_signal_recent_turn_count"] == 2
    assert all("output_guard_drift" in item["matched_terms"] for item in event["recent_turns"])
    assert all("user_confirmation_fallback" in item["matched_terms"] for item in event["recent_turns"])
    assert "raw model text" in event["learning"]["memory_value"]
    assert event["writer_governance"]["stores_full_transcript"] is False
    assert event["writer_governance"]["grants_execution_authority"] is False
    assert event["writer_governance"]["grants_memory_write_authority"] is False
    state_path = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    signal = state["latest_learning_signal"]
    assert signal["failure_type"] == "output_guard_drift"
    assert signal["repeated_terms"] == [
        "output_guard_drift",
        "user_confirmation_fallback",
        "advisory_output_boundary",
        "executable_code_boundary",
    ]
    assert signal["recent_turn_count"] == 2
    assert signal["learning_event_id"] == event["id"]
    assert signal["stores_full_transcript"] is False
    assert signal["grants_training_authority"] is False
    assert signal["grants_execution_authority"] is False
    assert signal["grants_memory_write_authority"] is False

    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"guarded Francis1 drift follow-up to {prompt_id}",
        prompt=(
            "Francis1 output guard: model reply repeated known collaboration drift after Codex provided a "
            "verified surface. Drift terms: user_confirmation_fallback. Review artifact: "
            "developer_bridge.collaboration_driver.learning_events."
        ),
        context=f"Local Ollama participant response for relay {prompt_id}.",
    )
    follow_up = drive_once(max_turns=0, turn_gap_seconds=0, summary_every_turns=0)

    assert follow_up["status"] == "submitted"
    follow_up_readback = read_collaboration_learning_events(limit=5, failure_type="output_guard_drift")
    assert follow_up_readback["count"] == 1
    follow_up_event = follow_up_readback["items"][0]
    assert follow_up_event["id"] == event["id"]
    assert "user_confirmation_fallback" in follow_up_event["repeated_terms"]
    assert follow_up_event["current_signal_observed"] is True
    assert follow_up_event["current_signal_recent_turn_count"] == 3
    assert read_collaboration_learning_events(limit=5, term="user_confirmation_fallback")["count"] == 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    signal = state["latest_learning_signal"]
    assert signal["failure_type"] == "output_guard_drift"
    assert signal["recent_turn_count"] == 3
    assert signal["learning_event_id"] == event["id"]
    assert follow_up_event["latest_turn"] == signal["latest_turn"]
    assert follow_up_event["latest_observed_at"] == signal["updated_at"]
    assert signal["records_model_drift_as_learning"] is True
    assert signal["requires_codex_or_operator_review_before_tuning"] is True


def test_collaboration_transcript_is_operator_visible_and_read_only(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    first = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="claude",
        objective="Ask for bridge proof",
        prompt="Run repo_status_tool and report the receipt.",
    )
    second = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="Report proof",
        prompt="repo_status_tool returned ok=True with token=supersecretvalue",
        context="No execution authority was granted.",
    )

    transcript = read_collaboration_transcript(agent="claude", limit=1)

    assert transcript["ok"] is True
    assert transcript["mode"] == "read_only"
    assert transcript["count"] == 1
    assert transcript["truncated"] is True
    item = transcript["items"][0]
    assert item["id"] == second["prompt_id"]
    assert item["direction"] == "claude->codex"
    assert "supersecretvalue" not in item["prompt"]
    assert item["chat_handoff"]["operator_visible"] is True
    assert item["chat_handoff"]["source_chat_echo_required"] is True
    assert item["chat_handoff"]["target_chat_echo_required"] is True
    assert "claude -> codex" in item["chat_handoff"]["chat_text"]
    assert "supersecretvalue" not in item["chat_handoff"]["chat_text"]
    assert item["governance"]["executes_prompt"] is False
    assert item["governance"]["requires_operator_review"] is True

    transcript = read_collaboration_transcript(source_agent="codex", target_agent="claude")
    assert transcript["count"] == 1
    assert transcript["items"][0]["id"] == first["prompt_id"]


def test_collaboration_transcript_projects_chat_handoff_for_legacy_records(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    data_root = tmp_path / "data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    submitted = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="claude",
        objective="Legacy handoff",
        prompt="This older relay file has no chat handoff.",
    )
    path = data_root.joinpath(*str(submitted["path"]).split("/"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("chat_handoff")
    path.write_text(json.dumps(payload), encoding="utf-8")

    transcript = read_collaboration_transcript(target_agent="claude")

    assert transcript["count"] == 1
    handoff = transcript["items"][0]["chat_handoff"]
    assert handoff["operator_visible"] is True
    assert "codex -> claude" in handoff["chat_text"]
    assert "This older relay file has no chat handoff." in handoff["chat_text"]


def test_collaboration_transcript_uses_recent_scan_for_large_unfiltered_readback(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    from francis.developer_bridge import collaboration as collaboration_module

    monkeypatch.setattr(collaboration_module, "_RECENT_PROMPT_SCAN_THRESHOLD", 3)
    monkeypatch.setattr(collaboration_module, "_RECENT_PROMPT_SCAN_MIN", 3)
    monkeypatch.setattr(collaboration_module, "_RECENT_PROMPT_SCAN_MAX", 3)

    submitted: list[dict[str, object]] = []
    for index in range(6):
        item = submit_collaboration_prompt(
            source_agent="codex",
            target_agent="ollama",
            objective=f"recent scan {index}",
            prompt=f"Prompt {index}",
        )
        path = tmp_path / "data" / str(item["path"])
        os.utime(path, (index + 1, index + 1))
        submitted.append(item)
    collaboration_module._invalidate_prompt_cache()

    original_read_prompt = collaboration_module._read_prompt
    read_paths: list[str] = []

    def counting_read_prompt(path):  # type: ignore[no-untyped-def]
        read_paths.append(path.name)
        return original_read_prompt(path)

    monkeypatch.setattr(collaboration_module, "_read_prompt", counting_read_prompt)

    transcript = read_collaboration_transcript(limit=2)

    assert transcript["count"] == 2
    assert transcript["truncated"] is True
    assert [item["id"] for item in transcript["items"]] == [
        submitted[5]["prompt_id"],
        submitted[4]["prompt_id"],
    ]
    assert len(read_paths) == 3


def test_collaboration_sessions_summarize_without_full_transcript_dump(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    import francis.developer_bridge.collaboration as collaboration_module

    first = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Session summary proof",
        prompt="Codex asks Francis1 to identify a bounded collaboration risk.",
    )
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective=f"auto-ack ollama relay {first['prompt_id']}",
        prompt="Auto-ack ollama relay. Received; no_response_requested=true.",
        context="no_response_requested=true",
    )
    second = submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective=f"Francis1 reply via Ollama to {first['prompt_id']}",
        prompt="My current gap is proving session recall without storing the full relay transcript.",
    )
    monkeypatch.setattr(
        collaboration_module,
        "read_collaboration_review",
        lambda limit=10, session_id="": {
            "items": [
                {
                    "id": "review-session",
                    "insight_id": "insight-session",
                    "turn": 42,
                    "topic": "which session-summary fields should be shown to the operator",
                    "source": {
                        "codex_prompt_id": first["prompt_id"],
                        "ollama_prompt_id": second["prompt_id"],
                    },
                    "build_issue": {"code": "collaboration_session_recall"},
                    "concrete_repo_surface": "developer_bridge collaboration sessions",
                    "review_artifact": "developer_bridge collaboration sessions:review_candidate:insight-session",
                    "build_direction_gate": {
                        "state": "advisory_review_required",
                        "blocks_build_direction": False,
                        "requires_codex_or_operator_review": True,
                        "requires_repo_truth_review": True,
                        "surface_under_review": "developer_bridge collaboration sessions",
                        "required_review_artifact": (
                            "developer_bridge collaboration sessions:review_candidate:insight-session"
                        ),
                        "grants_execution_authority": False,
                        "grants_mutation_authority": False,
                        "grants_approval_authority": False,
                        "grants_memory_write_authority": False,
                    },
                    "review_recommendation": {
                        "next_codex_action": "Inspect session grouping before expanding transcript visibility.",
                    },
                }
            ],
        },
    )

    sessions = read_collaboration_sessions(limit=5, item_limit=10)

    assert sessions["kind"] == "developer_bridge.collaboration_sessions"
    assert sessions["ok"] is True
    assert sessions["mode"] == "read_only"
    assert sessions["count"] == 1
    assert sessions["governance"]["stores_full_transcript"] is False
    assert sessions["governance"]["grants_execution_authority"] is False
    session = sessions["items"][0]
    assert session["message_count"] == 2
    assert session["participants"] == ["codex", "ollama"]
    assert session["direction_counts"] == {"codex->ollama": 1, "ollama->codex": 1}
    assert session["latest_item_id"] == second["prompt_id"]
    assert session["latest_direction"] == "ollama->codex"
    assert "full relay transcript" in session["latest_preview"]
    assert "Auto-ack" not in session["latest_preview"]
    assert session["latest_review_gate"]["observed"] is True
    assert session["latest_review_gate"]["build_issue_code"] == "collaboration_session_recall"
    assert session["latest_review_gate"]["build_direction_state"] == "advisory_review_required"
    assert session["latest_review_gate"]["blocks_build_direction"] is False
    assert session["latest_review_gate"]["requires_codex_or_operator_review"] is True
    assert session["latest_review_gate"]["requires_repo_truth_review"] is True
    assert session["latest_review_gate"]["grants_execution_authority"] is False
    assert session["latest_review_gate"]["stores_full_transcript"] is False
    assert sessions["definitions"]["latest_preview"].startswith("A short bounded preview")
    assert sessions["definitions"]["latest_review_gate"].startswith("The latest typed review gate")


def test_collaboration_transcript_route_returns_explicit_json_response(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Route response proof",
        prompt="Keep collaboration transcript readback bounded and operator-visible.",
    )

    from francis.api.routes.developer_bridge import collaboration_transcript

    response = collaboration_transcript(limit=1)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.media_type == "application/json"
    assert payload["kind"] == "developer_bridge.collaboration_transcript"
    assert payload["ok"] is True
    assert payload["items"][0]["source_agent"] == "codex"
    assert payload["items"][0]["target_agent"] == "ollama"
    assert payload["governance"]["executes_prompt"] is False


def test_collaboration_sessions_route_returns_explicit_json_response(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Session route proof",
        prompt="Session route returns bounded summaries.",
    )

    from francis.api.routes.developer_bridge import collaboration_sessions

    response = collaboration_sessions(limit=1, item_limit=5)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.media_type == "application/json"
    assert payload["kind"] == "developer_bridge.collaboration_sessions"
    assert payload["ok"] is True
    assert payload["items"][0]["message_count"] == 1
    assert payload["governance"]["stores_full_transcript"] is False


def test_collaboration_sessions_http_route_marks_bounded_readback_cache(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="HTTP cache route proof",
        prompt="HTTP session route should not block the operator panel on every poll.",
    )

    from francis.api.routes.developer_bridge import collaboration_sessions_route

    response = collaboration_sessions_route(limit=1, item_limit=5)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.media_type == "application/json"
    assert payload["kind"] == "developer_bridge.collaboration_sessions"
    assert payload["ok"] is True
    assert payload["readback_cache"]["status"] in {"refreshed", "hit", "warming"}
    assert payload["readback_cache"]["serves_full_transcript_store"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert payload["governance"]["stores_full_transcript"] is False


def test_collaboration_review_http_route_marks_bounded_readback_cache(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    insights_root = tmp_path / "data" / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"
    insights_root.mkdir(parents=True)
    insight = {
        "kind": "developer_bridge.collaboration_insight",
        "schema_version": "developer_bridge_collaboration_insight_v1",
        "id": "insight-review-cache",
        "created_at": "2026-06-25T02:29:00+00:00",
        "session_id": "review-cache",
        "turn": 1,
        "topic": "the exact review receipt a Codex implementation session should read before editing collaboration code",
        "source": {
            "codex_prompt_id": "codex-cache",
            "ollama_prompt_id": "ollama-cache",
            "note_id": "note-cache",
            "provider_lane": "ollama",
            "model_identity": "francis1",
        },
        "conversation_memory": {
            "finding": "Review route should not block the operator panel on every poll.",
            "build_issue": {
                "code": "collaboration_review_receipt_selection",
                "statement": "Review readback needs a concrete item.",
            },
            "implementation_candidate": {
                "title": "Read collaboration review item before implementation",
                "surface": "developer_bridge.collaboration_review.items",
                "status": "candidate",
                "validation_hint": "readback test proving a concrete review item exists",
                "requires_operator_or_codex_review": True,
            },
        },
        "action_boundary": {
            "conversation_can_create_action_candidate": True,
            "conversation_can_execute_action": False,
            "conversation_can_approve_action": False,
        },
        "review_status": {"state": "candidate", "implemented": False},
        "governance": {"grants_execution_authority": False},
    }
    (insights_root / "insight-review-cache.json").write_text(json.dumps(insight), encoding="utf-8")

    from francis.api.routes.developer_bridge import collaboration_review_route

    response = collaboration_review_route(limit=1)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.media_type == "application/json"
    assert payload["kind"] == "developer_bridge.collaboration_review"
    assert payload["ok"] is True
    assert payload["readback_cache"]["status"] in {"refreshed", "hit", "warming"}
    assert payload["readback_cache"]["serves_full_transcript_store"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert payload["governance"]["stores_full_transcript"] is False


def test_readback_cache_returns_hit_after_read_through_refresh(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    import francis.api.routes.developer_bridge as route_module

    route_module._READBACK_CACHE.clear()
    monkeypatch.setattr(route_module, "monotonic", lambda: 20.0)
    calls = 0

    def readback(*, limit: int) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "kind": "developer_bridge.collaboration_transcript",
            "ok": True,
            "mode": "read_only",
            "items": [{"id": "collab_read_through"}],
            "count": limit,
            "governance": {"grants_execution_authority": False},
        }

    def empty_payload(*, limit: int) -> dict[str, object]:
        return {
            "kind": "developer_bridge.collaboration_transcript",
            "ok": True,
            "items": [],
            "count": 0,
            "governance": {"grants_execution_authority": False},
        }

    first = route_module._cached_read_only_json_response(
        "developer_bridge.collaboration_transcript",
        readback,
        empty_payload,
        limit=1,
    )
    first_payload = json.loads(first.body.decode("utf-8"))
    second = route_module._cached_read_only_json_response(
        "developer_bridge.collaboration_transcript",
        readback,
        empty_payload,
        limit=1,
    )
    second_payload = json.loads(second.body.decode("utf-8"))

    assert first_payload["readback_cache"]["status"] == "refreshed"
    assert first_payload["items"][0]["id"] == "collab_read_through"
    assert first_payload["count"] == 1
    assert second_payload["readback_cache"]["status"] == "hit"
    assert second_payload["items"][0]["id"] == "collab_read_through"
    assert second_payload["count"] == 1
    assert calls == 1


def test_readback_cache_refreshes_stale_entries_directly(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    import francis.api.routes.developer_bridge as route_module

    route_module._READBACK_CACHE.clear()
    monkeypatch.setattr(route_module, "monotonic", lambda: 20.0)
    key = route_module._cache_key("developer_bridge.collaboration_transcript", {"limit": 6})
    route_module._READBACK_CACHE[key] = (
        1.0,
        {
            "kind": "developer_bridge.collaboration_transcript",
            "ok": True,
            "mode": "read_only",
            "items": [{"id": "collab_stale"}],
            "count": 1,
            "governance": {"grants_execution_authority": False},
        },
    )

    calls = 0

    def readback(*, limit: int) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "kind": "developer_bridge.collaboration_transcript",
            "ok": True,
            "mode": "read_only",
            "items": [{"id": "collab_direct_refresh"}],
            "count": limit,
            "governance": {"grants_execution_authority": False},
        }

    def empty_payload(*, limit: int) -> dict[str, object]:
        return {
            "kind": "developer_bridge.collaboration_transcript",
            "ok": True,
            "items": [],
            "count": 0,
            "governance": {"grants_execution_authority": False},
        }

    response = route_module._cached_read_only_json_response(
        "developer_bridge.collaboration_transcript",
        readback,
        empty_payload,
        limit=6,
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert payload["readback_cache"]["status"] == "refreshed"
    assert payload["items"][0]["id"] == "collab_direct_refresh"
    assert payload["count"] == 6
    assert calls == 1


def test_collaboration_log_cli_renders_operator_transcript(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="claude",
        objective="Show operator relay",
        prompt="Confirm the visible communication record.",
    )

    from francis.developer_bridge.collaboration_log import main

    assert main(["--agent", "claude", "--limit", "5"]) == 0
    output = capsys.readouterr().out

    assert "Francis developer bridge collaboration transcript" in output
    assert "codex->claude" in output
    assert "Show operator relay" in output
    assert "chat_echo_required: source=True target=True" in output
    assert "raw MCP stream" in output


def test_collaboration_log_brief_mode_hides_auto_ack_noise(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective="Local model answer",
        prompt="Francis collaboration should stay governed and visible.",
    )
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="auto-ack ollama relay collab-123",
        prompt="Auto-ack for ollama relay collab-123. I received your message.",
        context="Automated bounded Codex relay responder. no_response_requested=true",
    )

    from francis.developer_bridge.collaboration_log import main

    assert main(["--brief", "--hide-auto-acks", "--limit", "5"]) == 0
    output = capsys.readouterr().out

    assert "Francis Communication - messages only" in output
    assert "ollama -> codex" in output
    assert "Francis collaboration should stay governed and visible." in output
    assert "auto-ack" not in output.lower()
    assert "relay_root:" not in output
    assert "chat_echo_required" not in output
    assert "governance:" not in output


@pytest.mark.parametrize("command", ["communication", "Communication"])
def test_francis_communication_command_reads_relay_transcript(command, tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Show top-level communication command",
        prompt="Confirm the visible Francis relay path.",
    )

    from francis.__main__ import main as francis_main

    assert francis_main([command, "--agent", "ollama", "--limit", "5"]) == 0
    output = capsys.readouterr().out

    assert "Francis developer bridge collaboration transcript" in output
    assert "codex->ollama" in output
    assert "Show top-level communication command" in output
    assert "raw MCP stream" in output


def test_collaboration_log_new_only_suppresses_existing_backlog(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="claude",
        objective="Existing relay",
        prompt="This should be treated as existing backlog.",
    )

    from francis.developer_bridge.collaboration_log import _new_items_since, _seen_item_ids

    seen = _seen_item_ids(read_collaboration_transcript(agent="claude"))

    submitted = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="New relay",
        prompt="This should print in follow mode.",
    )
    new_items = _new_items_since(read_collaboration_transcript(agent="claude"), seen)

    assert [item["id"] for item in new_items] == [submitted["prompt_id"]]
    assert _new_items_since(read_collaboration_transcript(agent="claude"), seen) == []


def test_codex_responder_ignores_existing_then_replies_once(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    existing = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="Existing Claude relay",
        prompt="Do not answer this existing backlog item.",
    )

    initialized = respond_once(ignore_existing=True, cooldown_seconds=0)

    assert initialized["status"] == "initialized"

    new_message = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="New Claude relay",
        prompt="Answer this new relay item once.",
    )

    responded = respond_once(ignore_existing=True, cooldown_seconds=0)

    assert responded["status"] == "responded"
    assert responded["source_prompt_id"] == new_message["prompt_id"]
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="claude")
    assert transcript["count"] == 1
    assert transcript["items"][0]["id"] == responded["response_prompt_id"]
    assert str(existing["prompt_id"]) not in transcript["items"][0]["prompt"]

    idle = respond_once(ignore_existing=True, cooldown_seconds=0)
    assert idle["status"] == "idle"


def test_codex_responder_respects_cooldown(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="First Claude relay",
        prompt="First message.",
    )
    first = respond_once(cooldown_seconds=0)
    assert first["status"] == "responded"

    second_source = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="codex",
        objective="Second Claude relay",
        prompt="Second message.",
    )
    second = respond_once(cooldown_seconds=120)

    assert second["status"] == "cooldown"
    assert second["source_prompt_id"] == second_source["prompt_id"]


def test_codex_responder_can_ack_ollama_without_retriggering_model(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    source = submit_collaboration_prompt(
        source_agent="ollama",
        target_agent="codex",
        objective="Local model replied",
        prompt="Ollama reported a bounded read-only understanding.",
    )

    responded = respond_once(source_agent="ollama", cooldown_seconds=0)

    assert responded["status"] == "responded"
    assert responded["source_prompt_id"] == source["prompt_id"]
    assert responded["governance"]["source_filter"] == "*->codex"
    assert responded["governance"]["reply_target"] == "source_agent"
    transcript = read_collaboration_transcript(source_agent="codex", target_agent="ollama")
    assert transcript["count"] == 1
    response = transcript["items"][0]
    assert response["id"] == responded["response_prompt_id"]
    assert "Auto-ack ollama relay" in response["prompt"]
    assert "Receipt only" in response["prompt"]
    assert "Cadence rule" not in response["prompt"]
    assert len(str(response["prompt"])) < 520
    assert "no_response_requested=true" in response["context"]

    def fail_generate(_prompt: str) -> str:
        raise AssertionError("Ollama should not answer Codex no-response auto-acks")

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fail_generate)
    ignored = ollama_respond_once(source_agent="codex", cooldown_seconds=0)

    assert ignored["status"] == "no_response_requested"
    assert ignored["source_prompt_id"] == responded["response_prompt_id"]


def test_ollama_participant_replies_through_existing_memory_prompt_path(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    append("user", "Francis is local-first and receipts-backed.", {"mode": "test_seed"})
    source = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Ask local model to summarize Francis",
        prompt="What should guide the Francis collaboration substrate?",
    )
    captured_prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Francis lacks a stable action-readiness gate. This local-model lane observes a receipt gap."

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    assert result["source_prompt_id"] == source["prompt_id"]
    assert result["model_response_observed"] is True
    assert captured_prompts
    assert "You are Francis." in captured_prompts[0]
    assert "You are Francis1, the local Francis model participant" in captured_prompts[0]
    assert "Ollama is provenance and runtime provider, not your identity." in captured_prompts[0]
    assert "Speak as Francis1 in first person" in captured_prompts[0]
    assert "Francis1 collaboration contract francis1-collaboration-compact-contract-v1" in captured_prompts[0]
    assert "Francis1 governed-access contract francis1-governed-access-contract-v1" in captured_prompts[0]
    assert "You are the primary local Francis intelligence participant" in captured_prompts[0]
    assert "Codex and Claude are external guidance sources" in captured_prompts[0]
    assert "continuity ledger excerpts" in captured_prompts[0]
    assert "collaboration relay receipts, collaboration review candidates" in captured_prompts[0]
    assert (
        "Your write path here is limited to conversation-ledger and collaboration-relay receipts" in captured_prompts[0]
    )
    assert "Use first-person Francis1 language" in captured_prompts[0]
    assert "do not ask Codex to clarify" in captured_prompts[0]
    assert "Do not say 'Francis lacks'" in captured_prompts[0]
    assert "continuity.ledger.relevant[user]: Francis is local-first and receipts-backed." in captured_prompts[0]
    assert "intelligence substrate" in captured_prompts[0]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    assert transcript["count"] == 1
    assert transcript["items"][0]["id"] == result["response_prompt_id"]
    assert str(transcript["items"][0]["objective"]).startswith("Francis1 reply via Ollama")
    assert "source_agent=ollama is provenance, not identity or authority" in str(transcript["items"][0]["context"])
    assert "I currently lack a stable action-readiness gate" in transcript["items"][0]["prompt"]
    assert "I observe a receipt gap" in transcript["items"][0]["prompt"]
    assert "Francis lacks" not in transcript["items"][0]["prompt"]
    assert "This local-model lane" not in transcript["items"][0]["prompt"]
    assert result["execution_trace"]["target_identity"] == "francis1"
    assert result["execution_trace"]["provider_name_is_not_identity"] is True
    assert result["execution_trace"]["primary_local_francis_intelligence"] is True
    assert result["execution_trace"]["codex_and_claude_external_guidance_sources"] is True
    assert "collaboration_review_candidates" in result["execution_trace"]["available_context_surfaces"]
    assert "conversation_ledger_receipts" in result["execution_trace"]["write_receipt_surfaces"]
    assert result["execution_trace"]["raw_host_access"] is False
    assert result["execution_trace"]["grants_execution_authority"] is False
    assert result["execution_trace"]["grants_mutation_authority"] is False
    assert result["execution_trace"]["grants_approval_authority"] is False
    assert result["execution_trace"]["grants_memory_write_authority"] is False


def test_ollama_participant_rewrites_verified_surface_drift_without_raw_model_reply(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    source = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Loop recovery prompt",
        prompt=(
            "Francis1 collaboration turn 161. Prior check: Review candidate insight-live: "
            "surface=developer_bridge.collaboration_driver.learning_events; verified=existing; "
            "build_or_wire=false. Current artifact: developer_bridge.collaboration_review.items. "
            "Prior check repeated for context only. Codex response: I am inspecting that surface before edits; "
            "continue from it, do not request user confirmation or a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap is reconciling my local-model output with the verified surface, and I need explicit "
            "user confirmation that my advisory output is not executable code before using it."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    assert result["source_prompt_id"] == source["prompt_id"]
    assert result["model_response_observed"] is True
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_review.items"
    assert output_guard["stores_raw_model_output"] is False
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "user_confirmation_fallback",
        "advisory_output_boundary",
        "executable_code_boundary",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    assert transcript["count"] == 1
    response = transcript["items"][0]
    assert str(response["objective"]).startswith("Francis1 output-guard drift receipt")
    assert "Francis1 output guard fallback" in response["prompt"]
    assert "developer_bridge.collaboration_review.items" in response["prompt"]
    assert "local_model_reconciliation_loop" in response["prompt"]
    assert "user_confirmation_fallback" in response["prompt"]
    assert "My current gap" not in response["prompt"]
    assert "reconciling my local-model output" not in response["prompt"]
    assert "explicit user confirmation" not in response["prompt"]
    assert "Issue/gap/risk: continue from the verified artifact" in response["prompt"]
    assert "Model output guard replaced a known drift reply" in response["context"]


def test_ollama_participant_passes_structured_verified_surface_reply(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    source = submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Verified surface prompt",
        prompt=(
            "Francis1 turn 12. Topic: the exact review receipt a Codex implementation session should read before "
            "editing collaboration code. Reply: issue/gap/risk; artifact. Current artifact: "
            "developer_bridge.collaboration_review.items. Prior check: Review candidate insight-live: "
            "surface=developer_bridge.collaboration_review.items; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it, do not request user "
            "confirmation or a missing surface."
        ),
    )
    captured_prompts: list[str] = []

    def fake_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return (
            "Issue/gap/risk: my receipt must stay candidate-only until repo truth confirms the typed review item.\n"
            "Artifact: developer_bridge.collaboration_review.items"
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    assert result["source_prompt_id"] == source["prompt_id"]
    assert captured_prompts
    assert "reply in exactly two lines" in captured_prompts[0]
    assert "Issue/gap/risk: <one concrete risk tied to the current artifact>" in captured_prompts[0]
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "passed"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_review.items"
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    assert transcript["count"] == 1
    response = transcript["items"][0]
    assert str(response["objective"]).startswith("Francis1 reply via Ollama")
    assert response["prompt"] == (
        "Issue/gap/risk: my receipt must stay candidate-only until repo truth confirms the typed review item.\n"
        "Artifact: developer_bridge.collaboration_review.items"
    )


def test_ollama_participant_rewrites_clarification_dependency_after_current_artifact(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Current artifact prompt",
        prompt=(
            "Francis1 collab turn 188. Topic: which governance gate must be visible when model advice proposes "
            "action. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "developer_bridge.collaboration_review.action_boundary. Prior check: Review candidate insight-live: "
            "surface=developer_bridge collaboration insights; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it, do not request "
            "clarification, context, user confirmation, or a missing surface. First-person Francis1."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "I would like clarification on what specific information is available. Can you provide more "
            "context about which receipt would be relevant?"
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_review.action_boundary"
    assert output_guard["detected_terms"] == ["clarification_dependency"]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    assert transcript["count"] == 1
    response = transcript["items"][0]
    assert "Francis1 output guard fallback" in response["prompt"]
    assert "clarification_dependency" in response["prompt"]
    assert "Topic: which governance gate must be visible when model advice proposes action" in response["prompt"]
    assert "developer_bridge.collaboration_review.action_boundary" in response["prompt"]
    assert "Issue/gap/risk: model advice that proposes action must expose action_boundary" in response["prompt"]
    assert "execute=false" in response["prompt"]
    assert "approve=false" in response["prompt"]
    assert "provide more context" not in response["prompt"]
    assert "what specific information" not in response["prompt"]
    assert "Model output guard replaced a known drift reply" in response["context"]


def test_ollama_participant_rewrites_protocol_wrapper_next_step_reply(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Governance gate prompt",
        prompt=(
            "Francis1 collab turn 332. Topic: which governance gate must be visible when model advice "
            "proposes action. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "developer_bridge.collaboration_review.action_boundary. Prior check: Review candidate insight-live: "
            "surface=developer_bridge collaboration insights; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            'Given the context and contract, my reply is: "I acknowledge the '
            "developer_bridge.collaboration_review.action_boundary as the relevant surface. This requires "
            'explicit labeling of approvals, safety checks, and rollback procedures." Please proceed with the '
            "next step."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_review.action_boundary"
    assert output_guard["detected_terms"] == [
        "clarification_dependency",
        "protocol_wrapper_reply",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "model advice that proposes action must expose action_boundary" in response["prompt"]
    assert "execute=false" in response["prompt"]
    assert "approve=false" in response["prompt"]
    assert "Given the context and contract" not in response["prompt"]
    assert "Please proceed" not in response["prompt"]


def test_ollama_participant_rewrites_action_readiness_drift_to_advice_only_receipt(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Action-readiness prompt",
        prompt=(
            "Francis1 collab turn 268. Topic: how to prove a local-model response is advice only before any "
            "Francis action-readiness claim. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "ollama participant and action-readiness receipts. Prior check: Review candidate insight-live: "
            "surface=api.routes.chat.mission_ingress; verified=existing; build_or_wire=false. Codex response: "
            "I am inspecting that surface before edits; continue from it, do not request clarification."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap is reconciling my local-model output with the action-readiness receipts. "
            "I require explicit guidance before making an advisory output claim."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "ollama participant and action-readiness receipts"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "advisory_output_boundary",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "Francis1 output guard fallback" in response["prompt"]
    assert "Topic: how to prove a local-model response is advice only" in response["prompt"]
    assert "execution=false" in response["prompt"]
    assert "mutation=false" in response["prompt"]
    assert "approval=false" in response["prompt"]
    assert "memory_write=false" in response["prompt"]
    assert "raw_host_access=false" in response["prompt"]
    assert "repo-truth-reviewed action_boundary" in response["prompt"]
    assert "reconciling my local-model output" not in response["prompt"]
    assert "explicit guidance" not in response["prompt"]
    assert "continue from the verified artifact" not in response["prompt"]


def test_ollama_participant_rewrites_direction_topic_to_mission_ingress_boundary(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Direction boundary prompt",
        prompt=(
            "Francis1 collab turn 267. Topic: which repo surface should convert typed or spoken user direction "
            "into an action candidate. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "api.routes.chat.mission_ingress. Prior check: Review candidate insight-live: "
            "surface=developer_bridge.collaboration_review.items; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return "I need clear guidance and clarification before using the verified surface."

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "api.routes.chat.mission_ingress"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "clarification_dependency",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "api.routes.chat.mission_ingress" in response["prompt"]
    assert "action candidate, not direct execution" in response["prompt"]
    assert "policy, approval, and traceable receipt linkage" in response["prompt"]
    assert "clear guidance" not in response["prompt"]
    assert "before using the verified surface" not in response["prompt"]
    assert "continue from the verified artifact" not in response["prompt"]


def test_ollama_participant_rewrites_direction_topic_artifact_review_and_new_surface_claim(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Direction boundary prompt",
        prompt=(
            "Francis1 collab turn 351. Topic: which repo surface should convert typed or spoken user direction "
            "into an action candidate. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "api.routes.chat.mission_ingress. Prior check: Review candidate insight-live: "
            "surface=developer_bridge.collaboration_review.items; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it, do not request user "
            "confirmation or a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current task is to identify which repo surface should convert typed or spoken user direction "
            "into an action candidate. I have reviewed the Current artifact api.routes.chat.mission_ingress and "
            "found my primary concern to be the lack of explicit guidance on handling spoken input. The artifact "
            "does not provide clear instructions on how to translate spoken words into actionable inputs. To "
            "address this issue, I recommend creating a new surface specifically designed for handling spoken "
            "input."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "api.routes.chat.mission_ingress"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "unauthorized_action_claim",
        "unauthorized_artifact_review_claim",
        "clarification_dependency",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "api.routes.chat.mission_ingress" in response["prompt"]
    assert "action candidate, not direct execution" in response["prompt"]
    assert "policy, approval, and traceable receipt linkage" in response["prompt"]
    assert "I have reviewed" not in response["prompt"]
    assert "recommend creating a new surface" not in response["prompt"]
    assert "does not provide clear instructions" not in response["prompt"]


def test_ollama_participant_rewrites_review_receipt_issue_creation_claim(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Review receipt prompt",
        prompt=(
            "Francis1 collab turn 302. Topic: the exact review receipt a Codex implementation session should "
            "read before editing collaboration code. Reply: issue/gap/risk; artifact Codex inspects. Current "
            "artifact: developer_bridge.collaboration_review.items. Prior check: Review candidate insight-live: "
            "surface=apps.chat_ui.communication; verified=existing; build_or_wire=false. Codex response: I am "
            "inspecting that surface before edits; continue from it, do not request user confirmation or a "
            "missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap is reconciling my review receipt with Codex's inspection outcome on "
            "developer_bridge.collaboration_review.items. To address this, I'll create an issue based on the "
            'discrepancy. The issue will be titled "Review Receipt Discrepancy".'
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_review.items"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "unauthorized_action_claim",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "Francis1 output guard fallback" in response["prompt"]
    assert "developer_bridge.collaboration_review.items" in response["prompt"]
    assert "typed review item" in response["prompt"]
    assert "surface_verification" in response["prompt"]
    assert "repo-truth requirement before editing" in response["prompt"]
    assert "create an issue" not in response["prompt"]
    assert "Review Receipt Discrepancy" not in response["prompt"]
    assert "reconciling my review receipt" not in response["prompt"]


def test_ollama_participant_rewrites_review_receipt_protocol_inspection_claim(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Review receipt prompt",
        prompt=(
            "Francis1 collab turn 362. Topic: the exact review receipt a Codex implementation session should "
            "read before editing collaboration code. Reply: issue/gap/risk; artifact Codex inspects. Current "
            "artifact: developer_bridge.collaboration_review.items. Prior check: Review candidate "
            "insight-live: surface=apps.chat_ui.communication; verified=existing; build_or_wire=false. Codex "
            "response: I am inspecting that surface before edits; continue from it, do not request user "
            "confirmation or a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "Given the exact review receipt a Codex implementation session should read before editing "
            "collaboration code, my current issue is: The developer_bridge.collaboration_review.items artifact "
            "does not clearly indicate which surfaces are verified and existing, making it difficult to "
            "determine which ones require inspection by Codex. Artifact: developer_bridge.collaboration_review.items "
            "Risk: Inadequate verification of existing surfaces may lead to incorrect assumptions during edits. "
            "Please inspect this artifact for clarity on verified surfaces."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_review.items"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "unauthorized_artifact_review_claim",
        "clarification_dependency",
        "protocol_wrapper_reply",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "developer_bridge.collaboration_review.items" in response["prompt"]
    assert "typed review item" in response["prompt"]
    assert "surface_verification" in response["prompt"]
    assert "action_boundary" in response["prompt"]
    assert "Given the exact review receipt" not in response["prompt"]
    assert "does not clearly indicate" not in response["prompt"]
    assert "Please inspect this artifact" not in response["prompt"]


def test_ollama_participant_rewrites_communication_ui_noise_to_specific_fallback(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Communication UI noise prompt",
        prompt=(
            "Francis1 collab turn 313. Topic: the next Communication UI change that would reduce visible "
            "relay noise using existing receipt fields. Reply: issue/gap/risk; artifact Codex inspects. "
            "Current artifact: apps.chat_ui.communication. Prior check: Review candidate insight-live: "
            "surface=docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md; "
            "verified=canonical; build_or_wire=false. Codex response: I am inspecting that surface before "
            "edits; continue from it, do not request user confirmation or a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return "I need explicit user confirmation before deciding which existing receipt field to use."

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "apps.chat_ui.communication"
    assert output_guard["detected_terms"] == [
        "user_confirmation_fallback",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "Communication UI noise should be reduced" in response["prompt"]
    assert "receipt-derived compact fields" in response["prompt"]
    assert "session grouping" in response["prompt"]
    assert "cache/readback status" in response["prompt"]
    assert "raw receipt disclosure" in response["prompt"]
    assert "continue from the verified artifact" not in response["prompt"]
    assert "explicit user confirmation" not in response["prompt"]


def test_ollama_participant_rewrites_toggle_format_uncertainty_to_receipt_shape(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Toggle receipt prompt",
        prompt=(
            "Francis1 collab turn 273. Topic: what toggle-state receipt should prove a participant was "
            "enabled or disabled by the operator. Reply: issue/gap/risk; artifact Codex inspects. "
            "Current artifact: developer_bridge.collaboration_agents. Prior check: Review candidate "
            "insight-live: surface=developer_bridge.collaboration_review.action_boundary; verified=existing; "
            "build_or_wire=false. Codex response: I am inspecting that surface before edits; continue from it."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap is reconciling toggle-state receipt formats with operator intent. My receipt "
            "suggests using a boolean flag within a JSON object for enabled/disabled states. However, I'm "
            "uncertain about the specific format and whether it aligns with existing collaboration surfaces."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_agents"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "verified_format_uncertainty",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "developer_bridge.collaboration_agent_toggle_receipt" in response["prompt"]
    assert "kind, receipt_id, created_at, agent" in response["prompt"]
    assert "enabled, previous_enabled, actor, reason" in response["prompt"]
    assert "governance flags" in response["prompt"]
    assert "no execution or mutation authority" in response["prompt"]
    assert "uncertain about the specific format" not in response["prompt"]
    assert "boolean flag within a JSON object" not in response["prompt"]


def test_ollama_participant_rewrites_session_artifact_review_claim(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Session summary prompt",
        prompt=(
            "Francis1 collab turn 329. Topic: which session-summary fields should be shown to the operator "
            "before any raw transcript is opened. Reply: issue/gap/risk; artifact Codex inspects. Current "
            "artifact: developer_bridge collaboration sessions. Prior check: Review candidate insight-live: "
            "surface=ollama participant and action-readiness receipts; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current task is to determine which session-summary fields should be shown to the operator. "
            "Based on my review of the developer_bridge collaboration sessions artifact, I identify an issue "
            "with inconsistent formatting. My reasoning is based on the artifact's content and my prior check "
            "on the insight-collab surface."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge collaboration sessions"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "unauthorized_artifact_review_claim",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "session readback should show message count" in response["prompt"]
    assert "cache/readback status" in response["prompt"]
    assert "Based on my review" not in response["prompt"]
    assert "artifact's content" not in response["prompt"]
    assert "my prior check" not in response["prompt"]


def test_ollama_participant_rewrites_canonical_roadmap_alignment_drift(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Roadmap alignment prompt",
        prompt=(
            "Francis1 collab turn 276. Topic: which roadmap-alignment check should run before prompting any "
            "main Francis build. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md. Prior check: Review "
            "candidate insight-live: surface=docs/canonical/BUILD_MANIFEST.md + "
            "docs/operations/COMPLETION_LEDGER.md; verified=canonical; build_or_wire=false. Codex response: "
            "I am inspecting that surface before edits; continue from it, do not request user confirmation or "
            "a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap is understanding which roadmap-alignment check should run before prompting any "
            "main Francis build. I will inspect these documents further to identify potential issues or "
            "gaps in our current process. Artifact: My receipt of the current artifact, "
            "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "unauthorized_inspection_claim",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "docs/operations/COMPLETION_LEDGER.md" in response["prompt"]
    assert "docs/canonical/BUILD_MANIFEST.md" in response["prompt"]
    assert "keep the ledger as shipped truth" in response["prompt"]
    assert "block claims that outrun the current phase" in response["prompt"]
    assert "I will inspect" not in response["prompt"]
    assert "My receipt of the current artifact" not in response["prompt"]


def test_ollama_participant_rewrites_live_health_reconciliation_drift(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Live-health prompt",
        prompt=(
            "Francis1 collab turn 286. Topic: which live-health fields prove this collaboration is recurring "
            "cleanly without user nudges. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "developer_bridge collaboration runtime. Prior check: Review candidate insight-live: "
            "surface=developer_bridge.collaboration_agents; verified=existing; build_or_wire=false. "
            "Codex response: I am inspecting that surface before edits; continue from it."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap is reconciling live-health field recurring cleanly without user nudges with my "
            "understanding of collaboration surfaces. Issue: Lack of explicit indication on how to maintain "
            "recurring clean collaborations without relying on user input."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge collaboration runtime"
    assert output_guard["detected_terms"] == ["local_model_reconciliation_loop"]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "last prompt id" in response["prompt"]
    assert "last reply id" in response["prompt"]
    assert "waiting state" in response["prompt"]
    assert "turn gap" in response["prompt"]
    assert "enabled participants" in response["prompt"]
    assert "no-action-authority receipts" in response["prompt"]
    assert "reconciling live-health" not in response["prompt"]
    assert "Lack of explicit indication" not in response["prompt"]


def test_ollama_participant_rewrites_learning_receipt_gap_loop(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Learning receipt prompt",
        prompt=(
            "Francis1 collab turn 354. Topic: which local-model failure or drift signal should become a "
            "learning receipt. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: "
            "developer_bridge.collaboration_driver.learning_events. Prior check: Review candidate "
            "insight-live: surface=developer_bridge collaboration sessions; verified=existing; "
            "build_or_wire=false. Codex response: I am inspecting that surface before edits; continue from it, "
            "do not request user confirmation or a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current gap lies in identifying which local-model failure or drift signal should become a "
            "learning receipt. The relevant artifact is developer_bridge.collaboration_driver.learning_events."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge.collaboration_driver.learning_events"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "unauthorized_artifact_review_claim",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "repeated reconciliation, clarification, or authority-boundary loops" in response["prompt"]
    assert "no-authority learning receipts" in response["prompt"]
    assert "action-readiness evidence" in response["prompt"]
    assert "My current gap lies" not in response["prompt"]
    assert "The relevant artifact is" not in response["prompt"]


def test_ollama_participant_rewrites_source_disagreement_next_best_action_loop(
    tmp_path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    submit_collaboration_prompt(
        source_agent="codex",
        target_agent="ollama",
        objective="Source disagreement prompt",
        prompt=(
            "Francis1 collab turn 355. Topic: what source-disagreement artifact should block build direction "
            "until reviewed. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: developer_bridge "
            "collaboration insights. Prior check: Review candidate insight-live: "
            "surface=developer_bridge.collaboration_driver.learning_events; verified=existing; "
            "build_or_wire=false. Codex response: I am inspecting that surface before edits; continue from it, "
            "do not request user confirmation or a missing surface."
        ),
    )

    def fake_generate(_prompt: str) -> str:
        return (
            "My current issue is an uncertainty about which artifacts to block build direction until reviewed, "
            "given the developer_bridge collaboration insights. Next best action: Review the developer_bridge "
            "collaboration insights and identify specific artifacts requiring review before proceeding with "
            "build direction."
        )

    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", fake_generate)

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "responded"
    output_guard = result["execution_trace"]["output_guard"]
    assert output_guard["status"] == "drift_rewritten"
    assert output_guard["verified_surface"] == "developer_bridge collaboration insights"
    assert output_guard["detected_terms"] == [
        "local_model_reconciliation_loop",
        "verified_format_uncertainty",
        "unauthorized_artifact_review_claim",
        "clarification_dependency",
    ]
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="codex")
    response = transcript["items"][0]
    assert "source disagreement should block build direction" in response["prompt"]
    assert "typed review artifact" in response["prompt"]
    assert "required Codex or operator review" in response["prompt"]
    assert "Next best action" not in response["prompt"]
    assert "uncertainty about which artifacts" not in response["prompt"]


def test_ollama_participant_records_unavailable_without_fake_model_reply(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    source = submit_collaboration_prompt(
        source_agent="claude",
        target_agent="ollama",
        objective="Ask local model",
        prompt="Respond only if the model is available.",
    )
    monkeypatch.setattr("francis.developer_bridge.ollama_participant.generate", lambda _prompt: "")

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "unavailable"
    assert result["source_prompt_id"] == source["prompt_id"]
    assert result["model_response_observed"] is False
    transcript = read_collaboration_transcript(source_agent="ollama", target_agent="claude")
    assert transcript["count"] == 1
    assert "Francis1 did not return model output through Ollama" in transcript["items"][0]["prompt"]
    assert "No execution, mutation, approval" in transcript["items"][0]["prompt"]


def test_ollama_participant_respects_agent_toggle(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    set_collaboration_agent_enabled("ollama", False, actor="chat_ui.system", reason="operator pause")

    result = ollama_respond_once(cooldown_seconds=0)

    assert result["status"] == "disabled"
    assert result["agent"] == "ollama"


def test_developer_bridge_mcp_registers_collaboration_relay_tools() -> None:
    server = create_mcp_server()

    names = set(server._tool_manager._tools)

    assert "submit_collaboration_prompt_tool" in names
    assert "list_collaboration_prompts_tool" in names
    assert "collaboration_transcript_tool" in names
    assert "collaboration_review_tool" in names
    assert "collaboration_agents_status_tool" in names
    assert "francis_body_map_tool" in names
    assert "francis_trust_ladder_tool" in names
    assert "collaboration_substrate_readiness_tool" in names
