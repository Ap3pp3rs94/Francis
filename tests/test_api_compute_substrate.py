from __future__ import annotations

from dataclasses import replace
import inspect
import json
from pathlib import Path

from fastapi.testclient import TestClient

import francis.api.routes.compute_substrate as compute_route
from francis.api.app import create_app
from francis.compute_substrate import (
    ApprovalGrant,
    ApprovalScope,
    CapabilityReceipt,
    ComputeTaskRecord,
    LocalJsonComputeApprovalStore,
    LocalJsonComputeReceiptStore,
    LocalJsonComputeStatusStore,
)


def _client(
    monkeypatch,
    tmp_path: Path,
    *,
    actor_scopes: dict[str, list[str]],
) -> TestClient:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps(actor_scopes))
    return TestClient(create_app())


def _submit_payload(
    *,
    actor: str = "compute.submitter",
    request_id: str = "api-compute-echo",
    capability: str = "echo",
    message: str = "hello",
    payload: object | None = None,
    approval_required: bool = False,
    approval_id: str = "",
    resource_budget: dict[str, object] | None = None,
    deadline: object | None = None,
    cancel_requested: bool = False,
    cancellation_reason: str = "",
) -> dict[str, object]:
    body: dict[str, object] = {
        "actor_id": actor,
        "request_id": request_id,
        "requested_capability": capability,
        "payload": payload
        if payload is not None
        else {
            "message": message,
            "model_prompt": "MODEL_PROMPT_SHOULD_NOT_RETURN",
            "filesystem_hint": "C:\\Sensitive\\Should\\Not\\Return",
        },
        "payload_summary": "bounded test payload",
        "resource_budget": resource_budget or {},
        "approval_required": approval_required,
        "approval_id": approval_id,
        "correlation_id": f"trace-{request_id}",
    }
    if deadline is not None:
        body["deadline"] = deadline
    if cancel_requested:
        body["cancel_requested"] = True
        body["cancellation_reason"] = cancellation_reason
    return body


def _approval_grant(
    *,
    task_id: str,
    approval_id: str,
    capability: str = "echo",
    approval_secret: str = "APPROVAL_SECRET_SHOULD_NOT_PERSIST",
) -> ApprovalGrant:
    return ApprovalGrant(
        approval_id=approval_id,
        scope=ApprovalScope(
            task_id=task_id,
            allowed_capabilities=(capability,),
            allowed_worker_ids=("safe-local-1",),
            max_risk_level="low",
            max_runtime_ms=1000,
            max_memory_mb=128,
            max_cpu_weight=25,
            max_compute_units=1000,
        ),
        approved_by="operator",
        reason=f"token={approval_secret}",
        approval_note=f"token={approval_secret}",
    )


def _durable_text(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.rglob("*.json")))


class _FailingReceiptStore:
    def write_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt:
        raise OSError("receipt store unavailable RAW_OUTPUT_SHOULD_NOT_RETURN")

    def read_receipt(self, receipt_id: str) -> CapabilityReceipt | None:
        return None

    def describe(self) -> dict[str, object]:
        return {"kind": "test.failing_api_compute_receipt_store"}


class _FailingStatusStore:
    def __init__(self) -> None:
        self.upsert_calls = 0

    def upsert(self, record: ComputeTaskRecord) -> ComputeTaskRecord:
        self.upsert_calls += 1
        raise OSError("status store unavailable RAW_PAYLOAD_SHOULD_NOT_RETURN")

    def get_by_task_id(self, task_id: str) -> ComputeTaskRecord | None:
        return None

    def get_by_correlation_id(self, correlation_id: str) -> ComputeTaskRecord | None:
        return None

    def describe(self) -> dict[str, object]:
        return {"kind": "test.failing_api_compute_status_store", "durable": True}


def test_compute_substrate_submit_denies_missing_actor(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(actor=""),
    ).json()

    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["denial_reason"] == "missing_actor"
    assert body["governance"]["uses_compute_substrate_service"] is False
    assert not (tmp_path / "francis_data").exists()


