from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from francis import managed_copy_runtime_start as runtime_start
from francis import managed_copy_runtime_evidence as runtime_evidence
from francis.process_identity import process_identity


@pytest.fixture
def runtime_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    requested_data_root = tmp_path.parent / f"mcr_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(requested_data_root))
    data_root = runtime_start.data_dir()
    tenant_key = "a" * 64
    copy_id = "managed_copy_aaaaaaaaaaaaaaaa"
    provision_id = "managed_copy_provision_fixture"
    isolation_id = "managed_copy_isolation_fixture"
    tenant_root = data_root / "managed_copies" / "tenants" / tenant_key
    (tenant_root / "receipts").mkdir(parents=True)
    provision = {
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "receipt_id": provision_id,
        "provision_fingerprint": "b" * 64,
        "state_root": f"managed_copies/tenants/{tenant_key}",
    }
    isolation = {
        "copy_id": copy_id,
        "tenant_key": tenant_key,
        "receipt_id": isolation_id,
        "provisioning_receipt_id": provision_id,
        "provision_fingerprint": "b" * 64,
        "verification_fingerprint": "c" * 64,
        "live_state_aligned": True,
        "state_root": f"managed_copies/tenants/{tenant_key}",
    }

    def provision_for_copy(requested_copy: str, *, provisioning_receipt_id: str = "") -> dict[str, Any]:
        if requested_copy == copy_id and provisioning_receipt_id == provision_id:
            return dict(provision)
        return {}

    def isolation_for_provision(
        requested_provision: str,
        *,
        provision_fingerprint: str = "",
        copy_id: str = "",
    ) -> dict[str, Any]:
        if (
            requested_provision == provision_id
            and provision_fingerprint == provision["provision_fingerprint"]
            and copy_id == provision["copy_id"]
        ):
            return dict(isolation)
        return {}

    monkeypatch.setattr(runtime_start, "managed_copy_provision_for_copy", provision_for_copy)
    monkeypatch.setattr(
        runtime_start,
        "latest_managed_copy_isolation_verification_for_provision",
        isolation_for_provision,
    )
    payload = {
        "request_actor": "stage18.runtime-test",
        "approval_id": "runtime-start-approval-1",
        "copy_id": copy_id,
        "provisioning_receipt_id": provision_id,
        "isolation_verification_receipt_id": isolation_id,
        "action_nonce": "runtime-start-nonce-1",
        "trace_id": "trace-runtime-start-1",
        "startup_timeout_ms": 3_000,
        "lease_seconds": 10,
        "confirm_runtime_start": True,
    }
    return {
        "data_root": data_root,
        "tenant_root": tenant_root,
        "provision": provision,
        "isolation": isolation,
        "payload": payload,
    }


def _approve(runtime_fixture: dict[str, Any], *, changes: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = runtime_fixture["payload"]
    proposal = runtime_start.runtime_start_proposal(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert proposal["descriptor"]
    approval_payload = {
        "contract": runtime_start.RUNTIME_START_CONTRACT,
        "action": runtime_start.RUNTIME_START_ACTION,
        "request_actor": payload["request_actor"],
        "descriptor": proposal["descriptor"],
        "descriptor_fingerprint": proposal["descriptor_fingerprint"],
        "action_nonce": payload["action_nonce"],
        "trace_id": payload["trace_id"],
        "expires_at_unix_ms": int(time.time() * 1000) + 60_000,
        "revoked": False,
        "proposal_lineage": proposal["descriptor"]["proposal_lineage"],
    }
    approval_payload.update(changes or {})
    approval = {
        "id": payload["approval_id"],
        "ts": time.time(),
        "action": runtime_start.RUNTIME_START_ACTION,
        "reason": "isolated fixed fixture runtime startup",
        "payload": approval_payload,
        "status": "approved",
        "decision": "approve",
        "decision_actor": "test.operator",
        "decided_ts": time.time(),
    }
    path = runtime_fixture["data_root"] / "approvals" / "approved" / f"{approval['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approval), encoding="utf-8")
    return approval


def test_missing_expired_revoked_and_changed_approval_fail_closed(runtime_fixture: dict[str, Any]) -> None:
    payload = runtime_fixture["payload"]
    missing = runtime_start.runtime_start_proposal(payload, actor=payload["request_actor"], stage17_closed=True)
    assert missing["error"] == "managed_copy_runtime_start_approval_missing"

    _approve(runtime_fixture, changes={"expires_at_unix_ms": int(time.time() * 1000) - 1})
    expired = runtime_start.runtime_start_proposal(payload, actor=payload["request_actor"], stage17_closed=True)
    assert expired["error"] == "managed_copy_runtime_start_approval_expired"

    _approve(runtime_fixture, changes={"revoked": True})
    revoked = runtime_start.runtime_start_proposal(payload, actor=payload["request_actor"], stage17_closed=True)
    assert revoked["error"] == "managed_copy_runtime_start_approval_revoked"

    _approve(runtime_fixture)
    altered = {**payload, "lease_seconds": payload["lease_seconds"] + 1}
    mismatch = runtime_start.runtime_start_proposal(altered, actor=payload["request_actor"], stage17_closed=True)
    assert mismatch["error"] == "managed_copy_runtime_start_approval_binding_mismatch"
    assert not (runtime_fixture["tenant_root"] / "receipts" / "runtime_start").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"executable": "cmd.exe"},
        {"arguments": ["/c", "whoami"]},
        {"environment": {"SECRET": "value"}},
        {"working_directory": "C:/"},
        {"startup_timeout_ms": True},
        {"lease_seconds": 1.0},
    ],
)
def test_caller_process_injection_and_non_exact_numbers_are_rejected(
    runtime_fixture: dict[str, Any], change: dict[str, Any]
) -> None:
    payload = {**runtime_fixture["payload"], **change}
    result = runtime_start.runtime_start_proposal(
        payload,
        actor=runtime_fixture["payload"]["request_actor"],
        stage17_closed=True,
    )
    assert result["ok"] is False
    assert "managed_copy_runtime_start_payload_schema_invalid" in result["blockers"] or any(
        blocker.endswith("_invalid") for blocker in result["blockers"]
    )


