from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.governance import approvals
from francis.ingest import IngestService

_INGEST_LAB_ACTOR = "chat_ui.ingest"
_INGEST_LAB_RECEIPT_ACTOR = "test.ingest.lab.receipt.write"
_INGEST_LAB_APPROVAL_CONSUME_ACTOR = "test.ingest.lab.approval.consume"
_INGEST_LAB_NOOP_RUNNER_ACTOR = "test.ingest.lab.runner.noop"
_INGEST_LAB_NOOP_RUNNER_TRANSCRIPT_ACTOR = "test.ingest.lab.runner.noop.transcript"
_INGEST_LAB_NOOP_RUNNER_IDENTITY_ACTOR = "test.ingest.lab.runner.noop.identity"
_INGEST_LAB_SOURCE_MOUNT_READINESS_ACTOR = "test.ingest.lab.source_mount.readiness"
_INGEST_LAB_SOURCE_MOUNT_CONTRACT_ACTOR = "test.ingest.lab.source_mount.contract"
_INGEST_LAB_SANDBOX_PROVIDER_CONTRACT_ACTOR = "test.ingest.lab.sandbox.provider_contract"
_INGEST_LAB_SANDBOX_PROVIDER_BINDING_ACTOR = "test.ingest.lab.sandbox.provider_binding"
_INGEST_LAB_SANDBOX_PROVIDER_SELECTION_ACTOR = "test.ingest.lab.sandbox.provider_selection"
_INGEST_LAB_SANDBOX_PROVIDER_VERIFIER_ACTOR = "test.ingest.lab.sandbox.provider_verifier"
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_ACTOR = "test.ingest.lab.sandbox.provider_runtime_probe"
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_HARNESS_ACTOR = "test.ingest.lab.sandbox.provider_runtime_probe_harness"
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_READINESS_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_runner_readiness"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_BINDING_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_runner_binding"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_ENFORCEMENT_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_runner_enforcement"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_EXECUTION_BOUNDARY_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_execution_boundary"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_REFUSAL_ACTOR = "test.ingest.lab.sandbox.provider_runtime_probe_refusal"
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_REQUEST_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_approval_request"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_CONSUME_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_approval_consume"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_INVOCATION_BOUNDARY_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_invocation_boundary"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_PRE_EXECUTION_BOUNDARY_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_runner_pre_execution_boundary"
)
_INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_CONTROL_BINDING_ACTOR = (
    "test.ingest.lab.sandbox.provider_runtime_probe_runner_control_binding"
)
_INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_BOUNDARY_ACTOR = "test.ingest.lab.sandboxed_rebuild_run_test_boundary"
_INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_REQUEST_ACTOR = (
    "test.ingest.lab.sandboxed_rebuild_run_test_approval_request"
)
_INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_CONSUME_ACTOR = (
    "test.ingest.lab.sandboxed_rebuild_run_test_approval_consume"
)
_INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_RUNNER_BINDING_ACTOR = (
    "test.ingest.lab.sandboxed_rebuild_run_test_runner_binding"
)
_INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_SANDBOX_POLICY_ACTOR = (
    "test.ingest.lab.sandboxed_rebuild_run_test_sandbox_policy"
)
_INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR = "test.ingest.lab.run_boundary.preflight"


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "api_fixture_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "README.md").write_text("# API Fixture Repo\n", encoding="utf-8")
    (repo / "src" / "index.ts").write_text("export const ok = true;\n", encoding="utf-8")
    (repo / "tests" / "index.test.ts").write_text("import { ok } from '../src/index';\n", encoding="utf-8")
    (repo / ".env").write_text("API_TOKEN=super-secret-token-value\n", encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps(
            {
                "name": "api-fixture",
                "scripts": {
                    "test": "node -e \"require('fs').writeFileSync('lab-ran.txt','ran')\"",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return repo


def test_ingest_lab_approval_consumption_preflight_api_returns_runner_contract_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]

    response = TestClient(create_app()).post(
        "/ingest/lab/approval-consumption-preflight",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.approval_consumption_preflight"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["approval_consumption"]["approval_id"] == approval_id
    assert body["approval_consumption"]["binding"]["exact_match"] is True
    assert body["approval_consumption"]["approval_consumed"] is False
    assert body["approval_consumption"]["execution_authority"] is False
    assert body["runner_contract"]["runner_bound"] is False
    assert body["runner_contract"]["execution_enabled"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.execution.approval_consumption_preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["runner_contract_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_approval_consumption_preflight_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/approval-consumption-preflight",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_readiness_api_returns_missing_controls_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_readiness"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["runner_readiness"]["approval_id"] == approval_id
    assert body["runner_readiness"]["current_controls"]["workspace_manifest_present"] is True
    assert body["runner_readiness"]["current_controls"]["source_reference_read_only"] is True
    assert "approved_exact_action_record" in body["runner_readiness"]["missing_controls"]
    assert "governed_runner_bound" in body["runner_readiness"]["missing_controls"]
    assert "execution_receipt_sink_bound" in body["runner_readiness"]["missing_controls"]
    assert body["runner_readiness"]["execution_authority"] is False
    assert body["runner_readiness"]["executed"] is False
    assert body["approval_binding"]["approval_consumed"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.readiness.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_readiness_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_readiness"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_binding_api_returns_receipt_sink_contract_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["runner_binding"]["approval_id"] == approval_id
    assert body["runner_binding"]["runner_binding"]["runner_bound"] is False
    assert body["runner_binding"]["execution_receipt_sink"]["bound"] is False
    assert body["runner_binding"]["approval_consumed"] is False
    assert body["runner_binding"]["execution_authority"] is False
    assert body["runner_binding"]["executed"] is False
    assert "governed_runner_bound" in body["runner_binding"]["missing_controls"]
    assert "execution_receipt_sink_bound" in body["runner_binding"]["missing_controls"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.binding.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_binding_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_enforcement_api_returns_blocked_checks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-enforcement",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_enforcement"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["runner_enforcement"]["approval_id"] == approval_id
    assert body["runner_enforcement"]["current_checks"]["runner_binding_record_present"] is True
    assert body["runner_enforcement"]["current_checks"]["runner_identity_verified"] is False
    assert body["runner_enforcement"]["runner_bound"] is False
    assert body["runner_enforcement"]["receipt_sink_bound"] is False
    assert body["runner_enforcement"]["execution_authority"] is False
    assert body["runner_enforcement"]["executed"] is False
    assert "runner_identity_verified" in body["runner_enforcement"]["missing_checks"]
    assert "execution_receipt_prewrite_bound" in body["runner_enforcement"]["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.enforcement.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_enforcement_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-enforcement",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_enforcement"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_approval_consumption_handoff_api_returns_blocked_without_consuming(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/approval-consumption-handoff",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.approval_consumption_handoff"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["approval_consumption_handoff"]["approval_status"] == "approved"
    assert body["approval_consumption_handoff"]["approval_binding"]["exact_match"] is True
    assert body["approval_consumption_handoff"]["current_checks"]["approval_approved"] is True
    assert body["approval_consumption_handoff"]["current_checks"]["runner_enforcement_ready"] is False
    assert body["approval_consumption_handoff"]["current_checks"]["approval_consumption_not_disabled"] is False
    assert body["approval_consumption_handoff"]["approval_consumed"] is False
    assert body["approval_consumption_handoff"]["execution_authority"] is False
    assert "approval_consumption_not_disabled" in body["approval_consumption_handoff"]["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.execution.approval_consumption_handoff"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_approval_consumption_handoff_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/approval-consumption-handoff",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.approval_consumption_handoff"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_sink_reservation_api_returns_blocked_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-sink-reservation",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    reservation = body["execution_receipt_sink_reservation"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_sink_reservation"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert reservation["current_checks"]["approval_approved"] is True
    assert reservation["current_checks"]["approval_handoff_ready"] is False
    assert reservation["current_checks"]["receipt_sink_bound"] is False
    assert reservation["current_checks"]["execution_receipt_prewrite_bound"] is False
    assert reservation["current_checks"]["reserved_receipt_id_created"] is True
    assert reservation["current_checks"]["execution_receipt_not_written"] is True
    assert reservation["execution_receipt_written"] is False
    assert reservation["approval_consumed"] is False
    assert reservation["execution_authority"] is False
    assert "execution_receipt_prewrite_bound" in reservation["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.execution.receipt_sink_reservation"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_sink_reservation_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-sink-reservation",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_sink_reservation"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_command_allowlist_binding_api_returns_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-command-allowlist-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    command_allowlist = body["runner_command_allowlist"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_command_allowlist_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert command_allowlist["command_plan"]["command_count"] >= 1
    assert command_allowlist["current_checks"]["command_plan_present"] is True
    assert command_allowlist["current_checks"]["commands_from_exact_action"] is True
    assert command_allowlist["current_checks"]["command_allowlist_declared"] is False
    assert command_allowlist["current_checks"]["command_allowlist_bound"] is False
    assert command_allowlist["allowlist_declared"] is False
    assert command_allowlist["allowlist_bound"] is False
    assert command_allowlist["command_execution_enabled"] is False
    assert command_allowlist["approval_consumed"] is False
    assert command_allowlist["execution_authority"] is False
    assert "command_allowlist_bound" in command_allowlist["missing_checks"]
    assert body["execution_receipt_sink_reservation"]["execution_receipt_written"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.command_allowlist.binding"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_command_allowlist_binding_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-command-allowlist-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_command_allowlist_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_command_allowlist_declaration_api_returns_declared_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-command-allowlist-declaration",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    declaration = body["runner_command_allowlist_declaration"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_command_allowlist_declaration"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert declaration["allowlist_declaration"]["entry_count"] >= 1
    assert declaration["current_checks"]["command_allowlist_declared"] is True
    assert declaration["current_checks"]["every_command_has_declaration"] is True
    assert declaration["current_checks"]["command_allowlist_bound"] is False
    assert declaration["allowlist_declared"] is True
    assert declaration["allowlist_bound"] is False
    assert declaration["command_execution_enabled"] is False
    assert declaration["approval_consumed"] is False
    assert declaration["execution_authority"] is False
    assert "command_allowlist_bound" in declaration["missing_checks"]
    assert body["runner_command_allowlist"]["allowlist_bound"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.command_allowlist.declaration"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_command_allowlist_declaration_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-command-allowlist-declaration",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_command_allowlist_declaration"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_command_allowlist_enforcement_api_returns_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-command-allowlist-enforcement",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    enforcement = body["runner_command_allowlist_enforcement"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_command_allowlist_enforcement"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert enforcement["enforcement_projection"]["entry_count"] >= 1
    assert enforcement["current_checks"]["allowlist_entries_declared"] is True
    assert enforcement["current_checks"]["every_entry_has_command_hash"] is True
    assert enforcement["current_checks"]["runner_enforcement_ready"] is False
    assert enforcement["current_checks"]["command_allowlist_enforced"] is False
    assert enforcement["allowlist_declared"] is True
    assert enforcement["allowlist_bound"] is False
    assert enforcement["allowlist_enforced"] is False
    assert enforcement["command_execution_enabled"] is False
    assert enforcement["approval_consumed"] is False
    assert enforcement["execution_authority"] is False
    assert "command_allowlist_enforced" in enforcement["missing_checks"]
    assert body["runner_command_allowlist_declaration"]["allowlist_declared"] is True
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.command_allowlist.enforcement_preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_command_allowlist_enforcement_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-command-allowlist-enforcement",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_command_allowlist_enforcement"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_sandbox_readiness_api_returns_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-sandbox-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    readiness = body["runner_sandbox_readiness"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_sandbox_readiness"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert readiness["sandbox_profile"]["manifest_present"] is True
    assert readiness["current_checks"]["workspace_manifest_present"] is True
    assert readiness["current_checks"]["source_not_copied"] is True
    assert readiness["current_checks"]["sandbox_provider_bound"] is False
    assert readiness["current_checks"]["command_allowlist_enforced"] is False
    assert readiness["sandbox_bound"] is False
    assert readiness["sandbox_enforced"] is False
    assert readiness["runner_bound"] is False
    assert readiness["allowlist_enforced"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert "sandbox_provider_bound" in readiness["missing_checks"]
    assert "command_allowlist_enforced" in readiness["missing_checks"]
    assert body["runner_command_allowlist_enforcement"]["allowlist_enforced"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.runner.sandbox_readiness.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_runner_sandbox_readiness_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/runner-sandbox-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.runner_sandbox_readiness"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_contract_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-contract",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_CONTRACT_ACTOR,
        },
    )
    body = response.json()
    contract = body["sandbox_provider_contract"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_contract"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert contract["contract_kind"] == "francis.lab.sandbox_provider_contract"
    assert contract["contract_mode"] == "provider_contract_preflight_only_no_execution"
    assert contract["provider_contract_declared"] is True
    assert contract["sandbox_provider_bound"] is False
    assert contract["sandbox_bound"] is False
    assert contract["sandbox_enforced"] is False
    assert contract["execution_authority"] is False
    assert contract["executed"] is False
    assert contract["repo_code_executed"] is False
    assert contract["network_accessed"] is False
    assert contract["current_checks"]["runner_sandbox_readiness_present"] is True
    assert contract["current_checks"]["provider_contract_declared"] is True
    assert contract["current_checks"]["network_blocked_or_policy_bound"] is True
    assert contract["current_checks"]["sandbox_provider_bound"] is False
    assert contract["current_checks"]["sandbox_bound"] is False
    assert contract["current_checks"]["sandbox_enforced"] is False
    assert "sandbox_provider_bound" in contract["missing_checks"]
    assert "sandbox_bound" in contract["missing_checks"]
    assert "sandbox_enforced" in contract["missing_checks"]
    assert "network_blocked_or_policy_bound" not in contract["missing_checks"]
    assert body["runner_sandbox_readiness"]["sandbox_bound"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_contract.preflight"
    assert Path(body["sandbox_provider_contract_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert "super-secret-token-value" not in Path(body["sandbox_provider_contract_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_contract_api_denies_before_contract_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    contracts_before = _sandbox_provider_contract_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-contract",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_contract"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_contract_count(data_root) == contracts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_binding_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_BINDING_ACTOR,
        },
    )
    body = response.json()
    binding = body["sandbox_provider_binding"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert binding["binding_kind"] == "francis.lab.sandbox_provider_binding_preflight"
    assert binding["binding_mode"] == "binding_preflight_only_no_execution"
    assert binding["provider_contract_present"] is True
    assert binding["provider_contract_declared"] is True
    assert binding["provider_kind_selected"] is False
    assert binding["provider_binary_or_service_verified"] is False
    assert binding["provider_policy_manifest_bound"] is False
    assert binding["sandbox_provider_bound"] is False
    assert binding["sandbox_bound"] is False
    assert binding["sandbox_enforced"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert binding["repo_code_executed"] is False
    assert binding["network_accessed"] is False
    assert binding["current_checks"]["provider_binding_contract_declared"] is True
    assert binding["current_checks"]["provider_kind_selected"] is False
    assert binding["current_checks"]["provider_binary_or_service_verified"] is False
    assert binding["current_checks"]["network_blocked_or_policy_bound"] is True
    assert "provider_kind_selected" in binding["missing_checks"]
    assert "provider_binary_or_service_verified" in binding["missing_checks"]
    assert "sandbox_provider_bound" in binding["missing_checks"]
    assert "sandbox_bound" in binding["missing_checks"]
    assert "network_blocked_or_policy_bound" not in binding["missing_checks"]
    assert body["sandbox_provider_contract"]["provider_contract_declared"] is True
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_binding.preflight"
    assert Path(body["sandbox_provider_binding_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert "super-secret-token-value" not in Path(body["sandbox_provider_binding_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_binding_api_denies_before_binding_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    bindings_before = _sandbox_provider_binding_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_binding_count(data_root) == bindings_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_selection_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-selection",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_SELECTION_ACTOR,
        },
    )
    body = response.json()
    selection = body["sandbox_provider_selection"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_selection"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert selection["selection_kind"] == "francis.lab.sandbox_provider_selection_preflight"
    assert selection["selected_provider_kind"] == "local_process_sandbox"
    assert selection["provider_kind_selected"] is True
    assert selection["provider_reference_verified"] is True
    assert selection["provider_policy_manifest_bound"] is True
    assert selection["provider_binary_or_service_verified"] is False
    assert selection["sandbox_provider_bound"] is False
    assert selection["sandbox_bound"] is False
    assert selection["sandbox_enforced"] is False
    assert selection["execution_authority"] is False
    assert selection["executed"] is False
    assert selection["repo_code_executed"] is False
    assert selection["network_accessed"] is False
    assert selection["current_checks"]["provider_kind_selected"] is True
    assert selection["current_checks"]["provider_reference_verified"] is True
    assert selection["current_checks"]["provider_policy_manifest_bound"] is True
    assert selection["current_checks"]["provider_binary_or_service_verified"] is False
    assert "provider_kind_selected" not in selection["missing_checks"]
    assert "provider_reference_verified" not in selection["missing_checks"]
    assert "provider_policy_manifest_bound" not in selection["missing_checks"]
    assert "provider_binary_or_service_verified" in selection["missing_checks"]
    assert "sandbox_provider_bound" in selection["missing_checks"]
    assert body["sandbox_provider_binding"]["provider_contract_declared"] is True
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_selection.preflight"
    assert Path(body["sandbox_provider_selection_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_selection_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_selection_api_denies_before_selection_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    selections_before = _sandbox_provider_selection_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-selection",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_selection"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_selection_count(data_root) == selections_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_verifier_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-verifier",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_VERIFIER_ACTOR,
        },
    )
    body = response.json()
    verifier = body["sandbox_provider_verifier"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_verifier"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert verifier["verifier_kind"] == "francis.lab.sandbox_provider_verifier_preflight"
    assert verifier["verifier_mode"] == "static_identity_policy_verification_no_execution"
    assert verifier["provider_kind"] == "local_process_sandbox"
    assert verifier["provider_selection_present"] is True
    assert verifier["provider_reference_verified"] is True
    assert verifier["provider_policy_manifest_bound"] is True
    assert verifier["verifier_contract_declared"] is True
    assert verifier["verifier_implementation_bound"] is True
    assert verifier["verifier_identity_bound"] is True
    assert verifier["verifier_policy_bound"] is True
    assert verifier["verifier_receipt_contract_bound"] is True
    assert verifier["static_identity_verification_performed"] is True
    assert verifier["provider_reference_fingerprint_captured"] is True
    assert verifier["provider_policy_manifest_hash_captured"] is True
    assert verifier["provider_binary_or_service_verified"] is True
    assert verifier["provider_runtime_probe_performed"] is False
    assert verifier["provider_version_captured"] is True
    assert verifier["provider_identity_fingerprint_captured"] is True
    assert verifier["provider_identity"]["provider_reference_fingerprint"].startswith("sha256:")
    assert verifier["provider_identity"]["provider_identity_fingerprint"].startswith("sha256:")
    assert verifier["provider_identity"]["provider_version"] == "0.1.0"
    assert verifier["provider_policy_manifest"]["manifest_hash"].startswith("sha256:")
    assert verifier["provider_policy_manifest"]["network_disabled_by_manifest"] is True
    assert verifier["provider_policy_manifest"]["direct_execution_disabled_by_manifest"] is True
    assert "secret_token" not in verifier["provider_policy_manifest"]["manifest_keys"]
    assert verifier["provider_runtime_probe"]["status"] == "not_performed"
    assert verifier["service_query_performed"] is False
    assert verifier["process_launched"] is False
    assert verifier["container_launched"] is False
    assert verifier["sandbox_provider_bound"] is False
    assert verifier["execution_authority"] is False
    assert verifier["executed"] is False
    assert verifier["current_checks"]["verifier_contract_declared"] is True
    assert verifier["current_checks"]["verifier_implementation_bound"] is True
    assert verifier["current_checks"]["provider_binary_or_service_verified"] is True
    assert "verifier_contract_declared" not in verifier["missing_checks"]
    assert "provider_reference_verified" not in verifier["missing_checks"]
    assert "verifier_implementation_bound" not in verifier["missing_checks"]
    assert "verifier_identity_bound" not in verifier["missing_checks"]
    assert "provider_binary_or_service_verified" not in verifier["missing_checks"]
    assert "provider_identity_fingerprint_captured" not in verifier["missing_checks"]
    assert "provider_runtime_probe_performed" in verifier["missing_checks"]
    assert "sandbox_provider_bound" in verifier["missing_checks"]
    assert body["sandbox_provider_selection"]["provider_reference_verified"] is True
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_verifier.preflight"
    assert Path(body["sandbox_provider_verifier_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_verifier_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_verifier_api_denies_before_verifier_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text('{"network": false, "execution": false}\n', encoding="utf-8")
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    verifiers_before = _sandbox_provider_verifier_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-verifier",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_verifier"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_verifier_count(data_root) == verifiers_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_ACTOR,
        },
    )
    body = response.json()
    runtime_probe = body["sandbox_provider_runtime_probe"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert runtime_probe["probe_kind"] == "francis.lab.sandbox_provider_runtime_probe_preflight"
    assert runtime_probe["probe_mode"] == "runtime_probe_contract_preflight_only_no_provider_execution"
    assert runtime_probe["verifier_present"] is True
    assert runtime_probe["verifier_static_identity_ready"] is True
    assert runtime_probe["provider_identity_fingerprint_captured"] is True
    assert runtime_probe["provider_binary_or_service_verified"] is True
    assert runtime_probe["runtime_probe_contract_declared"] is True
    assert runtime_probe["runtime_probe_authorization_required"] is True
    assert runtime_probe["runtime_probe_policy_bound"] is True
    assert runtime_probe["runtime_probe_timeout_policy_declared"] is True
    assert runtime_probe["runtime_probe_network_blocked_by_contract"] is True
    assert runtime_probe["runtime_probe_workspace_isolation_required"] is True
    assert runtime_probe["runtime_probe_receipt_contract_declared"] is True
    assert runtime_probe["runtime_probe_repo_execution_separated"] is True
    assert runtime_probe["runtime_probe_runner_bound"] is False
    assert runtime_probe["runtime_probe_sandbox_bound"] is False
    assert runtime_probe["runtime_probe_service_query_guard_bound"] is False
    assert runtime_probe["runtime_probe_output_capture_bound"] is False
    assert runtime_probe["runtime_probe_kill_switch_bound"] is False
    assert runtime_probe["provider_runtime_probe_performed"] is False
    assert runtime_probe["service_query_performed"] is False
    assert runtime_probe["process_launched"] is False
    assert runtime_probe["container_launched"] is False
    assert runtime_probe["sandbox_provider_bound"] is False
    assert runtime_probe["execution_authority"] is False
    assert runtime_probe["executed"] is False
    assert runtime_probe["repo_code_executed"] is False
    assert runtime_probe["network_accessed"] is False
    assert "runtime_probe_contract_declared" not in runtime_probe["missing_checks"]
    assert "runtime_probe_network_blocked_by_contract" not in runtime_probe["missing_checks"]
    assert "runtime_probe_receipt_contract_declared" not in runtime_probe["missing_checks"]
    assert "runtime_probe_runner_bound" in runtime_probe["missing_checks"]
    assert "provider_runtime_probe_performed" in runtime_probe["missing_checks"]
    assert "sandbox_provider_bound" in runtime_probe["missing_checks"]
    assert body["sandbox_provider_verifier"]["provider_binary_or_service_verified"] is True
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.preflight"
    assert Path(body["sandbox_provider_runtime_probe_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_api_denies_before_probe_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text('{"network": false, "execution": false}\n', encoding="utf-8")
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    probes_before = _sandbox_provider_runtime_probe_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_count(data_root) == probes_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_harness_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-harness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_HARNESS_ACTOR,
        },
    )
    body = response.json()
    harness = body["sandbox_provider_runtime_probe_harness"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_harness"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert harness["harness_kind"] == "francis.lab.sandbox_provider_runtime_probe_harness_preflight"
    assert harness["harness_mode"] == "runtime_probe_harness_preflight_only_no_provider_execution"
    assert harness["runtime_probe_preflight_present"] is True
    assert harness["runtime_probe_contract_declared"] is True
    assert harness["runtime_probe_runner_contract_declared"] is True
    assert harness["runtime_probe_sandbox_contract_declared"] is True
    assert harness["runtime_probe_service_query_guard_declared"] is True
    assert harness["runtime_probe_output_capture_declared"] is True
    assert harness["runtime_probe_kill_switch_declared"] is True
    assert harness["runtime_probe_runner_bound"] is False
    assert harness["runtime_probe_sandbox_bound"] is False
    assert harness["runtime_probe_service_query_guard_bound"] is False
    assert harness["runtime_probe_output_capture_bound"] is False
    assert harness["runtime_probe_kill_switch_bound"] is False
    assert harness["provider_runtime_probe_performed"] is False
    assert harness["service_query_performed"] is False
    assert harness["process_launched"] is False
    assert harness["container_launched"] is False
    assert harness["sandbox_provider_bound"] is False
    assert harness["execution_authority"] is False
    assert harness["executed"] is False
    assert harness["repo_code_executed"] is False
    assert "runtime_probe_runner_contract_declared" not in harness["missing_checks"]
    assert "runtime_probe_runner_bound" in harness["missing_checks"]
    assert "runtime_probe_sandbox_bound" in harness["missing_checks"]
    assert "runtime_probe_service_query_guard_bound" in harness["missing_checks"]
    assert "provider_runtime_probe_performed" in harness["missing_checks"]
    assert body["sandbox_provider_runtime_probe"]["runtime_probe_contract_declared"] is True
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_harness.preflight"
    assert Path(body["sandbox_provider_runtime_probe_harness_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_harness_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_harness_api_denies_before_harness_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text('{"network": false, "execution": false}\n', encoding="utf-8")
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    harnesses_before = _sandbox_provider_runtime_probe_harness_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-harness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_harness"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_harness_count(data_root) == harnesses_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_readiness_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_READINESS_ACTOR,
        },
    )
    body = response.json()
    readiness = body["sandbox_provider_runtime_probe_runner_readiness"]
    harness = body["sandbox_provider_runtime_probe_harness"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_readiness"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert readiness["status"] == "blocked"
    assert readiness["runner_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_readiness"
    assert readiness["runner_mode"] == "probe_runner_interface_readiness_only_no_provider_execution"
    assert readiness["sandbox_provider_runtime_probe_harness_id"] == harness["id"]
    assert readiness["runtime_probe_harness_present"] is True
    assert readiness["runtime_probe_harness_contract_declared"] is True
    assert readiness["probe_runner_interface_declared"] is True
    assert readiness["probe_runner_implementation_bound"] is False
    assert readiness["probe_runner_identity_bound"] is False
    assert readiness["probe_runner_policy_bound"] is False
    assert readiness["probe_runner_sandbox_bound"] is False
    assert readiness["probe_runner_network_blocked"] is False
    assert readiness["probe_runner_workspace_isolated"] is False
    assert readiness["probe_runner_timeout_bound"] is False
    assert readiness["probe_runner_output_capture_bound"] is False
    assert readiness["probe_runner_kill_switch_bound"] is False
    assert readiness["probe_runner_receipt_contract_bound"] is False
    assert readiness["provider_runtime_probe_performed"] is False
    assert readiness["service_query_performed"] is False
    assert readiness["process_launched"] is False
    assert readiness["container_launched"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["repo_code_executed"] is False
    assert readiness["network_accessed"] is False
    assert "probe_runner_interface_declared" not in readiness["missing_checks"]
    assert "probe_runner_implementation_bound" in readiness["missing_checks"]
    assert "probe_runner_identity_bound" in readiness["missing_checks"]
    assert "probe_runner_sandbox_bound" in readiness["missing_checks"]
    assert "probe_runner_network_blocked" in readiness["missing_checks"]
    assert "probe_runner_workspace_isolated" in readiness["missing_checks"]
    assert "probe_runner_timeout_bound" in readiness["missing_checks"]
    assert "probe_runner_output_capture_bound" in readiness["missing_checks"]
    assert "probe_runner_kill_switch_bound" in readiness["missing_checks"]
    assert "probe_runner_receipt_contract_bound" in readiness["missing_checks"]
    assert "provider_runtime_probe_performed" in readiness["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_runner.readiness"
    assert Path(body["sandbox_provider_runtime_probe_runner_readiness_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_runner_readiness_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_readiness_api_denies_before_readiness_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text('{"network": false, "execution": false}\n', encoding="utf-8")
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    readiness_before = _sandbox_provider_runtime_probe_runner_readiness_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_readiness"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_runner_readiness_count(data_root) == readiness_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_binding_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_BINDING_ACTOR,
        },
    )
    body = response.json()
    binding = body["sandbox_provider_runtime_probe_runner_binding"]
    readiness = body["sandbox_provider_runtime_probe_runner_readiness"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert binding["status"] == "blocked"
    assert binding["runner_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight"
    assert binding["binding_mode"] == "probe_runner_binding_preflight_no_provider_execution"
    assert binding["sandbox_provider_runtime_probe_runner_readiness_id"] == readiness["id"]
    assert binding["runner_readiness_present"] is True
    assert binding["probe_runner_interface_declared"] is True
    assert binding["probe_runner_binding_contract_declared"] is True
    assert binding["probe_runner_readiness_ready"] is False
    assert binding["probe_runner_implementation_bound"] is False
    assert binding["probe_runner_identity_bound"] is False
    assert binding["probe_runner_policy_bound"] is False
    assert binding["probe_runner_sandbox_bound"] is False
    assert binding["probe_runner_network_blocked"] is False
    assert binding["probe_runner_workspace_isolated"] is False
    assert binding["probe_runner_timeout_bound"] is False
    assert binding["probe_runner_output_capture_bound"] is False
    assert binding["probe_runner_kill_switch_bound"] is False
    assert binding["probe_runner_receipt_contract_bound"] is False
    assert binding["probe_runner_bound"] is False
    assert binding["runtime_probe_bound"] is False
    assert binding["provider_runtime_probe_performed"] is False
    assert binding["service_query_performed"] is False
    assert binding["process_launched"] is False
    assert binding["container_launched"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert binding["repo_code_executed"] is False
    assert binding["network_accessed"] is False
    assert "probe_runner_binding_contract_declared" not in binding["missing_checks"]
    assert "probe_runner_readiness_ready" in binding["missing_checks"]
    assert "probe_runner_bound" in binding["missing_checks"]
    assert "runtime_probe_bound" in binding["missing_checks"]
    assert "provider_runtime_probe_performed" in binding["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_runner.binding_preflight"
    assert Path(body["sandbox_provider_runtime_probe_runner_binding_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_runner_binding_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_binding_api_denies_before_binding_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text('{"network": false, "execution": false}\n', encoding="utf-8")
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    bindings_before = _sandbox_provider_runtime_probe_runner_binding_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_runner_binding_count(data_root) == bindings_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_enforcement_api_reports_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-enforcement",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_ENFORCEMENT_ACTOR,
        },
    )
    body = response.json()
    enforcement = body["sandbox_provider_runtime_probe_runner_enforcement"]
    binding = body["sandbox_provider_runtime_probe_runner_binding"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_enforcement"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert enforcement["status"] == "blocked"
    assert enforcement["runner_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight"
    assert enforcement["enforcement_mode"] == "probe_runner_enforcement_preflight_no_provider_execution"
    assert enforcement["sandbox_provider_runtime_probe_runner_binding_id"] == binding["id"]
    assert enforcement["runner_binding_present"] is True
    assert enforcement["probe_runner_binding_contract_declared"] is True
    assert enforcement["probe_runner_enforcement_contract_declared"] is True
    assert enforcement["probe_runner_binding_ready"] is False
    assert enforcement["probe_runner_enforcement_bound"] is False
    assert enforcement["probe_runner_bound"] is False
    assert enforcement["runtime_probe_bound"] is False
    assert enforcement["probe_runner_identity_bound"] is False
    assert enforcement["probe_runner_policy_bound"] is False
    assert enforcement["probe_runner_sandbox_bound"] is False
    assert enforcement["probe_runner_network_blocked"] is False
    assert enforcement["probe_runner_workspace_isolated"] is False
    assert enforcement["probe_runner_timeout_bound"] is False
    assert enforcement["probe_runner_output_capture_bound"] is False
    assert enforcement["probe_runner_kill_switch_bound"] is False
    assert enforcement["probe_runner_receipt_contract_bound"] is False
    assert enforcement["provider_runtime_probe_performed"] is False
    assert enforcement["service_query_performed"] is False
    assert enforcement["process_launched"] is False
    assert enforcement["container_launched"] is False
    assert enforcement["execution_authority"] is False
    assert enforcement["executed"] is False
    assert enforcement["repo_code_executed"] is False
    assert enforcement["network_accessed"] is False
    assert "probe_runner_enforcement_contract_declared" not in enforcement["missing_checks"]
    assert "probe_runner_binding_ready" in enforcement["missing_checks"]
    assert "probe_runner_enforcement_bound" in enforcement["missing_checks"]
    assert "probe_runner_bound" in enforcement["missing_checks"]
    assert "runtime_probe_bound" in enforcement["missing_checks"]
    assert "provider_runtime_probe_performed" in enforcement["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_runner.enforcement_preflight"
    assert Path(body["sandbox_provider_runtime_probe_runner_enforcement_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_runner_enforcement_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_enforcement_api_denies_before_enforcement_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text('{"network": false, "execution": false}\n', encoding="utf-8")
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)
    enforcements_before = _sandbox_provider_runtime_probe_runner_enforcement_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-enforcement",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(policy_manifest),
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_enforcement"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_runner_enforcement_count(data_root) == enforcements_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_write_readiness_api_returns_blocked_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-write-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    readiness = body["execution_receipt_write_readiness"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_write_readiness"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert readiness["reserved_execution_receipt"]["id"]
    assert readiness["current_checks"]["reserved_execution_receipt_not_written"] is True
    assert readiness["current_checks"]["receipt_prewrite_writer_bound"] is False
    assert readiness["current_checks"]["receipt_final_writer_bound"] is False
    assert readiness["prewrite_bound"] is False
    assert readiness["final_write_bound"] is False
    assert readiness["execution_receipt_prewritten"] is False
    assert readiness["execution_receipt_finalized"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert "receipt_prewrite_writer_bound" in readiness["missing_checks"]
    assert "receipt_final_writer_bound" in readiness["missing_checks"]
    assert body["runner_sandbox_readiness"]["sandbox_bound"] is False
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.execution.receipt_write_readiness.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_write_readiness_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-write-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_write_readiness"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_prewrite_binding_api_returns_contract_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-prewrite-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    binding = body["execution_receipt_prewrite_binding"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_prewrite_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert binding["execution_receipt_schema"]["operation"] == "lab.execution.run"
    assert binding["prewrite_contract"]["writes_reserved_execution_receipt"] is False
    assert binding["final_write_contract"]["writes_reserved_execution_receipt"] is False
    assert binding["receipt_schema_bound"] is True
    assert binding["prewrite_contract_bound"] is True
    assert binding["final_write_contract_bound"] is True
    assert binding["prewrite_writer_bound"] is False
    assert binding["final_write_writer_bound"] is False
    assert binding["execution_receipt_prewritten"] is False
    assert binding["execution_receipt_finalized"] is False
    assert binding["approval_consumed"] is False
    assert binding["execution_authority"] is False
    assert "schema_contract_bound" not in binding["missing_checks"]
    assert "prewrite_writer_bound" in binding["missing_checks"]
    assert "final_writer_bound" in binding["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.execution.receipt_prewrite_binding.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_prewrite_binding_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-prewrite-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_prewrite_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_writer_preflight_api_returns_boundary_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-writer-preflight",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_ACTOR,
        },
    )
    body = response.json()
    writer = body["execution_receipt_writer_preflight"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_writer_preflight"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert writer["writer_contract"]["mode"] == "writer_preflight_only_no_execution_receipt_write"
    assert writer["writer_contract"]["writes_reserved_execution_receipt"] is False
    assert writer["writer_boundary"]["reserved_path_within_sink"] is True
    assert writer["writer_boundary"]["reserved_receipt_not_written"] is True
    assert writer["writer_boundary"]["writes_reserved_execution_receipt"] is False
    assert writer["writer_interface_declared"] is True
    assert writer["writer_implementation_bound"] is False
    assert writer["prewrite_writer_bound"] is False
    assert writer["final_write_writer_bound"] is False
    assert writer["execution_receipt_prewritten"] is False
    assert writer["execution_receipt_finalized"] is False
    assert writer["approval_consumed"] is False
    assert writer["execution_authority"] is False
    assert writer["prewrite_operation"]["performed"] is False
    assert writer["final_write_operation"]["performed"] is False
    assert "writer_implementation_bound" in writer["missing_checks"]
    assert "prewrite_writer_bound" in writer["missing_checks"]
    assert "final_writer_bound" in writer["missing_checks"]
    assert "reserved_execution_receipt_not_written" not in writer["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert body["receipt"]["operation"] == "lab.execution.receipt_writer.preflight"
    assert Path(body["artifact_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert not Path(body["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(body["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_execution_receipt_writer_preflight_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/execution-receipt-writer-preflight",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.execution_receipt_writer_preflight"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert body["execution"]["network_accessed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_synthetic_execution_receipt_api_prewrites_and_finalizes_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    prewrite_response = TestClient(create_app()).post(
        "/ingest/lab/synthetic-execution-receipt-prewrite",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RECEIPT_ACTOR,
        },
    )
    prewrite_body = prewrite_response.json()
    prewritten = prewrite_body["execution_receipt"]
    receipt_path = Path(prewrite_body["execution_receipt_path"])

    assert prewrite_response.status_code == 200
    assert prewrite_body["kind"] == "francis.ingest.lab.synthetic_execution_receipt_prewrite"
    assert prewrite_body["ok"] is True
    assert prewrite_body["status"] == "prewritten"
    assert prewritten["operation"] == "lab.execution.run"
    assert prewritten["mode"] == "synthetic_noop_execution_receipt"
    assert prewritten["synthetic"] is True
    assert prewritten["noop"] is True
    assert prewritten["prewritten"] is True
    assert prewritten["finalized"] is False
    assert prewritten["approval_consumed"] is False
    assert prewritten["execution_authority"] is False
    assert prewritten["executed"] is False
    assert prewritten["ran_repo_scripts"] is False
    assert prewritten["network_accessed"] is False
    assert prewrite_body["execution"]["executed"] is False
    assert prewrite_body["receipt"]["operation"] == "lab.execution.receipt.synthetic_prewrite"
    assert receipt_path.exists()
    assert receipt_path == Path(prewrite_body["reserved_execution_receipt"]["path"])
    assert "super-secret-token-value" not in receipt_path.read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()

    finalize_response = TestClient(create_app()).post(
        "/ingest/lab/synthetic-execution-receipt-finalize",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RECEIPT_ACTOR,
        },
    )
    finalize_body = finalize_response.json()
    finalized = finalize_body["execution_receipt"]

    assert finalize_response.status_code == 200
    assert finalize_body["kind"] == "francis.ingest.lab.synthetic_execution_receipt_finalize"
    assert finalize_body["ok"] is True
    assert finalize_body["status"] == "blocked"
    assert finalized["id"] == prewritten["id"]
    assert finalized["phase"] == "finalize"
    assert finalized["status"] == "blocked"
    assert finalized["result_status"] == "blocked"
    assert finalized["finalized"] is True
    assert finalized["approval_consumed"] is False
    assert finalized["execution_authority"] is False
    assert finalized["executed"] is False
    assert finalized["ran_repo_scripts"] is False
    assert finalized["network_accessed"] is False
    assert finalize_body["execution"]["executed"] is False
    assert finalize_body["receipt"]["operation"] == "lab.execution.receipt.synthetic_finalize"
    assert Path(finalize_body["execution_receipt_path"]) == receipt_path
    assert receipt_path.exists()
    assert "super-secret-token-value" not in receipt_path.read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_synthetic_execution_receipt_api_denies_before_receipt_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    receipts_before = _receipt_count(data_root)
    execution_receipts_before = _execution_receipt_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/synthetic-execution-receipt-prewrite",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": "test.ingest.lab.denied",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.synthetic_execution_receipt_prewrite"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _execution_receipt_count(data_root) == execution_receipts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_approval_consume_synthetic_noop_api_enforces_single_use_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/approval-consume-synthetic-noop",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_APPROVAL_CONSUME_ACTOR,
        },
    )
    body = response.json()
    record = body["approval_consumption_record"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.approval_consume_synthetic_noop"
    assert body["ok"] is True
    assert body["status"] == "consumed"
    assert record["approval_consumed"] is True
    assert record["single_use_enforced"] is True
    assert record["execution_authority"] is False
    assert record["executed"] is False
    assert record["ran_repo_scripts"] is False
    assert record["network_accessed"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.execution.approval.consume_synthetic_noop"
    assert Path(body["approval_consumption_record_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()

    reuse = service.preflight_lab_approval_consumption(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    assert reuse["status"] == "refused"
    assert reuse["approval_consumption"]["binding"]["approval_consumed"] is True
    assert reuse["approval_consumption"]["binding"]["approval_consumption_record_id"] == record["id"]
    assert "approval_already_consumed" in reuse["approval_consumption"]["blockers"]
    assert reuse["execution"]["executed"] is False
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_approval_consume_synthetic_noop_api_denies_before_consumption_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    consumptions_before = _approval_consumption_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/approval-consume-synthetic-noop",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RECEIPT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.approval_consume_synthetic_noop"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _approval_consumption_count(data_root) == consumptions_before
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_noop_runner_envelope_api_completes_builtin_noop_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    consumption = service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/noop-runner-envelope",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_NOOP_RUNNER_ACTOR,
        },
    )
    body = response.json()
    envelope = body["noop_runner_envelope"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.noop_runner_envelope"
    assert body["ok"] is True
    assert body["status"] == "completed"
    assert envelope["approval_consumption_record_id"] == consumption["approval_consumption_record"]["id"]
    assert envelope["noop_performed"] is True
    assert envelope["approval_consumed"] is True
    assert envelope["execution_authority"] is False
    assert envelope["executed"] is False
    assert envelope["commands_executed"] is False
    assert envelope["repo_code_executed"] is False
    assert envelope["network_accessed"] is False
    assert body["execution"]["builtin_noop_performed"] is True
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.runner.noop_envelope"
    assert Path(body["noop_runner_envelope_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_noop_runner_envelope_api_denies_before_envelope_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    envelopes_before = _noop_runner_envelope_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/noop-runner-envelope",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_APPROVAL_CONSUME_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.noop_runner_envelope"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _noop_runner_envelope_count(data_root) == envelopes_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_noop_runner_transcript_api_records_empty_builtin_noop_output_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    envelope = service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/noop-runner-transcript",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_NOOP_RUNNER_TRANSCRIPT_ACTOR,
        },
    )
    body = response.json()
    transcript = body["noop_runner_transcript"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.noop_runner_transcript"
    assert body["ok"] is True
    assert body["status"] == "completed"
    assert transcript["noop_runner_envelope_id"] == envelope["noop_runner_envelope"]["id"]
    assert transcript["status"] == "completed"
    assert transcript["noop_performed"] is True
    assert transcript["builtin_noop_output_captured"] is True
    assert transcript["real_process_output_captured"] is False
    assert transcript["stdout"]["bytes"] == 0
    assert transcript["stderr"]["bytes"] == 0
    assert transcript["stdout_content_stored"] is False
    assert transcript["stderr_content_stored"] is False
    assert transcript["output_content_stored"] is False
    assert transcript["execution_authority"] is False
    assert transcript["executed"] is False
    assert transcript["commands_executed"] is False
    assert transcript["repo_code_executed"] is False
    assert transcript["network_accessed"] is False
    assert body["execution"]["builtin_noop_output_captured"] is True
    assert body["execution"]["real_process_output_captured"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.runner.noop_transcript"
    assert Path(body["noop_runner_transcript_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["noop_runner_transcript_path"]).read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_noop_runner_transcript_api_denies_before_transcript_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    transcripts_before = _noop_runner_transcript_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/noop-runner-transcript",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_NOOP_RUNNER_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.noop_runner_transcript"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _noop_runner_transcript_count(data_root) == transcripts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_noop_runner_identity_binding_api_records_builtin_identity_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    transcript = service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/noop-runner-identity-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_NOOP_RUNNER_IDENTITY_ACTOR,
        },
    )
    body = response.json()
    identity = body["noop_runner_identity_binding"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.noop_runner_identity_binding"
    assert body["ok"] is True
    assert body["status"] == "completed"
    assert identity["noop_runner_transcript_id"] == transcript["noop_runner_transcript"]["id"]
    assert identity["runner_id"] == "francis.lab.runner.builtin_noop.v0"
    assert identity["runner_identity_bound"] is True
    assert identity["builtin_noop_only"] is True
    assert identity["live_runner_bound"] is False
    assert identity["sandbox_runner_bound"] is False
    assert identity["execution_authority"] is False
    assert identity["executed"] is False
    assert identity["commands_executed"] is False
    assert identity["repo_code_executed"] is False
    assert identity["network_accessed"] is False
    assert identity["real_process_output_captured"] is False
    assert identity["candidate_validated"] is False
    assert identity["capability_promoted"] is False
    assert body["execution"]["builtin_noop_runner_identity_bound"] is True
    assert body["execution"]["live_runner_bound"] is False
    assert body["execution"]["sandbox_runner_bound"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.runner.noop_identity_bind"
    assert Path(body["noop_runner_identity_binding_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["noop_runner_identity_binding_path"]).read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_noop_runner_identity_binding_api_denies_before_identity_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    identities_before = _noop_runner_identity_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/noop-runner-identity-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_NOOP_RUNNER_TRANSCRIPT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.noop_runner_identity_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _noop_runner_identity_count(data_root) == identities_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_source_mount_readiness_api_records_reference_only_boundary_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    identity = service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/source-mount-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SOURCE_MOUNT_READINESS_ACTOR,
        },
    )
    body = response.json()
    readiness = body["source_mount_readiness"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.source_mount_readiness"
    assert body["ok"] is True
    assert body["status"] == "ready"
    assert readiness["noop_runner_identity_binding_id"] == identity["noop_runner_identity_binding"]["id"]
    assert readiness["workspace"]["source_reference"]["mode"] == "reference_only_read_only"
    assert readiness["source_mount_mode"] == "reference_only_read_only"
    assert readiness["source_reference_ready"] is True
    assert readiness["read_only_reference_confirmed"] is True
    assert readiness["read_only_mount_bound"] is False
    assert readiness["source_mount_enforced"] is False
    assert readiness["source_copied"] is False
    assert readiness["source_write_allowed"] is False
    assert readiness["runner_identity_verified"] is True
    assert readiness["live_runner_bound"] is False
    assert readiness["sandbox_runner_bound"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["commands_executed"] is False
    assert readiness["repo_code_executed"] is False
    assert readiness["network_accessed"] is False
    assert readiness["candidate_validated"] is False
    assert readiness["capability_promoted"] is False
    assert body["execution"]["source_mount_ready"] is True
    assert body["execution"]["read_only_mount_bound"] is False
    assert body["execution"]["source_mount_enforced"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.source_mount.readiness"
    assert Path(body["source_mount_readiness_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["source_mount_readiness_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_source_mount_contract_api_records_future_read_only_contract_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/source-mount-contract",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SOURCE_MOUNT_CONTRACT_ACTOR,
        },
    )
    body = response.json()
    contract = body["source_mount_contract"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.source_mount_contract"
    assert body["ok"] is True
    assert body["status"] == "ready"
    assert contract["status"] == "ready"
    assert contract["contract_kind"] == "francis.lab.source_mount_contract"
    assert contract["contract_mode"] == "contract_only_no_live_mount"
    assert contract["mount_mode"] == "future_read_only_source_mount"
    assert contract["contract_declared"] is True
    assert contract["source_mount_contract"]["allowed_read_roots"] == [source["canonical_path"]]
    assert contract["source_mount_contract"]["denied_write_roots"] == [source["canonical_path"]]
    assert contract["live_mount_bound"] is False
    assert contract["mount_enforced"] is False
    assert contract["read_only_mount_bound"] is False
    assert contract["source_copied"] is False
    assert contract["source_write_allowed"] is False
    assert contract["live_runner_bound"] is False
    assert contract["sandbox_runner_bound"] is False
    assert contract["execution_authority"] is False
    assert contract["executed"] is False
    assert contract["commands_executed"] is False
    assert contract["repo_code_executed"] is False
    assert contract["network_accessed"] is False
    assert contract["candidate_validated"] is False
    assert contract["capability_promoted"] is False
    assert body["execution"]["source_mount_contract_recorded"] is True
    assert body["execution"]["source_mount_contract_declared"] is True
    assert body["execution"]["live_mount_bound"] is False
    assert body["execution"]["mount_enforced"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.source_mount.contract"
    assert Path(body["source_mount_contract_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["source_mount_contract_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_run_boundary_preflight_api_reports_blocked_controls_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/run-boundary-preflight",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()
    boundary = body["run_boundary_preflight"]
    provider_contract = body["sandbox_provider_contract"]
    provider_binding = body["sandbox_provider_binding"]
    provider_selection = body["sandbox_provider_selection"]
    provider_verifier = body["sandbox_provider_verifier"]
    provider_runtime_probe = body["sandbox_provider_runtime_probe"]
    provider_runtime_probe_harness = body["sandbox_provider_runtime_probe_harness"]
    provider_runtime_probe_runner_enforcement = body["sandbox_provider_runtime_probe_runner_enforcement"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.run_boundary_preflight"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert boundary["status"] == "blocked"
    assert boundary["boundary_kind"] == "francis.lab.run_boundary_preflight"
    assert boundary["boundary_mode"] == "preflight_only_no_execution"
    assert boundary["run_mode"] == "future_sandboxed_rebuild_run_test"
    assert boundary["source_mount_contract_declared"] is True
    assert boundary["sandbox_provider_contract_id"] == provider_contract["id"]
    assert boundary["sandbox_provider_binding_id"] == provider_binding["id"]
    assert boundary["sandbox_provider_selection_id"] == provider_selection["id"]
    assert boundary["sandbox_provider_verifier_id"] == provider_verifier["id"]
    assert boundary["sandbox_provider_runtime_probe_id"] == provider_runtime_probe["id"]
    assert boundary["sandbox_provider_runtime_probe_harness_id"] == provider_runtime_probe_harness["id"]
    assert (
        boundary["sandbox_provider_runtime_probe_runner_enforcement_id"]
        == provider_runtime_probe_runner_enforcement["id"]
    )
    assert boundary["sandbox_provider_contract_declared"] is True
    assert boundary["sandbox_provider_binding_ready"] is False
    assert boundary["sandbox_provider_selection_ready"] is False
    assert boundary["sandbox_provider_verifier_ready"] is False
    assert boundary["sandbox_provider_runtime_probe_ready"] is False
    assert boundary["sandbox_provider_runtime_probe_harness_ready"] is False
    assert boundary["sandbox_provider_runtime_probe_runner_enforcement_ready"] is False
    assert boundary["runtime_probe_harness_contract_declared"] is True
    assert boundary["runtime_probe_runner_enforcement_contract_declared"] is True
    assert boundary["runtime_probe_runner_enforcement_bound"] is False
    assert boundary["runtime_probe_runner_bound"] is False
    assert boundary["runtime_probe_sandbox_bound"] is False
    assert boundary["runtime_probe_service_query_guard_bound"] is False
    assert boundary["runtime_probe_output_capture_bound"] is False
    assert boundary["runtime_probe_kill_switch_bound"] is False
    assert boundary["provider_runtime_probe_performed"] is False
    assert boundary["sandbox_provider_bound"] is False
    assert boundary["read_only_mount_bound"] is False
    assert boundary["mount_enforced"] is False
    assert boundary["sandbox_bound"] is False
    assert boundary["sandbox_enforced"] is False
    assert boundary["command_allowlist_enforced"] is False
    assert boundary["writer_implementation_bound"] is False
    assert boundary["receipt_prewrite_bound"] is False
    assert boundary["receipt_final_write_bound"] is False
    assert boundary["execution_authority"] is False
    assert boundary["executed"] is False
    assert boundary["commands_executed"] is False
    assert boundary["repo_code_executed"] is False
    assert boundary["network_accessed"] is False
    assert "read_only_mount_bound" in boundary["missing_checks"]
    assert "sandbox_provider_contract_ready" in boundary["missing_checks"]
    assert "sandbox_provider_binding_ready" in boundary["missing_checks"]
    assert "sandbox_provider_selection_ready" in boundary["missing_checks"]
    assert "sandbox_provider_verifier_ready" in boundary["missing_checks"]
    assert "sandbox_provider_runtime_probe_ready" in boundary["missing_checks"]
    assert "sandbox_provider_runtime_probe_harness_ready" in boundary["missing_checks"]
    assert "sandbox_provider_runtime_probe_runner_enforcement_ready" in boundary["missing_checks"]
    assert "runtime_probe_harness_contract_declared" not in boundary["missing_checks"]
    assert "runtime_probe_runner_enforcement_contract_declared" not in boundary["missing_checks"]
    assert "runtime_probe_runner_enforcement_bound" in boundary["missing_checks"]
    assert "runtime_probe_runner_bound" in boundary["missing_checks"]
    assert "runtime_probe_sandbox_bound" in boundary["missing_checks"]
    assert "runtime_probe_service_query_guard_bound" in boundary["missing_checks"]
    assert "runtime_probe_output_capture_bound" in boundary["missing_checks"]
    assert "runtime_probe_kill_switch_bound" in boundary["missing_checks"]
    assert "provider_runtime_probe_performed" in boundary["missing_checks"]
    assert "provider_kind_selected" in boundary["missing_checks"]
    assert "verifier_implementation_bound" not in boundary["missing_checks"]
    assert "verifier_identity_bound" not in boundary["missing_checks"]
    assert "provider_binary_or_service_verified" in boundary["missing_checks"]
    assert "sandbox_provider_bound" in boundary["missing_checks"]
    assert "sandbox_bound" in boundary["missing_checks"]
    assert "command_allowlist_enforced" in boundary["missing_checks"]
    assert "writer_implementation_bound" in boundary["missing_checks"]
    assert body["execution"]["run_boundary_preflight_recorded"] is True
    assert body["execution"]["run_boundary_ready"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.run_boundary.preflight"
    assert Path(body["run_boundary_preflight_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["run_boundary_preflight_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_execution_boundary_api_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-execution-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_EXECUTION_BOUNDARY_ACTOR,
        },
    )
    body = response.json()
    boundary = body["sandbox_provider_runtime_probe_execution_boundary"]
    run_boundary = body["run_boundary_preflight"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_execution_boundary"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert boundary["status"] == "blocked"
    assert boundary["boundary_kind"] == "francis.lab.sandbox_provider_runtime_probe_execution_boundary"
    assert boundary["boundary_mode"] == "execution_boundary_preflight_only_no_provider_execution"
    assert boundary["probe_mode"] == "future_sandbox_provider_runtime_probe"
    assert boundary["run_boundary_preflight_id"] == run_boundary["id"]
    assert boundary["run_boundary_present"] is True
    assert boundary["run_boundary_ready"] is False
    assert boundary["runtime_probe_runner_enforcement_present"] is True
    assert boundary["runtime_probe_runner_enforcement_ready"] is False
    assert boundary["runtime_probe_runner_enforcement_bound"] is False
    assert boundary["runtime_probe_runner_bound"] is False
    assert boundary["runtime_probe_bound"] is False
    assert boundary["provider_probe_execution_boundary_declared"] is True
    assert boundary["provider_probe_execution_boundary_bound"] is False
    assert boundary["provider_runtime_probe_performed"] is False
    assert boundary["execution_receipt_writer_bound"] is False
    assert boundary["sandbox_bound"] is False
    assert boundary["sandbox_enforced"] is False
    assert boundary["network_blocked_or_policy_bound"] is True
    assert boundary["workspace_isolated"] is False
    assert boundary["timeout_policy_bound"] is False
    assert boundary["kill_switch_bound"] is False
    assert boundary["output_capture_bound"] is False
    assert boundary["approval_not_consumed"] is True
    assert boundary["execution_authority_absent"] is True
    assert boundary["provider_binary_not_executed"] is True
    assert boundary["service_query_not_performed"] is True
    assert boundary["process_not_launched"] is True
    assert boundary["container_not_launched"] is True
    assert boundary["repo_code_not_executed"] is True
    assert boundary["network_not_accessed"] is True
    assert boundary["repo_write_not_performed"] is True
    assert boundary["execution_receipt_not_written"] is True
    assert boundary["execution_authority"] is False
    assert boundary["executed"] is False
    assert boundary["service_query_performed"] is False
    assert boundary["process_launched"] is False
    assert boundary["container_launched"] is False
    assert boundary["repo_code_executed"] is False
    assert boundary["network_accessed"] is False
    assert boundary["wrote_to_repo"] is False
    assert boundary["execution_receipt_written"] is False
    assert "provider_probe_execution_boundary_declared" not in boundary["missing_checks"]
    assert "run_boundary_ready" in boundary["missing_checks"]
    assert "runtime_probe_runner_enforcement_ready" in boundary["missing_checks"]
    assert "runtime_probe_runner_enforcement_bound" in boundary["missing_checks"]
    assert "runtime_probe_bound" in boundary["missing_checks"]
    assert "provider_probe_execution_boundary_bound" in boundary["missing_checks"]
    assert "provider_runtime_probe_performed" in boundary["missing_checks"]
    assert "execution_receipt_writer_bound" in boundary["missing_checks"]
    assert "sandbox_bound" in boundary["missing_checks"]
    assert "network_blocked_or_policy_bound" not in boundary["missing_checks"]
    assert "approval_not_consumed" not in boundary["missing_checks"]
    assert "provider_binary_not_executed" not in boundary["missing_checks"]
    assert "execution_receipt_not_written" not in boundary["missing_checks"]
    assert body["execution"]["provider_runtime_probe_execution_boundary_recorded"] is True
    assert body["execution"]["provider_runtime_probe_execution_boundary_ready"] is False
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.execution_boundary"
    assert Path(body["sandbox_provider_runtime_probe_execution_boundary_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_execution_boundary_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_refuse_api_writes_refusal_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-refuse",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_REFUSAL_ACTOR,
        },
    )
    body = response.json()
    refusal = body["sandbox_provider_runtime_probe_refusal"]
    boundary = body["sandbox_provider_runtime_probe_execution_boundary"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_refusal"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert refusal["status"] == "blocked"
    assert refusal["refusal_kind"] == "francis.lab.sandbox_provider_runtime_probe_refusal"
    assert refusal["refusal_mode"] == "refusal_only_no_provider_execution"
    assert refusal["execution_boundary_id"] == boundary["id"]
    assert refusal["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.refuse"
    assert refusal["provider_runtime_probe_performed"] is False
    assert refusal["provider_binary_executed"] is False
    assert refusal["service_query_performed"] is False
    assert refusal["process_launched"] is False
    assert refusal["container_launched"] is False
    assert refusal["repo_code_executed"] is False
    assert refusal["network_accessed"] is False
    assert refusal["wrote_to_repo"] is False
    assert refusal["execution_receipt_written"] is False
    assert refusal["approval_consumed"] is False
    assert "sandbox_provider_runtime_probe_refused_in_v0" in refusal["blockers"]
    assert "no_governed_provider_probe_runner_bound" in refusal["blockers"]
    assert body["execution"]["provider_runtime_probe_execution_boundary_recorded"] is True
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["execution_receipt_written"] is False
    assert body["execution"]["approval_consumed"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.refuse"
    assert Path(body["sandbox_provider_runtime_probe_refusal_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_refusal_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_request_approval_api_writes_request_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-request-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_REQUEST_ACTOR,
        },
    )
    body = response.json()
    approval_request = body["sandbox_provider_runtime_probe_approval_request"]
    boundary = body["sandbox_provider_runtime_probe_execution_boundary"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_approval_request"
    assert body["ok"] is True
    assert body["status"] == "needs_approval"
    assert approval_request["status"] == "needs_approval"
    assert approval_request["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert approval_request["approval_created"] is True
    assert approval_request["approval_id"] == body["approval"]["id"]
    assert approval_request["upstream_approval_id"] == approval_id
    assert approval_request["execution_boundary_id"] == boundary["id"]
    assert approval_request["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.request_approval"
    assert approval_request["approval_consumed"] is False
    assert approval_request["upstream_approval_consumed"] is False
    assert approval_request["execution_authority"] is False
    assert approval_request["executed"] is False
    assert approval_request["provider_runtime_probe_performed"] is False
    assert approval_request["provider_binary_executed"] is False
    assert approval_request["service_query_performed"] is False
    assert approval_request["process_launched"] is False
    assert approval_request["container_launched"] is False
    assert approval_request["repo_code_executed"] is False
    assert approval_request["network_accessed"] is False
    assert approval_request["wrote_to_repo"] is False
    assert approval_request["execution_receipt_written"] is False
    assert "sandbox_provider_runtime_probe_requires_operator_approval" in approval_request["blockers"]
    assert body["approval"]["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert body["execution"]["approval_request_created"] is True
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["execution_receipt_written"] is False
    assert body["execution"]["approval_consumed"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.approval_request"
    assert Path(body["sandbox_provider_runtime_probe_approval_request_path"]).exists()
    assert Path(body["approval_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_approval_request_path"]).read_text(encoding="utf-8")
    approval_text = Path(body["approval_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert "super-secret-token-value" not in approval_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_consume_approval_api_writes_consumption_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-consume-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_APPROVAL_CONSUME_ACTOR,
        },
    )
    body = response.json()
    consumption = body["sandbox_provider_runtime_probe_approval_consumption"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_approval_consume"
    assert body["ok"] is True
    assert body["status"] == "consumed"
    assert consumption["status"] == "consumed"
    assert consumption["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert consumption["approval_id"] == provider_probe_approval_id
    assert (
        consumption["approval_request_id"]
        == approval_request_result["sandbox_provider_runtime_probe_approval_request"]["id"]
    )
    assert consumption["approval_status"] == "approved"
    assert consumption["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.consume_approval"
    assert consumption["approval_consumed"] is True
    assert consumption["single_use_enforced"] is True
    assert consumption["upstream_approval_consumed"] is False
    assert consumption["execution_authority"] is False
    assert consumption["executed"] is False
    assert consumption["provider_runtime_probe_performed"] is False
    assert consumption["provider_binary_executed"] is False
    assert consumption["service_query_performed"] is False
    assert consumption["process_launched"] is False
    assert consumption["container_launched"] is False
    assert consumption["repo_code_executed"] is False
    assert consumption["network_accessed"] is False
    assert consumption["wrote_to_repo"] is False
    assert consumption["execution_receipt_written"] is False
    assert body["approval_binding"]["exact_match"] is True
    assert body["approval_binding"]["approval_consumed"] is False
    assert body["execution"]["approval_consumed"] is True
    assert body["execution"]["provider_runtime_probe_approval_consumed"] is True
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["execution_receipt_written"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.approval.consume"
    assert Path(body["sandbox_provider_runtime_probe_approval_consumption_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_approval_consumption_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_consume_approval_api_denies_before_consumption_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    receipts_before = _receipt_count(data_root)
    consumptions_before = _sandbox_provider_runtime_probe_approval_consumption_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-consume-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_approval_consume"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_approval_consumption_count(data_root) == consumptions_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_invocation_boundary_api_writes_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    consumption_result = service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-invocation-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_INVOCATION_BOUNDARY_ACTOR,
        },
    )
    body = response.json()
    invocation = body["sandbox_provider_runtime_probe_invocation_boundary"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_invocation_boundary"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert invocation["status"] == "blocked"
    assert invocation["boundary_kind"] == "francis.lab.sandbox_provider_runtime_probe_invocation_boundary"
    assert invocation["boundary_mode"] == "invocation_boundary_preflight_only_no_provider_execution"
    assert invocation["approval_id"] == provider_probe_approval_id
    assert (
        invocation["approval_consumption_id"]
        == consumption_result["sandbox_provider_runtime_probe_approval_consumption"]["id"]
    )
    assert invocation["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.invocation_boundary"
    assert invocation["approval_consumed"] is True
    assert invocation["single_use_consumption_found"] is True
    assert invocation["single_use_enforced"] is True
    assert invocation["exact_action_binding_verified"] is True
    assert invocation["execution_boundary_present"] is True
    assert invocation["execution_boundary_recorded"] is True
    assert invocation["execution_boundary_ready"] is False
    assert invocation["provider_probe_execution_boundary_bound"] is False
    assert invocation["probe_runner_bound"] is False
    assert invocation["probe_runner_policy_bound"] is False
    assert invocation["probe_runner_sandbox_bound"] is False
    assert invocation["probe_runner_timeout_bound"] is False
    assert invocation["probe_runner_output_capture_bound"] is False
    assert invocation["probe_runner_kill_switch_bound"] is False
    assert invocation["probe_runner_receipt_writer_bound"] is False
    assert invocation["execution_authority"] is False
    assert invocation["executed"] is False
    assert invocation["provider_runtime_probe_performed"] is False
    assert invocation["provider_binary_executed"] is False
    assert invocation["service_query_performed"] is False
    assert invocation["process_launched"] is False
    assert invocation["container_launched"] is False
    assert invocation["repo_code_executed"] is False
    assert invocation["network_accessed"] is False
    assert invocation["wrote_to_repo"] is False
    assert invocation["execution_receipt_written"] is False
    assert "probe_runner_bound" in invocation["missing_checks"]
    assert "probe_runner_receipt_writer_bound" in invocation["missing_checks"]
    assert "provider_runtime_probe_invocation_blocked_until_governed_runner_bound" in invocation["blockers"]
    assert body["execution"]["provider_runtime_probe_invocation_boundary_recorded"] is True
    assert body["execution"]["provider_runtime_probe_invocation_boundary_ready"] is False
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["execution_receipt_written"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.invocation_boundary"
    assert Path(body["sandbox_provider_runtime_probe_invocation_boundary_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_invocation_boundary_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_invocation_boundary_api_denies_before_boundary_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    boundaries_before = _sandbox_provider_runtime_probe_invocation_boundary_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-invocation-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_invocation_boundary"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_invocation_boundary_count(data_root) == boundaries_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_api_writes_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    consumption_result = service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    invocation_result = service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-pre-execution-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_PRE_EXECUTION_BOUNDARY_ACTOR,
        },
    )
    body = response.json()
    pre_execution = body["sandbox_provider_runtime_probe_runner_pre_execution_boundary"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert pre_execution["status"] == "blocked"
    assert pre_execution["boundary_kind"] == (
        "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    )
    assert pre_execution["boundary_mode"] == "runner_pre_execution_boundary_no_provider_execution"
    assert pre_execution["pre_execution_mode"] == "future_sandbox_provider_runtime_probe_runner_pre_execution"
    assert pre_execution["approval_id"] == provider_probe_approval_id
    assert (
        pre_execution["approval_consumption_id"]
        == consumption_result["sandbox_provider_runtime_probe_approval_consumption"]["id"]
    )
    assert (
        pre_execution["invocation_boundary_id"]
        == invocation_result["sandbox_provider_runtime_probe_invocation_boundary"]["id"]
    )
    assert (
        pre_execution["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
    )
    assert pre_execution["invocation_boundary_found"] is True
    assert pre_execution["invocation_boundary_recorded"] is True
    assert pre_execution["invocation_boundary_ready"] is False
    assert pre_execution["approval_consumed"] is True
    assert pre_execution["single_use_consumption_found"] is True
    assert pre_execution["single_use_enforced"] is True
    assert pre_execution["exact_action_binding_verified"] is True
    assert pre_execution["runner_identity_declared"] is True
    assert pre_execution["runner_identity_bound"] is False
    assert pre_execution["runner_policy_declared"] is True
    assert pre_execution["runner_policy_bound"] is False
    assert pre_execution["sandbox_policy_declared"] is True
    assert pre_execution["sandbox_policy_bound"] is False
    assert pre_execution["network_block_declared"] is True
    assert pre_execution["network_block_bound"] is False
    assert pre_execution["timeout_policy_declared"] is True
    assert pre_execution["timeout_policy_bound"] is False
    assert pre_execution["output_capture_declared"] is True
    assert pre_execution["output_capture_bound"] is False
    assert pre_execution["kill_switch_declared"] is True
    assert pre_execution["kill_switch_bound"] is False
    assert pre_execution["execution_receipt_writer_declared"] is True
    assert pre_execution["execution_receipt_writer_bound"] is False
    assert pre_execution["execution_authority"] is False
    assert pre_execution["executed"] is False
    assert pre_execution["provider_runtime_probe_performed"] is False
    assert pre_execution["provider_binary_executed"] is False
    assert pre_execution["service_query_performed"] is False
    assert pre_execution["process_launched"] is False
    assert pre_execution["container_launched"] is False
    assert pre_execution["repo_code_executed"] is False
    assert pre_execution["network_accessed"] is False
    assert pre_execution["wrote_to_repo"] is False
    assert pre_execution["execution_receipt_written"] is False
    assert "runner_identity_bound" in pre_execution["missing_checks"]
    assert "runner_policy_bound" in pre_execution["missing_checks"]
    assert "sandbox_policy_bound" in pre_execution["missing_checks"]
    assert "network_block_bound" in pre_execution["missing_checks"]
    assert "execution_receipt_writer_bound" in pre_execution["missing_checks"]
    assert (
        "provider_runtime_probe_runner_pre_execution_boundary_blocked_until_live_runner_controls_bound"
        in pre_execution["blockers"]
    )
    assert body["execution"]["provider_runtime_probe_runner_pre_execution_boundary_recorded"] is True
    assert body["execution"]["provider_runtime_probe_runner_pre_execution_boundary_ready"] is False
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["execution_receipt_written"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
    assert Path(body["sandbox_provider_runtime_probe_runner_pre_execution_boundary_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_runner_pre_execution_boundary_path"]).read_text(
        encoding="utf-8"
    )
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary_api_denies_before_boundary_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    boundaries_before = _sandbox_provider_runtime_probe_runner_pre_execution_boundary_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-pre-execution-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_runner_pre_execution_boundary_count(data_root) == boundaries_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_control_binding_api_writes_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    pre_execution_result = service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-control-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_SANDBOX_PROVIDER_RUNTIME_PROBE_RUNNER_CONTROL_BINDING_ACTOR,
        },
    )
    body = response.json()
    control_binding = body["sandbox_provider_runtime_probe_runner_control_binding"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_control_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert control_binding["status"] == "blocked"
    assert control_binding["binding_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_control_binding"
    assert control_binding["binding_mode"] == "control_binding_preflight_only_no_provider_execution"
    assert control_binding["control_binding_mode"] == "future_sandbox_provider_runtime_probe_runner_control_binding"
    assert control_binding["approval_id"] == provider_probe_approval_id
    assert (
        control_binding["pre_execution_boundary_id"]
        == pre_execution_result["sandbox_provider_runtime_probe_runner_pre_execution_boundary"]["id"]
    )
    assert control_binding["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.runner_control_binding"
    assert control_binding["pre_execution_boundary_found"] is True
    assert control_binding["pre_execution_boundary_recorded"] is True
    assert control_binding["pre_execution_boundary_ready"] is False
    assert control_binding["approval_consumed"] is True
    assert control_binding["single_use_consumption_found"] is True
    assert control_binding["single_use_enforced"] is True
    assert control_binding["exact_action_binding_verified"] is True
    assert control_binding["control_binding_recorded"] is True
    assert control_binding["runner_identity_declared"] is True
    assert control_binding["runner_identity_binding_recorded"] is True
    assert control_binding["runner_identity_bound"] is False
    assert control_binding["runner_policy_binding_recorded"] is True
    assert control_binding["runner_policy_bound"] is False
    assert control_binding["sandbox_policy_binding_recorded"] is True
    assert control_binding["sandbox_policy_bound"] is False
    assert control_binding["sandbox_bound"] is False
    assert control_binding["sandbox_enforced"] is False
    assert control_binding["network_block_binding_recorded"] is True
    assert control_binding["network_block_bound"] is False
    assert control_binding["timeout_policy_binding_recorded"] is True
    assert control_binding["timeout_policy_bound"] is False
    assert control_binding["output_capture_binding_recorded"] is True
    assert control_binding["output_capture_bound"] is False
    assert control_binding["kill_switch_binding_recorded"] is True
    assert control_binding["kill_switch_bound"] is False
    assert control_binding["execution_receipt_writer_binding_recorded"] is True
    assert control_binding["execution_receipt_writer_bound"] is False
    assert control_binding["execution_authority"] is False
    assert control_binding["executed"] is False
    assert control_binding["provider_runtime_probe_performed"] is False
    assert control_binding["provider_binary_executed"] is False
    assert control_binding["service_query_performed"] is False
    assert control_binding["process_launched"] is False
    assert control_binding["container_launched"] is False
    assert control_binding["repo_code_executed"] is False
    assert control_binding["network_accessed"] is False
    assert control_binding["wrote_to_repo"] is False
    assert control_binding["execution_receipt_written"] is False
    assert "runner_identity_bound" in control_binding["missing_checks"]
    assert "network_block_bound" in control_binding["missing_checks"]
    assert "execution_receipt_writer_bound" in control_binding["missing_checks"]
    assert (
        "provider_runtime_probe_runner_control_binding_blocked_until_live_runner_enforced"
        in control_binding["blockers"]
    )
    assert body["execution"]["provider_runtime_probe_runner_control_binding_recorded"] is True
    assert body["execution"]["provider_runtime_probe_runner_control_binding_ready"] is False
    assert body["execution"]["provider_runtime_probe_performed"] is False
    assert body["execution"]["provider_binary_executed"] is False
    assert body["execution"]["provider_service_queried"] is False
    assert body["execution"]["process_launched"] is False
    assert body["execution"]["container_launched"] is False
    assert body["execution"]["execution_receipt_written"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.runner_control_binding"
    assert Path(body["sandbox_provider_runtime_probe_runner_control_binding_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandbox_provider_runtime_probe_runner_control_binding_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_runner_control_binding_api_denies_before_boundary_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    boundaries_before = _sandbox_provider_runtime_probe_runner_control_binding_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-runner-control-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_runner_control_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_runner_control_binding_count(data_root) == boundaries_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_boundary_api_writes_boundary_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    control_binding_result = service.preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_BOUNDARY_ACTOR,
        },
    )
    body = response.json()
    boundary = body["sandboxed_rebuild_run_test_boundary"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_boundary"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert boundary["status"] == "blocked"
    assert boundary["boundary_kind"] == "francis.lab.sandboxed_rebuild_run_test_boundary"
    assert boundary["boundary_mode"] == "sandboxed_rebuild_run_test_boundary_no_execution"
    assert boundary["run_mode"] == "future_sandboxed_rebuild_run_test"
    assert boundary["approval_id"] == provider_probe_approval_id
    assert (
        boundary["control_binding_id"]
        == control_binding_result["sandbox_provider_runtime_probe_runner_control_binding"]["id"]
    )
    assert boundary["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.boundary"
    assert boundary["control_binding_found"] is True
    assert boundary["control_binding_recorded"] is True
    assert boundary["control_binding_ready"] is False
    assert boundary["approval_consumed"] is True
    assert boundary["execution_approval_required"] is True
    assert boundary["execution_approval_consumed"] is False
    assert boundary["runner_identity_bound"] is False
    assert boundary["runner_policy_bound"] is False
    assert boundary["sandbox_policy_bound"] is False
    assert boundary["sandbox_bound"] is False
    assert boundary["sandbox_enforced"] is False
    assert boundary["network_block_bound"] is False
    assert boundary["timeout_policy_bound"] is False
    assert boundary["output_capture_bound"] is False
    assert boundary["kill_switch_bound"] is False
    assert boundary["execution_receipt_writer_bound"] is False
    assert boundary["rebuild_declared"] is True
    assert boundary["run_declared"] is True
    assert boundary["test_declared"] is True
    assert boundary["execution_authority"] is False
    assert boundary["executed"] is False
    assert boundary["process_launched"] is False
    assert boundary["container_launched"] is False
    assert boundary["commands_executed"] is False
    assert boundary["repo_code_executed"] is False
    assert boundary["ran_install"] is False
    assert boundary["ran_build"] is False
    assert boundary["ran_tests"] is False
    assert boundary["network_accessed"] is False
    assert boundary["wrote_to_repo"] is False
    assert boundary["execution_receipt_written"] is False
    assert boundary["candidate_validated"] is False
    assert boundary["capability_promoted"] is False
    assert "control_binding_ready" in boundary["missing_checks"]
    assert "execution_approval_consumed" in boundary["missing_checks"]
    assert "runner_identity_bound" in boundary["missing_checks"]
    assert "sandbox_enforced" in boundary["missing_checks"]
    assert "sandboxed_rebuild_run_test_boundary_blocked_until_live_runner_enforced" in boundary["blockers"]
    assert body["execution"]["sandboxed_rebuild_run_test_boundary_recorded"] is True
    assert body["execution"]["sandboxed_rebuild_run_test_boundary_ready"] is False
    assert body["execution"]["execution_approval_required"] is True
    assert body["execution"]["execution_approval_consumed"] is False
    assert body["execution"]["ran_install"] is False
    assert body["execution"]["ran_build"] is False
    assert body["execution"]["ran_tests"] is False
    assert body["execution"]["repo_code_executed"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.boundary"
    assert Path(body["sandboxed_rebuild_run_test_boundary_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandboxed_rebuild_run_test_boundary_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_boundary_api_denies_before_boundary_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    boundaries_before = _sandboxed_rebuild_run_test_boundary_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_boundary"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandboxed_rebuild_run_test_boundary_count(data_root) == boundaries_before
    assert not (repo / "lab-ran.txt").exists()


def _prepare_api_sandboxed_rebuild_run_test_boundary(
    tmp_path: Path,
) -> tuple[Path, dict[str, Any], str, dict[str, Any]]:
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    boundary_result = service.preflight_lab_sandboxed_rebuild_run_test_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    return repo, source, provider_probe_approval_id, boundary_result["sandboxed_rebuild_run_test_boundary"]


def test_ingest_lab_sandboxed_rebuild_run_test_request_approval_api_writes_request_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, provider_probe_approval_id, boundary = _prepare_api_sandboxed_rebuild_run_test_boundary(tmp_path)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-request-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_REQUEST_ACTOR,
        },
    )
    body = response.json()
    approval_request = body["sandboxed_rebuild_run_test_approval_request"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_approval_request"
    assert body["ok"] is True
    assert body["status"] == "needs_approval"
    assert approval_request["status"] == "needs_approval"
    assert approval_request["action"] == "francis.lab.sandboxed_rebuild_run_test"
    assert approval_request["approval_created"] is True
    assert approval_request["approval_id"] == body["approval"]["id"]
    assert approval_request["upstream_approval_id"] == provider_probe_approval_id
    assert approval_request["sandboxed_boundary_id"] == boundary["id"]
    assert approval_request["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.request_approval"
    assert approval_request["approval_consumed"] is False
    assert approval_request["upstream_approval_consumed"] is False
    assert approval_request["boundary_recorded"] is True
    assert approval_request["boundary_ready"] is False
    assert approval_request["execution_authority"] is False
    assert approval_request["executed"] is False
    assert approval_request["process_launched"] is False
    assert approval_request["container_launched"] is False
    assert approval_request["commands_executed"] is False
    assert approval_request["repo_code_executed"] is False
    assert approval_request["ran_install"] is False
    assert approval_request["ran_build"] is False
    assert approval_request["ran_tests"] is False
    assert approval_request["network_accessed"] is False
    assert approval_request["wrote_to_repo"] is False
    assert approval_request["execution_receipt_written"] is False
    assert approval_request["candidate_validated"] is False
    assert approval_request["capability_promoted"] is False
    assert "sandboxed_rebuild_run_test_requires_operator_execution_approval" in approval_request["blockers"]
    assert body["execution"]["approval_request_created"] is True
    assert body["execution"]["sandboxed_rebuild_run_test_approval_consumed"] is False
    assert body["execution"]["execution_approval_consumed"] is False
    assert body["execution"]["ran_build"] is False
    assert body["execution"]["ran_tests"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.approval_request"
    assert Path(body["sandboxed_rebuild_run_test_approval_request_path"]).exists()
    assert Path(body["approval_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandboxed_rebuild_run_test_approval_request_path"]).read_text(encoding="utf-8")
    pending_approval_text = Path(body["approval_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert "super-secret-token-value" not in pending_approval_text
    assert _sandboxed_rebuild_run_test_approval_request_count(data_root) == 1
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_request_approval_api_denies_before_request_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, provider_probe_approval_id, _boundary = _prepare_api_sandboxed_rebuild_run_test_boundary(tmp_path)
    receipts_before = _receipt_count(data_root)
    requests_before = _sandboxed_rebuild_run_test_approval_request_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-request-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": provider_probe_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_approval_request"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandboxed_rebuild_run_test_approval_request_count(data_root) == requests_before
    assert not (repo / "lab-ran.txt").exists()


def _prepare_api_sandboxed_rebuild_run_test_approval_request(
    tmp_path: Path,
) -> tuple[Path, dict[str, Any], str, dict[str, Any]]:
    repo, source, provider_probe_approval_id, _boundary = _prepare_api_sandboxed_rebuild_run_test_boundary(tmp_path)
    service = IngestService()
    request_result = service.request_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    approval_request = request_result["sandboxed_rebuild_run_test_approval_request"]
    sandboxed_approval_id = approval_request["approval_id"]
    approvals.decide(sandboxed_approval_id, "approve", actor="test.operator")
    return repo, source, sandboxed_approval_id, approval_request


def test_ingest_lab_sandboxed_rebuild_run_test_consume_approval_api_writes_consumption_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, sandboxed_approval_id, approval_request = _prepare_api_sandboxed_rebuild_run_test_approval_request(
        tmp_path
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-consume-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": sandboxed_approval_id,
            "actor": _INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_APPROVAL_CONSUME_ACTOR,
        },
    )
    body = response.json()
    consumption = body["sandboxed_rebuild_run_test_approval_consumption"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_approval_consume"
    assert body["ok"] is True
    assert body["status"] == "consumed"
    assert consumption["status"] == "consumed"
    assert consumption["action"] == "francis.lab.sandboxed_rebuild_run_test"
    assert consumption["approval_id"] == sandboxed_approval_id
    assert consumption["approval_request_id"] == approval_request["id"]
    assert consumption["sandboxed_boundary_id"] == approval_request["sandboxed_boundary_id"]
    assert consumption["control_binding_id"] == approval_request["control_binding_id"]
    assert consumption["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.consume_approval"
    assert consumption["approval_status"] == "approved"
    assert consumption["approval_consumed"] is True
    assert consumption["single_use_enforced"] is True
    assert consumption["execution_authority"] is False
    assert consumption["executed"] is False
    assert consumption["process_launched"] is False
    assert consumption["container_launched"] is False
    assert consumption["commands_executed"] is False
    assert consumption["repo_code_executed"] is False
    assert consumption["ran_install"] is False
    assert consumption["ran_build"] is False
    assert consumption["ran_tests"] is False
    assert consumption["network_accessed"] is False
    assert consumption["wrote_to_repo"] is False
    assert consumption["execution_receipt_written"] is False
    assert consumption["candidate_validated"] is False
    assert consumption["capability_promoted"] is False
    assert consumption["approval_binding"]["exact_match"] is True
    assert body["execution"]["sandboxed_rebuild_run_test_approval_consumed"] is True
    assert body["execution"]["execution_approval_consumed"] is True
    assert body["execution"]["ran_build"] is False
    assert body["execution"]["ran_tests"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.approval.consume"
    assert Path(body["sandboxed_rebuild_run_test_approval_consumption_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    artifact_text = Path(body["sandboxed_rebuild_run_test_approval_consumption_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in artifact_text
    assert _sandboxed_rebuild_run_test_approval_consumption_count(data_root) == 1
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_consume_approval_api_denies_before_consumption_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, sandboxed_approval_id, _approval_request = _prepare_api_sandboxed_rebuild_run_test_approval_request(
        tmp_path
    )
    receipts_before = _receipt_count(data_root)
    consumptions_before = _sandboxed_rebuild_run_test_approval_consumption_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-consume-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": sandboxed_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_approval_consume"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandboxed_rebuild_run_test_approval_consumption_count(data_root) == consumptions_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_runner_binding_api_writes_preflight_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, sandboxed_approval_id, approval_request = _prepare_api_sandboxed_rebuild_run_test_approval_request(
        tmp_path
    )
    service = IngestService()
    consumption_result = service.consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.api.ingest",
    )
    consumption = consumption_result["sandboxed_rebuild_run_test_approval_consumption"]
    provider_reference = tmp_path / "api-sandbox-runner"
    provider_reference.write_text("metadata only api sandbox runner reference\n", encoding="utf-8")
    provider_policy_manifest = tmp_path / "api-sandbox-runner-policy.json"
    provider_policy_manifest.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-runner-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": sandboxed_approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(provider_policy_manifest),
            "actor": _INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_RUNNER_BINDING_ACTOR,
        },
    )
    body = response.json()
    binding = body["sandboxed_rebuild_run_test_runner_binding"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_runner_binding"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert binding["status"] == "blocked"
    assert binding["approval_id"] == sandboxed_approval_id
    assert binding["approval_consumption_id"] == consumption["id"]
    assert binding["approval_request_id"] == approval_request["id"]
    assert binding["sandboxed_boundary_id"] == approval_request["sandboxed_boundary_id"]
    assert binding["control_binding_id"] == approval_request["control_binding_id"]
    assert binding["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.runner_binding"
    assert binding["binding_kind"] == "sandboxed_rebuild_run_test_runner_binding_preflight"
    assert binding["binding_mode"] == "static_provider_reference_only_no_live_runner"
    assert binding["selected_provider_kind"] == "local_process_sandbox"
    assert binding["approval_consumed"] is True
    assert binding["single_use_enforced"] is True
    assert binding["static_provider_reference_bound"] is True
    assert binding["provider_reference_verified"] is True
    assert binding["provider_policy_manifest_bound"] is True
    assert binding["runner_binding_declared"] is True
    assert binding["live_runner_bound"] is False
    assert binding["sandbox_runner_bound"] is False
    assert binding["sandbox_bound"] is False
    assert binding["sandbox_enforced"] is False
    assert binding["provider_binary_executed"] is False
    assert binding["provider_service_queried"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert binding["process_launched"] is False
    assert binding["container_launched"] is False
    assert binding["commands_executed"] is False
    assert binding["repo_code_executed"] is False
    assert binding["ran_install"] is False
    assert binding["ran_build"] is False
    assert binding["ran_tests"] is False
    assert binding["network_accessed"] is False
    assert binding["wrote_to_repo"] is False
    assert binding["execution_receipt_written"] is False
    assert binding["candidate_validated"] is False
    assert binding["capability_promoted"] is False
    assert "live_runner_bound" in binding["missing_checks"]
    assert "sandbox_runner_bound" in binding["missing_checks"]
    assert "sandbox_enforced" in binding["missing_checks"]
    assert body["execution"]["sandboxed_rebuild_run_test_runner_binding_recorded"] is True
    assert body["execution"]["static_provider_reference_bound"] is True
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.runner_binding"
    assert Path(body["sandboxed_rebuild_run_test_runner_binding_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["sandboxed_rebuild_run_test_runner_binding_path"]).read_text(
        encoding="utf-8"
    )
    assert _sandboxed_rebuild_run_test_runner_binding_count(data_root) == 1
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_runner_binding_api_denies_before_preflight_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, sandboxed_approval_id, _approval_request = _prepare_api_sandboxed_rebuild_run_test_approval_request(
        tmp_path
    )
    IngestService().consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.api.ingest",
    )
    provider_reference = tmp_path / "api-denied-sandbox-runner"
    provider_reference.write_text("metadata only api denied sandbox runner reference\n", encoding="utf-8")
    provider_policy_manifest = tmp_path / "api-denied-sandbox-runner-policy.json"
    provider_policy_manifest.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )
    receipts_before = _receipt_count(data_root)
    runner_bindings_before = _sandboxed_rebuild_run_test_runner_binding_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-runner-binding",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": sandboxed_approval_id,
            "provider_kind": "local_process_sandbox",
            "provider_reference": str(provider_reference),
            "provider_policy_manifest": str(provider_policy_manifest),
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_runner_binding"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandboxed_rebuild_run_test_runner_binding_count(data_root) == runner_bindings_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_sandbox_policy_api_writes_preflight_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, sandboxed_approval_id, approval_request = _prepare_api_sandboxed_rebuild_run_test_approval_request(
        tmp_path
    )
    service = IngestService()
    consumption_result = service.consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.api.ingest",
    )
    consumption = consumption_result["sandboxed_rebuild_run_test_approval_consumption"]
    provider_reference = tmp_path / "api-policy-sandbox-runner"
    provider_reference.write_text("metadata only api policy sandbox runner reference\n", encoding="utf-8")
    provider_policy_manifest = tmp_path / "api-policy-sandbox-runner-policy.json"
    provider_policy_manifest.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )
    runner_binding_result = service.preflight_lab_sandboxed_rebuild_run_test_runner_binding(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(provider_policy_manifest),
        actor="test.api.ingest",
    )
    runner_binding = runner_binding_result["sandboxed_rebuild_run_test_runner_binding"]

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-sandbox-policy",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": sandboxed_approval_id,
            "actor": _INGEST_LAB_SANDBOXED_REBUILD_RUN_TEST_SANDBOX_POLICY_ACTOR,
        },
    )
    body = response.json()
    policy = body["sandboxed_rebuild_run_test_sandbox_policy"]

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_sandbox_policy"
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert policy["status"] == "blocked"
    assert policy["approval_id"] == sandboxed_approval_id
    assert policy["approval_consumption_id"] == consumption["id"]
    assert policy["runner_binding_id"] == runner_binding["id"]
    assert policy["approval_request_id"] == approval_request["id"]
    assert policy["sandboxed_boundary_id"] == approval_request["sandboxed_boundary_id"]
    assert policy["control_binding_id"] == approval_request["control_binding_id"]
    assert policy["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy"
    assert policy["policy_kind"] == "sandboxed_rebuild_run_test_sandbox_policy_preflight"
    assert policy["policy_mode"] == "policy_preflight_no_live_sandbox"
    assert policy["approval_consumed"] is True
    assert policy["runner_binding_present"] is True
    assert policy["static_provider_reference_bound"] is True
    assert policy["provider_kind_selected"] is True
    assert policy["sandbox_policy_declared"] is True
    assert policy["network_default_deny"] is True
    assert policy["network_allowed"] is False
    assert policy["repo_write_allowed"] is False
    assert policy["destructive_allowed"] is False
    assert policy["secret_storage_allowed"] is False
    assert policy["command_execution_enabled"] is False
    assert policy["command_allowlist_bound"] is False
    assert policy["execution_receipt_writer_bound"] is False
    assert policy["live_sandbox_bound"] is False
    assert policy["sandbox_enforced"] is False
    assert policy["execution_authority"] is False
    assert policy["executed"] is False
    assert policy["process_launched"] is False
    assert policy["container_launched"] is False
    assert policy["commands_executed"] is False
    assert policy["repo_code_executed"] is False
    assert policy["ran_install"] is False
    assert policy["ran_build"] is False
    assert policy["ran_tests"] is False
    assert policy["network_accessed"] is False
    assert policy["wrote_to_repo"] is False
    assert policy["execution_receipt_written"] is False
    assert policy["candidate_validated"] is False
    assert policy["capability_promoted"] is False
    assert policy["sandbox_policy"]["network_policy"]["default"] == "deny"
    assert policy["sandbox_policy"]["command_policy"]["command_execution_enabled"] is False
    assert "command_allowlist_bound" in policy["missing_checks"]
    assert "execution_receipt_writer_bound" in policy["missing_checks"]
    assert "live_sandbox_bound" in policy["missing_checks"]
    assert "sandbox_enforced" in policy["missing_checks"]
    assert body["execution"]["sandboxed_rebuild_run_test_sandbox_policy_recorded"] is True
    assert body["execution"]["network_default_deny"] is True
    assert body["execution"]["repo_write_allowed"] is False
    assert body["execution"]["executed"] is False
    assert body["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.sandbox_policy"
    assert Path(body["sandboxed_rebuild_run_test_sandbox_policy_path"]).exists()
    assert Path(body["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(body["sandboxed_rebuild_run_test_sandbox_policy_path"]).read_text(
        encoding="utf-8"
    )
    assert _sandboxed_rebuild_run_test_sandbox_policy_count(data_root) == 1
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandboxed_rebuild_run_test_sandbox_policy_api_denies_before_preflight_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo, source, sandboxed_approval_id, _approval_request = _prepare_api_sandboxed_rebuild_run_test_approval_request(
        tmp_path
    )
    service = IngestService()
    service.consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.api.ingest",
    )
    provider_reference = tmp_path / "api-policy-denied-sandbox-runner"
    provider_reference.write_text("metadata only api denied policy sandbox runner reference\n", encoding="utf-8")
    provider_policy_manifest = tmp_path / "api-policy-denied-sandbox-runner-policy.json"
    provider_policy_manifest.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )
    service.preflight_lab_sandboxed_rebuild_run_test_runner_binding(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(provider_policy_manifest),
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    policies_before = _sandboxed_rebuild_run_test_sandbox_policy_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandboxed-rebuild-run-test-sandbox-policy",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": sandboxed_approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandboxed_rebuild_run_test_sandbox_policy"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandboxed_rebuild_run_test_sandbox_policy_count(data_root) == policies_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_source_mount_readiness_api_denies_before_readiness_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    readiness_before = _source_mount_readiness_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/source-mount-readiness",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_NOOP_RUNNER_IDENTITY_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.source_mount_readiness"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _source_mount_readiness_count(data_root) == readiness_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_source_mount_contract_api_denies_before_contract_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    contracts_before = _source_mount_contract_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/source-mount-contract",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SOURCE_MOUNT_READINESS_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.source_mount_contract"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _source_mount_contract_count(data_root) == contracts_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_run_boundary_preflight_api_denies_before_boundary_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    boundaries_before = _run_boundary_preflight_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/run-boundary-preflight",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_SOURCE_MOUNT_CONTRACT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.run_boundary_preflight"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _run_boundary_preflight_count(data_root) == boundaries_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_execution_boundary_api_denies_before_boundary_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    boundaries_before = _sandbox_provider_runtime_probe_execution_boundary_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-execution-boundary",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_execution_boundary"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_execution_boundary_count(data_root) == boundaries_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_refuse_api_denies_before_refusal_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    refusals_before = _sandbox_provider_runtime_probe_refusal_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-refuse",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_refusal"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_refusal_count(data_root) == refusals_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_lab_sandbox_provider_runtime_probe_request_approval_api_denies_before_request_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)
    requests_before = _sandbox_provider_runtime_probe_approval_request_count(data_root)

    response = TestClient(create_app()).post(
        "/ingest/lab/sandbox-provider-runtime-probe-request-approval",
        json={
            "source_or_path": source["id"],
            "candidate": "run_project_tests",
            "approval_id": approval_id,
            "actor": _INGEST_LAB_RUN_BOUNDARY_PREFLIGHT_ACTOR,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.lab.sandbox_provider_runtime_probe_approval_request"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert _receipt_count(data_root) == receipts_before
    assert _sandbox_provider_runtime_probe_approval_request_count(data_root) == requests_before
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_readback_api_lists_source_repo_candidate_and_lab_artifacts_without_writes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.api.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.api.ingest")
    approvals.decide(request["approval"]["id"], "approve", actor="test.operator")
    service.preflight_lab_approval_consumption(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_readiness(
        source["id"],
        "run_project_tests",
        approval_id=request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_binding(
        source["id"],
        "run_project_tests",
        approval_id=request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_enforcement(
        source["id"],
        "run_project_tests",
        approval_id=request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_approval_consumption_handoff(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_execution_receipt_sink_reservation(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_command_allowlist_binding(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_command_allowlist_declaration(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_command_allowlist_enforcement(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_runner_sandbox_readiness(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_execution_receipt_write_readiness(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_execution_receipt_prewrite_binding(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_execution_receipt_writer(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_source_mount_readiness(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_source_mount_contract(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_run_boundary(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_harness(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_readiness(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_binding(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_enforcement(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    service.refuse_lab_sandbox_provider_runtime_probe(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    provider_probe_request = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        request["approval"]["id"],
        actor="test.api.ingest",
    )
    provider_probe_approval_id = provider_probe_request["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    service.preflight_lab_sandboxed_rebuild_run_test_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    sandboxed_approval_request = service.request_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.api.ingest",
    )
    sandboxed_approval_id = sandboxed_approval_request["sandboxed_rebuild_run_test_approval_request"]["approval_id"]
    approvals.decide(sandboxed_approval_id, "approve", actor="test.operator")
    service.consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.api.ingest",
    )
    sandbox_runner_provider = tmp_path / "readback-sandbox-runner"
    sandbox_runner_provider.write_text("metadata only readback sandbox runner reference\n", encoding="utf-8")
    sandbox_runner_policy = tmp_path / "readback-sandbox-runner-policy.json"
    sandbox_runner_policy.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )
    service.preflight_lab_sandboxed_rebuild_run_test_runner_binding(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(sandbox_runner_provider),
        provider_policy_manifest=str(sandbox_runner_policy),
        actor="test.api.ingest",
    )
    service.preflight_lab_sandboxed_rebuild_run_test_sandbox_policy(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.api.ingest",
    )
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).get(
        "/ingest/readback",
        params={"actor": _INGEST_LAB_ACTOR, "source_id": source["id"]},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.readback"
    assert body["ok"] is True
    assert body["status"] == "readback"
    assert body["source_id"] == source["id"]
    assert body["counts"]["sources"] == 1
    assert body["counts"]["repo_maps"] == 1
    assert body["counts"]["capability_candidates"] >= 1
    assert body["counts"]["lab_preflights"] >= 1
    assert body["counts"]["approval_consumption_preflights"] == 1
    assert body["counts"]["approval_consumptions"] == 1
    assert body["counts"]["noop_runner_envelopes"] == 1
    assert body["counts"]["noop_runner_transcripts"] == 1
    assert body["counts"]["noop_runner_identity_bindings"] == 1
    assert body["counts"]["source_mount_readiness"] == 1
    assert body["counts"]["source_mount_contracts"] == 1
    assert body["counts"]["runner_contracts"] == 1
    assert body["counts"]["runner_readiness"] == 1
    assert body["counts"]["runner_bindings"] == 1
    assert body["counts"]["runner_enforcements"] == 1
    assert body["counts"]["approval_consumption_handoffs"] == 1
    assert body["counts"]["execution_receipt_sink_reservations"] == 1
    assert body["counts"]["runner_command_allowlists"] == 1
    assert body["counts"]["runner_command_allowlist_declarations"] == 1
    assert body["counts"]["runner_command_allowlist_enforcements"] == 1
    assert body["counts"]["runner_sandbox_readiness"] == 1
    assert body["counts"]["sandbox_provider_contracts"] == 1
    assert body["counts"]["sandbox_provider_bindings"] == 1
    assert body["counts"]["sandbox_provider_selections"] == 1
    assert body["counts"]["sandbox_provider_verifier_preflights"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_preflights"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_harness_preflights"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_runner_readiness"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_runner_bindings"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_runner_enforcements"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_execution_boundaries"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_refusals"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_approval_requests"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_approval_consumptions"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_invocation_boundaries"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"] == 1
    assert body["counts"]["sandbox_provider_runtime_probe_runner_control_bindings"] == 1
    assert body["counts"]["sandboxed_rebuild_run_test_boundaries"] == 1
    assert body["counts"]["sandboxed_rebuild_run_test_approval_requests"] == 1
    assert body["counts"]["sandboxed_rebuild_run_test_approval_consumptions"] == 1
    assert body["counts"]["sandboxed_rebuild_run_test_runner_bindings"] == 1
    assert body["counts"]["sandboxed_rebuild_run_test_sandbox_policies"] == 1
    assert body["counts"]["execution_receipt_write_readiness"] == 1
    assert body["counts"]["execution_receipt_prewrite_bindings"] == 1
    assert body["counts"]["execution_receipt_writer_preflights"] == 1
    assert body["counts"]["run_boundary_preflights"] == 1
    assert body["counts"]["execution_receipts"] == 1
    assert body["sources"][0]["id"] == source["id"]
    assert body["repo_maps"][0]["repo_map"]["source_id"] == source["id"]
    assert any(candidate["name"] == "run_project_tests" for candidate in body["capability_candidates"])
    assert body["approval_consumption_preflights"][0]["approval_consumption"]["approval_consumed"] is False
    assert body["approval_consumptions"][0]["approval_consumption_record"]["approval_consumed"] is True
    assert body["approval_consumptions"][0]["approval_consumption_record"]["single_use_enforced"] is True
    assert body["approval_consumptions"][0]["approval_consumption_record"]["execution_authority"] is False
    assert body["approval_consumptions"][0]["approval_consumption_record"]["executed"] is False
    assert body["approval_consumptions"][0]["approval_consumption_record"]["network_accessed"] is False
    assert body["noop_runner_envelopes"][0]["noop_runner_envelope"]["noop_performed"] is True
    assert body["noop_runner_envelopes"][0]["noop_runner_envelope"]["approval_consumed"] is True
    assert body["noop_runner_envelopes"][0]["noop_runner_envelope"]["execution_authority"] is False
    assert body["noop_runner_envelopes"][0]["noop_runner_envelope"]["executed"] is False
    assert body["noop_runner_envelopes"][0]["noop_runner_envelope"]["repo_code_executed"] is False
    assert body["noop_runner_transcripts"][0]["noop_runner_transcript"]["builtin_noop_output_captured"] is True
    assert body["noop_runner_transcripts"][0]["noop_runner_transcript"]["output_content_stored"] is False
    assert body["noop_runner_transcripts"][0]["noop_runner_transcript"]["real_process_output_captured"] is False
    assert body["noop_runner_transcripts"][0]["noop_runner_transcript"]["repo_code_executed"] is False
    assert body["noop_runner_identity_bindings"][0]["noop_runner_identity_binding"]["runner_identity_bound"] is True
    assert body["noop_runner_identity_bindings"][0]["noop_runner_identity_binding"]["live_runner_bound"] is False
    assert body["noop_runner_identity_bindings"][0]["noop_runner_identity_binding"]["sandbox_runner_bound"] is False
    assert body["noop_runner_identity_bindings"][0]["noop_runner_identity_binding"]["candidate_validated"] is False
    assert (
        body["source_mount_readiness"][0]["source_mount_readiness"]["source_mount_mode"] == "reference_only_read_only"
    )
    assert body["source_mount_readiness"][0]["source_mount_readiness"]["source_mount_enforced"] is False
    assert body["source_mount_readiness"][0]["source_mount_readiness"]["read_only_mount_bound"] is False
    assert body["source_mount_readiness"][0]["source_mount_readiness"]["source_copied"] is False
    assert body["source_mount_readiness"][0]["source_mount_readiness"]["execution_authority"] is False
    assert body["source_mount_readiness"][0]["source_mount_readiness"]["executed"] is False
    assert body["source_mount_contracts"][0]["source_mount_contract"]["contract_mode"] == "contract_only_no_live_mount"
    assert body["source_mount_contracts"][0]["source_mount_contract"]["mount_mode"] == "future_read_only_source_mount"
    assert body["source_mount_contracts"][0]["source_mount_contract"]["live_mount_bound"] is False
    assert body["source_mount_contracts"][0]["source_mount_contract"]["mount_enforced"] is False
    assert body["source_mount_contracts"][0]["source_mount_contract"]["execution_authority"] is False
    assert body["source_mount_contracts"][0]["source_mount_contract"]["executed"] is False
    assert body["runner_contracts"][0]["runner_contract"]["runner_bound"] is False
    assert body["runner_readiness"][0]["runner_readiness"]["execution_authority"] is False
    assert body["runner_bindings"][0]["runner_binding"]["receipt_sink_bound"] is False
    assert body["runner_enforcements"][0]["runner_enforcement"]["runner_bound"] is False
    assert body["approval_consumption_handoffs"][0]["approval_handoff"]["approval_consumed"] is False
    assert (
        body["execution_receipt_sink_reservations"][0]["receipt_sink_reservation"]["execution_receipt_written"] is False
    )
    assert body["runner_command_allowlists"][0]["runner_command_allowlist"]["allowlist_bound"] is False
    assert body["runner_command_allowlists"][0]["runner_command_allowlist"]["command_execution_enabled"] is False
    assert (
        body["runner_command_allowlist_declarations"][0]["runner_command_allowlist_declaration"]["allowlist_declared"]
        is True
    )
    assert (
        body["runner_command_allowlist_declarations"][0]["runner_command_allowlist_declaration"]["allowlist_bound"]
        is False
    )
    assert (
        body["runner_command_allowlist_enforcements"][0]["runner_command_allowlist_enforcement"]["allowlist_enforced"]
        is False
    )
    assert (
        body["runner_command_allowlist_enforcements"][0]["runner_command_allowlist_enforcement"][
            "command_execution_enabled"
        ]
        is False
    )
    assert body["runner_sandbox_readiness"][0]["runner_sandbox_readiness"]["sandbox_bound"] is False
    assert body["runner_sandbox_readiness"][0]["runner_sandbox_readiness"]["sandbox_enforced"] is False
    assert body["runner_sandbox_readiness"][0]["runner_sandbox_readiness"]["execution_authority"] is False
    assert body["sandbox_provider_contracts"][0]["sandbox_provider_contract"]["provider_contract_declared"] is True
    assert body["sandbox_provider_contracts"][0]["sandbox_provider_contract"]["sandbox_provider_bound"] is False
    assert body["sandbox_provider_contracts"][0]["sandbox_provider_contract"]["sandbox_bound"] is False
    assert body["sandbox_provider_contracts"][0]["sandbox_provider_contract"]["execution_authority"] is False
    assert body["sandbox_provider_bindings"][0]["sandbox_provider_binding"]["provider_kind_selected"] is False
    assert body["sandbox_provider_bindings"][0]["sandbox_provider_binding"]["sandbox_provider_bound"] is False
    assert body["sandbox_provider_bindings"][0]["sandbox_provider_binding"]["sandbox_bound"] is False
    assert body["sandbox_provider_bindings"][0]["sandbox_provider_binding"]["execution_authority"] is False
    assert body["sandbox_provider_selections"][0]["sandbox_provider_selection"]["provider_kind_selected"] is False
    assert (
        body["sandbox_provider_selections"][0]["sandbox_provider_selection"]["provider_binary_or_service_verified"]
        is False
    )
    assert body["sandbox_provider_selections"][0]["sandbox_provider_selection"]["sandbox_provider_bound"] is False
    assert body["sandbox_provider_selections"][0]["sandbox_provider_selection"]["sandbox_bound"] is False
    assert body["sandbox_provider_selections"][0]["sandbox_provider_selection"]["execution_authority"] is False
    assert (
        body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"]["verifier_contract_declared"]
        is True
    )
    assert (
        body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"]["verifier_implementation_bound"]
        is True
    )
    assert (
        body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"][
            "provider_binary_or_service_verified"
        ]
        is False
    )
    assert body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"]["process_launched"] is False
    assert body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"]["container_launched"] is False
    assert (
        body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"]["sandbox_provider_bound"] is False
    )
    assert body["sandbox_provider_verifier_preflights"][0]["sandbox_provider_verifier"]["execution_authority"] is False
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"][
            "runtime_probe_contract_declared"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"][
            "runtime_probe_network_blocked_by_contract"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"][
            "runtime_probe_runner_bound"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"][
            "provider_runtime_probe_performed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"]["container_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_preflights"][0]["sandbox_provider_runtime_probe"]["execution_authority"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "runtime_probe_runner_contract_declared"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "runtime_probe_sandbox_contract_declared"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "runtime_probe_service_query_guard_declared"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "runtime_probe_runner_bound"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "provider_runtime_probe_performed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "process_launched"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "container_launched"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_harness_preflights"][0]["sandbox_provider_runtime_probe_harness"][
            "execution_authority"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_readiness"][0]["sandbox_provider_runtime_probe_runner_readiness"][
            "probe_runner_interface_declared"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_readiness"][0]["sandbox_provider_runtime_probe_runner_readiness"][
            "probe_runner_implementation_bound"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_readiness"][0]["sandbox_provider_runtime_probe_runner_readiness"][
            "probe_runner_sandbox_bound"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_readiness"][0]["sandbox_provider_runtime_probe_runner_readiness"][
            "provider_runtime_probe_performed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_readiness"][0]["sandbox_provider_runtime_probe_runner_readiness"][
            "process_launched"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_readiness"][0]["sandbox_provider_runtime_probe_runner_readiness"][
            "execution_authority"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_bindings"][0]["sandbox_provider_runtime_probe_runner_binding"][
            "probe_runner_binding_contract_declared"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_bindings"][0]["sandbox_provider_runtime_probe_runner_binding"][
            "probe_runner_bound"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_bindings"][0]["sandbox_provider_runtime_probe_runner_binding"][
            "runtime_probe_bound"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_bindings"][0]["sandbox_provider_runtime_probe_runner_binding"][
            "process_launched"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_bindings"][0]["sandbox_provider_runtime_probe_runner_binding"][
            "execution_authority"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_enforcements"][0][
            "sandbox_provider_runtime_probe_runner_enforcement"
        ]["probe_runner_enforcement_contract_declared"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_enforcements"][0][
            "sandbox_provider_runtime_probe_runner_enforcement"
        ]["probe_runner_enforcement_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_enforcements"][0][
            "sandbox_provider_runtime_probe_runner_enforcement"
        ]["probe_runner_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_enforcements"][0][
            "sandbox_provider_runtime_probe_runner_enforcement"
        ]["runtime_probe_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_enforcements"][0][
            "sandbox_provider_runtime_probe_runner_enforcement"
        ]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_enforcements"][0][
            "sandbox_provider_runtime_probe_runner_enforcement"
        ]["execution_authority"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["provider_probe_execution_boundary_declared"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["provider_probe_execution_boundary_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["provider_runtime_probe_performed"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["container_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["execution_receipt_written"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["execution_authority"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"]["refusal_kind"]
        == "francis.lab.sandbox_provider_runtime_probe_refusal"
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"][
            "provider_runtime_probe_performed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"][
            "provider_binary_executed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"][
            "container_launched"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"][
            "execution_receipt_written"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_refusals"][0]["sandbox_provider_runtime_probe_refusal"][
            "approval_consumed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "action"
        ]
        == "francis.lab.sandbox_provider_runtime_probe"
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "approval_created"
        ]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "approval_consumed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "upstream_approval_consumed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "provider_runtime_probe_performed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "provider_binary_executed"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "process_launched"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_requests"][0]["sandbox_provider_runtime_probe_approval_request"][
            "execution_receipt_written"
        ]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["action"]
        == "francis.lab.sandbox_provider_runtime_probe"
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["approval_consumed"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["single_use_enforced"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["provider_runtime_probe_performed"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["provider_binary_executed"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_approval_consumptions"][0][
            "sandbox_provider_runtime_probe_approval_consumption"
        ]["execution_receipt_written"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["boundary_kind"]
        == "francis.lab.sandbox_provider_runtime_probe_invocation_boundary"
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["approval_consumed"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["single_use_enforced"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["exact_action_binding_verified"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["probe_runner_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["probe_runner_receipt_writer_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["provider_runtime_probe_performed"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_invocation_boundaries"][0][
            "sandbox_provider_runtime_probe_invocation_boundary"
        ]["execution_receipt_written"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["boundary_kind"]
        == "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["approval_consumed"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["single_use_enforced"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["runner_identity_declared"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["runner_identity_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["runner_policy_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["network_block_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["provider_runtime_probe_performed"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["process_launched"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_pre_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary"
        ]["execution_receipt_written"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["binding_kind"]
        == "francis.lab.sandbox_provider_runtime_probe_runner_control_binding"
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["control_binding_recorded"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["runner_identity_binding_recorded"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["runner_identity_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["runner_policy_binding_recorded"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["runner_policy_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["network_block_binding_recorded"]
        is True
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["network_block_bound"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["provider_runtime_probe_performed"]
        is False
    )
    assert (
        body["sandbox_provider_runtime_probe_runner_control_bindings"][0][
            "sandbox_provider_runtime_probe_runner_control_binding"
        ]["execution_receipt_written"]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"]["boundary_kind"]
        == "francis.lab.sandboxed_rebuild_run_test_boundary"
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"][
            "control_binding_recorded"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"]["control_binding_ready"]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"][
            "execution_approval_required"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"][
            "execution_approval_consumed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"]["sandbox_enforced"]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"]["commands_executed"]
        is False
    )
    assert body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"]["ran_build"] is False
    assert body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"]["ran_tests"] is False
    assert (
        body["sandboxed_rebuild_run_test_boundaries"][0]["sandboxed_rebuild_run_test_boundary"][
            "execution_receipt_written"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"]["action"]
        == "francis.lab.sandboxed_rebuild_run_test"
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "approval_created"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "approval_consumed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "boundary_recorded"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "boundary_ready"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "commands_executed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "ran_build"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "ran_tests"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_requests"][0]["sandboxed_rebuild_run_test_approval_request"][
            "execution_receipt_written"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "action"
        ]
        == "francis.lab.sandboxed_rebuild_run_test"
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "approval_consumed"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "single_use_enforced"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "execution_authority"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "commands_executed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "ran_build"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "ran_tests"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_approval_consumptions"][0]["sandboxed_rebuild_run_test_approval_consumption"][
            "execution_receipt_written"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "binding_kind"
        ]
        == "sandboxed_rebuild_run_test_runner_binding_preflight"
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "binding_mode"
        ]
        == "static_provider_reference_only_no_live_runner"
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "static_provider_reference_bound"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "provider_reference_verified"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "provider_policy_manifest_bound"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "live_runner_bound"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "sandbox_runner_bound"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "sandbox_enforced"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "commands_executed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"]["ran_build"]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"]["ran_tests"]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_runner_bindings"][0]["sandboxed_rebuild_run_test_runner_binding"][
            "execution_receipt_written"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "policy_kind"
        ]
        == "sandboxed_rebuild_run_test_sandbox_policy_preflight"
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "policy_mode"
        ]
        == "policy_preflight_no_live_sandbox"
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "runner_binding_present"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "network_default_deny"
        ]
        is True
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "repo_write_allowed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "command_execution_enabled"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "command_allowlist_bound"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "execution_receipt_writer_bound"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "live_sandbox_bound"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "sandbox_enforced"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"][
            "commands_executed"
        ]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"]["ran_build"]
        is False
    )
    assert (
        body["sandboxed_rebuild_run_test_sandbox_policies"][0]["sandboxed_rebuild_run_test_sandbox_policy"]["ran_tests"]
        is False
    )
    assert (
        body["execution_receipt_write_readiness"][0]["execution_receipt_write_readiness"][
            "execution_receipt_prewritten"
        ]
        is False
    )
    assert (
        body["execution_receipt_write_readiness"][0]["execution_receipt_write_readiness"]["execution_authority"]
        is False
    )
    assert (
        body["execution_receipt_prewrite_bindings"][0]["execution_receipt_prewrite_binding"]["receipt_schema_bound"]
        is True
    )
    assert (
        body["execution_receipt_prewrite_bindings"][0]["execution_receipt_prewrite_binding"][
            "execution_receipt_prewritten"
        ]
        is False
    )
    assert (
        body["execution_receipt_prewrite_bindings"][0]["execution_receipt_prewrite_binding"]["execution_authority"]
        is False
    )
    assert (
        body["execution_receipt_writer_preflights"][0]["execution_receipt_writer_preflight"][
            "writer_implementation_bound"
        ]
        is False
    )
    assert (
        body["execution_receipt_writer_preflights"][0]["execution_receipt_writer_preflight"]["writer_path_within_sink"]
        is True
    )
    assert (
        body["execution_receipt_writer_preflights"][0]["execution_receipt_writer_preflight"][
            "execution_receipt_prewritten"
        ]
        is False
    )
    assert (
        body["execution_receipt_writer_preflights"][0]["execution_receipt_writer_preflight"]["execution_authority"]
        is False
    )
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"]["boundary_mode"] == "preflight_only_no_execution"
    )
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"]["run_mode"] == "future_sandboxed_rebuild_run_test"
    )
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_bound"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_contract_declared"] is True
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_binding_ready"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_selection_ready"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_verifier_ready"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_runtime_probe_ready"] is False
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_runtime_probe_harness_ready"]
        is False
    )
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"][
            "sandbox_provider_runtime_probe_runner_enforcement_ready"
        ]
        is False
    )
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_harness_contract_declared"] is True
    )
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"][
            "runtime_probe_runner_enforcement_contract_declared"
        ]
        is True
    )
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_runner_enforcement_bound"] is False
    )
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_runner_bound"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_sandbox_bound"] is False
    assert (
        body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_service_query_guard_bound"] is False
    )
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_output_capture_bound"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["runtime_probe_kill_switch_bound"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["provider_runtime_probe_performed"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["sandbox_provider_bound"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["command_allowlist_enforced"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["execution_authority"] is False
    assert body["run_boundary_preflights"][0]["run_boundary_preflight"]["executed"] is False
    assert body["execution_receipts"][0]["execution_receipt"]["synthetic"] is True
    assert body["execution_receipts"][0]["execution_receipt"]["noop"] is True
    assert body["execution_receipts"][0]["execution_receipt"]["finalized"] is True
    assert body["execution_receipts"][0]["execution_receipt"]["approval_consumed"] is False
    assert body["execution_receipts"][0]["execution_receipt"]["execution_authority"] is False
    assert body["execution_receipts"][0]["execution_receipt"]["executed"] is False
    assert body["execution_receipts"][0]["execution_receipt"]["ran_repo_scripts"] is False
    assert body["execution_receipts"][0]["execution_receipt"]["network_accessed"] is False
    assert "governed_runner_bound" in body["runner_readiness"][0]["runner_readiness"]["missing_controls"]
    assert "execution_receipt_sink_bound" in body["runner_bindings"][0]["runner_binding"]["missing_controls"]
    assert "runner_identity_verified" in body["runner_enforcements"][0]["runner_enforcement"]["missing_checks"]
    assert (
        "approval_consumption_not_disabled"
        in body["approval_consumption_handoffs"][0]["approval_handoff"]["missing_checks"]
    )
    assert (
        "execution_receipt_prewrite_bound"
        in body["execution_receipt_sink_reservations"][0]["receipt_sink_reservation"]["missing_checks"]
    )
    assert (
        "command_allowlist_bound" in body["runner_command_allowlists"][0]["runner_command_allowlist"]["missing_checks"]
    )
    assert (
        "command_allowlist_bound"
        in body["runner_command_allowlist_declarations"][0]["runner_command_allowlist_declaration"]["missing_checks"]
    )
    assert (
        "command_allowlist_enforced"
        in body["runner_command_allowlist_enforcements"][0]["runner_command_allowlist_enforcement"]["missing_checks"]
    )
    assert "sandbox_provider_bound" in body["runner_sandbox_readiness"][0]["runner_sandbox_readiness"]["missing_checks"]
    assert (
        "sandbox_provider_bound" in body["sandbox_provider_contracts"][0]["sandbox_provider_contract"]["missing_checks"]
    )
    assert (
        "provider_kind_selected" in body["sandbox_provider_bindings"][0]["sandbox_provider_binding"]["missing_checks"]
    )
    assert (
        "receipt_prewrite_writer_bound"
        in body["execution_receipt_write_readiness"][0]["execution_receipt_write_readiness"]["missing_checks"]
    )
    assert (
        "prewrite_writer_bound"
        in body["execution_receipt_prewrite_bindings"][0]["execution_receipt_prewrite_binding"]["missing_checks"]
    )
    assert (
        "writer_implementation_bound"
        in body["execution_receipt_writer_preflights"][0]["execution_receipt_writer_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_contract_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_binding_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_selection_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_verifier_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_runtime_probe_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_runtime_probe_harness_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "sandbox_provider_runtime_probe_runner_enforcement_ready"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_harness_contract_declared"
        not in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_runner_enforcement_contract_declared"
        not in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_runner_enforcement_bound"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_runner_bound" in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_sandbox_bound" in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_service_query_guard_bound"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_output_capture_bound"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "runtime_probe_kill_switch_bound"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "provider_runtime_probe_performed"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "provider_probe_execution_boundary_declared"
        not in body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["missing_checks"]
    )
    assert (
        "run_boundary_ready"
        in body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["missing_checks"]
    )
    assert (
        "provider_probe_execution_boundary_bound"
        in body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["missing_checks"]
    )
    assert (
        "provider_runtime_probe_performed"
        in body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["missing_checks"]
    )
    assert (
        "execution_receipt_not_written"
        not in body["sandbox_provider_runtime_probe_execution_boundaries"][0][
            "sandbox_provider_runtime_probe_execution_boundary"
        ]["missing_checks"]
    )
    assert (
        "verifier_implementation_bound"
        not in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert (
        "provider_binary_or_service_verified"
        in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    )
    assert "sandbox_bound" in body["run_boundary_preflights"][0]["run_boundary_preflight"]["missing_checks"]
    assert body["execution"]["executed"] is False
    assert body["receipts_written"] is False
    assert body["artifacts_written"] is False
    assert _receipt_count(data_root) == receipts_before
    assert "super-secret-token-value" not in json.dumps(body)
    assert not (repo / "lab-ran.txt").exists()


def test_ingest_readback_api_denies_without_writing_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    source = IngestService().add_source(repo, actor="test.api.ingest")["source"]
    receipts_before = _receipt_count(data_root)

    response = TestClient(create_app()).get(
        "/ingest/readback",
        params={"actor": "test.ingest.lab.denied", "source_id": source["id"]},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "francis.ingest.readback"
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["execution"]["executed"] is False
    assert body["execution"]["ran_repo_scripts"] is False
    assert _receipt_count(data_root) == receipts_before
    assert not (repo / "lab-ran.txt").exists()


def _receipt_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "receipts").glob("*.json")))


def _execution_receipt_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_execution_receipts").glob("*.json")))


def _approval_consumption_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_approval_consumptions").glob("*.json")))


def _noop_runner_envelope_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_noop_runner_envelopes").glob("*.json")))


def _noop_runner_transcript_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_noop_runner_transcripts").glob("*.json")))


def _noop_runner_identity_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_noop_runner_identity_bindings").glob("*.json")))


def _source_mount_readiness_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_source_mount_readiness").glob("*.json")))


def _source_mount_contract_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_source_mount_contracts").glob("*.json")))


def _sandbox_provider_contract_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_sandbox_provider_contracts").glob("*.json")))


def _sandbox_provider_binding_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_sandbox_provider_bindings").glob("*.json")))


def _sandbox_provider_selection_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_sandbox_provider_selections").glob("*.json")))


def _sandbox_provider_verifier_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_sandbox_provider_verifier_preflights").glob("*.json")))


def _sandbox_provider_runtime_probe_count(data_root: Path) -> int:
    return len(
        list((data_root / "artifacts" / "ingest" / "lab_sandbox_provider_runtime_probe_preflights").glob("*.json"))
    )


def _sandbox_provider_runtime_probe_harness_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_harness_preflights").glob("*.json")))


def _sandbox_provider_runtime_probe_runner_readiness_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_runner_readiness").glob("*.json")))


def _sandbox_provider_runtime_probe_runner_binding_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_runner_bindings").glob("*.json")))


def _sandbox_provider_runtime_probe_runner_enforcement_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_runner_enforcements").glob("*.json")))


def _sandbox_provider_runtime_probe_execution_boundary_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_execution_boundaries").glob("*.json")))


def _sandbox_provider_runtime_probe_refusal_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_refusals").glob("*.json")))


def _sandbox_provider_runtime_probe_approval_request_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_approval_requests").glob("*.json")))


def _sandbox_provider_runtime_probe_approval_consumption_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_approval_consumptions").glob("*.json")))


def _sandbox_provider_runtime_probe_invocation_boundary_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_invocation_boundaries").glob("*.json")))


def _sandbox_provider_runtime_probe_runner_pre_execution_boundary_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_preexec_boundaries").glob("*.json")))


def _sandbox_provider_runtime_probe_runner_control_binding_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_runtime_probe_control_bindings").glob("*.json")))


def _sandboxed_rebuild_run_test_boundary_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_sandboxed_rebuild_run_test_boundaries").glob("*.json")))


def _sandboxed_rebuild_run_test_approval_request_count(data_root: Path) -> int:
    return len(
        list((data_root / "artifacts" / "ingest" / "lab_sandboxed_rebuild_run_test_approval_requests").glob("*.json"))
    )


def _sandboxed_rebuild_run_test_approval_consumption_count(data_root: Path) -> int:
    return len(
        list(
            (data_root / "artifacts" / "ingest" / "lab_sandboxed_rebuild_run_test_approval_consumptions").glob("*.json")
        )
    )


def _sandboxed_rebuild_run_test_runner_binding_count(data_root: Path) -> int:
    return len(
        list((data_root / "artifacts" / "ingest" / "lab_sandboxed_rebuild_run_test_runner_bindings").glob("*.json"))
    )


def _sandboxed_rebuild_run_test_sandbox_policy_count(data_root: Path) -> int:
    return len(
        list((data_root / "artifacts" / "ingest" / "lab_sandboxed_rebuild_run_test_sandbox_policies").glob("*.json"))
    )


def _run_boundary_preflight_count(data_root: Path) -> int:
    return len(list((data_root / "artifacts" / "ingest" / "lab_run_boundary_preflights").glob("*.json")))