def test_compute_substrate_submit_requires_submit_scope(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"status.reader": ["compute:status:read"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(actor="status.reader", request_id="api-status-reader-submit"),
    ).json()

    assert body["ok"] is False
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["required_scope"] == "compute:submit"
    assert body["governance"]["uses_compute_substrate_service"] is False
    assert not (tmp_path / "francis_data").exists()


def test_compute_substrate_submit_scope_does_not_allow_status_read(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    submitted = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(request_id="api-submit-no-status"),
    ).json()

    readback = client.get(
        "/compute-substrate/status/api-submit-no-status",
        params={"actor": "compute.submitter"},
    ).json()

    assert submitted["ok"] is True
    assert readback["ok"] is False
    assert readback["error"] == "api_permission_denied"
    assert readback["governance"]["required_scope"] == "compute:status:read"


def test_compute_substrate_submit_allows_bounded_direct_request(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    raw_output_marker = "RAW_OUTPUT_SHOULD_NOT_RETURN"

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-bounded-submit",
            message=raw_output_marker,
        ),
    ).json()
    serialized = json.dumps(body, sort_keys=True)

    assert body["ok"] is True
    assert body["accepted"] is True
    assert body["status"] == "succeeded"
    assert body["task_id"] == "api-bounded-submit"
    assert body["correlation_id"] == "trace-api-bounded-submit"
    assert body["receipt_id"]
    assert body["receipt_persisted"] is True
    assert body["durable_status_persistence"] is True
    assert body["status_persisted"] is True
    assert body["governance"]["uses_compute_substrate_service"] is True
    assert body["governance"]["calls_backend_directly"] is False
    assert body["governance"]["calls_governor_directly"] is False
    assert body["record"]["stores_payload"] is False
    assert body["record"]["stores_output"] is False
    assert raw_output_marker not in serialized
    assert "MODEL_PROMPT_SHOULD_NOT_RETURN" not in serialized
    assert "C:\\Sensitive\\Should\\Not\\Return" not in serialized
    assert "receipt_path" not in serialized


def test_compute_substrate_submit_malformed_request_denied_safely(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(request_id="api-malformed", capability=""),
    ).json()

    assert body["ok"] is False
    assert body["accepted"] is False
    assert body["error"] == "malformed_request"
    assert body["denial_reason"] == "missing_requested_capability"
    assert body["governance"]["uses_compute_substrate_service"] is False


def test_compute_substrate_submit_rejects_malformed_body_parts_without_consuming_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    approval_store = LocalJsonComputeApprovalStore()
    cases: tuple[tuple[str, dict[str, object], str], ...] = (
        (
            "api-invalid-request-id",
            {
                **_submit_payload(
                    request_id="api-invalid-request-id",
                    approval_required=True,
                    approval_id="api-approval-invalid-request-id",
                ),
                "request_id": {"raw": "RAW_ID_SHOULD_NOT_RETURN"},
            },
            "invalid_request_id",
        ),
        (
            "api-invalid-payload",
            _submit_payload(
                request_id="api-invalid-payload",
                payload=["RAW_PAYLOAD_SHOULD_NOT_RETURN"],
                approval_required=True,
                approval_id="api-approval-invalid-payload",
            ),
            "invalid_payload",
        ),
        (
            "api-invalid-budget",
            _submit_payload(
                request_id="api-invalid-budget",
                approval_required=True,
                approval_id="api-approval-invalid-budget",
                resource_budget=["RAW_BUDGET_SHOULD_NOT_RETURN"],  # type: ignore[arg-type]
            ),
            "invalid_resource_budget",
        ),
        (
            "api-invalid-deadline",
            _submit_payload(
                request_id="api-invalid-deadline",
                approval_required=True,
                approval_id="api-approval-invalid-deadline",
                deadline="RAW_DEADLINE_SHOULD_NOT_RETURN",
            ),
            "invalid_deadline",
        ),
        (
            "api-invalid-approval-required",
            {
                **_submit_payload(
                    request_id="api-invalid-approval-required",
                    approval_required=True,
                    approval_id="api-approval-invalid-approval-required",
                ),
                "approval_required": "RAW_APPROVAL_BOOL_SHOULD_NOT_RETURN",
            },
            "invalid_approval_required",
        ),
        (
            "api-invalid-cancel-requested",
            {
                **_submit_payload(
                    request_id="api-invalid-cancel-requested",
                    approval_required=True,
                    approval_id="api-approval-invalid-cancel-requested",
                ),
                "cancel_requested": "RAW_CANCEL_BOOL_SHOULD_NOT_RETURN",
            },
            "invalid_cancel_requested",
        ),
    )

    for task_id, request_body, expected_reason in cases:
        approval_id = str(request_body["approval_id"])
        approval_store.add(_approval_grant(task_id=task_id, approval_id=approval_id))

        response_body = client.post("/compute-substrate/submit", json=request_body).json()
        serialized = json.dumps(response_body, sort_keys=True)
        approval = approval_store.get(approval_id)

        assert response_body["ok"] is False
        assert response_body["error"] == "malformed_request"
        assert response_body["denial_reason"] == expected_reason
        assert response_body["governance"]["uses_compute_substrate_service"] is False
        assert approval is not None
        assert approval.consumed_at_ms == 0
        assert "RAW_ID_SHOULD_NOT_RETURN" not in serialized
        assert "RAW_PAYLOAD_SHOULD_NOT_RETURN" not in serialized
        assert "RAW_BUDGET_SHOULD_NOT_RETURN" not in serialized
        assert "RAW_DEADLINE_SHOULD_NOT_RETURN" not in serialized
        assert "RAW_APPROVAL_BOOL_SHOULD_NOT_RETURN" not in serialized
        assert "RAW_CANCEL_BOOL_SHOULD_NOT_RETURN" not in serialized