def test_fixed_fixture_startup_current_verification_and_exact_cleanup(runtime_fixture: dict[str, Any]) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    result: dict[str, Any] = {}
    try:
        result = runtime_start.start_fixture_runtime(
            payload,
            actor=payload["request_actor"],
            stage17_closed=True,
        )
        assert result["ok"] is True, result
        assert result["status"] == "ready"
        receipt = result["receipt"]
        assert receipt["fixture_runtime"] is True
        assert receipt["evidence_class"] == "fixture_software_only"
        assert receipt["runtime_gate_ready"] is False
        observed = process_identity(receipt["pid"])
        assert observed
        assert observed["parent_pid"] == receipt["parent_pid"]

        source = runtime_start.verify_runtime_startup_source(receipt["receipt_id"], runtime_start._fingerprint(receipt))
        assert source["valid"] is True, source
        assert source["evidence_class"] == "fixture_software_only"

        replay = runtime_start.start_fixture_runtime(
            payload,
            actor=payload["request_actor"],
            stage17_closed=True,
        )
        assert replay["ok"] is True, replay
        assert replay["status"] == "already_started"
        assert replay["receipt"]["receipt_id"] == receipt["receipt_id"]
    finally:
        if result.get("ok") and result.get("receipt"):
            cleanup = runtime_start.cleanup_fixture_runtime(result["receipt"])
            assert cleanup["ok"] is True
            assert not process_identity(result["receipt"]["pid"])
            assert not (runtime_fixture["tenant_root"] / "receipts" / "runtime_start" / ".write.lock").exists()

        consumed = runtime_start.start_fixture_runtime(
            payload,
            actor=payload["request_actor"],
            stage17_closed=True,
        )
        assert consumed["error"] == "managed_copy_runtime_start_approval_already_consumed"


