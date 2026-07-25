from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.api.routes import managed_copies as managed_routes
from francis import managed_copy_pilot_runtime as pilot
from francis import managed_copy_rogue_runtime_halt as runtime_halt
from francis.governance.pilot_scope_lease import (
    PilotLeaseBinding,
    PilotScopeLease,
    PilotScopeLeaseRegistry,
)


def _payload() -> dict[str, Any]:
    return {
        "request_actor": "stage18.recovery-operator",
        "pilot_lease_id": "pilot-lease-001",
        "startup_receipt_id": "startup-001",
        "approval_id": "halt-approval-001",
        "copy_id": "copy-001",
        "provisioning_receipt_id": "provision-001",
        "isolation_verification_receipt_id": "isolation-001",
        "integrity_evidence_receipt_id": "integrity-001",
        "integrity_evidence_fingerprint": "1" * 64,
        "rogue_detection_assessment_receipt_id": "assessment-001",
        "disposition_receipt_id": "disposition-001",
        "disposition_fingerprint": "2" * 64,
        "replacement_source": "clean_core_baseline",
        "recovery_intent_fingerprint": "3" * 64,
        "recovery_plan_fingerprint": "4" * 64,
        "confirm_halt": True,
        "trace_id": "trace-rogue-halt-001",
    }


def _startup() -> dict[str, Any]:
    return {
        "receipt_id": "startup-001",
        "startup_fingerprint": "5" * 64,
        "actor": "stage18.recovery-operator",
        "copy_id": "copy-001",
        "pilot_run_id": "pilot-run-001",
        "pilot_lease_id": "pilot-lease-001",
        "provisioning_receipt_id": "provision-001",
        "isolation_verification_receipt_id": "isolation-001",
        "pid": 1234,
        "process_creation_token": 5678,
        "runtime_identity": "francis.managed_copy.runtime.v1",
    }


@pytest.fixture
def halt_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    payload = _payload()
    startup = _startup()
    stop_calls: list[dict[str, Any]] = []
    cleanup = {
        "kind": "francis.stage18.managed_copies.pilot_runtime_cleanup_receipt",
        "receipt_id": "cleanup-001",
        "startup_receipt_id": startup["receipt_id"],
        "pilot_run_id": startup["pilot_run_id"],
        "status": "stopped",
        "pid": startup["pid"],
        "process_creation_token": startup["process_creation_token"],
        "fixture_runtime": False,
        "recorded_at_unix_ms": int(time.time() * 1000),
        "receipt_fingerprint": "",
    }
    cleanup["receipt_fingerprint"] = runtime_halt._fingerprint_without(cleanup, "receipt_fingerprint")
    state_directory = tmp_path / "runtime-state"
    state_directory.mkdir()
    monkeypatch.setattr(runtime_halt, "_state_dir", lambda receipt: state_directory)

    def plan(request: dict[str, Any], *, actor: str) -> dict[str, Any]:
        expected = runtime_halt._plan_payload(payload)
        return {
            "ok": request == expected and actor == payload["request_actor"],
            "plan_fingerprint": payload["recovery_plan_fingerprint"] if request == expected else "",
        }

    monkeypatch.setattr(
        runtime_halt,
        "managed_copy_rogue_recovery_plan",
        plan,
    )
    monkeypatch.setattr(runtime_halt, "_startup_receipt", lambda receipt_id: dict(startup))

    def stop(request: dict[str, Any], *, actor: str, seal_lease: bool = True) -> dict[str, Any]:
        stop_calls.append({"request": request, "actor": actor, "seal_lease": seal_lease})
        (state_directory / "cleanup.json").write_text(json.dumps(cleanup), encoding="utf-8")
        return {
            "ok": True,
            "status": "stopped",
            "receipt": cleanup,
        }

    monkeypatch.setattr(runtime_halt, "stop_pilot_runtime", stop)
    authority = {
        "valid": True,
        "actor_id": payload["request_actor"],
        "lease_id": payload["pilot_lease_id"],
        "pilot_run_id": startup["pilot_run_id"],
        "package_id": "rogue-halt-package-001",
        "package_fingerprint": "7" * 64,
        "operator_decision_fingerprint": "8" * 64,
        "operation_consumed_binding_count": 2,
        "lease_authority_fingerprint": "a" * 64,
    }
    descriptor = runtime_halt._descriptor(
        payload,
        startup=startup,
        actor=payload["request_actor"],
        authority=authority,
    )
    approval = {
        "approval_id": payload["approval_id"],
        "status": "approved",
        "decision": "approved",
        "action": runtime_halt.ROGUE_RUNTIME_HALT_ACTION,
        "payload": {
            "contract": runtime_halt.ROGUE_RUNTIME_HALT_CONTRACT,
            "descriptor": descriptor,
            "descriptor_fingerprint": runtime_halt._fingerprint(descriptor),
            "expires_at_unix_ms": int(time.time() * 1000) + 60_000,
            "revoked": False,
        },
        "approval_fingerprint": "",
    }
    approval["approval_fingerprint"] = runtime_halt._fingerprint_without(approval, "approval_fingerprint")
    approval_path = tmp_path / "approvals" / "approved" / f"{payload['approval_id']}.json"
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    return {
        "root": tmp_path,
        "payload": payload,
        "startup": startup,
        "approval_path": approval_path,
        "stop_calls": stop_calls,
        "cleanup": cleanup,
        "authority": authority,
    }