def test_compute_substrate_api_cannot_downgrade_approval_required(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-approval-budget-required",
            approval_required=False,
            resource_budget={"approval_required": True},
        ),
    ).json()

    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["denial_reason"] == "missing_approval"
    assert body["approval_required"] is True
    assert body["approval_satisfied"] is False
    assert body["approval_consumed"] is False


def test_compute_substrate_api_denies_default_for_network_gpu_and_filesystem(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    network = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-network-denied",
            resource_budget={"allow_network": True},
        ),
    ).json()
    gpu = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-gpu-denied",
            resource_budget={"allow_gpu": True},
        ),
    ).json()
    filesystem = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-filesystem-denied",
            resource_budget={"filesystem_scope": ["D:/Francis"]},
        ),
    ).json()

    assert network["status"] == "denied"
    assert network["denial_reason"] == "network_allowed"
    assert gpu["status"] == "denied"
    assert gpu["denial_reason"] == "gpu_allowed"
    assert filesystem["status"] == "denied"
    assert filesystem["denial_reason"] == "filesystem_scope_allowed"


def test_compute_substrate_api_approval_required_without_valid_approval_denied(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-missing-approval",
            approval_required=True,
        ),
    ).json()

    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["denial_reason"] == "missing_approval"
    assert body["approval_required"] is True


def test_compute_substrate_api_approval_grant_does_not_replace_api_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"status.reader": ["compute:status:read"]})
    approval_store = LocalJsonComputeApprovalStore()
    approval_store.add(_approval_grant(task_id="api-no-submit-scope", approval_id="api-approval-no-submit-scope"))

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            actor="status.reader",
            request_id="api-no-submit-scope",
            approval_required=True,
            approval_id="api-approval-no-submit-scope",
        ),
    ).json()
    approval = approval_store.get("api-approval-no-submit-scope")

    assert body["ok"] is False
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["uses_compute_substrate_service"] is False
    assert approval is not None
    assert approval.consumed_at_ms == 0