def test_pid_identity_and_stale_heartbeat_collapse_readiness(
    runtime_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    result = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert result["ok"] is True, result
    receipt = result["receipt"]
    try:
        changed = {**receipt, "process_creation_token": receipt["process_creation_token"] + 1}
        changed_without_fingerprint = {key: value for key, value in changed.items() if key != "startup_fingerprint"}
        changed["startup_fingerprint"] = runtime_start._fingerprint(changed_without_fingerprint)
        assert runtime_start._current_state(changed)["ready"] is False

        state_dir = runtime_fixture["data_root"] / receipt["state_path"]
        heartbeat_path = state_dir / "heartbeat.json"
        heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        heartbeat["observed_at_unix_ms"] = int(time.time() * 1000) - 5_000
        original_read_json = runtime_start._read_json
        monkeypatch.setattr(
            runtime_start,
            "_read_json",
            lambda path: heartbeat if path == heartbeat_path else original_read_json(path),
        )
        assert runtime_start._current_state(receipt)["blocker"] == "runtime_heartbeat_stale"
    finally:
        runtime_start.cleanup_fixture_runtime(receipt)


def test_current_state_and_cleanup_fail_closed_when_guarded_path_is_rejected(
    runtime_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    result = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert result["ok"] is True, result
    receipt = result["receipt"]
    guarded_subpath = runtime_start.managed_copy_isolation_guarded_subpath
    try:
        monkeypatch.setattr(runtime_start, "managed_copy_isolation_guarded_subpath", lambda *args, **kwargs: None)
        assert runtime_start._current_state(receipt)["blocker"] == "runtime_process_identity_mismatch"
        assert runtime_start.cleanup_fixture_runtime(receipt)["error"] == "fixture_runtime_identity_mismatch"
    finally:
        monkeypatch.setattr(runtime_start, "managed_copy_isolation_guarded_subpath", guarded_subpath)
        assert runtime_start.cleanup_fixture_runtime(receipt)["ok"] is True


def test_child_exit_before_handshake_records_failure_and_leaves_no_process(
    runtime_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    monkeypatch.setattr(
        runtime_start,
        "_fixture_command",
        lambda **_: [sys.executable, "-c", "raise SystemExit(7)"],
    )
    result = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert not process_identity(result["receipt"]["pid"])
    assert list(runtime_fixture["tenant_root"].glob("receipts/runtime_start/*/failed.json"))

    replay = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert replay["error"] == "managed_copy_runtime_start_approval_already_consumed"


def test_process_creation_failure_records_failed_attempt_and_consumes_approval(
    runtime_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    monkeypatch.setattr(
        runtime_start.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fixture launch denied")),
    )

    result = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert result["error"] == "managed_copy_runtime_start_process_creation_failed"
    assert result["receipt"]["process_created"] is False
    replay = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert replay["error"] == "managed_copy_runtime_start_approval_already_consumed"


def test_runtime_failure_receipt_does_not_expose_exception_text(
    runtime_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)

    def raise_sensitive_error(*args: object, **kwargs: object) -> str:
        raise RuntimeError(r"C:\operator\secret.txt")

    monkeypatch.setattr(runtime_start, "_runtime_records_blocker", raise_sensitive_error)
    result = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )

    assert result["error"] == "managed_copy_runtime_start_runtime_failed"
    serialized = json.dumps(result["receipt"])
    assert "operator" not in serialized
    assert "secret" not in serialized


def test_last_moment_approval_revocation_prevents_process_creation(
    runtime_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = runtime_fixture["payload"]
    approval = _approve(runtime_fixture)
    approval_path = runtime_fixture["data_root"] / "approvals" / "approved" / f"{approval['id']}.json"
    original_write = runtime_start._write_immutable

    def revoke_after_attempt(path: Path, value: dict[str, Any]) -> None:
        original_write(path, value)
        if path.name == "attempt.json":
            approval["payload"]["revoked"] = True
            approval_path.write_text(json.dumps(approval), encoding="utf-8")

    monkeypatch.setattr(runtime_start, "_write_immutable", revoke_after_attempt)
    monkeypatch.setattr(
        runtime_start.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("revoked approval must not create a process"),
    )
    result = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )

    assert result["error"] == "managed_copy_runtime_start_approval_revoked"
    assert result["receipt"]["process_created"] is False
    assert list(runtime_fixture["tenant_root"].glob("receipts/runtime_start/*/failed.json"))


def test_current_fixture_startup_cannot_satisfy_canonical_runtime_evidence(
    runtime_fixture: dict[str, Any],
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    started = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert started["ok"] is True, started
    startup = started["receipt"]
    try:
        evidence_payload: dict[str, Any] = {
            "request_actor": payload["request_actor"],
            "requirement_id": runtime_evidence.COPY_CREATION_REQUIREMENT,
            "proof_kind": runtime_evidence.COPY_CREATION_PROOF_KIND,
            "source_receipt_id": startup["receipt_id"],
            "source_receipt_fingerprint": runtime_start._fingerprint(startup),
            "trace_id": payload["trace_id"],
            "dry_run": True,
            "record_fingerprint": "",
            "confirm_runtime_evidence": False,
        }
        plan = runtime_evidence.plan_runtime_evidence(
            evidence_payload,
            actor=payload["request_actor"],
            stage17_closed=True,
        )
        assert plan["ok"] is False
        assert plan["blockers"] == [runtime_evidence.COPY_CREATION_SOURCE_MISSING]
        assert plan["receipt_ready"] is False
    finally:
        assert runtime_start.cleanup_fixture_runtime(startup)["ok"] is True


def test_startup_receipt_rejects_injected_fields_even_with_recomputed_fingerprint(
    runtime_fixture: dict[str, Any],
) -> None:
    payload = runtime_fixture["payload"]
    _approve(runtime_fixture)
    started = runtime_start.start_fixture_runtime(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
    )
    assert started["ok"] is True, started
    receipt = started["receipt"]
    try:
        injected = {**receipt, "unexpected": "field"}
        without_fingerprint = {key: value for key, value in injected.items() if key != "startup_fingerprint"}
        injected["startup_fingerprint"] = runtime_start._fingerprint(without_fingerprint)
        assert runtime_start._valid_startup_receipt(injected) is False
        assert runtime_start._current_state(injected)["blocker"] == "runtime_startup_receipt_invalid"
    finally:
        assert runtime_start.cleanup_fixture_runtime(receipt)["ok"] is True