def test_exact_approved_halt_delegates_owned_stop_and_records_immutable_receipt(
    halt_fixture: dict[str, Any],
) -> None:
    payload = halt_fixture["payload"]
    first = runtime_halt.execute_rogue_runtime_halt(
        payload,
        actor=payload["request_actor"],
        authority=halt_fixture["authority"],
    )
    second = runtime_halt.execute_rogue_runtime_halt(
        payload,
        actor=payload["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert first["ok"] is True
    assert first["status"] == "halted"
    assert first["idempotent_replay"] is False
    assert runtime_halt.valid_rogue_runtime_halt_receipt(first["receipt"]) is True
    assert first["receipt"]["cleanup_receipt_fingerprint"] == runtime_halt._hash(halt_fixture["cleanup"])
    assert second["ok"] is True
    assert second["idempotent_replay"] is True
    assert len(halt_fixture["stop_calls"]) == 1
    assert halt_fixture["stop_calls"][0]["seal_lease"] is False
    verified = runtime_halt.verify_rogue_runtime_halt_receipt(
        first["receipt"]["receipt_id"],
        first["receipt"]["receipt_fingerprint"],
        expected=payload,
    )
    assert verified["valid"] is True


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"confirm_halt": 1}, "managed_copy_rogue_runtime_halt_confirmation_invalid"),
        ({"copy_id": "copy-002"}, "managed_copy_rogue_runtime_halt_recovery_plan_mismatch"),
        (
            {"startup_receipt_id": "startup-002"},
            "managed_copy_rogue_runtime_halt_startup_lineage_mismatch",
        ),
    ],
)
def test_malformed_or_changed_lineage_fails_before_stop(
    halt_fixture: dict[str, Any],
    change: dict[str, Any],
    error: str,
) -> None:
    payload = {**halt_fixture["payload"], **change}
    result = runtime_halt.execute_rogue_runtime_halt(
        payload,
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert result == {"ok": False, "status": "blocked", "error": error}
    assert halt_fixture["stop_calls"] == []
    assert not runtime_halt.rogue_runtime_halt_receipt_directory().exists()


def test_expired_or_tampered_approval_fails_before_stop(
    halt_fixture: dict[str, Any],
) -> None:
    approval = json.loads(halt_fixture["approval_path"].read_text(encoding="utf-8"))
    approval["payload"]["expires_at_unix_ms"] = int(time.time() * 1000) - 1
    approval["approval_fingerprint"] = runtime_halt._fingerprint_without(approval, "approval_fingerprint")
    halt_fixture["approval_path"].write_text(json.dumps(approval), encoding="utf-8")

    result = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert result["error"] == "managed_copy_rogue_runtime_halt_approval_expired"
    assert halt_fixture["stop_calls"] == []


def test_invalid_cleanup_receipt_cannot_become_halt_evidence(
    halt_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        runtime_halt,
        "stop_pilot_runtime",
        lambda *args, **kwargs: {
            "ok": True,
            "status": "stopped",
            "receipt": {**halt_fixture["cleanup"], "process_creation_token": 9999},
        },
    )

    result = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert result["error"] == "managed_copy_rogue_runtime_halt_owned_stop_failed"
    attempts = list(runtime_halt.rogue_runtime_halt_receipt_directory().glob("*.attempt.json"))
    assert len(attempts) == 1
    assert runtime_halt._valid_halt_attempt(json.loads(attempts[0].read_text(encoding="utf-8")))


def test_prior_generic_cleanup_cannot_be_relabelled_as_rogue_halt(
    halt_fixture: dict[str, Any],
) -> None:
    state_directory = halt_fixture["root"] / "runtime-state"
    (state_directory / "cleanup.json").write_text(json.dumps(halt_fixture["cleanup"]), encoding="utf-8")

    result = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert result["error"] == "managed_copy_rogue_runtime_halt_runtime_already_stopped_without_halt_attempt"
    assert halt_fixture["stop_calls"] == []


def test_matching_attempt_recovers_receipt_after_interrupted_write(
    halt_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write = runtime_halt._write_immutable
    failed_once = False

    def interrupt_receipt(path: Path, payload: dict[str, Any]) -> None:
        nonlocal failed_once
        if path.suffix == ".json" and not path.name.endswith(".attempt.json") and not failed_once:
            failed_once = True
            raise OSError("interrupted")
        original_write(path, payload)

    monkeypatch.setattr(runtime_halt, "_write_immutable", interrupt_receipt)
    first = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )
    second = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert first["error"] == "managed_copy_rogue_runtime_halt_receipt_write_failed"
    assert second["ok"] is True
    assert second["idempotent_replay"] is False
    assert len(halt_fixture["stop_calls"]) == 1


def test_approval_identity_change_after_owned_stop_fails_closed(
    halt_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_verify = runtime_halt._ApprovalFileIdentity.verify
    calls = 0

    def changes_after_stop(identity: runtime_halt._ApprovalFileIdentity) -> bool:
        nonlocal calls
        calls += 1
        return original_verify(identity) if calls < 3 else False

    monkeypatch.setattr(runtime_halt._ApprovalFileIdentity, "verify", changes_after_stop)
    result = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )

    assert result["error"] == "managed_copy_rogue_runtime_halt_approval_changed_under_authority"
    assert len(halt_fixture["stop_calls"]) == 1
    assert not [
        path
        for path in runtime_halt.rogue_runtime_halt_receipt_directory().glob("mcrrh_*.json")
        if not path.name.endswith(".attempt.json")
    ]


def test_missing_or_tampered_halt_receipt_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    expected = {
        "copy_id": "copy-001",
        "provisioning_receipt_id": "provision-001",
        "isolation_verification_receipt_id": "isolation-001",
        "integrity_evidence_receipt_id": "integrity-001",
        "integrity_evidence_fingerprint": "1" * 64,
        "rogue_detection_assessment_receipt_id": "assessment-001",
        "disposition_receipt_id": "disposition-001",
        "disposition_fingerprint": "2" * 64,
        "recovery_plan_fingerprint": "4" * 64,
    }

    missing = runtime_halt.verify_rogue_runtime_halt_receipt("halt-missing", "9" * 64, expected=expected)

    assert missing["error"] == "stage18_rogue_recovery_runtime_halt_receipt_invalid"
    assert not runtime_halt.rogue_runtime_halt_receipt_directory().exists()


def test_missing_halt_attempt_invalidates_durable_receipt(
    halt_fixture: dict[str, Any],
) -> None:
    result = runtime_halt.execute_rogue_runtime_halt(
        halt_fixture["payload"],
        actor=halt_fixture["payload"]["request_actor"],
        authority=halt_fixture["authority"],
    )
    receipt = result["receipt"]
    attempt_path = runtime_halt.rogue_runtime_halt_receipt_directory() / f"{receipt['receipt_id']}.attempt.json"
    attempt_path.unlink()

    verification = runtime_halt.verify_rogue_runtime_halt_receipt(
        receipt["receipt_id"],
        receipt["receipt_fingerprint"],
        expected=halt_fixture["payload"],
    )

    assert verification["error"] == "stage18_rogue_recovery_runtime_halt_cleanup_lineage_invalid"


def test_unscoped_route_denial_occurs_before_payload_or_filesystem_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FRANCIS_API_ACTOR_SCOPES", raising=False)
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.execute_rogue_runtime_halt",
        lambda *args, **kwargs: pytest.fail("halt implementation must not run"),
    )

    body = (
        TestClient(create_app())
        .post(
            runtime_halt.ROGUE_RUNTIME_HALT_ROUTE,
            json={"request_actor": "stage18.unscoped"},
        )
        .json()
    )

    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == runtime_halt.ROGUE_RUNTIME_HALT_SCOPE
    assert not (tmp_path / "logs" / "managed_copies").exists()