def test_compute_substrate_api_full_governed_checkpoint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(
        monkeypatch,
        tmp_path,
        actor_scopes={
            "compute.submitter": ["compute:submit"],
            "status.reader": ["compute:status:read"],
        },
    )
    data_root = tmp_path / "francis_data"
    task_id = "api-full-governed-checkpoint"
    approval_id = "api-approval-full-governed-checkpoint"
    correlation_id = f"trace-{task_id}"
    raw_payload_marker = "RAW_PAYLOAD_SHOULD_NOT_PERSIST"
    raw_output_marker = "RAW_OUTPUT_SHOULD_NOT_PERSIST"
    approval_secret_marker = "APPROVAL_SECRET_SHOULD_NOT_PERSIST"
    model_prompt_marker = "MODEL_PROMPT_SHOULD_NOT_PERSIST"
    filesystem_marker = "C:\\Sensitive\\Should\\Not\\Persist"
    approval_store = LocalJsonComputeApprovalStore()
    receipt_store = LocalJsonComputeReceiptStore()
    status_store = LocalJsonComputeStatusStore()
    approval_store.add(
        _approval_grant(
            task_id=task_id,
            approval_id=approval_id,
            approval_secret=approval_secret_marker,
        )
    )
    stored_before = approval_store.get(approval_id)
    assert stored_before is not None
    assert stored_before.consumed_at_ms == 0
    assert stored_before.consumed_by_task_id == ""

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id=task_id,
            payload={
                "message": raw_output_marker,
                "payload_marker": raw_payload_marker,
                "model_prompt": model_prompt_marker,
                "filesystem_hint": filesystem_marker,
            },
            approval_required=True,
            approval_id=approval_id,
        ),
    ).json()
    task_status = client.get(
        f"/compute-substrate/status/{task_id}",
        params={"actor": "status.reader"},
    ).json()
    correlation_status = client.get(
        f"/compute-substrate/status/by-correlation/{correlation_id}",
        params={"actor": "status.reader"},
    ).json()
    consumed = approval_store.get(approval_id)
    receipt = receipt_store.read_receipt(str(body["receipt_id"]))
    persisted_task_status = status_store.get_by_task_id(task_id)
    persisted_correlation_status = status_store.get_by_correlation_id(correlation_id)
    durable_text = _durable_text(data_root / "artifacts" / "compute_substrate")
    serialized = json.dumps(
        {
            "submit": body,
            "task_status": task_status,
            "correlation_status": correlation_status,
        },
        sort_keys=True,
    )

    assert body["ok"] is True
    assert body["accepted"] is True
    assert body["status"] == "succeeded"
    assert body["error"] == ""
    assert body["task_id"] == task_id
    assert body["correlation_id"] == correlation_id
    assert body["approval_required"] is True
    assert body["approval_satisfied"] is True
    assert body["approval_id"] == approval_id
    assert body["approval_consumed"] is True
    assert body["receipt_id"]
    assert body["receipt_persisted"] is True
    assert body["receipt_persistence_status"] == "persisted_local_json"
    assert body["receipt_persistence_failed"] is False
    assert body["durable_status_persistence"] is True
    assert body["status_write_attempted"] is True
    assert body["status_write_succeeded"] is True
    assert body["status_persisted"] is True
    assert body["status_persistence_failed"] is False
    assert body["status_persistence_error"] == ""
    assert body["governance"]["api_permission_gate"] is True
    assert body["governance"]["uses_compute_substrate_service"] is True
    assert body["governance"]["calls_backend_directly"] is False
    assert body["governance"]["calls_governor_directly"] is False
    assert body["governance"]["durable_approval_persistence"] is True
    assert body["governance"]["durable_compute_receipt_persistence"] is True
    assert body["governance"]["durable_status_persistence"] is True
    assert consumed is not None
    assert consumed.consumed_at_ms > 0
    assert consumed.consumed_by_task_id == task_id

    assert receipt is not None
    assert receipt.receipt_id == body["receipt_id"]
    assert receipt.task_id == task_id
    assert receipt.trace_id == correlation_id
    assert receipt.approval_id == approval_id
    assert receipt.persisted is True
    assert receipt.status == "success"
    assert receipt.governance["approval_required"] is True
    assert receipt.governance["approval_satisfied"] is True
    assert receipt.governance["approval_consumed"] is True
    assert receipt.governance["approval_persistence"] == "persisted_local_json"
    assert receipt.governance["receipt_persistence"] == "persisted_local_json"
    assert receipt.governance["long_term_memory_persistence"] is False
    assert receipt.governance["writes_memory"] is False

    assert task_status["ok"] is True
    assert task_status["record"]["task_id"] == task_id
    assert task_status["record"]["status"] == "succeeded"
    assert task_status["record"]["receipt_id"] == body["receipt_id"]
    assert task_status["record"]["receipt_persisted"] is True
    assert task_status["record"]["approval_required"] is True
    assert task_status["record"]["approval_id"] == approval_id
    assert task_status["record"]["approval_satisfied"] is True
    assert task_status["record"]["approval_consumed"] is True
    assert task_status["record"]["status_write_succeeded"] is True
    assert task_status["governance"]["status_readback_only"] is True
    assert task_status["governance"]["grants_execution_authority"] is False

    assert correlation_status["ok"] is True
    assert correlation_status["record"]["task_id"] == task_id
    assert correlation_status["record"]["correlation_id"] == correlation_id
    assert correlation_status["record"]["receipt_id"] == body["receipt_id"]
    assert correlation_status["record"]["approval_consumed"] is True

    assert persisted_task_status is not None
    assert persisted_task_status.task_id == task_id
    assert persisted_task_status.correlation_id == correlation_id
    assert persisted_task_status.receipt_id == body["receipt_id"]
    assert persisted_task_status.receipt_persisted is True
    assert persisted_task_status.approval_required is True
    assert persisted_task_status.approval_id == approval_id
    assert persisted_task_status.approval_satisfied is True
    assert persisted_task_status.approval_consumed is True
    assert persisted_task_status.status_write_succeeded is True
    assert persisted_correlation_status == persisted_task_status

    for sentinel in (
        raw_payload_marker,
        "RAW_OUTPUT_SHOULD_NOT_PERSIST",
        approval_secret_marker,
        model_prompt_marker,
        filesystem_marker,
        "C:\\\\Sensitive\\\\Should\\\\Not\\\\Persist",
    ):
        assert sentinel not in serialized
        assert sentinel not in durable_text
    assert "LiveLearningEvent" not in durable_text
    assert "live_learning_event" not in durable_text


