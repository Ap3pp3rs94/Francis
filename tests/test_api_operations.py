from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path

_PLUGIN_ACTOR = "test.plugins.write"


def _forge_promotion_meta(label: str) -> dict[str, object]:
    return {
        "friction_summary": f"Repeated {label} operation plugin review",
        "proposal_evidence": [f"mission.operations.{label}"],
        "tests": [f"tests/test_api_operations.py::{label}"],
        "docs": ["README.md"],
        "risk_tier": "normal",
    }


def _approve_forge_proposal(client, proposal_id: str) -> None:
    approved = client.post(
        "/forge/proposals/decision",
        json={
            "id": proposal_id,
            "action": "approve",
            "actor": _PLUGIN_ACTOR,
            "reason": "test proposal approval",
        },
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True
    assert approved_body["status"] == "approved"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def test_operations_create_list_get_cancel(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "api_operations_test",
            "input": {"goal": "verify operations API"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    assert any(str(item.get("id")) == operation_id for item in listed_body["items"])

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id

    cancelled = client.post(f"/operations/{operation_id}/cancel", json={"reason": "test_cancel"})
    assert cancelled.status_code == 200
    cancelled_body = cancelled.json()
    assert "status" in cancelled_body
    assert cancelled_body["status"] in {"queued", "running", "failed", "canceled", "succeeded", "unknown"}


def test_operations_readback_derives_stage17_invocation_caller_context(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Read back Stage 17 invocation caller context.",
            "summary": "The operation readback should derive mission caller context without execution authority.",
            "requester_id": "test.missions.trace",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    def create_operation(payload: dict[str, object]) -> str:
        created = client.post("/operations/create", json=payload)
        assert created.status_code == 200
        created_body = created.json()
        assert created_body["ok"] is True
        return str(created_body["operation_id"])

    def read_context(operation_id: str) -> dict[str, object]:
        fetched = client.get(f"/operations/{operation_id}")
        assert fetched.status_code == 200
        context = fetched.json()["operation"]["meta"].get("invocation_caller_context")
        assert isinstance(context, dict)
        return context

    plugin_operation_id = create_operation(
        {
            "action": "plugin.run",
            "reason": "mission plugin caller-context readback",
            "mission_id": mission_id,
            "input": {"id": "stage17.readback.plugin", "action": "run"},
        }
    )
    plugin_context = read_context(plugin_operation_id)
    assert plugin_context["contract"] == "stage17_operation_invocation_caller_context_readback_v1"
    assert plugin_context["status"] == "derived"
    assert plugin_context["readback_scope"] == "operation_readback_metadata"
    assert plugin_context["source"] == "operation_capability_and_mission_linkage"
    assert plugin_context["operation_capability"] == "plugin.run"
    assert plugin_context["mission_linked"] is True
    assert plugin_context["derived"] is True
    assert plugin_context["derived_caller_context"] == "mission_linked_operation"
    assert plugin_context["expected_caller_context"] == "mission_linked_operation"
    assert plugin_context["input_caller_context_present"] is False
    assert plugin_context["input_caller_context_matches_derived"] is None
    assert plugin_context["eligible_for_invocation_audit_after_execution"] is True
    assert plugin_context["reject_reasons"] == []
    assert plugin_context["receipt_backing"]["source_kind"] == "delegation_task_record"
    assert plugin_context["receipt_backing"]["operation_record_present"] is True
    assert plugin_context["receipt_backing"]["actual_invocation_receipt_read"] is False
    assert plugin_context["receipt_backing"]["actual_invocation_receipt_required_for_execution_audit"] is True
    assert plugin_context["receipt_backing"]["writes_receipts"] is False
    assert plugin_context["governance"]["read_only"] is True
    assert plugin_context["governance"]["writes_data"] is False
    assert plugin_context["governance"]["executes_capabilities"] is False
    assert plugin_context["governance"]["grants_execution_authority"] is False
    assert plugin_context["governance"]["memory_write"] is False

    def assert_surface_carries_plugin_context(operation: dict[str, object]) -> None:
        meta = operation.get("meta")
        assert isinstance(meta, dict)
        context = meta.get("invocation_caller_context")
        assert context == plugin_context
        assert context["governance"]["read_only"] is True
        assert context["governance"]["writes_data"] is False
        assert context["governance"]["executes_capabilities"] is False
        assert context["governance"]["grants_execution_authority"] is False
        assert context["governance"]["memory_write"] is False

    listed = client.get("/operations/list", params={"mission_id": mission_id})
    assert listed.status_code == 200
    listed_operation = next(item for item in listed.json()["items"] if item["id"] == plugin_operation_id)
    assert_surface_carries_plugin_context(listed_operation)

    searched = client.get("/operations/list", params={"search": "mission plugin caller-context readback"})
    assert searched.status_code == 200
    searched_operation = next(item for item in searched.json()["items"] if item["id"] == plugin_operation_id)
    assert_surface_carries_plugin_context(searched_operation)

    exported_json = client.get("/operations/export", params={"format": "json", "mission_id": mission_id})
    assert exported_json.status_code == 200
    exported_operation = next(item for item in exported_json.json()["items"] if item["id"] == plugin_operation_id)
    assert_surface_carries_plugin_context(exported_operation)

    exported_jsonl = client.get("/operations/export", params={"format": "jsonl", "mission_id": mission_id})
    assert exported_jsonl.status_code == 200
    exported_jsonl_items = [json.loads(line) for line in exported_jsonl.text.splitlines() if line.strip()]
    exported_jsonl_operation = next(item for item in exported_jsonl_items if item["id"] == plugin_operation_id)
    assert_surface_carries_plugin_context(exported_jsonl_operation)

    tool_operation_id = create_operation(
        {
            "action": "tool.run",
            "reason": "mission tool caller-context readback",
            "mission_id": mission_id,
            "input": {"id": "stage17.readback.tool"},
        }
    )
    tool_context = read_context(tool_operation_id)
    assert tool_context["status"] == "derived"
    assert tool_context["operation_capability"] == "plugin.tool.run"
    assert tool_context["derived_caller_context"] == "mission_linked_tool_operation"
    assert tool_context["expected_caller_context"] == "mission_linked_tool_operation"
    assert tool_context["eligible_for_invocation_audit_after_execution"] is True
    assert tool_context["reject_reasons"] == []

    non_mission_operation_id = create_operation(
        {
            "action": "plugin.run",
            "reason": "non-mission plugin caller-context readback",
            "input": {"id": "stage17.readback.plugin", "action": "run"},
        }
    )
    non_mission_context = read_context(non_mission_operation_id)
    assert non_mission_context["status"] == "not_applicable"
    assert non_mission_context["operation_capability"] == "plugin.run"
    assert non_mission_context["mission_linked"] is False
    assert non_mission_context["derived"] is False
    assert non_mission_context["derived_caller_context"] is None
    assert non_mission_context["expected_caller_context"] == "mission_linked_operation"
    assert non_mission_context["eligible_for_invocation_audit_after_execution"] is False
    assert non_mission_context["reject_reasons"] == ["mission_linkage_missing"]

    unsupported_operation_id = create_operation(
        {
            "action": "plan.create",
            "reason": "unsupported mission caller-context readback",
            "mission_id": mission_id,
            "input": {"goal": "prove unsupported shape does not claim invocation context"},
        }
    )
    unsupported_context = read_context(unsupported_operation_id)
    assert unsupported_context["status"] == "not_applicable"
    assert unsupported_context["operation_capability"] == "plan.create"
    assert unsupported_context["mission_linked"] is True
    assert unsupported_context["derived"] is False
    assert unsupported_context["expected_caller_context"] is None
    assert unsupported_context["eligible_for_invocation_audit_after_execution"] is False
    assert unsupported_context["reject_reasons"] == ["unsupported_operation_capability"]

    mismatch_operation_id = create_operation(
        {
            "action": "tool.run",
            "reason": "mismatched caller-context readback",
            "mission_id": mission_id,
            "input": {"id": "stage17.readback.tool"},
            "meta": {"caller_context": "mission_linked_operation"},
        }
    )
    mismatch_context = read_context(mismatch_operation_id)
    assert mismatch_context["status"] == "mismatch"
    assert mismatch_context["operation_capability"] == "plugin.tool.run"
    assert mismatch_context["mission_linked"] is True
    assert mismatch_context["derived"] is True
    assert mismatch_context["derived_caller_context"] == "mission_linked_tool_operation"
    assert mismatch_context["input_caller_context_present"] is True
    assert mismatch_context["input_caller_context"] == "mission_linked_operation"
    assert mismatch_context["input_caller_context_matches_derived"] is False
    assert mismatch_context["eligible_for_invocation_audit_after_execution"] is False
    assert mismatch_context["reject_reasons"] == ["input_caller_context_mismatch"]
    assert mismatch_context["governance"]["read_only"] is True
    assert mismatch_context["governance"]["writes_receipts"] is False
    assert mismatch_context["governance"]["changes_operation_input"] is False


def test_operations_create_reuses_existing_operation_for_matching_idempotency_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    first = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "idempotent operation create",
            "actor": "test.operations.write",
            "idempotency_key": "idem-stage8-lease-review",
            "input": {"goal": "dedupe this operation"},
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["ok"] is True
    operation_id = str(first_body["operation_id"])
    assert operation_id

    second = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "idempotent operation create duplicate",
            "actor": "test.operations.write",
            "idempotency_key": "idem-stage8-lease-review",
            "input": {"goal": "dedupe this operation"},
        },
    )

    assert second.status_code == 200
    second_body = second.json()
    assert second_body["ok"] is True
    assert second_body["operation_id"] == operation_id
    assert second_body["idempotent_reuse"] is True
    assert second_body["duplicate_create_blocked"] is True
    assert second_body["message"] == "idempotent_reuse"
    assert second_body["operation"]["id"] == operation_id
    assert second_body["operation"]["input"]["idempotency_key"] == "idem-stage8-lease-review"
    assert len([path for path in (data_root / "tasks").iterdir() if path.is_dir()]) == 1

    audit_log = data_root / "tasks" / operation_id / "audit.log"
    audit_lines = [json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines()]
    reuse_events = [line for line in audit_lines if line["event"] == "idempotency_reused"]
    assert len(reuse_events) == 1
    assert reuse_events[0]["details"]["idempotency_key"] == "idem-stage8-lease-review"
    assert reuse_events[0]["details"]["duplicate_create_blocked"] is True


def test_operations_operator_surfaces_redact_secret_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "operator reason password=operationreasonsecret123",
            "input": {"goal": "draft plan token=operationinputsecret123"},
            "meta": {"ticket": "OPS-1", "operator_note": "secret=operationmetasecret123"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])
    assert created_body["operation"]["meta"]["objective"] == "operator reason password=[REDACTED:secret]"
    assert created_body["operation"]["input"]["goal"] == "draft plan token=[REDACTED:secret]"
    assert created_body["operation"]["input"]["meta"]["operator_note"] == "secret=[REDACTED:secret]"
    assert created_body["operation"]["input"]["meta"]["ticket"] == "OPS-1"

    patched = client.patch(
        f"/operations/{operation_id}",
        json={
            "note": "patch note token=operationpatchnotesecret123",
            "meta": {"operator_note": "password=operationpatchmetasecret123"},
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is True

    fetched = client.get(f"/operations/{operation_id}")
    listed = client.get("/operations/list")
    many = client.post("/operations/get_many", json={"ids": [operation_id]})
    exported = client.get("/operations/export?format=json")
    assert fetched.status_code == 200
    assert listed.status_code == 200
    assert many.status_code == 200
    assert exported.status_code == 200

    fetched_body = fetched.json()
    assert fetched_body["meta"]["task"]["objective"] == "operator reason password=[REDACTED:secret]"
    assert fetched_body["meta"]["task"]["inputs"]["goal"] == "draft plan token=[REDACTED:secret]"
    assert fetched_body["meta"]["task"]["meta"]["note"] == "patch note token=[REDACTED:secret]"
    assert fetched_body["meta"]["task"]["meta"]["operator_note"] == "password=[REDACTED:secret]"

    cancelled = client.post(
        f"/operations/{operation_id}/cancel",
        json={"reason": "cancel reason secret=operationcancelsecret123"},
    )
    assert cancelled.status_code == 200

    combined_response_text = "\n".join(
        [
            json.dumps(created_body, sort_keys=True),
            json.dumps(patched_body, sort_keys=True),
            json.dumps(fetched_body, sort_keys=True),
            json.dumps(listed.json(), sort_keys=True),
            json.dumps(many.json(), sort_keys=True),
            exported.text,
            json.dumps(cancelled.json(), sort_keys=True),
        ]
    )
    for raw in (
        "operationreasonsecret123",
        "operationinputsecret123",
        "operationmetasecret123",
        "operationpatchnotesecret123",
        "operationpatchmetasecret123",
        "operationcancelsecret123",
    ):
        assert raw not in combined_response_text

    record_text = (data_root / "tasks" / operation_id / "record.json").read_text(encoding="utf-8")
    audit_text = (data_root / "tasks" / operation_id / "audit.log").read_text(encoding="utf-8")
    assert "operationreasonsecret123" not in record_text
    assert "operationmetasecret123" not in record_text
    assert "operationpatchnotesecret123" not in record_text
    assert "operationpatchmetasecret123" not in record_text
    assert "operationcancelsecret123" not in record_text
    assert "operationcancelsecret123" not in audit_text
    assert "operationinputsecret123" in record_text


def test_operations_run_executes_plan_create(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "run_now", "input": {"goal": "run immediately"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] in {"succeeded", "failed"}
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["kind"] == "plan.create.result"
    assert output["plan_status"] == "in_progress"
    assert output["plan_current_step_id"] == "understand"
    assert output["plan_current_step_title"] == "Understand goal + constraints"
    assert output["plan_step_count"] == 4
    assert output["plan_checkpoint_count"] == 3
    assert output["plan"]["status"] == "in_progress"
    trace_id = str(output.get("trace_id") or "")
    run_id = str(output.get("run_id") or "")
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")
    assert run_body["operation"]["trace_id"] == trace_id
    assert run_body["operation"]["run_id"] == run_id

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id
    assert fetched_body["operation"]["status"] in {"succeeded", "failed"}
    assert fetched_body["operation"]["trace_id"] == trace_id
    assert fetched_body["operation"]["run_id"] == run_id
    final_status_log = next(
        item
        for item in fetched_body["logs"]
        if item["kind"] == "audit_event" and item["name"] == "status_updated" and item["status"] == "succeeded"
    )
    assert final_status_log["trace_id"] == trace_id
    assert final_status_log["run_id"] == run_id
    assert final_status_log["output"]["trace_id"] == trace_id
    assert final_status_log["output"]["run_id"] == run_id

    listed_by_trace = client.get("/operations/list", params={"trace_id": trace_id})
    assert listed_by_trace.status_code == 200
    assert [item["id"] for item in listed_by_trace.json()["items"]] == [operation_id]


def test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    sent = client.post(
        "/chat/send",
        json={
            "message": "hey Francis paint the Mona Lisa in sandbox",
            "use_llm": False,
            "actor": "test.chat.write",
            "voice_turn_id": "voice_turn_mona_sandbox_operator",
        },
    )
    assert sent.status_code == 200
    mission_body = sent.json()
    mission_id = str(mission_body["mission_id"])
    plan_operation_id = str(mission_body["operation_id"])
    operation_id = str(mission_body["sandbox_operation_id"])
    assert operation_id.startswith("tsk_")
    assert operation_id != plan_operation_id
    assert mission_body["sandbox_operation_queued"] is True
    assert mission_body["mission"]["linked_task_ids"] == [plan_operation_id, operation_id]
    assert mission_body["queue_item"]["action_target_id"] == operation_id
    assert mission_body["sandbox_operation"]["name"] == "sandbox.canvas.paint_mona_lisa"
    assert mission_body["sandbox_operation"]["input"]["mission_id"] == mission_id
    assert mission_body["sandbox_operation"]["input"]["plan_operation_id"] == plan_operation_id
    assert mission_body["sandbox_operation"]["input"]["canvas"] == {"width": 512, "height": 512}

    run_now = client.post(
        f"/operations/{operation_id}/run",
        json={"worker_id": "test.operations.sandbox_canvas", "actor": "api.operations"},
    )
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["ok"] is True
    assert run_body["status"] == "succeeded"
    operation = run_body["operation"]
    output = operation["output"]
    assert output["kind"] == "sandbox.canvas.paint_mona_lisa.result"
    assert output["status"] == "sandbox_completed"
    assert output["execution_mode"] == "sandbox"
    assert output["live_desktop_execution"] is False
    assert output["no_pasted_image"] is True
    assert output["imports_finished_image"] is False
    assert output["created_through_operator_primitives"] is True
    assert output["operator_primitives_count"] >= 12
    assert output["verification"]["status"] == "passed"
    assert output["governance"]["sandbox_only"] is True
    assert output["governance"]["desktop_control"] is False
    assert operation["trace_id"] == output["trace_id"]
    assert operation["run_id"] == output["run_id"]
    assert operation["artifact_dir"] == output["artifact_dir"]

    artifact_dir = Path(output["artifact_dir"])
    assert artifact_dir.exists()
    assert data_root.resolve() in artifact_dir.resolve().parents
    svg_path = Path(output["artifact_path"])
    actions_path = Path(output["actions_path"])
    manifest_path = Path(output["manifest_path"])
    receipt_path = Path(output["receipt_path"])
    for path in (svg_path, actions_path, manifest_path, receipt_path):
        assert path.exists()
        assert artifact_dir.resolve() in path.resolve().parents

    svg_text = svg_path.read_text(encoding="utf-8")
    assert "<image" not in svg_text
    assert svg_text.count("<path") >= 8

    action_lines = [json.loads(line) for line in actions_path.read_text(encoding="utf-8").splitlines()]
    assert len(action_lines) == output["operator_primitives_count"]
    assert all(line["kind"] == "sandbox.canvas.operator_primitive" for line in action_lines)
    assert all(line["live_desktop_action"] is False for line in action_lines)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "francis.sandbox_canvas.mona_lisa.receipt"
    assert receipt["mission_id"] == mission_id
    assert receipt["status"] == "sandbox_completed"
    assert receipt["created_through_operator_primitives"] is True
    assert receipt["lens_overlay_observation"]["actual_inspected_region"]["width"] == 512
    structured_receipt = receipt["structured_observation_receipts"][0]
    assert structured_receipt == receipt["lens_overlay_observation"]["structured_observation_receipt"]
    assert output["structured_observation_receipts"] == [structured_receipt]
    assert structured_receipt["kind"] == "francis.lens.overlay.structured_observation_receipt"
    assert structured_receipt["status"] == "observed"
    assert structured_receipt["source"]["name"] == "sandbox_canvas_coordinate_model"
    assert structured_receipt["source"]["live_simulated_fixture_or_replay"] == "sandbox"
    assert structured_receipt["requested_region"] == receipt["lens_overlay_observation"]["requested_region"]
    assert structured_receipt["mapped_overlay_region"] == receipt["lens_overlay_observation"]["mapped_overlay_region"]
    assert structured_receipt["actual_inspected_region"]["width"] == 512
    assert structured_receipt["evidence_reference"]["manifest_ref"] == str(manifest_path)
    assert structured_receipt["evidence_reference"]["manifest_hash"] == output["manifest_hash"]
    assert structured_receipt["evidence_reference"]["actions_hash"] == output["actions_hash"]
    assert structured_receipt["evidence_reference"]["artifact_hash"] == output["artifact_hash"]
    assert structured_receipt["inferred_information"]["primitive_count"] == output["operator_primitives_count"]
    assert "desktop_pixels" in structured_receipt["unknowns"]
    assert structured_receipt["failure_or_refusal_reason"] == ""
    assert structured_receipt["governance"]["desktop_control"] is False
    assert receipt["orb_embodiment"]["visual_change"] is False
    assert receipt["orb_embodiment"]["visual_lock_preserved"] is True
    assert receipt["claim_completed_painting"] is True
    assert receipt["governance"]["live_desktop_authority"] is False

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["artifact_dir"] == output["artifact_dir"]
    assert fetched_body["operation"]["meta"]["mission_id"] == mission_id
    assert fetched_body["memory_receipt_count"] >= 1

    evaluation = client.get(
        "/operations/sandbox-canvas/mona-lisa/evaluation",
        params={"operation_id": operation_id},
    )
    assert evaluation.status_code == 200
    evaluation_body = evaluation.json()
    assert evaluation_body["kind"] == "francis.sandbox_canvas.mona_lisa.evaluation"
    assert evaluation_body["ok"] is True
    assert evaluation_body["status"] == "evaluated"
    assert evaluation_body["evaluation_mode"] == "read_only_replay"
    assert evaluation_body["operation_id"] == operation_id
    assert evaluation_body["mission_id"] == mission_id
    assert evaluation_body["artifact_dir"] == output["artifact_dir"]
    assert evaluation_body["passed"] is True
    assert evaluation_body["created_through_operator_primitives"] is True
    assert evaluation_body["operator_primitives_count"] == output["operator_primitives_count"]
    assert evaluation_body["checks"]["primitive_count_matches_receipt"] is True
    assert evaluation_body["checks"]["primitive_sequence_contiguous"] is True
    assert evaluation_body["checks"]["no_live_desktop_actions"] is True
    assert evaluation_body["checks"]["svg_has_no_image_import"] is True
    assert evaluation_body["hashes"]["artifact"]["matches"] is True
    assert evaluation_body["hashes"]["actions"]["matches"] is True
    assert evaluation_body["hashes"]["manifest"]["matches"] is True
    assert evaluation_body["checks"]["structured_observation_receipt_present"] is True
    assert evaluation_body["checks"]["structured_observation_evidence_references_manifest"] is True
    assert evaluation_body["checks"]["structured_observation_unknowns_live_desktop_pixels"] is True
    assert evaluation_body["checks"]["recognizability_offline_fixture_evidence_present"] is True
    assert evaluation_body["checks"]["recognizability_offline_fixture_no_pixel_claim"] is True
    assert evaluation_body["checks"]["recognizability_offline_fixture_no_visual_similarity_claim"] is True
    assert evaluation_body["structured_observation_receipts"] == [structured_receipt]
    assert (
        evaluation_body["recognizability"]["basis"]
        == "operator_primitive_replay_plus_offline_svg_geometry_fixture_not_pixel_similarity"
    )
    fixture_evidence = evaluation_body["recognizability"]["offline_fixture_evidence"]
    assert fixture_evidence["status"] == "evaluated"
    assert fixture_evidence["evidence_mode"] == "offline_svg_geometry"
    assert fixture_evidence["fixture_kind"] == "francis.sandbox_canvas.mona_lisa.recognizability_fixture"
    assert fixture_evidence["passed"] is True
    assert fixture_evidence["pixel_evidence"] is False
    assert fixture_evidence["visual_similarity_claim"] is False
    assert fixture_evidence["reference_image_used"] is False
    assert fixture_evidence["zone_count"] >= fixture_evidence["required_zone_count"]
    assert fixture_evidence["feature_count"] >= fixture_evidence["required_feature_count"]
    assert evaluation_body["recognizability"]["score"] >= 0.85
    assert evaluation_body["recognizability"]["recognizable_lower_complexity_target"] is True
    assert evaluation_body["governance"]["read_only"] is True
    assert evaluation_body["governance"]["writes_files"] is False
    assert evaluation_body["governance"]["runs_operation"] is False
    assert evaluation_body["governance"]["desktop_control"] is False
    assert evaluation_body["governance"]["visual_similarity_claim"] is False
    assert evaluation_body["governance"]["live_desktop_perception_claim"] is False
    assert evaluation_body["improvement_proposals"]
    assert all(item["status"] == "proposed_not_promoted" for item in evaluation_body["improvement_proposals"])

    recorded = client.post(
        "/operations/sandbox-canvas/mona-lisa/evaluation/record",
        json={
            "operation_id": operation_id,
            "actor": "test.operations.write",
            "reason": "test_record_mona_lisa_sandbox_evaluation",
            "meta": {"test": "mona_lisa_sandbox_vertical_slice"},
        },
    )
    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["kind"] == "francis.sandbox_canvas.mona_lisa.evaluation_record.result"
    assert recorded_body["ok"] is True
    assert recorded_body["status"] == "recorded"
    assert recorded_body["operation_id"] == operation_id
    assert recorded_body["mission_id"] == mission_id
    assert recorded_body["artifact_dir"] == output["artifact_dir"]
    assert recorded_body["queue_item"]["status"] == "queued_for_review"
    assert recorded_body["queue_item"]["failure_classification"] == []
    assert recorded_body["queue_item"]["improvement_proposal_count"] == len(evaluation_body["improvement_proposals"])
    assert recorded_body["governance"]["writes_files"] is True
    assert recorded_body["governance"]["writes_evaluation_record"] is True
    assert recorded_body["governance"]["writes_queue_item"] is True
    assert recorded_body["governance"]["writes_proposal_records"] is True
    assert recorded_body["governance"]["runs_operation"] is False
    assert recorded_body["governance"]["desktop_control"] is False
    assert recorded_body["governance"]["approves_proposals"] is False
    assert recorded_body["governance"]["promotes_changes"] is False
    assert recorded_body["governance"]["visual_similarity_claim"] is False
    assert recorded_body["governance"]["live_desktop_perception_claim"] is False

    record_path = Path(recorded_body["paths"]["evaluation_record"])
    queue_path = Path(recorded_body["paths"]["queue_item"])
    proposal_paths = [Path(path) for path in recorded_body["paths"]["improvement_proposals"]]
    assert record_path.exists()
    assert queue_path.exists()
    assert proposal_paths
    assert all(path.exists() for path in proposal_paths)
    assert artifact_dir.resolve() in record_path.resolve().parents
    assert artifact_dir.resolve() in queue_path.resolve().parents
    assert all(artifact_dir.resolve() in path.resolve().parents for path in proposal_paths)

    stored_record = json.loads(record_path.read_text(encoding="utf-8"))
    assert stored_record["evaluation"]["status"] == "evaluated"
    assert stored_record["evaluation"]["governance"]["read_only"] is True
    assert stored_record["evaluation"]["structured_observation_receipts"] == [structured_receipt]
    assert stored_record["queue_item"]["queue_item_id"] == recorded_body["queue_item_id"]
    assert all(item["promotion"]["promoted"] is False for item in stored_record["improvement_proposals"])

    queue_list = client.get("/operations/sandbox-canvas/mona-lisa/evaluation-queue")
    assert queue_list.status_code == 200
    queue_body = queue_list.json()
    assert queue_body["kind"] == "francis.sandbox_canvas.mona_lisa.evaluation_queue"
    assert queue_body["ok"] is True
    assert queue_body["governance"]["read_only"] is True
    assert queue_body["governance"]["writes_files"] is False
    assert any(item["queue_item_id"] == recorded_body["queue_item_id"] for item in queue_body["items"])
    review_scoring = queue_body["review_scoring"]
    assert review_scoring["kind"] == "francis.sandbox_canvas.mona_lisa.evaluation_review_scoring"
    assert review_scoring["classification"] == "passed_with_proposals"
    assert review_scoring["total_records"] == 1
    assert review_scoring["passed_count"] == 1
    assert review_scoring["failed_count"] == 0
    assert review_scoring["repeated_failure_classes"] == []
    assert review_scoring["governance"]["promotes_changes"] is False

    for index in range(2):
        repeated_failure_item = {
            **recorded_body["queue_item"],
            "queue_item_id": f"queue_repeated_failure_{index}",
            "evaluation_id": f"eval_repeated_failure_{index}",
            "created_at": f"2099-01-01T00:00:0{index}Z",
            "passed": False,
            "failure_classification": ["recognizability_threshold_not_met"],
            "improvement_proposal_count": 1,
        }
        (queue_path.parent / f"{repeated_failure_item['queue_item_id']}.json").write_text(
            json.dumps(repeated_failure_item, indent=2),
            encoding="utf-8",
        )

    repeated_queue = client.get("/operations/sandbox-canvas/mona-lisa/evaluation-queue")
    repeated_body = repeated_queue.json()
    repeated_scoring = repeated_body["review_scoring"]
    assert repeated_scoring["classification"] == "repeated_failure_pattern"
    assert repeated_scoring["failed_count"] == 2
    assert repeated_scoring["failure_class_counts"] == {"recognizability_threshold_not_met": 2}
    assert repeated_scoring["repeated_failure_classes"] == [
        {"failure_class": "recognizability_threshold_not_met", "count": 2}
    ]
    assert repeated_scoring["next_recommended_action"] == "review_repeated_failures_before_new_proposals"
    assert repeated_scoring["governance"]["writes_files"] is False
    assert repeated_scoring["governance"]["promotes_changes"] is False

    proposal_list = client.get(
        "/operations/sandbox-canvas/mona-lisa/improvement-proposals",
        params={"status": "proposed_not_promoted"},
    )
    assert proposal_list.status_code == 200
    proposal_body = proposal_list.json()
    assert proposal_body["kind"] == "francis.sandbox_canvas.mona_lisa.improvement_proposals"
    assert proposal_body["ok"] is True
    assert proposal_body["governance"]["read_only"] is True
    assert proposal_body["governance"]["promotes_changes"] is False
    proposal_ids = {item["proposal_record_id"] for item in proposal_body["items"]}
    assert {item["proposal_record_id"] for item in recorded_body["improvement_proposals"]}.issubset(proposal_ids)
    assert all(item["status"] == "proposed_not_promoted" for item in proposal_body["items"])
    assert all(item["promotion"]["promoted"] is False for item in proposal_body["items"])

    missing = client.get(
        "/operations/sandbox-canvas/mona-lisa/evaluation",
        params={"artifact_dir": str(data_root / "sandbox_canvas" / "mona_lisa" / "missing")},
    )
    assert missing.status_code == 200
    missing_body = missing.json()
    assert missing_body["ok"] is False
    assert missing_body["status"] == "blocked"
    assert missing_body["governance"]["read_only"] is True

    outside_artifact = tmp_path / "outside_sandbox_artifact"
    outside_artifact.mkdir()
    (outside_artifact / "receipt.json").write_text("{}", encoding="utf-8")
    outside = client.get(
        "/operations/sandbox-canvas/mona-lisa/evaluation",
        params={"artifact_dir": str(outside_artifact)},
    )
    assert outside.status_code == 200
    outside_body = outside.json()
    assert outside_body["ok"] is False
    assert outside_body["status"] == "blocked"
    assert outside_body["error"] == "sandbox_artifact_dir_not_found_or_out_of_bounds"

    invalid_run = client.get(
        "/operations/sandbox-canvas/mona-lisa/evaluation",
        params={"run_id": "../outside"},
    )
    assert invalid_run.status_code == 200
    invalid_run_body = invalid_run.json()
    assert invalid_run_body["ok"] is False
    assert invalid_run_body["status"] == "blocked"
    assert invalid_run_body["error"] == "invalid_run_id"

    invalid_record = client.post(
        "/operations/sandbox-canvas/mona-lisa/evaluation/record",
        json={
            "run_id": "../outside",
            "actor": "test.operations.write",
            "reason": "test_invalid_run_id_block",
        },
    )
    assert invalid_record.status_code == 200
    invalid_record_body = invalid_record.json()
    assert invalid_record_body["ok"] is False
    assert invalid_record_body["status"] == "blocked"
    assert invalid_record_body["error"] == "invalid_run_id"
    assert invalid_record_body["governance"]["writes_files"] is False


def test_operations_create_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    set_control_mode("observe", reason="test_observe_create_block", actor="tests")

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "observe_block", "input": {"goal": "should not queue"}},
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is False
    assert created_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in created_body["error"]

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["items"] == []


def test_operations_create_denies_unscoped_actor_before_mutation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "permission_gate_create",
            "actor": "test.operations.write",
            "input": {"goal": "do not create without scoped actor"},
        },
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1

    task_root = data_root / "tasks"
    assert not task_root.exists() or not any(task_root.iterdir())


def test_operations_run_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "observe_block", "input": {"goal": "stay queued in observe"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    set_control_mode("observe", reason="test_observe_block", actor="tests")

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["ok"] is False
    assert run_body["status"] == "queued"
    assert "Observe mode keeps execution read-only." in run_body["message"]

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["status"] == "queued"


def test_operations_run_denies_unscoped_actor_before_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "permission_gate_run",
            "input": {"goal": "do not execute without scoped actor"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    denied = client.post(
        f"/operations/{operation_id}/run",
        json={"worker_id": "test.operations.permission_gate", "actor": "test.operations.run"},
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["status"] == "queued"
    assert fetched_body["operation"].get("output") is None


def test_operations_lifecycle_mutations_are_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    operation_ids: list[str] = []
    for label in ("patch", "cancel", "delete"):
        created = client.post(
            "/operations/create",
            json={"action": "plan.create", "reason": f"observe_{label}", "input": {"goal": label}},
        )
        assert created.status_code == 200
        operation_ids.append(str(created.json()["operation_id"]))

    patch_operation_id, cancel_operation_id, delete_operation_id = operation_ids

    set_control_mode("observe", reason="test_observe_lifecycle_block", actor="tests")

    patched = client.patch(
        f"/operations/{patch_operation_id}",
        json={
            "tags": ["observe-mutated"],
            "meta": {"operator_note": "should not persist"},
            "note": "observe patch should not persist",
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is False
    assert patched_body["status"] == "queued"
    assert patched_body["operation"]["id"] == patch_operation_id
    assert "Observe mode keeps Francis read-only." in patched_body["message"]

    cancelled = client.post(f"/operations/{cancel_operation_id}/cancel", json={"reason": "observe_cancel"})
    assert cancelled.status_code == 200
    cancelled_body = cancelled.json()
    assert cancelled_body["ok"] is False
    assert cancelled_body["status"] == "queued"
    assert cancelled_body["operation"]["id"] == cancel_operation_id
    assert "Observe mode keeps Francis read-only." in cancelled_body["message"]

    deleted = client.request("DELETE", f"/operations/{delete_operation_id}", json={"reason": "observe_delete"})
    assert deleted.status_code == 200
    deleted_body = deleted.json()
    assert deleted_body["ok"] is False
    assert deleted_body["status"] == "queued"
    assert deleted_body["operation"]["id"] == delete_operation_id
    assert "Observe mode keeps Francis read-only." in deleted_body["message"]

    patch_record = json.loads((data_root / "tasks" / patch_operation_id / "record.json").read_text(encoding="utf-8"))
    assert patch_record.get("tags") is None
    assert "observe patch should not persist" not in json.dumps(patch_record, sort_keys=True)
    assert "should not persist" not in json.dumps(patch_record, sort_keys=True)

    for operation_id in (patch_operation_id, cancel_operation_id, delete_operation_id):
        fetched = client.get(f"/operations/{operation_id}")
        assert fetched.status_code == 200
        assert fetched.json()["operation"]["status"] == "queued"


def test_operations_lifecycle_mutations_deny_unscoped_actor_before_mutation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    operation_ids: list[str] = []
    for label in ("patch", "cancel", "delete"):
        created = client.post(
            "/operations/create",
            json={"action": "plan.create", "reason": f"permission_{label}", "input": {"goal": label}},
        )
        assert created.status_code == 200
        operation_ids.append(str(created.json()["operation_id"]))

    patch_operation_id, cancel_operation_id, delete_operation_id = operation_ids
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    patched = client.patch(
        f"/operations/{patch_operation_id}",
        json={
            "tags": ["permission-mutated"],
            "meta": {"operator_note": "should not persist"},
            "note": "permission patch should not persist",
            "actor": "test.operations.write",
        },
    )
    cancelled = client.post(
        f"/operations/{cancel_operation_id}/cancel",
        json={"reason": "permission_cancel", "actor": "test.operations.write"},
    )
    deleted = client.request(
        "DELETE",
        f"/operations/{delete_operation_id}",
        json={"reason": "permission_delete", "actor": "test.operations.write"},
    )

    for response in (patched, cancelled, deleted):
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["status"] == "denied"
        assert body["error"] == "api_permission_denied"
        assert body["governance"]["gate"] == "permission_gate"
        assert body["governance"]["reason"] == "missing_scopes"
        assert body["governance"]["evidence"]["actor_present"] is True
        assert body["governance"]["evidence"]["required_scope_count"] == 1

    patch_record = json.loads((data_root / "tasks" / patch_operation_id / "record.json").read_text(encoding="utf-8"))
    assert patch_record.get("tags") is None
    assert "permission patch should not persist" not in json.dumps(patch_record, sort_keys=True)
    assert "should not persist" not in json.dumps(patch_record, sort_keys=True)

    for operation_id in (patch_operation_id, cancel_operation_id, delete_operation_id):
        fetched = client.get(f"/operations/{operation_id}")
        assert fetched.status_code == 200
        assert fetched.json()["operation"]["status"] == "queued"


def test_operations_lifecycle_observe_block_does_not_fabricate_missing_operations(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())
    set_control_mode("observe", reason="test_observe_missing_operation_block", actor="tests")

    requests = [
        (
            "tsk_missing_patch",
            client.patch("/operations/tsk_missing_patch", json={"tags": ["should-not-apply"]}),
        ),
        (
            "tsk_missing_cancel",
            client.post("/operations/tsk_missing_cancel/cancel", json={"reason": "observe_cancel"}),
        ),
        (
            "tsk_missing_delete",
            client.request("DELETE", "/operations/tsk_missing_delete", json={"reason": "observe_delete"}),
        ),
    ]

    for operation_id, response in requests:
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["status"] == "blocked"
        assert body["operation_id"] == operation_id
        assert "operation" not in body
        assert "Observe mode keeps Francis read-only." in body["message"]


def test_operations_run_once_worker_route_completes_cleanly(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    run_once = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
        },
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is True
    assert body["exit_code"] == 0


def test_operations_run_once_denies_unscoped_actor_before_worker_cycle(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
            "actor": "test.operations.run",
        },
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["exit_code"] == 1
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1


def test_operations_run_once_worker_route_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    set_control_mode("observe", reason="test_observe_worker_block", actor="tests")

    client = TestClient(create_app())

    run_once = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
        },
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is False
    assert body["exit_code"] == 1
    assert body["status"] == "blocked"
    assert "Observe mode keeps execution read-only." in body["error"]


def test_operations_export_jsonl_contains_task(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "export_test", "input": {"goal": "export"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    exported = client.get("/operations/export?format=jsonl")
    assert exported.status_code == 200
    assert operation_id in exported.text


def test_operations_plugin_run_action_executes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={
            "name": "Ops Plugin",
            "description": "operation plugin action",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("plugin_run_action"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    plugin_id = str(built_body["plugin_id"])
    _approve_forge_proposal(client, str(built_body["proposal_id"]))
    enabled = client.post("/plugins/enable", json={"id": plugin_id, "reason": "test_enable", "actor": _PLUGIN_ACTOR})
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is True

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "plugin.run" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "queue plugin run",
            "input": {"id": plugin_id, "action": "run", "input": "hello from operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert str(output["output"]) == "Plugin response: hello from operation"
    trace_id = str(output["receipt"].get("trace_id") or "")
    run_id = str(output["receipt"].get("run_id") or "")
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")
    assert run_body["operation"]["trace_id"] == trace_id
    assert run_body["operation"]["run_id"] == run_id
    assert run_body["operation"]["meta"]["trace_id"] == trace_id
    assert run_body["operation"]["meta"]["run_id"] == run_id

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["trace_id"] == trace_id
    assert fetched_body["operation"]["run_id"] == run_id
    assert fetched_body["operation"]["meta"]["trace_id"] == trace_id
    assert fetched_body["operation"]["meta"]["run_id"] == run_id

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_operation = next(item for item in listed.json()["items"] if item["id"] == operation_id)
    assert listed_operation["trace_id"] == trace_id
    assert listed_operation["run_id"] == run_id

    listed_by_trace = client.get("/operations/list", params={"trace_id": trace_id})
    assert listed_by_trace.status_code == 200
    assert [item["id"] for item in listed_by_trace.json()["items"]] == [operation_id]

    listed_by_run = client.get("/operations/list", params={"run_id": run_id})
    assert listed_by_run.status_code == 200
    assert [item["id"] for item in listed_by_run.json()["items"]] == [operation_id]

    exported_json = client.get("/operations/export", params={"format": "json", "run_id": run_id})
    assert exported_json.status_code == 200
    assert [item["id"] for item in exported_json.json()["items"]] == [operation_id]

    exported_csv = client.get("/operations/export", params={"format": "csv", "trace_id": trace_id})
    assert exported_csv.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    assert [row["id"] for row in rows] == [operation_id]
    assert rows[0]["trace_id"] == trace_id
    assert rows[0]["run_id"] == run_id
    assert "artifact_dir" in rows[0]


def test_operations_list_and_export_filter_artifact_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    task_id = "tsk_artifact_filter"
    artifact_dir = str(data_root / "artifacts" / "supervised_exec" / "run_filter")
    task_dir = data_root / "tasks" / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "record.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "status": "completed",
                "capability": "codex.supervised_exec",
                "requester_id": "test.operations.artifact_filter",
                "created_at": "2024-03-09T16:00:00+00:00",
                "updated_at": "2024-03-09T16:00:01+00:00",
                "inputs": {},
                "result": {
                    "data": {
                        "ok": True,
                        "receipt": {
                            "trace_id": "trace_artifact_filter",
                            "run_id": "run_artifact_filter",
                            "artifact_dir": artifact_dir,
                        },
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    listed = client.get("/operations/list", params={"artifact_dir": artifact_dir})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [task_id]

    exported = client.get("/operations/export", params={"format": "csv", "artifact_dir": artifact_dir})
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert [row["id"] for row in rows] == [task_id]
    assert rows[0]["trace_id"] == "trace_artifact_filter"
    assert rows[0]["run_id"] == "run_artifact_filter"
    assert rows[0]["artifact_dir"] == artifact_dir


def test_operations_list_get_and_export_preserve_metadata_only_trace_handles(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    task_id = "tsk_metadata_handles"
    mission_id = "msn_metadata_handles"
    trace_id = "trace_metadata_handles"
    run_id = "run_metadata_handles"
    approval_id = "apr_metadata_handles"
    artifact_dir = str(data_root / "artifacts" / "metadata" / "run_metadata_handles")
    task_dir = data_root / "tasks" / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "record.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "status": "completed",
                "capability": "plugin.run",
                "requester_id": "test.operations.metadata_handles",
                "created_at": "2024-03-09T16:00:00+00:00",
                "updated_at": "2024-03-09T16:00:01+00:00",
                "inputs": {
                    "meta": {
                        "mission_id": mission_id,
                        "run_id": run_id,
                        "approval_id": approval_id,
                        "artifact_dir": artifact_dir,
                    }
                },
                "meta": {
                    "trace_id": trace_id,
                },
                "result": {
                    "data": {
                        "ok": True,
                        "message": "completed without receipt handles",
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_operation = next(item for item in listed.json()["items"] if item["id"] == task_id)
    assert listed_operation["mission_id"] == mission_id
    assert listed_operation["trace_id"] == trace_id
    assert listed_operation["run_id"] == run_id
    assert listed_operation["artifact_dir"] == artifact_dir
    assert listed_operation["meta"]["mission_id"] == mission_id
    assert listed_operation["meta"]["approval_id"] == approval_id
    assert listed_operation["meta"]["trace_id"] == trace_id
    assert listed_operation["meta"]["run_id"] == run_id
    assert listed_operation["meta"]["artifact_dir"] == artifact_dir

    listed_by_trace = client.get("/operations/list", params={"trace_id": trace_id})
    assert listed_by_trace.status_code == 200
    assert [item["id"] for item in listed_by_trace.json()["items"]] == [task_id]

    listed_by_run = client.get("/operations/list", params={"run_id": run_id})
    assert listed_by_run.status_code == 200
    assert [item["id"] for item in listed_by_run.json()["items"]] == [task_id]

    listed_by_artifact = client.get("/operations/list", params={"artifact_dir": artifact_dir})
    assert listed_by_artifact.status_code == 200
    assert [item["id"] for item in listed_by_artifact.json()["items"]] == [task_id]

    listed_by_approval = client.get("/operations/list", params={"approval_id": approval_id})
    assert listed_by_approval.status_code == 200
    assert [item["id"] for item in listed_by_approval.json()["items"]] == [task_id]

    listed_by_mission = client.get("/operations/list", params={"mission_id": mission_id})
    assert listed_by_mission.status_code == 200
    assert [item["id"] for item in listed_by_mission.json()["items"]] == [task_id]

    fetched = client.get(f"/operations/{task_id}")
    assert fetched.status_code == 200
    fetched_operation = fetched.json()["operation"]
    assert fetched_operation["mission_id"] == mission_id
    assert fetched_operation["trace_id"] == trace_id
    assert fetched_operation["run_id"] == run_id
    assert fetched_operation["artifact_dir"] == artifact_dir

    exported_json = client.get("/operations/export", params={"format": "json", "mission_id": mission_id})
    assert exported_json.status_code == 200
    assert [item["id"] for item in exported_json.json()["items"]] == [task_id]
    assert exported_json.json()["items"][0]["mission_id"] == mission_id
    assert exported_json.json()["items"][0]["trace_id"] == trace_id

    exported_approval_json = client.get("/operations/export", params={"format": "json", "approval_id": approval_id})
    assert exported_approval_json.status_code == 200
    assert [item["id"] for item in exported_approval_json.json()["items"]] == [task_id]
    assert exported_approval_json.json()["items"][0]["meta"]["approval_id"] == approval_id

    exported_csv = client.get("/operations/export", params={"format": "csv", "artifact_dir": artifact_dir})
    assert exported_csv.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    assert [row["id"] for row in rows] == [task_id]
    assert rows[0]["mission_id"] == mission_id
    assert rows[0]["approval_id"] == approval_id
    assert rows[0]["trace_id"] == trace_id
    assert rows[0]["run_id"] == run_id
    assert rows[0]["artifact_dir"] == artifact_dir


def test_operations_run_surfaces_completed_mission_memory_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Expose direct operation memory receipt",
            "summary": "Completed mission-linked operation run should return the memory receipt handoff.",
            "requester_id": "test.operations.memory_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    built = client.post(
        "/plugins/build",
        json={
            "name": "Ops Memory Receipt Plugin",
            "description": "operation memory receipt",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("memory_receipt"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    plugin_id = str(built_body["plugin_id"])
    _approve_forge_proposal(client, str(built_body["proposal_id"]))
    enabled = client.post("/plugins/enable", json={"id": plugin_id, "reason": "test_enable", "actor": _PLUGIN_ACTOR})
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "direct operation memory receipt",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "run", "input": "operation memory receipt"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.memory_receipt"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    trace_id = str(run_body["operation"]["trace_id"])
    run_id = str(run_body["operation"]["run_id"])
    artifact_dir = str(run_body["operation"].get("artifact_dir") or "")

    receipt = run_body["memory_receipt"]
    assert receipt["source"] == "continuity.ledger"
    assert receipt["kind"] == "ledger_append"
    assert receipt["role"] == "system"
    assert receipt["scope"] == "mission.loop"
    assert receipt["operation_status"] == "succeeded"
    assert receipt["subsystem"] == "operations.runtime"
    assert receipt["mission_id"] == mission_id
    assert receipt["operation_id"] == operation_id
    assert receipt["trace_id"] == trace_id
    assert receipt["run_id"] == run_id
    if artifact_dir:
        assert receipt["artifact_dir"] == artifact_dir
    assert receipt["handoff_gate"] == "operator_review"
    assert receipt["current_task_gate"] == "operator_review"
    assert receipt["current_task_operation_name"] == "plugin.run"
    assert receipt["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert receipt["current_task_advance_action"] == "run_operation"
    expected_references = {
        "mission_id": mission_id,
        "operation_id": operation_id,
        "trace_id": trace_id,
        "run_id": run_id,
    }
    if artifact_dir:
        expected_references["artifact_dir"] = artifact_dir
    assert receipt["references"] == expected_references
    assert receipt["handoff_trace_id"] == trace_id
    assert receipt["current_task_trace_id"] == trace_id
    assert run_body["operation"]["meta"]["memory_receipt_count"] == 1
    assert run_body["operation"]["meta"]["latest_memory_receipt"]["operation_id"] == operation_id

    listed = client.get("/memory/timeline/list", params={"run_id": run_id, "include_payload": 1})
    assert listed.status_code == 200
    listed_items = [
        item for item in listed.json()["items"] if item.get("references", {}).get("operation_id") == operation_id
    ]
    assert listed_items
    assert listed_items[0]["loop"]["current_task_operation_name"] == "plugin.run"
    assert listed_items[0]["loop"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert listed_items[0]["loop"]["current_task_advance_action"] == "run_operation"

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["memory_receipt_count"] == 1
    assert fetched_body["latest_memory_receipt"]["operation_id"] == operation_id
    assert fetched_body["latest_memory_receipt"]["handoff_gate"] == "operator_review"
    assert fetched_body["latest_memory_receipt"]["current_task_gate"] == "operator_review"
    assert fetched_body["latest_memory_receipt"]["current_task_operation_name"] == "plugin.run"
    assert fetched_body["latest_memory_receipt"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert fetched_body["latest_memory_receipt"]["current_task_advance_action"] == "run_operation"
    assert fetched_body["latest_memory_receipt"]["current_task_trace_id"] == trace_id
    assert fetched_body["latest_memory_receipt"]["references"] == expected_references
    assert fetched_body["operation"]["meta"]["memory_receipt_count"] == 1
    assert fetched_body["operation"]["meta"]["latest_memory_receipt"]["operation_id"] == operation_id

    fetched_many = client.post("/operations/get_many", json={"ids": [operation_id]})
    assert fetched_many.status_code == 200
    many_item = fetched_many.json()["items"][0]
    assert many_item["memory_receipt_count"] == 1
    assert many_item["latest_memory_receipt"]["operation_id"] == operation_id
    assert many_item["latest_memory_receipt"]["handoff_gate"] == "operator_review"
    assert many_item["latest_memory_receipt"]["current_task_gate"] == "operator_review"
    assert many_item["latest_memory_receipt"]["current_task_operation_name"] == "plugin.run"
    assert many_item["latest_memory_receipt"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert many_item["latest_memory_receipt"]["current_task_advance_action"] == "run_operation"


def test_operations_run_surfaces_failed_mission_memory_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Expose failed operation memory receipt",
            "summary": "Failed mission-linked operation run should return the memory receipt handoff.",
            "requester_id": "test.operations.failed_memory_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "direct failed operation memory receipt",
            "mission_id": mission_id,
            "input": {"action": "run", "input": "missing plugin id"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(
        f"/operations/{operation_id}/run", json={"worker_id": "test.operations.failed_memory_receipt"}
    )
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["ok"] is False
    assert run_body["status"] == "failed"
    assert run_body["operation"]["error"] == "plugin_id_required"

    receipt = run_body["memory_receipt"]
    assert receipt["source"] == "continuity.ledger"
    assert receipt["kind"] == "ledger_append"
    assert receipt["role"] == "system"
    assert receipt["scope"] == "mission.loop"
    assert receipt["operation_status"] == "failed"
    assert receipt["operation_error"] == "plugin_id_required"
    assert receipt["recovery_next_step"] == "review_operation_detail"
    assert receipt["subsystem"] == "operations.runtime"
    assert receipt["mission_id"] == mission_id
    assert receipt["operation_id"] == operation_id
    assert receipt["active_stage"] == "deadletter"
    assert receipt["handoff_stage"] == "deadletter"
    assert receipt["handoff_action"] == "retry_or_deadletter"
    assert receipt["handoff_gate"] == "operator_review"
    assert receipt["handoff_operation_id"] == operation_id
    assert receipt["handoff_next_step"] == "review_operation_detail"
    assert receipt["current_task_source"] == "terminal_operation_receipt"
    assert receipt["current_task_operation_id"] == operation_id
    assert receipt["current_task_operation_name"] == "plugin.run"
    assert receipt["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert receipt["current_task_advance_action"] == "run_operation"
    assert receipt["current_task_gate"] == "operator_review"
    assert receipt["current_task_next_step"] == "review_operation_detail"
    assert receipt["memory_receipt_count"] == 1
    assert "Mission operation failed" in receipt["message"]
    assert receipt["references"]["mission_id"] == mission_id
    assert receipt["references"]["operation_id"] == operation_id
    assert str(receipt["references"]["trace_id"]).startswith("trace_")
    assert str(receipt["references"]["run_id"]).startswith("run_")
    assert str(receipt["trace_id"]).startswith("trace_")
    assert str(receipt["run_id"]).startswith("run_")

    listed = client.get(
        "/memory/timeline/list",
        params={"mission_id": mission_id, "operation_id": operation_id, "include_payload": 1},
    )
    assert listed.status_code == 200
    receipts = [
        item
        for item in listed.json()["items"]
        if item.get("kind") == "ledger_append"
        and item.get("references", {}).get("mission_id") == mission_id
        and item.get("references", {}).get("operation_id") == operation_id
    ]
    assert receipts
    assert receipts[0]["payload"]["meta"]["operation_status"] == "failed"
    assert receipts[0]["payload"]["meta"]["operation_error"] == "plugin_id_required"
    assert receipts[0]["payload"]["meta"]["recovery_next_step"] == "review_operation_detail"
    assert receipts[0]["loop"]["active_stage"] == "deadletter"
    assert receipts[0]["loop"]["handoff_stage"] == "deadletter"
    assert receipts[0]["loop"]["handoff_action"] == "retry_or_deadletter"
    assert receipts[0]["loop"]["handoff_gate"] == "operator_review"
    assert receipts[0]["loop"]["handoff_operation_id"] == operation_id
    assert receipts[0]["loop"]["handoff_next_step"] == "review_operation_detail"
    assert receipts[0]["loop"]["current_task_source"] == "terminal_operation_receipt"
    assert receipts[0]["loop"]["current_task_operation_id"] == operation_id
    assert receipts[0]["loop"]["current_task_operation_name"] == "plugin.run"
    assert receipts[0]["loop"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert receipts[0]["loop"]["current_task_advance_action"] == "run_operation"
    assert receipts[0]["loop"]["current_task_gate"] == "operator_review"
    assert receipts[0]["loop"]["current_task_next_step"] == "review_operation_detail"
    assert receipts[0]["loop"]["operation_error"] == "plugin_id_required"
    assert receipts[0]["loop"]["recovery_next_step"] == "review_operation_detail"

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["latest_memory_receipt"]["operation_error"] == "plugin_id_required"
    assert fetched_body["latest_memory_receipt"]["recovery_next_step"] == "review_operation_detail"
    assert fetched_body["latest_memory_receipt"]["handoff_action"] == "retry_or_deadletter"
    assert fetched_body["latest_memory_receipt"]["handoff_gate"] == "operator_review"
    assert fetched_body["latest_memory_receipt"]["current_task_source"] == "terminal_operation_receipt"
    assert fetched_body["latest_memory_receipt"]["current_task_gate"] == "operator_review"
    assert fetched_body["latest_memory_receipt"]["current_task_operation_name"] == "plugin.run"
    assert fetched_body["latest_memory_receipt"]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert fetched_body["latest_memory_receipt"]["current_task_advance_action"] == "run_operation"


def test_operations_tool_run_action_executes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post(
        "/plugins/build",
        json={
            "name": "Ops Tool Plugin",
            "description": "operation tool action",
            "actor": _PLUGIN_ACTOR,
            "meta": _forge_promotion_meta("tool_run_action"),
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    plugin_id = str(built_body["plugin_id"])
    _approve_forge_proposal(client, str(built_body["proposal_id"]))
    enabled = client.post("/plugins/enable", json={"id": plugin_id, "reason": "test_enable", "actor": _PLUGIN_ACTOR})
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is True

    tools = client.get(f"/plugins/tools/list?plugin_id={plugin_id}")
    assert tools.status_code == 200
    tools_body = tools.json()
    assert isinstance(tools_body.get("items"), list)
    assert tools_body["items"]
    tool_id = str(tools_body["items"][0]["id"])

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "plugin.tool.run" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "tool.run",
            "reason": "queue tool run",
            "input": {"id": tool_id, "input": "hello from tool operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.tool"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert output["tool_id"] == tool_id
    assert str(output["output"]) == "Plugin response: hello from tool operation"


def test_operations_governance_holds_are_visible_and_rerunnable(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy",
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"
    blocked_meta = blocked_body["operation"]["meta"]
    assert blocked_meta["orb_plane"] == "P3_GOVERNANCE"
    assert blocked_meta["governance"]["gate"] == "trust_gate"
    assert blocked_meta["governance"]["next_step"] == "raise_trust_or_reduce_risk"

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "operations-governance-test", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == approval_id
    assert task_inputs["meta"]["approval_id"] == approval_id
    log_names = [str(item.get("name")) for item in detail_pending_body["logs"]]
    assert "status_updated" in log_names
    assert "governance_hold" in log_names

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "ok"

    detail_executed = client.get(f"/operations/{operation_id}")
    assert detail_executed.status_code == 200
    detail_executed_body = detail_executed.json()
    governance_holds = [item for item in detail_executed_body["logs"] if item.get("name") == "governance_hold"]
    assert len(governance_holds) >= 2


def test_operations_approved_mission_run_receipt_preserves_approval_posture(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Preserve approved operation posture",
            "summary": "Approved mission-linked execution should keep approval posture in receipts.",
            "requester_id": "test.operations.approved_mission_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/ops-approved-mission",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to a target environment.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    assert installed.json()["ok"] is True
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "operations-approved-mission-receipt", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "approved mission operation",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.approved"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.approved"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    assert executed_body["operation"]["meta"]["approval_id"] == approval_id

    receipt = executed_body["memory_receipt"]
    assert receipt["operation_status"] == "succeeded"
    assert receipt["approval_status"] == "approved"
    assert receipt["references"]["mission_id"] == mission_id
    assert receipt["references"]["operation_id"] == operation_id
    assert receipt["references"]["approval_id"] == approval_id

    detail = client.get(f"/operations/{operation_id}")
    assert detail.status_code == 200
    assert detail.json()["operation"]["meta"]["approval_id"] == approval_id

    listed = client.get(
        "/memory/timeline/list",
        params={"mission_id": mission_id, "operation_id": operation_id, "include_payload": 1},
    )
    assert listed.status_code == 200
    receipts = [
        item for item in listed.json()["items"] if item.get("references", {}).get("operation_id") == operation_id
    ]
    assert receipts
    assert receipts[0]["loop"]["handoff_approval_id"] == approval_id
    assert receipts[0]["loop"]["handoff_approval_status"] == "approved"


def test_operations_approved_supervised_exec_preserves_receipt_handles(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Preserve approved supervised execution handles",
            "summary": "Approved supervised execution should keep trace, run, and artifact handles.",
            "requester_id": "test.operations.approved_mission_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "approved supervised operation",
            "mission_id": mission_id,
            "input": {"user_command": "echo approved operation receipt", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.approved_handles"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.approved_handles"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    operation = executed_body["operation"]
    assert operation["meta"]["approval_id"] == approval_id
    trace_id = str(operation["trace_id"])
    run_id = str(operation["run_id"])
    artifact_dir = str(operation["artifact_dir"])
    assert trace_id.startswith("trace_")
    assert run_id
    assert artifact_dir

    receipt = executed_body["memory_receipt"]
    assert receipt["operation_status"] == "succeeded"
    assert receipt["approval_status"] == "approved"
    assert receipt["references"]["mission_id"] == mission_id
    assert receipt["references"]["operation_id"] == operation_id
    assert receipt["references"]["approval_id"] == approval_id
    assert receipt["references"]["trace_id"] == trace_id
    assert receipt["references"]["run_id"] == run_id
    assert receipt["references"]["artifact_dir"] == artifact_dir
    assert receipt["handoff_trace_id"] == trace_id
    assert receipt["handoff_run_id"] == run_id
    assert receipt["handoff_artifact_dir"] == artifact_dir
    assert receipt["current_task_trace_id"] == trace_id
    assert receipt["current_task_run_id"] == run_id
    assert receipt["current_task_artifact_dir"] == artifact_dir

    detail = client.get(f"/operations/{operation_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["operation"]["meta"]["approval_id"] == approval_id
    assert detail_body["operation"]["trace_id"] == trace_id
    assert detail_body["operation"]["run_id"] == run_id
    assert detail_body["operation"]["artifact_dir"] == artifact_dir
    assert detail_body["latest_memory_receipt"]["references"]["approval_id"] == approval_id
    assert detail_body["latest_memory_receipt"]["references"]["trace_id"] == trace_id
    assert detail_body["latest_memory_receipt"]["references"]["run_id"] == run_id
    assert detail_body["latest_memory_receipt"]["references"]["artifact_dir"] == artifact_dir

    listed = client.get(
        "/memory/timeline/list",
        params={
            "mission_id": mission_id,
            "operation_id": operation_id,
            "approval_id": approval_id,
            "trace_id": trace_id,
            "run_id": run_id,
            "artifact_dir": artifact_dir,
            "include_payload": 1,
        },
    )
    assert listed.status_code == 200
    receipts = [
        item for item in listed.json()["items"] if item.get("references", {}).get("operation_id") == operation_id
    ]
    assert receipts
    assert receipts[0]["references"]["approval_id"] == approval_id
    assert receipts[0]["references"]["trace_id"] == trace_id
    assert receipts[0]["references"]["run_id"] == run_id
    assert receipts[0]["references"]["artifact_dir"] == artifact_dir
    assert receipts[0]["loop"]["handoff_approval_id"] == approval_id
    assert receipts[0]["loop"]["handoff_approval_status"] == "approved"
    assert receipts[0]["loop"]["handoff_trace_id"] == trace_id
    assert receipts[0]["loop"]["handoff_run_id"] == run_id
    assert receipts[0]["loop"]["handoff_artifact_dir"] == artifact_dir
    assert receipts[0]["loop"]["current_task_trace_id"] == trace_id
    assert receipts[0]["loop"]["current_task_run_id"] == run_id
    assert receipts[0]["loop"]["current_task_artifact_dir"] == artifact_dir


def test_operations_plugin_run_refreshes_exact_action_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/ops-governed",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to a target environment.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "operations-plugin-refresh-test", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy refresh",
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    record_path = data_root / "tasks" / operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["input"] = {"target": "staging"}
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatch_output["previous_approval_id"] == approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    art = Path(str(mismatch_output["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == refreshed_approval_id
    assert task_inputs["meta"]["approval_id"] == refreshed_approval_id
    assert task_inputs["input"]["target"] == "staging"
    governance_holds = [item for item in detail_pending_body["logs"] if item.get("name") == "governance_hold"]
    assert governance_holds
    last_hold = governance_holds[-1]["output"]
    assert last_hold["approval_id"] == refreshed_approval_id

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "ok"
    assert output["meta"]["action"] == "deploy"


def test_operations_git_push_requires_approval_and_pushes_branch(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    remote_root = tmp_path / "remote.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(remote_root))
    _git(repo_root, "remote", "add", "origin", str(remote_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "git.push" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push current branch",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    pending_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert pending_inputs["approval_id"] == approval_id
    assert pending_inputs["meta"]["approval_id"] == approval_id
    log_names = [str(item.get("name")) for item in detail_pending_body["logs"]]
    assert "governance_hold" in log_names

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["branch"] == "main"
    assert output["remote"] == "origin"
    assert output["exit_code"] == 0

    remote_branch = subprocess.run(
        ["git", "--git-dir", str(remote_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert remote_branch.returncode == 0
    assert remote_branch.stdout.strip()


def test_operations_git_push_branch_first_policy_blocks_protected_branch_before_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "branch-first executor push",
            "input": {"cwd": str(repo_root), "branch_first_required": True},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_branch"})

    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"
    operation = blocked_body["operation"]
    output = operation["output"]
    assert output["status"] == "blocked"
    assert output["error"] == "branch_first_workflow_required"
    assert output["branch"] == "main"
    assert output["branch_first_policy"] == {
        "required": True,
        "workflow_policy": "branch_first",
        "protected_branches": ["main", "master", "trunk", "production"],
        "protected_branch": True,
    }
    assert output["governance"]["gate"] == "branch_first_workflow"
    assert output["governance"]["approval_requested"] is False
    receipt_id = str(output["branch_first_policy_receipt_id"])
    assert receipt_id.startswith("gitpush_branch_policy_")
    receipt_path = Path(str(output["branch_first_policy_receipt_path"]))
    assert receipt_path == data_root / "artifacts" / "git_push_branch_policy_receipts" / f"{receipt_id}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "git.push.branch_first_policy.receipt"
    assert receipt["receipt_id"] == receipt_id
    assert receipt["decision"] == "blocked"
    assert receipt["reason"] == "branch_first_workflow_required"
    assert receipt["branch"] == "main"
    assert receipt["branch_first_policy"]["protected_branch"] is True
    assert receipt["governance"]["branch_first_workflow_enforcement"] is True
    assert receipt["governance"]["blocks_protected_branch_before_approval"] is True
    assert not (data_root / "approvals" / "pending").exists()


def test_operations_git_push_refreshes_approval_when_remote_changes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    origin_root = tmp_path / "origin.git"
    mirror_root = tmp_path / "mirror.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(origin_root))
    _git(repo_root, "init", "--bare", str(mirror_root))
    _git(repo_root, "remote", "add", "origin", str(origin_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push current branch",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert pending.status_code == 200
    pending_body = pending.json()
    first_approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert first_approval_id

    approved = client.post(
        "/approvals/decision", json={"id": first_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    _git(repo_root, "remote", "set-url", "origin", str(mirror_root))

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != first_approval_id
    assert mismatch_output["previous_approval_id"] == first_approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    art = Path(str(mismatch_output["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()
    assert not (art / "result.json").exists()

    mirror_branch_before = subprocess.run(
        ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert mirror_branch_before.returncode != 0

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["approval_id"] == refreshed_approval_id
    assert output["run_id"] == refreshed_approval_id
    assert executed_body["operation"]["run_id"] == refreshed_approval_id
    assert executed_body["operation"]["artifact_dir"] == output["artifact_dir"]
    assert executed_body["operation"]["meta"]["run_id"] == refreshed_approval_id
    assert executed_body["operation"]["meta"]["artifact_dir"] == output["artifact_dir"]
    assert output["remote_url"] == str(mirror_root)

    mirror_branch_after = subprocess.run(
        ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert mirror_branch_after.returncode == 0
    assert mirror_branch_after.stdout.strip()


def test_operations_git_push_seals_secret_remote_url_and_redacts_artifacts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    origin_secret = "gitpushoriginsecret123"
    mirror_secret = "gitpushmirrorsecret123"
    origin_root = tmp_path / f"password={origin_secret}.git"
    mirror_root = tmp_path / f"password={mirror_secret}.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(origin_root))
    _git(repo_root, "init", "--bare", str(mirror_root))
    _git(repo_root, "remote", "add", "origin", str(origin_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push credential-bearing remote",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_secret"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    first_approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert first_approval_id

    approval_path = data_root / "approvals" / "pending" / f"{first_approval_id}.json"
    approval_text = approval_path.read_text(encoding="utf-8")
    assert origin_secret not in approval_text
    approval_payload = json.loads(approval_text)
    sealed_remote = approval_payload["payload"]["remote_url"]
    assert sealed_remote["kind"] == "sealed_secret"
    assert sealed_remote["redacted"].endswith("password=[REDACTED:secret]")
    assert str(sealed_remote["digest"]).startswith("hmac-sha256:")

    request_artifact = data_root / "artifacts" / "git_push" / first_approval_id / "request.json"
    request_artifact_text = request_artifact.read_text(encoding="utf-8")
    assert origin_secret not in request_artifact_text
    assert "hmac-sha256:" not in request_artifact_text

    approved = client.post(
        "/approvals/decision", json={"id": first_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    _git(repo_root, "remote", "set-url", "origin", str(mirror_root))

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_secret"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id != first_approval_id

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    mismatch_artifact_text = (refreshed_art / "mismatch.json").read_text(encoding="utf-8")
    assert origin_secret not in mismatch_artifact_text
    assert mirror_secret not in mismatch_artifact_text
    assert "hmac-sha256:" not in mismatch_artifact_text
    refreshed_approval_text = (data_root / "approvals" / "pending" / f"{refreshed_approval_id}.json").read_text(
        encoding="utf-8"
    )
    assert mirror_secret not in refreshed_approval_text

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_secret"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["status"] in {"succeeded", "failed"}
    executed_text = json.dumps(executed_body, sort_keys=True)
    assert origin_secret not in executed_text
    assert mirror_secret not in executed_text
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] in {"success", "error"}
    assert isinstance(output["exit_code"], int)

    art = Path(str(output["artifact_dir"]))
    for artifact_name in ("plan.json", "result.json", "stdout.txt", "stderr.txt"):
        artifact_text = (art / artifact_name).read_text(encoding="utf-8")
        assert origin_secret not in artifact_text
        assert mirror_secret not in artifact_text
        assert "hmac-sha256:" not in artifact_text

    if output["status"] == "success":
        mirror_branch_after = subprocess.run(
            ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        assert mirror_branch_after.returncode == 0
        assert mirror_branch_after.stdout.strip()


def test_operations_git_push_seals_https_userinfo_remote_and_redacts_projection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")

    raw_userinfo = "francis-userinfo-secret123"
    redacted_remote = "https://[REDACTED:secret]@example.invalid/owner/repo.git"
    _git(repo_root, "remote", "add", "origin", f"https://{raw_userinfo}@example.invalid/owner/repo.git")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push userinfo credential remote",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push_userinfo"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    pending_text = json.dumps(pending_body, sort_keys=True)
    assert raw_userinfo not in pending_text

    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    approval_text = approval_path.read_text(encoding="utf-8")
    assert raw_userinfo not in approval_text
    approval_payload = json.loads(approval_text)
    sealed_remote = approval_payload["payload"]["remote_url"]
    assert sealed_remote["kind"] == "sealed_secret"
    assert sealed_remote["redacted"] == redacted_remote
    assert str(sealed_remote["digest"]).startswith("hmac-sha256:")

    request_artifact = data_root / "artifacts" / "git_push" / approval_id / "request.json"
    request_artifact_text = request_artifact.read_text(encoding="utf-8")
    assert raw_userinfo not in request_artifact_text
    assert "hmac-sha256:" not in request_artifact_text
    assert redacted_remote in request_artifact_text

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)
    listed_text = json.dumps(listed_item, sort_keys=True)
    assert raw_userinfo not in listed_text
    assert "hmac-sha256:" not in listed_text
    assert listed_item["payload"]["remote_url"] == redacted_remote


def test_operations_supervised_exec_seals_secret_command_and_redacts_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_secret = "supervisedexecsecret123"
    command = f"echo password={raw_secret}"
    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "run approved secret-bearing command",
            "input": {"user_command": command, "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_secret"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    assert pending_body["operation"]["input"]["user_command"] == "echo password=[REDACTED:secret]"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    approval_text = approval_path.read_text(encoding="utf-8")
    assert raw_secret not in approval_text
    approval_payload = json.loads(approval_text)
    sealed_command = approval_payload["payload"]["user_command"]
    assert sealed_command["kind"] == "sealed_secret"
    assert sealed_command["redacted"] == "echo password=[REDACTED:secret]"
    assert str(sealed_command["digest"]).startswith("hmac-sha256:")

    request_artifact = data_root / "artifacts" / "supervised_exec" / approval_id / "request.json"
    request_artifact_text = request_artifact.read_text(encoding="utf-8")
    assert raw_secret not in request_artifact_text
    assert "hmac-sha256:" not in request_artifact_text

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_secret"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    art = Path(str(output["artifact_dir"]))
    assert raw_secret not in (art / "stdout.txt").read_text(encoding="utf-8")
    assert "password=[REDACTED:secret]" in (art / "stdout.txt").read_text(encoding="utf-8")
    plan_text = (art / "plan.json").read_text(encoding="utf-8")
    result_text = (art / "result.json").read_text(encoding="utf-8")
    assert raw_secret not in plan_text
    assert raw_secret not in result_text
    assert "hmac-sha256:" not in plan_text
    assert "hmac-sha256:" not in result_text

    mismatch_secret = "supervisedmismatchsecret123"
    different_secret = "superviseddifferentsecret123"
    mismatch_created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "verify sealed mismatch",
            "input": {"user_command": f"echo password={mismatch_secret}", "cwd": str(tmp_path)},
        },
    )
    assert mismatch_created.status_code == 200
    mismatch_operation_id = str(mismatch_created.json()["operation_id"])

    mismatch_pending = client.post(
        f"/operations/{mismatch_operation_id}/run",
        json={"worker_id": "test.operations.supervised_mismatch"},
    )
    assert mismatch_pending.status_code == 200
    first_approval_id = str(mismatch_pending.json()["operation"]["meta"]["approval_id"])
    assert first_approval_id

    first_approval = client.post(
        "/approvals/decision", json={"id": first_approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert first_approval.status_code == 200
    assert first_approval.json()["ok"] is True

    record_path = data_root / "tasks" / mismatch_operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["user_command"] = f"echo password={different_secret}"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(
        f"/operations/{mismatch_operation_id}/run",
        json={"worker_id": "test.operations.supervised_mismatch"},
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id != first_approval_id

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    mismatch_artifact_text = (refreshed_art / "mismatch.json").read_text(encoding="utf-8")
    assert mismatch_secret not in mismatch_artifact_text
    assert different_secret not in mismatch_artifact_text
    assert "hmac-sha256:" not in mismatch_artifact_text
    refreshed_approval_text = (data_root / "approvals" / "pending" / f"{refreshed_approval_id}.json").read_text(
        encoding="utf-8"
    )
    assert different_secret not in refreshed_approval_text


def test_operations_supervised_exec_refreshes_stale_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "run approved command",
            "input": {"user_command": "echo approved", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    record_path = data_root / "tasks" / operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["user_command"] = "echo refreshed"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatch_output["previous_approval_id"] == approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == refreshed_approval_id
    assert task_inputs["meta"]["approval_id"] == refreshed_approval_id
    assert task_inputs["user_command"] == "echo refreshed"
    governance_holds = [item for item in detail_pending_body["logs"] if item.get("name") == "governance_hold"]
    assert governance_holds
    last_hold = governance_holds[-1]["output"]
    assert last_hold["approval_id"] == refreshed_approval_id
    assert last_hold["gate"] == "approvals_gate"

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    assert (refreshed_art / "request.json").exists()
    assert (refreshed_art / "mismatch.json").exists()
    assert not (refreshed_art / "result.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["approval_id"] == refreshed_approval_id