def test_exact_scope_and_one_run_lease_reach_halt_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    actor = "stage18.recovery-operator"
    lease_id = "rogue-halt-lease-001"
    registry = PilotScopeLeaseRegistry()
    now = int(time.time() * 1000)
    registry.issue(
        PilotScopeLease(
            lease_id=lease_id,
            actor_id=actor,
            package_id="rogue-halt-package-001",
            package_fingerprint="7" * 64,
            pilot_run_id="pilot-run-001",
            bindings=(
                PilotLeaseBinding(
                    pilot.PILOT_RUNTIME_SCOPE,
                    pilot.PILOT_RUNTIME_START_ROUTE,
                    "POST",
                    pilot.PILOT_RUNTIME_START_ACTION,
                ),
                PilotLeaseBinding(
                    runtime_halt.ROGUE_RUNTIME_HALT_SCOPE,
                    runtime_halt.ROGUE_RUNTIME_HALT_ROUTE,
                    "POST",
                    runtime_halt.ROGUE_RUNTIME_HALT_ACTION,
                ),
            ),
            issued_at_ms=now - 1_000,
            expires_at_ms=now + 60_000,
            runtime_nonce="rogue-halt-runtime-nonce",
            operator_decision_fingerprint="8" * 64,
        )
    )
    started = registry.authorize_binding(
        lease_id=lease_id,
        actor_id=actor,
        scope=pilot.PILOT_RUNTIME_SCOPE,
        route=pilot.PILOT_RUNTIME_START_ROUTE,
        method="POST",
        action=pilot.PILOT_RUNTIME_START_ACTION,
    )
    assert started.allowed is True
    monkeypatch.setattr(managed_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(pilot, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: [runtime_halt.ROGUE_RUNTIME_HALT_SCOPE]}),
    )
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    observed: list[tuple[dict[str, Any], str, dict[str, Any]]] = []

    def execute(payload: dict[str, Any], *, actor: str, authority: dict[str, Any]) -> dict[str, Any]:
        observed.append((payload, actor, authority))
        if len(observed) == 1:
            return {"ok": False, "status": "blocked", "error": "managed_copy_rogue_runtime_halt_receipt_write_failed"}
        return {"ok": True, "status": "halted"}

    monkeypatch.setattr(managed_routes, "execute_rogue_runtime_halt", execute)
    payload = {**_payload(), "pilot_lease_id": lease_id}

    interrupted = TestClient(create_app()).post(runtime_halt.ROGUE_RUNTIME_HALT_ROUTE, json=payload).json()
    body = TestClient(create_app()).post(runtime_halt.ROGUE_RUNTIME_HALT_ROUTE, json=payload).json()
    replay = TestClient(create_app()).post(runtime_halt.ROGUE_RUNTIME_HALT_ROUTE, json=payload).json()

    assert interrupted["error"] == "managed_copy_rogue_runtime_halt_receipt_write_failed"
    assert body == {"ok": True, "status": "halted"}
    assert observed[1][0:2] == (payload, actor)
    assert observed[1][2]["valid"] is True
    assert replay["error"] == "api_permission_denied"