def test_compute_substrate_api_consumed_approval_cannot_be_reused(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    approval_store = LocalJsonComputeApprovalStore()
    approval_store.add(_approval_grant(task_id="api-reuse-approval", approval_id="api-approval-reuse"))

    first = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-reuse-approval",
            approval_required=True,
            approval_id="api-approval-reuse",
        ),
    ).json()
    second = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-reuse-approval",
            approval_required=True,
            approval_id="api-approval-reuse",
        ),
    ).json()
    approval = approval_store.get("api-approval-reuse")

    assert first["status"] == "succeeded"
    assert first["approval_consumed"] is True
    assert second["status"] == "denied"
    assert second["denial_reason"] == "already_consumed_approval"
    assert second["approval_consumed"] is False
    assert approval is not None
    assert approval.consumed_at_ms > 0
    assert approval.consumed_by_task_id == "api-reuse-approval"


def test_compute_substrate_api_denies_expired_revoked_and_mismatched_approvals(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    approval_store = LocalJsonComputeApprovalStore()
    cases = (
        (
            "api-expired-approval",
            "api-approval-expired",
            replace(
                _approval_grant(task_id="api-expired-approval", approval_id="api-approval-expired"),
                expires_at_ms=1,
            ),
            "expired_approval",
        ),
        (
            "api-revoked-approval",
            "api-approval-revoked",
            replace(
                _approval_grant(task_id="api-revoked-approval", approval_id="api-approval-revoked"),
                revoked=True,
            ),
            "revoked_approval",
        ),
        (
            "api-mismatched-approval",
            "api-approval-mismatched",
            _approval_grant(task_id="different-task-boundary", approval_id="api-approval-mismatched"),
            "task_id_mismatch",
        ),
    )

    for task_id, approval_id, grant, expected_reason in cases:
        approval_store.add(grant)

        body = client.post(
            "/compute-substrate/submit",
            json=_submit_payload(
                request_id=task_id,
                approval_required=True,
                approval_id=approval_id,
            ),
        ).json()
        approval = approval_store.get(approval_id)

        assert body["status"] == "denied"
        assert body["denial_reason"] == expected_reason
        assert body["approval_consumed"] is False
        assert approval is not None
        assert approval.consumed_at_ms == 0


def test_compute_substrate_api_pre_execution_interruption_does_not_consume_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    approval_store = LocalJsonComputeApprovalStore()
    approval_store.add(_approval_grant(task_id="api-cancel-before-start", approval_id="api-approval-cancel"))
    approval_store.add(_approval_grant(task_id="api-deadline-before-start", approval_id="api-approval-deadline"))

    cancelled = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-cancel-before-start",
            approval_required=True,
            approval_id="api-approval-cancel",
            cancel_requested=True,
            cancellation_reason="operator_cancelled_before_start",
        ),
    ).json()
    timed_out = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-deadline-before-start",
            approval_required=True,
            approval_id="api-approval-deadline",
            deadline={"deadline_at_ms": 1, "source": "test"},
        ),
    ).json()
    cancel_approval = approval_store.get("api-approval-cancel")
    deadline_approval = approval_store.get("api-approval-deadline")

    assert cancelled["status"] == "cancelled"
    assert cancelled["approval_satisfied"] is True
    assert cancelled["approval_consumed"] is False
    assert cancelled["cancellation_requested"] is True
    assert cancelled["record"]["execution_started"] is False
    assert timed_out["status"] == "timed_out"
    assert timed_out["approval_satisfied"] is True
    assert timed_out["approval_consumed"] is False
    assert timed_out["timed_out"] is True
    assert timed_out["timeout_stage"] == "pre_execution"
    assert timed_out["record"]["execution_started"] is False
    assert cancel_approval is not None
    assert cancel_approval.consumed_at_ms == 0
    assert deadline_approval is not None
    assert deadline_approval.consumed_at_ms == 0


def test_compute_substrate_api_timeout_after_backend_start_consumes_approval_truthfully(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})
    approval_store = LocalJsonComputeApprovalStore()
    approval_store.add(
        _approval_grant(
            task_id="api-timeout-after-start",
            approval_id="api-approval-timeout-after-start",
            capability="cooperative_delay_test",
        )
    )

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-timeout-after-start",
            capability="cooperative_delay_test",
            payload={
                "steps": 1,
                "delay_ms": 25,
                "model_prompt": "MODEL_PROMPT_SHOULD_NOT_RETURN",
            },
            approval_required=True,
            approval_id="api-approval-timeout-after-start",
            resource_budget={"max_runtime_ms": 1, "max_compute_units": 5},
            deadline={"deadline_at_ms": 9999999999999, "source": "test"},
        ),
    ).json()
    approval = approval_store.get("api-approval-timeout-after-start")
    serialized = json.dumps(body, sort_keys=True)

    assert body["status"] == "timed_out"
    assert body["approval_satisfied"] is True
    assert body["approval_consumed"] is True
    assert body["timed_out"] is True
    assert body["timeout_stage"] == "post_execution"
    assert body["record"]["execution_started"] is True
    assert approval is not None
    assert approval.consumed_at_ms > 0
    assert "MODEL_PROMPT_SHOULD_NOT_RETURN" not in serialized


def test_compute_substrate_status_unknown_and_unsafe_inputs_fail_closed(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path, actor_scopes={"status.reader": ["compute:status:read"]})

    body = client.get(
        "/compute-substrate/status/missing-task",
        params={"actor": "status.reader"},
    ).json()

    assert body["ok"] is False
    assert body["found"] is False
    assert body["status"] == "unknown"
    assert body["error"] == "status_not_found"
    assert body["record"]["stores_payload"] is False
    assert body["record"]["stores_output"] is False

    correlation = client.get(
        "/compute-substrate/status/by-correlation/missing-correlation",
        params={"actor": "status.reader"},
    ).json()
    assert correlation["ok"] is False
    assert correlation["found"] is False
    assert correlation["status"] == "unknown"

    for path, expected_reason in (
        ("/compute-substrate/status/%20%20%20", "invalid_task_id"),
        ("/compute-substrate/status/bad..id", "invalid_task_id"),
        ("/compute-substrate/status/bad:id", "invalid_task_id"),
        ("/compute-substrate/status/bad%5Cid", "invalid_task_id"),
        ("/compute-substrate/status/C:Temp", "invalid_task_id"),
        ("/compute-substrate/status/by-correlation/%20%20%20", "invalid_correlation_id"),
        ("/compute-substrate/status/by-correlation/bad..id", "invalid_correlation_id"),
        ("/compute-substrate/status/by-correlation/bad:id", "invalid_correlation_id"),
        ("/compute-substrate/status/by-correlation/bad%5Cid", "invalid_correlation_id"),
    ):
        rejected = client.get(path, params={"actor": "status.reader"}).json()
        assert rejected["ok"] is False
        assert rejected["error"] == "malformed_request"
        assert rejected["denial_reason"] == expected_reason

    assert client.get("/compute-substrate/status/bad/id", params={"actor": "status.reader"}).status_code == 404


def test_compute_substrate_api_reports_receipt_persistence_failure_truthfully(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.compute_substrate import ComputeSubstrateService

    service = ComputeSubstrateService(receipt_store=_FailingReceiptStore())
    monkeypatch.setattr(compute_route, "_compute_substrate_service", lambda: service)
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(request_id="api-receipt-failure"),
    ).json()
    serialized = json.dumps(body, sort_keys=True)

    assert body["ok"] is False
    assert body["status"] == "receipt_persistence_failed"
    assert body["receipt_persisted"] is False
    assert body["receipt_persistence_status"] == "persistence_failed"
    assert body["receipt_persistence_failed"] is True
    assert "RAW_OUTPUT_SHOULD_NOT_RETURN" not in serialized


def test_compute_substrate_api_reports_status_persistence_failure_truthfully(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.compute_substrate import ComputeSubstrateService

    status_store = _FailingStatusStore()
    service = ComputeSubstrateService(status_store=status_store)
    monkeypatch.setattr(compute_route, "_compute_substrate_service", lambda: service)
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-status-failure",
            message="RAW_PAYLOAD_SHOULD_NOT_RETURN",
        ),
    ).json()
    serialized = json.dumps(body, sort_keys=True)

    assert status_store.upsert_calls == 2
    assert body["ok"] is True
    assert body["status"] == "succeeded"
    assert body["status_write_attempted"] is True
    assert body["status_write_succeeded"] is False
    assert body["status_persistence_failed"] is True
    assert body["status_persistence_error"] == "OSError: status_store_write_failed"
    assert "RAW_PAYLOAD_SHOULD_NOT_RETURN" not in serialized


def test_compute_substrate_api_reports_receipt_and_status_persistence_failures_together(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.compute_substrate import ComputeSubstrateService

    status_store = _FailingStatusStore()
    service = ComputeSubstrateService(
        receipt_store=_FailingReceiptStore(),
        status_store=status_store,
    )
    monkeypatch.setattr(compute_route, "_compute_substrate_service", lambda: service)
    client = _client(monkeypatch, tmp_path, actor_scopes={"compute.submitter": ["compute:submit"]})

    body = client.post(
        "/compute-substrate/submit",
        json=_submit_payload(
            request_id="api-receipt-and-status-failure",
            message="RAW_OUTPUT_AND_PAYLOAD_SHOULD_NOT_RETURN",
        ),
    ).json()
    serialized = json.dumps(body, sort_keys=True)

    assert status_store.upsert_calls == 2
    assert body["ok"] is False
    assert body["status"] == "receipt_persistence_failed"
    assert body["receipt_persisted"] is False
    assert body["receipt_persistence_failed"] is True
    assert body["status_write_attempted"] is True
    assert body["status_write_succeeded"] is False
    assert body["status_persistence_failed"] is True
    assert body["status_persistence_error"] == "OSError: status_store_write_failed"
    assert "RAW_OUTPUT_AND_PAYLOAD_SHOULD_NOT_RETURN" not in serialized


def test_compute_substrate_api_route_uses_service_boundary() -> None:
    source = inspect.getsource(compute_route)

    assert "ComputeSubstrateService" in source
    assert ".submit(submission)" in source
    assert "SafeLocalBackend" not in source
    assert "SubstrateGovernor" not in source
    assert "import subprocess" not in source
    assert "shell=True" not in source
    assert "asyncio.create_task" not in source
    assert ".authorize(" not in source
    assert ".consume(" not in source
    assert "backend_for(" not in source
