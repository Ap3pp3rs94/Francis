from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from francis import managed_copies
from francis import managed_copy_container_isolation as container_isolation
from francis import managed_copy_container_live_evidence as live_evidence
from francis import managed_copy_pilot_runtime as pilot_runtime
from francis import managed_copy_runtime_evidence as runtime_evidence
from francis import managed_copy_runtime_start as runtime_start
from francis.api.app import create_app
from francis.api.routes import managed_copies as managed_copy_routes
from francis.governance.pilot_scope_lease import (
    PilotLeaseBinding,
    PilotLeaseState,
    PilotScopeLease,
    PilotScopeLeaseRegistry,
)

_REAL_PILOT_LEASE_CONTEXT = container_isolation._pilot_lease_context


def test_windows_default_proof_base_uses_fixed_local_application_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.delenv("FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(container_isolation.sys, "platform", "win32")

    assert container_isolation._proof_base() == local_app_data / "Francis" / "managed-copy-container-proofs"


def test_explicit_proof_base_override_remains_authoritative(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "operator-proof-root"
    monkeypatch.setenv("FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT", str(configured))

    assert container_isolation._proof_base() == configured


def test_mount_snapshot_allows_expected_writable_state_updates(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    tenant = root / "tenant"
    state = root / "state"
    tenant.mkdir(parents=True)
    state.mkdir()
    operation_input = {"contract": container_isolation.INPUT_CONTRACT, "items": []}
    input_path = tenant / "work_items.json"
    input_path.write_text(json.dumps(operation_input), encoding="utf-8")
    descriptor = {
        "operation_input_file_fingerprint": container_isolation._file_sha256(input_path),
    }
    before = container_isolation._mount_source_snapshot(root, descriptor=descriptor)

    (state / "handshake.json").write_text('{"pid":1}\n', encoding="utf-8")
    (state / "heartbeat.json").write_text('{"sequence":1}\n', encoding="utf-8")

    assert before
    assert container_isolation._mount_source_snapshot(root, descriptor=descriptor) == before


def test_state_root_identity_accepts_unchanged_directory(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    state = root / "state"
    state.mkdir(parents=True)

    identity = container_isolation._StateRootIdentity.acquire(state)
    assert identity is not None
    try:
        assert identity.verify() is True
    finally:
        identity.close()


def test_state_root_identity_rejects_delete_and_recreate_with_retained_handle(tmp_path: Path) -> None:
    state = tmp_path / "proof" / "state"
    state.mkdir(parents=True)
    identity = container_isolation._StateRootIdentity.acquire(state)
    assert identity is not None
    original_token = identity.path.read_bytes()

    try:
        try:
            identity.path.unlink()
            state.rmdir()
        except PermissionError:
            # Windows denies replacement while the controller retains the file handle.
            assert identity.verify() is True
        else:
            state.mkdir()
            identity.path.write_bytes(original_token)
            assert identity.verify() is False
            assert identity.file_identity != container_isolation._file_identity(identity.path.lstat())
    finally:
        identity.close()


@pytest.mark.skipif(os.name == "nt", reason="Windows prevents replacement while the identity handle is retained")
def test_state_root_identity_rejects_replacement_when_weak_metadata_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "proof" / "state"
    state.mkdir(parents=True)
    identity = container_isolation._StateRootIdentity.acquire(state)
    assert identity is not None
    original_token = identity.path.read_bytes()

    try:
        identity.path.unlink()
        state.rmdir()
        state.mkdir()
        identity.path.write_bytes(original_token)
        monkeypatch.setattr(container_isolation, "_file_identity", lambda stat: identity.file_identity)

        assert identity.verify() is False
    finally:
        identity.close()


def test_state_root_identity_fails_closed_for_missing_or_altered_token(tmp_path: Path) -> None:
    state = tmp_path / "proof" / "state"
    state.mkdir(parents=True)
    identity = container_isolation._StateRootIdentity.acquire(state)
    assert identity is not None

    try:
        try:
            identity.path.write_text("altered\n", encoding="utf-8")
        except PermissionError:
            identity.close()
            identity.path.unlink()
        assert identity.verify() is False
    finally:
        identity.close()


def test_state_root_identity_fails_closed_when_identity_evidence_is_missing(tmp_path: Path) -> None:
    state = tmp_path / "proof" / "state"
    state.mkdir(parents=True)
    identity = container_isolation._StateRootIdentity.acquire(state)
    assert identity is not None

    identity.close()
    identity.path.unlink()

    assert identity.verify() is False


def test_state_root_identity_rejects_symlink_redirection_where_supported(tmp_path: Path) -> None:
    state = tmp_path / "proof" / "state"
    replacement = tmp_path / "replacement"
    state.mkdir(parents=True)
    replacement.mkdir()
    identity = container_isolation._StateRootIdentity.acquire(state)
    assert identity is not None

    try:
        try:
            identity.path.unlink()
        except OSError:
            assert identity.verify() is True
        else:
            try:
                identity.path.symlink_to(replacement / "identity")
            except OSError:
                assert identity.verify() is False
            else:
                assert identity.verify() is False
    finally:
        identity.close()


def test_mount_snapshot_rejects_tenant_input_tampering(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    tenant = root / "tenant"
    (root / "state").mkdir(parents=True)
    tenant.mkdir()
    input_path = tenant / "work_items.json"
    input_path.write_text('{"contract":"stage18_managed_copy_work_briefing_input_v1","items":[]}', encoding="utf-8")
    descriptor = {
        "operation_input_file_fingerprint": container_isolation._file_sha256(input_path),
    }
    assert container_isolation._mount_source_snapshot(root, descriptor=descriptor)

    input_path.write_text('{"contract":"tampered","items":[]}', encoding="utf-8")

    assert container_isolation._mount_source_snapshot(root, descriptor=descriptor) == {}


@pytest.fixture
def isolation_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    local_app_data = tmp_path / "LocalAppData"
    proof_base = local_app_data / "Francis" / "proof-journeys" / "MC-ISO-TEST"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT", str(proof_base))
    tenant_key = "a" * 64
    provision = {
        "copy_id": "managed_copy_aaaaaaaaaaaaaaaa",
        "tenant_key": tenant_key,
        "receipt_id": "managed_copy_provision_fixture",
        "provision_fingerprint": "b" * 64,
    }
    isolation = {
        "copy_id": provision["copy_id"],
        "tenant_key": tenant_key,
        "receipt_id": "managed_copy_isolation_fixture",
        "provisioning_receipt_id": provision["receipt_id"],
        "provision_fingerprint": provision["provision_fingerprint"],
        "verification_fingerprint": "c" * 64,
        "live_state_aligned": True,
    }
    monkeypatch.setattr(
        container_isolation,
        "managed_copy_provision_for_copy",
        lambda copy_id, *, provisioning_receipt_id="": (
            dict(provision)
            if copy_id == provision["copy_id"] and provisioning_receipt_id == provision["receipt_id"]
            else {}
        ),
    )
    monkeypatch.setattr(
        container_isolation,
        "latest_managed_copy_isolation_verification_for_provision",
        lambda provision_id, *, provision_fingerprint="", copy_id="": (
            dict(isolation)
            if provision_id == provision["receipt_id"]
            and provision_fingerprint == provision["provision_fingerprint"]
            and copy_id == provision["copy_id"]
            else {}
        ),
    )
    now_ms = int(time.time() * 1000)
    registry = PilotScopeLeaseRegistry()
    registry.issue(
        PilotScopeLease(
            lease_id="mciso-lease-1",
            actor_id="stage18.container-test",
            package_id="stage18-container-pilot-package",
            package_fingerprint="e" * 64,
            pilot_run_id="mciso-test-1",
            bindings=container_isolation.container_isolation_lease_bindings(),
            issued_at_ms=now_ms - 1_000,
            expires_at_ms=now_ms + 120_000,
            runtime_nonce="mciso-runtime-nonce-1",
            operator_decision_fingerprint="f" * 64,
        )
    )
    monkeypatch.setattr(pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    server = {"Os": "linux", "Arch": "amd64", "Version": "fixture"}
    image_id = "sha256:" + "d" * 64
    image_config = {
        "User": container_isolation.FIXED_CONTAINER_USER,
        "Entrypoint": ["python", container_isolation.RUNTIME_PROGRAM_CONTAINER_PATH],
        "Labels": {
            "francis.runtime.contract": container_isolation.RUNTIME_IDENTITY,
            "francis.runtime.program_sha256": container_isolation._file_sha256(container_isolation.RUNTIME_PROGRAM),
        },
    }
    payload = {
        "request_actor": "stage18.container-test",
        "approval_id": "container-isolation-approval-1",
        "runtime_start_approval_id": "runtime-start-approval-1",
        "copy_id": provision["copy_id"],
        "provisioning_receipt_id": provision["receipt_id"],
        "isolation_verification_receipt_id": isolation["receipt_id"],
        "image_manifest_digest": image_id,
        "image_platform_digest": image_id,
        "image_id": image_id,
        "image_config_fingerprint": container_isolation._fingerprint(image_config),
        "engine_id": "engine-fixture-1",
        "engine_server_fingerprint": container_isolation._fingerprint(server),
        "docker_context": "desktop-linux",
        "proof_run_id": "mciso-test-1",
        "lease_id": "mciso-lease-1",
        "runtime_nonce": "mciso-runtime-nonce-1",
        "action_nonce": "mciso-action-nonce-1",
        "trace_id": "trace-mciso-1",
        "lease_seconds": 5,
        "confirm_container_isolation": True,
        "operation_input": {
            "contract": container_isolation.INPUT_CONTRACT,
            "items": [
                {"id": "work-2", "title": "Prepare report", "priority": "normal", "status": "open"},
                {"id": "work-1", "title": "Resolve intake", "priority": "critical", "status": "open"},
            ],
        },
        "runtime_evidence_intent": {
            "requirement_id": "copy_creation_runtime_proof",
            "proof_kind": "managed_copy_creation_runtime_receipt",
            "confirm_runtime_evidence": True,
        },
    }
    return {
        "payload": payload,
        "provision": provision,
        "isolation": isolation,
        "data": tmp_path / "data",
        "server": server,
        "image_config": image_config,
        "registry": registry,
    }


def _evidence_execution_kwargs(isolation_fixture: dict[str, Any]) -> dict[str, Any]:
    payload = isolation_fixture["payload"]
    registry: PilotScopeLeaseRegistry = isolation_fixture["registry"]
    first = registry.authorize_binding(
        lease_id=payload["lease_id"],
        actor_id=payload["request_actor"],
        scope=container_isolation.CONTAINER_ISOLATION_SCOPE,
        route=container_isolation.CONTAINER_ISOLATION_ROUTE,
        method="POST",
        action=container_isolation.CONTAINER_ISOLATION_ACTION,
    )
    assert first.allowed is True
    authority = pilot_runtime.pilot_runtime_lease_authority_snapshot(
        payload["lease_id"],
        actor=payload["request_actor"],
        expected_bindings=container_isolation.container_isolation_lease_bindings(),
    )

    def authorize() -> bool:
        return registry.authorize_binding(
            lease_id=payload["lease_id"],
            actor_id=payload["request_actor"],
            scope=container_isolation.RUNTIME_EVIDENCE_SCOPE,
            route=container_isolation.RUNTIME_EVIDENCE_ROUTE,
            method="POST",
            action=container_isolation.RUNTIME_EVIDENCE_ACTION,
        ).allowed

    return {"evidence_authority": authority, "authorize_runtime_evidence": authorize}


def _write_approval(isolation_fixture: dict[str, Any]) -> None:
    payload = isolation_fixture["payload"]
    root = isolation_fixture["data"] / "approvals" / "approved"
    root.mkdir(parents=True, exist_ok=True)
    runtime_descriptor = runtime_start._launch_descriptor(
        provision=isolation_fixture["provision"],
        isolation=isolation_fixture["isolation"],
        action_nonce="runtime-start-nonce-1",
        trace_id="trace-runtime-start-1",
        startup_timeout_ms=3_000,
        lease_seconds=10,
    )
    runtime_descriptor_fingerprint = runtime_start._fingerprint(runtime_descriptor)
    runtime = {
        "id": payload["runtime_start_approval_id"],
        "ts": time.time(),
        "action": "managed_copies.runtime_start",
        "reason": "fixed fixture runtime",
        "payload": {
            "contract": runtime_start.RUNTIME_START_CONTRACT,
            "action": runtime_start.RUNTIME_START_ACTION,
            "request_actor": payload["request_actor"],
            "descriptor": runtime_descriptor,
            "descriptor_fingerprint": runtime_descriptor_fingerprint,
            "action_nonce": "runtime-start-nonce-1",
            "trace_id": "trace-runtime-start-1",
            "revoked": False,
            "expires_at_unix_ms": int(time.time() * 1000) + 60_000,
            "proposal_lineage": runtime_descriptor["proposal_lineage"],
        },
        "status": "approved",
        "decision": "approve",
        "decision_actor": "test.operator",
        "decided_ts": time.time(),
    }
    (root / f"{runtime['id']}.json").write_text(json.dumps(runtime), encoding="utf-8")
    proposal = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    assert proposal["descriptor"]
    approval = {
        "id": payload["approval_id"],
        "ts": time.time(),
        "action": container_isolation.CONTAINER_ISOLATION_ACTION,
        "reason": "fixed Docker isolation proof",
        "payload": {
            "contract": container_isolation.CONTAINER_ISOLATION_CONTRACT,
            "action": container_isolation.CONTAINER_ISOLATION_ACTION,
            "request_actor": payload["request_actor"],
            "descriptor": proposal["descriptor"],
            "descriptor_fingerprint": proposal["descriptor_fingerprint"],
            "action_nonce": payload["action_nonce"],
            "trace_id": payload["trace_id"],
            "expires_at_unix_ms": int(time.time() * 1000) + 60_000,
            "revoked": False,
        },
        "status": "approved",
        "decision": "approve",
        "decision_actor": "test.operator",
        "decided_ts": time.time(),
    }
    (root / f"{approval['id']}.json").write_text(json.dumps(approval), encoding="utf-8")


def _security_inspect() -> dict[str, Any]:
    return {
        "Config": {"User": "65532:65532"},
        "HostConfig": {
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": None,
            "SecurityOpt": ["no-new-privileges:true"],
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "RestartPolicy": {"Name": "no"},
            "Memory": 67_108_864,
            "NanoCpus": 250_000_000,
            "PidsLimit": 32,
        },
    }


def _owned_inspect_item(descriptor: dict[str, Any], root: Path, *, host_pid: object = 65532) -> dict[str, Any]:
    item = _security_inspect()
    item.update(
        {
            "Id": "9" * 64,
            "Name": f"/francis-mciso-{descriptor['proof_run_id']}",
            "Image": descriptor["image_id"],
            "Mounts": [
                {"Source": str((root / "tenant").resolve()), "Destination": "/francis/tenant", "RW": False},
                {"Source": str((root / "state").resolve()), "Destination": "/francis/state", "RW": True},
            ],
            "State": {
                "Running": True,
                "Pid": host_pid,
                "StartedAt": "2026-07-17T19:42:36.000000000Z",
            },
        }
    )
    item["Config"].update(
        {
            "Entrypoint": ["python", container_isolation.RUNTIME_PROGRAM_CONTAINER_PATH],
            "Cmd": container_isolation._runtime_cmd(descriptor),
            "Labels": {
                "francis.proof_run_id": descriptor["proof_run_id"],
                "francis.tenant_key": descriptor["tenant_key"],
                "francis.copy_id": descriptor["copy_id"],
                "francis.approval_id": descriptor["approval_id"],
            },
        }
    )
    item["HostConfig"]["Tmpfs"] = {"/tmp": "rw,noexec,nodev,nosuid,size=1m"}
    return item


def _write_runtime_records(root: Path, payload: dict[str, Any], tenant_key: str, *, pid: int = 1) -> None:
    state = root / "state"
    common = {
        "copy_id": payload["copy_id"],
        "tenant_key": tenant_key,
        "pilot_run_id": payload["proof_run_id"],
        "runtime_nonce_hash": container_isolation._sha256_text(payload["runtime_nonce"]),
    }
    operation_name = container_isolation.runtime_operation_name(payload["operation_input"])
    if operation_name == container_isolation.TENANT_BOUNDARY_OPERATION:
        output = container_isolation.build_tenant_boundary_probe(
            payload["operation_input"],
            approved_input_read=True,
            sibling_boundary_absent=True,
        )
    else:
        output = container_isolation.build_runtime_operation_preview(payload["operation_input"])
    output_name = (
        "tenant_boundary_probe" if operation_name == container_isolation.TENANT_BOUNDARY_OPERATION else "briefing"
    )
    handshake = {
        "kind": "francis.stage18.managed_copies.runtime_handshake",
        "runtime_identity": container_isolation.RUNTIME_IDENTITY,
        "fixture_runtime": False,
        "pid": pid,
        "parent_pid": 0,
        **common,
    }
    heartbeat = {
        **handshake,
        "kind": "francis.stage18.managed_copies.runtime_heartbeat",
        "heartbeat_identity": container_isolation.HEARTBEAT_IDENTITY,
        "ready": True,
        "operation_completed": True,
        "sequence": 1,
        "observed_at_unix_ms": int(time.time() * 1000),
    }
    operation = {
        "kind": "francis.stage18.managed_copies.runtime_operation_receipt",
        "operation": operation_name,
        "status": "completed",
        **common,
        "input_fingerprint": output.get("input_fingerprint", output.get("approved_tenant_input_fingerprint")),
        "output_fingerprint": output["output_fingerprint"],
        "fixture_runtime": False,
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    operation["receipt_fingerprint"] = container_isolation._fingerprint(operation)
    for name, value in {
        "handshake": handshake,
        "heartbeat": heartbeat,
        "operation": operation,
        output_name: output,
    }.items():
        (state / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize(
    ("field_name", "mutate"),
    [
        ("Config.User", lambda item: item["Config"].__setitem__("User", "0:0")),
        ("HostConfig.Privileged", lambda item: item["HostConfig"].__setitem__("Privileged", True)),
        ("HostConfig.CapDrop", lambda item: item["HostConfig"].__setitem__("CapDrop", [])),
        ("HostConfig.CapAdd", lambda item: item["HostConfig"].__setitem__("CapAdd", ["NET_RAW"])),
        ("HostConfig.SecurityOpt", lambda item: item["HostConfig"].__setitem__("SecurityOpt", [])),
        ("HostConfig.ReadonlyRootfs", lambda item: item["HostConfig"].__setitem__("ReadonlyRootfs", False)),
        ("HostConfig.NetworkMode", lambda item: item["HostConfig"].__setitem__("NetworkMode", "bridge")),
        (
            "HostConfig.RestartPolicy.Name",
            lambda item: item["HostConfig"]["RestartPolicy"].__setitem__("Name", "always"),
        ),
        ("HostConfig.Memory", lambda item: item["HostConfig"].__setitem__("Memory", 0)),
        ("HostConfig.NanoCpus", lambda item: item["HostConfig"].__setitem__("NanoCpus", 0)),
        ("HostConfig.PidsLimit", lambda item: item["HostConfig"].__setitem__("PidsLimit", 0)),
    ],
)
def test_security_diagnostic_identifies_each_allowlisted_field(field_name: str, mutate: Any) -> None:
    item = _security_inspect()
    mutate(item)

    diagnostics = container_isolation._security_profile_diagnostics(item)

    assert [diagnostic.field_name for diagnostic in diagnostics] == [field_name]


def test_security_diagnostics_are_normalized_and_deterministic() -> None:
    item = _security_inspect()
    item["HostConfig"]["CapDrop"] = ["all", "ALL"]
    item["HostConfig"]["CapAdd"] = ["sys_admin", "NET_RAW", "net_raw"]
    item["HostConfig"]["SecurityOpt"] = ["NO-NEW-PRIVILEGES", "no-new-privileges"]

    diagnostics = container_isolation._security_profile_diagnostics(item)

    assert [diagnostic.field_name for diagnostic in diagnostics] == [
        "HostConfig.CapAdd",
        "HostConfig.SecurityOpt",
    ]
    assert diagnostics[0].observed_value == [
        f"sha256:{container_isolation._fingerprint('NET_RAW')}",
        f"sha256:{container_isolation._fingerprint('SYS_ADMIN')}",
    ]
    assert diagnostics[1].observed_value == ["no-new-privileges:true"]
    assert diagnostics[1].classification is container_isolation.SecurityComparison.EQUIVALENT


def test_security_opt_accepts_only_proven_explicit_true_spellings() -> None:
    for spelling in ("no-new-privileges:true", "no-new-privileges=true"):
        item = _security_inspect()
        item["HostConfig"]["SecurityOpt"] = [spelling]
        assert container_isolation._security_profile_diagnostics(item) == ()

    bare = _security_inspect()
    bare["HostConfig"]["SecurityOpt"] = ["no-new-privileges"]
    bare_diagnostic = container_isolation._security_profile_diagnostics(bare)
    assert bare_diagnostic[0].classification is container_isolation.SecurityComparison.EQUIVALENT

    unknown = _security_inspect()
    unknown["HostConfig"]["SecurityOpt"] = ["no-new-privileges=maybe"]
    unknown_diagnostic = container_isolation._security_profile_diagnostics(unknown)
    assert unknown_diagnostic[0].classification is container_isolation.SecurityComparison.WEAKER


def test_missing_malformed_and_weaker_security_values_remain_failures() -> None:
    item = _security_inspect()
    item["HostConfig"].pop("ReadonlyRootfs")
    item["HostConfig"]["Memory"] = True
    item["HostConfig"]["PidsLimit"] = 64

    diagnostics = {item.field_name: item for item in container_isolation._security_profile_diagnostics(item)}

    assert diagnostics["HostConfig.ReadonlyRootfs"].classification is container_isolation.SecurityComparison.INVALID
    assert diagnostics["HostConfig.Memory"].classification is container_isolation.SecurityComparison.INVALID
    assert diagnostics["HostConfig.PidsLimit"].classification is container_isolation.SecurityComparison.WEAKER


def test_security_diagnostic_receipt_is_bounded_and_fingerprinted() -> None:
    item = _security_inspect()
    item["HostConfig"]["NetworkMode"] = "bridge"
    item["UnexpectedSecret"] = "RAW-INSPECT-MARKER"
    plan = {"descriptor": {"proof_run_id": "mciso-diagnostic-test"}}
    first = container_isolation._security_profile_diagnostic_receipt(
        plan, container_isolation._security_profile_diagnostics(item), recorded_at_unix_ms=1
    )
    item["HostConfig"]["NetworkMode"] = "host"
    second = container_isolation._security_profile_diagnostic_receipt(
        plan, container_isolation._security_profile_diagnostics(item), recorded_at_unix_ms=1
    )

    encoded = json.dumps(first, sort_keys=True)
    assert "RAW-INSPECT-MARKER" not in encoded
    assert "UnexpectedSecret" not in encoded
    assert first["mismatch_count"] == 1
    assert first["receipt_fingerprint"] != second["receipt_fingerprint"]


def test_security_diagnostic_receipt_bounds_and_hashes_inspect_controlled_tokens() -> None:
    item = _security_inspect()
    secrets = [f"secret-token-{index}-" + "x" * 200 for index in range(20)]
    item["HostConfig"]["CapAdd"] = secrets
    plan = {"descriptor": {"proof_run_id": "mciso-bounded-diagnostic"}}

    receipt = container_isolation._security_profile_diagnostic_receipt(
        plan, container_isolation._security_profile_diagnostics(item), recorded_at_unix_ms=1
    )

    encoded = json.dumps(receipt, sort_keys=True)
    observed = receipt["mismatches"][0]["observed_normalized_value"]
    assert all(secret not in encoded for secret in secrets)
    assert len(observed) == container_isolation._MAX_DIAGNOSTIC_TOKENS + 1
    assert observed[-1].startswith("overflow:12:sha256:")
    assert len(encoded) < 2_500


def test_unrelated_inspect_blocker_does_not_write_security_diagnostic(tmp_path: Path) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    result = container_isolation.DockerResult(("docker",), 1, "", "not found")

    written = container_isolation._write_security_profile_diagnostic(
        receipts,
        plan={"descriptor": {"proof_run_id": "mciso-unrelated"}},
        inspected=result,
    )

    assert written == {}
    assert not (receipts / "security-profile-diagnostic.json").exists()


def test_cleanup_still_executes_after_security_diagnostic_creation(
    isolation_fixture: dict[str, Any], tmp_path: Path
) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    assert plan["ok"] is True
    descriptor = plan["descriptor"]
    container_id = "7" * 64
    name = f"francis-mciso-{payload['proof_run_id']}"
    inspected_item = _security_inspect()
    inspected_item.update(
        {
            "Id": container_id,
            "Name": f"/{name}",
            "Image": payload["image_id"],
        }
    )
    inspected_item["Config"].update(
        {
            "Entrypoint": ["python", container_isolation.RUNTIME_PROGRAM_CONTAINER_PATH],
            "Cmd": container_isolation._runtime_cmd(descriptor),
            "Labels": {
                "francis.proof_run_id": descriptor["proof_run_id"],
                "francis.tenant_key": descriptor["tenant_key"],
                "francis.copy_id": descriptor["copy_id"],
                "francis.approval_id": descriptor["approval_id"],
            },
        }
    )
    inspected_item["HostConfig"]["NetworkMode"] = "bridge"
    inspected = container_isolation.DockerResult(("docker",), 0, json.dumps([inspected_item]), "")
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    commands: list[list[str]] = []
    removed = False

    def fake_cleanup(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        nonlocal removed
        commands.append(argv)
        if argv[3:5] == ["container", "inspect"]:
            if removed:
                return container_isolation.DockerResult(tuple(argv), 1, "", "not found")
            return inspected
        if argv[3:5] == ["container", "rm"]:
            removed = True
            return container_isolation.DockerResult(tuple(argv), 0, container_id, "")
        if argv[3:5] == ["container", "stop"]:
            return container_isolation.DockerResult(tuple(argv), 0, container_id, "")
        raise AssertionError((argv, timeout))

    container_isolation._write_security_profile_diagnostic(receipts, plan=plan, inspected=inspected)
    cleanup_status = container_isolation._cleanup_exact(
        fake_cleanup,
        container_id,
        name=name,
        receipts=receipts,
        plan=plan,
    )

    assert cleanup_status == "removed"
    assert (receipts / "security-profile-diagnostic.json").exists()
    assert json.loads((receipts / "cleanup.json").read_text(encoding="utf-8"))["status"] == "removed"
    assert any(command[3:5] == ["container", "rm"] for command in commands)


def test_denials_happen_before_docker_or_receipt_creation(isolation_fixture: dict[str, Any]) -> None:
    called = False

    def forbidden(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        nonlocal called
        called = True
        raise AssertionError((argv, timeout))

    payload = isolation_fixture["payload"]
    missing = container_isolation.execute_container_isolation(
        payload, actor=payload["request_actor"], stage17_closed=True, run=forbidden
    )
    assert missing["error"] == "managed_copy_container_isolation_runtime_start_approval_invalid"
    assert called is False
    assert not isolation_fixture["data"].exists()

    malformed = dict(payload)
    malformed["lease_seconds"] = True
    result = container_isolation.execute_container_isolation(
        malformed, actor=payload["request_actor"], stage17_closed=True, run=forbidden
    )
    assert result["error"] == "managed_copy_container_isolation_binding_invalid"
    assert called is False


def test_missing_evidence_authority_blocks_before_docker_or_filesystem_effects(
    isolation_fixture: dict[str, Any],
) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    called = False

    def forbidden(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        nonlocal called
        called = True
        raise AssertionError((argv, timeout))

    result = container_isolation.execute_container_isolation(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
        run=forbidden,
    )

    assert result["error"] == "managed_copy_container_runtime_evidence_authority_invalid"
    assert called is False
    assert not container_isolation._proof_base().exists()


@pytest.mark.parametrize("include_evidence_scope", [True, False])
def test_route_requires_static_evidence_scope_before_exact_two_binding_sequence(
    isolation_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    include_evidence_scope: bool,
) -> None:
    payload = isolation_fixture["payload"]
    registry: PilotScopeLeaseRegistry = isolation_fixture["registry"]
    monkeypatch.setattr(managed_copy_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(
        managed_copy_routes,
        "managed_copies_status_snapshot",
        lambda: {"stage17_closed_by_receipt": True},
    )
    scopes = [container_isolation.CONTAINER_ISOLATION_SCOPE]
    if include_evidence_scope:
        scopes.append(container_isolation.RUNTIME_EVIDENCE_SCOPE)
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({payload["request_actor"]: scopes}))
    executed = False

    def execute(
        body: dict[str, Any],
        *,
        actor: str,
        stage17_closed: bool,
        evidence_authority: dict[str, Any],
        authorize_runtime_evidence: Any,
    ) -> dict[str, Any]:
        nonlocal executed
        executed = True
        assert body == payload
        assert actor == payload["request_actor"]
        assert stage17_closed is True
        assert evidence_authority["operation_consumed_binding_count"] == 1
        assert authorize_runtime_evidence() is True
        return {"ok": True, "status": "runtime_ready"}

    monkeypatch.setattr(managed_copy_routes, "execute_container_isolation", execute)
    result = TestClient(create_app()).post(container_isolation.CONTAINER_ISOLATION_ROUTE, json=payload).json()

    if include_evidence_scope:
        assert result["ok"] is True
        assert executed is True
        assert registry.state(payload["lease_id"]) is PilotLeaseState.CONSUMED
    else:
        assert result["error"] == "api_permission_denied"
        assert result["required_scope"] == container_isolation.RUNTIME_EVIDENCE_SCOPE
        assert executed is False
        assert registry.state(payload["lease_id"]) is PilotLeaseState.ACTIVE


def test_exact_approval_binding_rejects_changed_digest_and_runtime_approval(isolation_fixture: dict[str, Any]) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    ready = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    assert ready["ok"] is True
    assert "operation_input" not in ready["descriptor"]
    assert "Prepare report" not in json.dumps(ready["descriptor"])

    changed = dict(payload)
    changed["image_platform_digest"] = "sha256:" + "1" * 64
    denied = container_isolation.container_isolation_proposal(
        changed, actor=payload["request_actor"], stage17_closed=True
    )
    assert denied["error"] == "managed_copy_container_isolation_fixed_image_mismatch"

    changed = json.loads(json.dumps(payload))
    changed["operation_input"]["items"][0]["title"] = "Altered after approval"
    denied = container_isolation.container_isolation_proposal(
        changed, actor=payload["request_actor"], stage17_closed=True
    )
    assert denied["error"] == "managed_copy_container_isolation_approval_binding_mismatch"

    runtime_path = isolation_fixture["data"] / "approvals" / "approved" / f"{payload['runtime_start_approval_id']}.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["payload"]["revoked"] = True
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    denied = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    assert "managed_copy_container_isolation_runtime_start_approval_invalid" in denied["blockers"]


def test_runtime_start_approval_for_other_copy_cannot_be_reused(isolation_fixture: dict[str, Any]) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    runtime_path = isolation_fixture["data"] / "approvals" / "approved" / f"{payload['runtime_start_approval_id']}.json"
    approval = json.loads(runtime_path.read_text(encoding="utf-8"))
    approval["payload"]["descriptor"]["copy_id"] = "managed_copy_bbbbbbbbbbbbbbbb"
    approval["payload"]["descriptor_fingerprint"] = runtime_start._fingerprint(approval["payload"]["descriptor"])
    runtime_path.write_text(json.dumps(approval), encoding="utf-8")

    denied = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )

    assert denied["error"] == "managed_copy_container_isolation_runtime_start_approval_invalid"


def test_daemon_identity_mismatch_blocks_before_proof_root_creation(isolation_fixture: dict[str, Any]) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    commands: list[list[str]] = []

    def mismatched_daemon(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        commands.append(argv)
        if argv[1:3] == ["context", "inspect"]:
            return container_isolation.DockerResult(tuple(argv), 0, '[{"Name":"desktop-linux"}]', "")
        if argv[3:5] == ["version", "--format"]:
            return container_isolation.DockerResult(
                tuple(argv), 0, json.dumps({"Os": "linux", "Arch": "amd64", "Version": "other"}), ""
            )
        if argv[3:5] == ["info", "--format"]:
            return container_isolation.DockerResult(tuple(argv), 0, json.dumps({"ID": payload["engine_id"]}), "")
        if argv[3:5] == ["image", "inspect"]:
            image = [
                {
                    "Id": payload["image_id"],
                    "Os": "linux",
                    "Architecture": "amd64",
                    "Config": isolation_fixture["image_config"],
                }
            ]
            return container_isolation.DockerResult(tuple(argv), 0, json.dumps(image), "")
        raise AssertionError((argv, timeout))

    result = container_isolation.execute_container_isolation(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
        run=mismatched_daemon,
        **_evidence_execution_kwargs(isolation_fixture),
    )

    assert result["error"] == "managed_copy_container_engine_identity_mismatch"
    assert not (container_isolation._proof_base() / payload["proof_run_id"]).exists()
    assert not any("create" in command for command in commands)


def test_controller_verifier_change_blocks_before_docker_invocation(
    isolation_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    original_hash = container_isolation._file_sha256
    called = False

    def changed_hash(path: Path) -> str:
        if path == container_isolation.CONTROLLER_VERIFIER:
            return "0" * 64
        return original_hash(path)

    def forbidden(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        nonlocal called
        called = True
        raise AssertionError((argv, timeout))

    monkeypatch.setattr(container_isolation, "_file_sha256", changed_hash)

    assert (
        container_isolation._docker_preflight(forbidden, plan["descriptor"])
        == "managed_copy_container_runtime_image_source_changed_before_launch"
    )
    assert called is False


@pytest.mark.parametrize(
    ("remove_exit", "expected_status", "expected_error"),
    [
        (0, "failed", "managed_copy_container_create_failed"),
        (1, "cleanup_required", "managed_copy_container_create_failed_cleanup_failed"),
    ],
)
def test_create_timeout_recovers_only_proof_owned_container_and_surfaces_cleanup(
    isolation_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    remove_exit: int,
    expected_status: str,
    expected_error: str,
) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    container_id = "8" * 64
    commands: list[list[str]] = []
    removed = False
    monkeypatch.setattr(container_isolation, "_docker_preflight", lambda run, descriptor: "")

    owned = [
        {
            "Id": container_id,
            "Name": f"/francis-mciso-{payload['proof_run_id']}",
            "Image": payload["image_id"],
            "Config": {
                "Entrypoint": ["python", container_isolation.RUNTIME_PROGRAM_CONTAINER_PATH],
                "Cmd": container_isolation._runtime_cmd(
                    container_isolation.container_isolation_proposal(
                        payload, actor=payload["request_actor"], stage17_closed=True
                    )["descriptor"]
                ),
                "Labels": {
                    "francis.proof_run_id": payload["proof_run_id"],
                    "francis.tenant_key": isolation_fixture["provision"]["tenant_key"],
                    "francis.copy_id": payload["copy_id"],
                    "francis.approval_id": payload["approval_id"],
                },
            },
        }
    ]

    def timed_out_create(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        nonlocal removed
        commands.append(argv)
        if argv[3:5] == ["container", "create"]:
            return container_isolation.DockerResult(tuple(argv), 124, "", "", timed_out=True)
        if argv[3:5] == ["container", "inspect"]:
            if removed:
                return container_isolation.DockerResult(tuple(argv), 1, "", "not found")
            return container_isolation.DockerResult(tuple(argv), 0, json.dumps(owned), "")
        if argv[3:5] == ["container", "stop"]:
            return container_isolation.DockerResult(tuple(argv), 0, container_id, "")
        if argv[3:5] == ["container", "rm"]:
            removed = remove_exit == 0
            return container_isolation.DockerResult(tuple(argv), remove_exit, container_id, "")
        raise AssertionError((argv, timeout))

    result = container_isolation.execute_container_isolation(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
        run=timed_out_create,
        **_evidence_execution_kwargs(isolation_fixture),
    )

    assert result["status"] == expected_status
    assert result["error"] == expected_error
    assert any(command[3:5] == ["container", "rm"] for command in commands)


def test_create_timeout_without_recoverable_identity_is_cleanup_required(
    isolation_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    monkeypatch.setattr(container_isolation, "_docker_preflight", lambda run, descriptor: "")

    def unresolved(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        if argv[3:5] == ["container", "create"]:
            return container_isolation.DockerResult(tuple(argv), 124, "", "", timed_out=True)
        if argv[3:5] == ["container", "inspect"]:
            return container_isolation.DockerResult(tuple(argv), 1, "", "not found")
        raise AssertionError((argv, timeout))

    result = container_isolation.execute_container_isolation(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
        run=unresolved,
        **_evidence_execution_kwargs(isolation_fixture),
    )

    assert result["status"] == "cleanup_required"
    assert result["error"] == "managed_copy_container_create_timeout_cleanup_unverified"


@pytest.mark.parametrize(
    ("operation_input", "evidence_failure"),
    [
        (None, False),
        (
            {
                "contract": container_isolation.TENANT_BOUNDARY_INPUT_CONTRACT,
                "probe_id": "tenant-boundary-probe-001",
                "tenant_marker": "synthetic-tenant-a-marker",
            },
            False,
        ),
        (None, True),
    ],
    ids=("work-briefing", "tenant-boundary-probe", "evidence-failure"),
)
def test_fixed_docker_profile_launches_proves_and_cleans_up(
    isolation_fixture: dict[str, Any],
    operation_input: dict[str, Any] | None,
    evidence_failure: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if operation_input is not None:
        isolation_fixture["payload"]["operation_input"] = operation_input
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    container_id = "9" * 64
    commands: list[list[str]] = []
    created_argv: list[str] = []
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    descriptor = plan["descriptor"]

    def inspect_payload(running: bool) -> str:
        root = container_isolation._proof_base() / payload["proof_run_id"]
        mounts = [
            {"Source": str((root / "tenant").resolve()), "Destination": "/francis/tenant", "RW": False},
            {"Source": str((root / "state").resolve()), "Destination": "/francis/state", "RW": True},
        ]
        value = [
            {
                "Id": container_id,
                "Name": f"/francis-mciso-{payload['proof_run_id']}",
                "Image": payload["image_id"],
                "Config": {
                    "User": "65532:65532",
                    "Entrypoint": ["python", container_isolation.RUNTIME_PROGRAM_CONTAINER_PATH],
                    "Cmd": container_isolation._runtime_cmd(descriptor),
                    "Labels": {
                        "francis.proof_run_id": payload["proof_run_id"],
                        "francis.tenant_key": isolation_fixture["provision"]["tenant_key"],
                        "francis.copy_id": payload["copy_id"],
                        "francis.approval_id": payload["approval_id"],
                    },
                },
                "HostConfig": {
                    "Privileged": False,
                    "CapDrop": ["ALL"],
                    "CapAdd": None,
                    "SecurityOpt": ["no-new-privileges:true"],
                    "ReadonlyRootfs": True,
                    "NetworkMode": "none",
                    "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                    "Memory": 67_108_864,
                    "NanoCpus": 250_000_000,
                    "PidsLimit": 32,
                    "Tmpfs": {"/tmp": "rw,noexec,nodev,nosuid,size=1m"},
                },
                "Mounts": mounts,
                "State": {
                    "Running": running,
                    "Pid": 65532 if running else 0,
                    "StartedAt": "2026-07-17T19:42:36.000000000Z" if running else "0001-01-01T00:00:00Z",
                },
            }
        ]
        return json.dumps(value)

    running = False
    removed = False

    def fake_run(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        nonlocal running, removed, created_argv
        commands.append(argv)
        if argv[1:3] == ["context", "inspect"]:
            return container_isolation.DockerResult(tuple(argv), 0, '[{"Name":"desktop-linux"}]', "")
        if argv[3:5] == ["version", "--format"]:
            return container_isolation.DockerResult(tuple(argv), 0, json.dumps(isolation_fixture["server"]), "")
        if argv[3:5] == ["info", "--format"]:
            return container_isolation.DockerResult(tuple(argv), 0, json.dumps({"ID": payload["engine_id"]}), "")
        if argv[3:5] == ["image", "inspect"]:
            image = [
                {
                    "Id": payload["image_id"],
                    "Os": "linux",
                    "Architecture": "amd64",
                    "Config": isolation_fixture["image_config"],
                }
            ]
            return container_isolation.DockerResult(tuple(argv), 0, json.dumps(image), "")
        if argv[3:5] == ["container", "create"]:
            created_argv = argv
            return container_isolation.DockerResult(tuple(argv), 0, container_id + "\n", "")
        if argv[3:5] == ["container", "start"]:
            running = True
            root = container_isolation._proof_base() / payload["proof_run_id"]
            _write_runtime_records(root, payload, isolation_fixture["provision"]["tenant_key"])
            return container_isolation.DockerResult(tuple(argv), 0, container_id + "\n", "")
        if argv[3:5] == ["container", "inspect"]:
            if removed:
                return container_isolation.DockerResult(tuple(argv), 1, "", "not found")
            return container_isolation.DockerResult(tuple(argv), 0, inspect_payload(running), "")
        if argv[3:5] == ["container", "stop"]:
            running = False
            return container_isolation.DockerResult(tuple(argv), 0, container_id + "\n", "")
        if argv[3:5] == ["container", "rm"]:
            removed = True
            return container_isolation.DockerResult(tuple(argv), 0, container_id + "\n", "")
        raise AssertionError((argv, timeout))

    if evidence_failure:
        monkeypatch.setattr(container_isolation, "plan_runtime_evidence", lambda *args, **kwargs: {"ok": False})
    evidence_kwargs = _evidence_execution_kwargs(isolation_fixture)
    result = container_isolation.execute_container_isolation(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
        run=fake_run,
        **evidence_kwargs,
    )
    cleanup = container_isolation._proof_base() / payload["proof_run_id"] / "receipts" / "cleanup.json"
    assert json.loads(cleanup.read_text(encoding="utf-8"))["status"] == "removed"
    assert running is False
    if evidence_failure:
        assert result["ok"] is False
        assert result["error"] == "managed_copy_container_runtime_evidence_failed"
        assert list(runtime_evidence.receipt_directory().glob("*.json")) == []
        return
    assert result["ok"] is True, result
    assert result["runtime_evidence"]["receipt"]["requirement_id"] == runtime_evidence.COPY_CREATION_REQUIREMENT
    assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is True
    readbacks = managed_copies.managed_copy_runtime_evidence_readbacks_snapshot()
    copy_check = next(
        check for check in readbacks["checks"] if check["id"] == runtime_evidence.COPY_CREATION_REQUIREMENT
    )
    assert copy_check["passed"] is True
    assert copy_check["blocker"] == ""
    monkeypatch.setattr(pilot_runtime, "PILOT_RUNTIME_LEASES", PilotScopeLeaseRegistry())
    assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is True
    assert isolation_fixture["registry"].state(payload["lease_id"]) is PilotLeaseState.CONSUMED
    assert sum(command[3:5] == ["container", "inspect"] for command in commands) >= 5
    command_count = len(commands)
    replay = container_isolation.execute_container_isolation(
        payload,
        actor=payload["request_actor"],
        stage17_closed=True,
        run=fake_run,
        **evidence_kwargs,
    )
    assert replay["error"] == "managed_copy_container_isolation_pilot_lease_lineage_invalid"
    assert len(commands) == command_count
    cleanup_value = json.loads(cleanup.read_text(encoding="utf-8"))
    cleanup_value["status"] = "cleanup_required"
    cleanup.write_text(json.dumps(cleanup_value), encoding="utf-8")
    source = runtime_evidence.verify_copy_creation_runtime_source(
        result["lifecycle_receipt"]["receipt_id"],
        result["lifecycle_receipt"]["receipt_fingerprint"],
    )
    assert source["valid"] is False
    assert source["blocker"] == "stage18_copy_creation_lifecycle_invalid"
    cleanup_value["status"] = "removed"
    cleanup.write_text(json.dumps(cleanup_value), encoding="utf-8")
    if operation_input is None:
        lifecycle_path = Path(result["proof_root"]) / "receipts" / "lifecycle-complete.json"
        lifecycle_value = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        assert lifecycle_value["receipt_id"].startswith("mclc_")
        resolved = runtime_evidence.verify_copy_creation_runtime_source(
            lifecycle_value["receipt_id"],
            lifecycle_value["receipt_fingerprint"],
        )
        assert resolved["valid"] is True
        assert resolved["current_state_hash"] == result["runtime_evidence"]["receipt"]["current_state_hash"]
        monkeypatch.delenv("FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT")
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is True
        monkeypatch.setenv("FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT", str(Path(result["proof_root"]).parent))

        lifecycle_path.unlink()
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        lifecycle_path.write_text(json.dumps(lifecycle_value), encoding="utf-8")

        tampered_lifecycle = {**lifecycle_value, "unexpected": True}
        lifecycle_path.write_text(json.dumps(tampered_lifecycle), encoding="utf-8")
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        lifecycle_path.write_text(json.dumps(lifecycle_value), encoding="utf-8")

        ready_path = Path(result["proof_root"]) / "receipts" / "ready.json"
        ready_value = json.loads(ready_path.read_text(encoding="utf-8"))
        ready_path.write_text(json.dumps({**ready_value, "output_fingerprint": "0" * 64}), encoding="utf-8")
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        ready_path.write_text(json.dumps(ready_value), encoding="utf-8")

        decoy_roots: list[Path] = []
        for index in range(257):
            decoy = container_isolation._proof_base() / f"000-decoy-{index:03d}" / "receipts"
            decoy.mkdir(parents=True)
            (decoy / "lifecycle-complete.json").write_text(
                json.dumps({"receipt_id": f"mclc_decoy_{index:03d}"}),
                encoding="utf-8",
            )
            decoy_roots.append(decoy)
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is True

        duplicate = container_isolation._proof_base() / "zzz-duplicate" / "receipts"
        duplicate.mkdir(parents=True)
        (duplicate / "lifecycle-complete.json").write_text(json.dumps(lifecycle_value), encoding="utf-8")
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        (duplicate / "lifecycle-complete.json").unlink()
        duplicate.rmdir()
        duplicate.parent.rmdir()
        for decoy in decoy_roots:
            (decoy / "lifecycle-complete.json").unlink()
            decoy.rmdir()
            decoy.parent.rmdir()

        approval_path = isolation_fixture["data"] / "approvals" / "approved" / f"{payload['approval_id']}.json"
        approval_value = json.loads(approval_path.read_text(encoding="utf-8"))
        approval_value["payload"]["revoked"] = True
        approval_path.write_text(json.dumps(approval_value), encoding="utf-8")
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        approval_value["payload"]["revoked"] = False
        approval_path.write_text(json.dumps(approval_value), encoding="utf-8")

        original_provision = container_isolation.managed_copy_provision_for_copy
        monkeypatch.setattr(container_isolation, "managed_copy_provision_for_copy", lambda *args, **kwargs: {})
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        monkeypatch.setattr(container_isolation, "managed_copy_provision_for_copy", original_provision)

        original_isolation = container_isolation.latest_managed_copy_isolation_verification_for_provision
        monkeypatch.setattr(
            container_isolation,
            "latest_managed_copy_isolation_verification_for_provision",
            lambda *args, **kwargs: {},
        )
        assert runtime_evidence.receipt_satisfies_runtime_requirement(result["runtime_evidence"]["receipt"]) is False
        monkeypatch.setattr(
            container_isolation,
            "latest_managed_copy_isolation_verification_for_provision",
            original_isolation,
        )

        ambiguous_cleanup = {**cleanup_value, "post_removal_inspect_exit_code": 0}
        ambiguous_cleanup["receipt_fingerprint"] = container_isolation._fingerprint(
            {key: value for key, value in ambiguous_cleanup.items() if key != "receipt_fingerprint"}
        )
        cleanup.write_text(json.dumps(ambiguous_cleanup), encoding="utf-8")
        ambiguous_lifecycle = {
            **lifecycle_value,
            "cleanup_receipt_fingerprint": ambiguous_cleanup["receipt_fingerprint"],
        }
        ambiguous_lifecycle["receipt_fingerprint"] = container_isolation._fingerprint(
            {key: value for key, value in ambiguous_lifecycle.items() if key != "receipt_fingerprint"}
        )
        lifecycle_path.write_text(json.dumps(ambiguous_lifecycle), encoding="utf-8")
        assert (
            runtime_evidence.verify_copy_creation_runtime_source(
                ambiguous_lifecycle["receipt_id"],
                ambiguous_lifecycle["receipt_fingerprint"],
            )["valid"]
            is False
        )
        cleanup.write_text(json.dumps(cleanup_value), encoding="utf-8")
        lifecycle_path.write_text(json.dumps(lifecycle_value), encoding="utf-8")

        fabricated_ready = {**ready_value, "unexpected_rehashed_field": True}
        fabricated_ready["receipt_fingerprint"] = container_isolation._fingerprint(
            {key: value for key, value in fabricated_ready.items() if key != "receipt_fingerprint"}
        )
        ready_path.write_text(json.dumps(fabricated_ready), encoding="utf-8")
        fabricated_cleanup = {**cleanup_value, "container_id": "8" * 64}
        fabricated_cleanup["receipt_fingerprint"] = container_isolation._fingerprint(
            {key: value for key, value in fabricated_cleanup.items() if key != "receipt_fingerprint"}
        )
        cleanup.write_text(json.dumps(fabricated_cleanup), encoding="utf-8")
        fabricated_lifecycle = {
            **lifecycle_value,
            "ready_receipt_fingerprint": fabricated_ready["receipt_fingerprint"],
            "cleanup_receipt_fingerprint": fabricated_cleanup["receipt_fingerprint"],
        }
        fabricated_lifecycle["receipt_id"] = live_evidence._lifecycle_id(fabricated_lifecycle)
        fabricated_lifecycle["receipt_fingerprint"] = container_isolation._fingerprint(
            {key: value for key, value in fabricated_lifecycle.items() if key != "receipt_fingerprint"}
        )
        lifecycle_path.write_text(json.dumps(fabricated_lifecycle), encoding="utf-8")
        assert (
            runtime_evidence.verify_copy_creation_runtime_source(
                fabricated_lifecycle["receipt_id"],
                fabricated_lifecycle["receipt_fingerprint"],
            )["valid"]
            is False
        )
        ready_path.write_text(json.dumps(ready_value), encoding="utf-8")
        cleanup.write_text(json.dumps(cleanup_value), encoding="utf-8")
        lifecycle_path.write_text(json.dumps(lifecycle_value), encoding="utf-8")
    assert result["receipt"]["bounded_cross_tenant_mount_denial"] is True
    assert result["receipt"]["cross_tenant_production_isolation_proven"] is False
    assert result["receipt"]["runtime_gate_ready"] is False
    assert result["receipt"]["fixture_only"] is False
    assert result["receipt"]["container_host_pid"] == 65532
    assert result["receipt"]["runtime_namespace_pid"] == 1
    assert result["receipt"]["runtime_namespace_parent_pid"] == 0
    assert result["receipt"]["controller_verifier_fingerprint"] == container_isolation._file_sha256(
        container_isolation.CONTROLLER_VERIFIER
    )
    if operation_input is None:
        assert result["output"]["next_action"]["id"] == "work-1"
    else:
        assert result["output"]["approved_tenant_input_read"] is True
        assert result["output"]["sibling_tenant_boundary_absent"] is True
        assert result["output"]["bounded_cross_tenant_denial"] is True
        assert result["output"]["comprehensive_tenant_isolation_proven"] is False
        assert result["receipt"]["tenant_boundary_probe_id"] == "tenant-boundary-probe-001"
        assert result["receipt"]["approved_tenant_input_read"] is True
        assert result["receipt"]["sibling_tenant_boundary_absent"] is True
        assert result["receipt"]["comprehensive_tenant_isolation_proven"] is False
        assert "synthetic-tenant-a-marker" not in " ".join(created_argv)
    assert ["--network", "none"] == created_argv[created_argv.index("--network") : created_argv.index("--network") + 2]
    assert "--read-only" in created_argv
    assert ["--cap-drop", "ALL"] == created_argv[
        created_argv.index("--cap-drop") : created_argv.index("--cap-drop") + 2
    ]
    assert "--privileged" not in created_argv and "docker.sock" not in " ".join(created_argv)
    assert any(command[3:5] == ["container", "rm"] for command in commands)
    cleanup = Path(result["proof_root"]) / "receipts" / "cleanup.json"
    assert json.loads(cleanup.read_text(encoding="utf-8"))["status"] == "removed"


def test_live_verifier_rejects_tampered_or_stopped_historical_source(
    isolation_fixture: dict[str, Any],
) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    authority_args = _evidence_execution_kwargs(isolation_fixture)
    assert authority_args["authorize_runtime_evidence"]() is True
    authority = pilot_runtime.pilot_runtime_lease_authority_snapshot(
        payload["lease_id"],
        actor=payload["request_actor"],
        expected_bindings=container_isolation.container_isolation_lease_bindings(),
    )
    root = container_isolation._proof_base() / payload["proof_run_id"]
    (root / "receipts").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "tenant").mkdir()
    (root / "tenant" / "work_items.json").write_text(
        json.dumps(payload["operation_input"], sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_runtime_records(root, payload, isolation_fixture["provision"]["tenant_key"])
    records = {
        name: json.loads((root / "state" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("handshake", "heartbeat", "operation", "briefing")
    }
    ready = container_isolation._receipt(
        plan,
        "ready",
        {
            "container_id": "9" * 64,
            "container_name": f"francis-mciso-{payload['proof_run_id']}",
            "container_host_pid": 65532,
            "handshake_fingerprint": container_isolation._fingerprint(records["handshake"]),
            "heartbeat_fingerprint": container_isolation._fingerprint(records["heartbeat"]),
            "heartbeat_sequence": records["heartbeat"]["sequence"],
            "operation_receipt_fingerprint": records["operation"]["receipt_fingerprint"],
            "output_fingerprint": records["briefing"]["output_fingerprint"],
            "fixture_only": False,
        },
    )
    (root / "receipts" / "ready.json").write_text(json.dumps(ready), encoding="utf-8")
    running = True

    def inspect(argv: list[str], timeout: float) -> container_isolation.DockerResult:
        assert argv[3:5] == ["container", "inspect"]
        item = _owned_inspect_item(plan["descriptor"], root, host_pid=65532)
        item["State"]["Running"] = running
        return container_isolation.DockerResult(tuple(argv), 0, json.dumps([item]), "")

    verifier = live_evidence.live_container_source_verifier(
        plan=plan,
        proof_root=root,
        operation_input=payload["operation_input"],
        run=inspect,
        expected_authority=authority,
    )
    assert verifier(ready["receipt_id"], ready["receipt_fingerprint"])["valid"] is True

    records["heartbeat"]["sequence"] = 2
    (root / "state" / "heartbeat.json").write_text(json.dumps(records["heartbeat"]), encoding="utf-8")
    assert verifier(ready["receipt_id"], ready["receipt_fingerprint"])["valid"] is True

    (root / "state" / "heartbeat.json").write_text(
        json.dumps(
            {
                **records["heartbeat"],
                "sequence": ready["heartbeat_sequence"],
                "observed_at_unix_ms": records["heartbeat"]["observed_at_unix_ms"] + 1,
            }
        ),
        encoding="utf-8",
    )
    assert verifier(ready["receipt_id"], ready["receipt_fingerprint"])["valid"] is False

    (root / "state" / "heartbeat.json").write_text(json.dumps(records["heartbeat"]), encoding="utf-8")
    running = False
    assert verifier(ready["receipt_id"], ready["receipt_fingerprint"])["valid"] is False


def test_tenant_boundary_probe_tamper_is_rejected(isolation_fixture: dict[str, Any], tmp_path: Path) -> None:
    payload = isolation_fixture["payload"]
    payload["operation_input"] = {
        "contract": container_isolation.TENANT_BOUNDARY_INPUT_CONTRACT,
        "probe_id": "tenant-boundary-probe-tamper",
        "tenant_marker": "synthetic-tenant-a-marker",
    }
    _write_approval(isolation_fixture)
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    root = tmp_path / "proof"
    (root / "state").mkdir(parents=True)
    _write_runtime_records(root, payload, isolation_fixture["provision"]["tenant_key"])
    output_path = root / "state" / "tenant_boundary_probe.json"
    output = json.loads(output_path.read_text(encoding="utf-8"))
    output["sibling_tenant_boundary_absent"] = False
    output["bounded_cross_tenant_denial"] = False
    output["output_fingerprint"] = container_isolation._fingerprint(
        {key: value for key, value in output.items() if key != "output_fingerprint"}
    )
    output_path.write_text(json.dumps(output), encoding="utf-8")
    operation_path = root / "state" / "operation.json"
    operation = json.loads(operation_path.read_text(encoding="utf-8"))
    operation["output_fingerprint"] = output["output_fingerprint"]
    operation["receipt_fingerprint"] = container_isolation._fingerprint(
        {key: value for key, value in operation.items() if key != "receipt_fingerprint"}
    )
    operation_path.write_text(json.dumps(operation), encoding="utf-8")
    records = {
        name: json.loads((root / "state" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("handshake", "heartbeat", "operation", "tenant_boundary_probe")
    }

    assert (
        container_isolation._runtime_records_blocker(
            records,
            plan["descriptor"],
            operation_input=payload["operation_input"],
        )
        == "managed_copy_container_runtime_output_invalid"
    )


def test_tenant_boundary_probe_rejects_caller_selected_boundary(
    isolation_fixture: dict[str, Any],
) -> None:
    payload = isolation_fixture["payload"]
    payload["operation_input"] = {
        "contract": container_isolation.TENANT_BOUNDARY_INPUT_CONTRACT,
        "probe_id": "tenant-boundary-caller-path",
        "tenant_marker": "synthetic-tenant-a-marker",
        "sibling_path": "C:/operator-selected",
    }

    result = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )

    assert result["error"] == "managed_copy_tenant_boundary_probe_input_schema_invalid"
    assert not container_isolation._proof_base().exists()


def test_runtime_records_reject_tampered_useful_output(isolation_fixture: dict[str, Any], tmp_path: Path) -> None:
    _write_approval(isolation_fixture)
    payload = isolation_fixture["payload"]
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    root = tmp_path / "proof"
    (root / "state").mkdir(parents=True)
    _write_runtime_records(root, payload, isolation_fixture["provision"]["tenant_key"])
    briefing_path = root / "state" / "briefing.json"
    briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
    briefing["next_action"]["id"] = "attacker-selected"
    briefing_path.write_text(json.dumps(briefing), encoding="utf-8")
    records = {
        name: json.loads((root / "state" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("handshake", "heartbeat", "operation", "briefing")
    }

    assert (
        container_isolation._runtime_records_blocker(
            records,
            plan["descriptor"],
            operation_input=payload["operation_input"],
        )
        == "managed_copy_container_runtime_output_invalid"
    )


def test_readiness_uses_full_authorized_lease_after_ten_seconds(
    isolation_fixture: dict[str, Any], tmp_path: Path
) -> None:
    payload = isolation_fixture["payload"]
    payload["lease_seconds"] = 30
    _write_approval(isolation_fixture)
    state = tmp_path / "state"
    state.mkdir()
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    descriptor = plan["descriptor"]
    elapsed = 0.0

    def clock() -> float:
        return elapsed

    def sleep(seconds: float) -> None:
        nonlocal elapsed
        elapsed += seconds
        if elapsed >= 10.5 and not (state / "handshake.json").exists():
            _write_runtime_records(tmp_path, payload, isolation_fixture["provision"]["tenant_key"])

    records = container_isolation._wait_for_runtime_records(
        state,
        descriptor,
        operation_input=payload["operation_input"],
        clock=clock,
        sleeper=sleep,
    )

    assert elapsed >= 10.5
    assert elapsed < 30
    assert (
        container_isolation._runtime_records_blocker(records, descriptor, operation_input=payload["operation_input"])
        == ""
    )


def test_readiness_after_authorized_deadline_fails(isolation_fixture: dict[str, Any], tmp_path: Path) -> None:
    payload = isolation_fixture["payload"]
    _write_approval(isolation_fixture)
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    state = tmp_path / "state"
    state.mkdir()
    elapsed = 0.0

    def clock() -> float:
        return elapsed

    def sleep(seconds: float) -> None:
        nonlocal elapsed
        elapsed += seconds

    records = container_isolation._wait_for_runtime_records(
        state,
        plan["descriptor"],
        operation_input=payload["operation_input"],
        clock=clock,
        sleeper=sleep,
    )

    assert elapsed >= payload["lease_seconds"]
    assert (
        container_isolation._runtime_records_blocker(
            records, plan["descriptor"], operation_input=payload["operation_input"]
        )
        == "managed_copy_container_runtime_handshake_missing_or_invalid"
    )


def test_readiness_above_thirty_seconds_is_rejected(isolation_fixture: dict[str, Any]) -> None:
    payload = dict(isolation_fixture["payload"])
    payload["lease_seconds"] = 31

    denied = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )

    assert denied["error"] == "managed_copy_container_isolation_binding_invalid"


@pytest.mark.parametrize("host_pid", [0, -1, True, None, "65532"])
def test_container_host_pid_rejects_non_positive_or_non_integer_values(host_pid: object) -> None:
    result = container_isolation.DockerResult(("docker",), 0, json.dumps([{"State": {"Pid": host_pid}}]), "")

    assert container_isolation._container_host_pid(result) == 0


@pytest.mark.parametrize(("pid", "parent_pid"), [(2, 0), (1, 1), (65532, 0)])
def test_runtime_namespace_identity_is_exact(
    isolation_fixture: dict[str, Any], tmp_path: Path, pid: int, parent_pid: int
) -> None:
    payload = isolation_fixture["payload"]
    _write_approval(isolation_fixture)
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    (tmp_path / "state").mkdir()
    _write_runtime_records(tmp_path, payload, isolation_fixture["provision"]["tenant_key"])
    records = {
        name: json.loads((tmp_path / "state" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("handshake", "heartbeat", "operation", "briefing")
    }
    records["handshake"]["pid"] = pid
    records["handshake"]["parent_pid"] = parent_pid

    assert (
        container_isolation._runtime_records_blocker(
            records, plan["descriptor"], operation_input=payload["operation_input"]
        )
        == "managed_copy_container_runtime_process_identity_mismatch"
    )


def test_different_host_and_namespace_pids_are_valid(isolation_fixture: dict[str, Any], tmp_path: Path) -> None:
    payload = isolation_fixture["payload"]
    _write_approval(isolation_fixture)
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    (tmp_path / "tenant").mkdir()
    (tmp_path / "state").mkdir()
    inspected = container_isolation.DockerResult(
        ("docker",), 0, json.dumps([_owned_inspect_item(plan["descriptor"], tmp_path)]), ""
    )
    _write_runtime_records(tmp_path, payload, isolation_fixture["provision"]["tenant_key"])
    records = {
        name: json.loads((tmp_path / "state" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("handshake", "heartbeat", "operation", "briefing")
    }

    assert (
        container_isolation._inspect_blocker(
            inspected,
            plan["descriptor"],
            name=f"francis-mciso-{payload['proof_run_id']}",
            root=tmp_path,
            require_running=True,
        )
        == ""
    )
    assert container_isolation._container_host_pid(inspected) == 65532
    assert records["handshake"]["pid"] == 1
    assert records["handshake"]["parent_pid"] == 0
    assert (
        container_isolation._runtime_records_blocker(
            records, plan["descriptor"], operation_input=payload["operation_input"]
        )
        == ""
    )


@pytest.mark.parametrize("tamper", ["container_id", "label", "command"])
def test_container_identity_tampering_is_denied(isolation_fixture: dict[str, Any], tmp_path: Path, tamper: str) -> None:
    payload = isolation_fixture["payload"]
    _write_approval(isolation_fixture)
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    (tmp_path / "tenant").mkdir()
    (tmp_path / "state").mkdir()
    item = _owned_inspect_item(plan["descriptor"], tmp_path)
    if tamper == "container_id":
        item["Image"] = "sha256:" + "0" * 64
    elif tamper == "label":
        item["Config"]["Labels"]["francis.proof_run_id"] = "other-run"
    else:
        item["Config"]["Cmd"] = ["--unapproved"]
    inspected = container_isolation.DockerResult(("docker",), 0, json.dumps([item]), "")

    assert (
        container_isolation._inspect_blocker(
            inspected,
            plan["descriptor"],
            name=f"francis-mciso-{payload['proof_run_id']}",
            root=tmp_path,
            require_running=True,
        )
        != ""
    )


@pytest.mark.parametrize("field", ["runtime_nonce_hash", "copy_id", "tenant_key", "pilot_run_id"])
def test_runtime_lineage_tampering_is_denied(isolation_fixture: dict[str, Any], tmp_path: Path, field: str) -> None:
    payload = isolation_fixture["payload"]
    _write_approval(isolation_fixture)
    plan = container_isolation.container_isolation_proposal(
        payload, actor=payload["request_actor"], stage17_closed=True
    )
    (tmp_path / "state").mkdir()
    _write_runtime_records(tmp_path, payload, isolation_fixture["provision"]["tenant_key"])
    records = {
        name: json.loads((tmp_path / "state" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("handshake", "heartbeat", "operation", "briefing")
    }
    records["handshake"][field] = "tampered"

    assert (
        container_isolation._runtime_records_blocker(
            records, plan["descriptor"], operation_input=payload["operation_input"]
        )
        == "managed_copy_container_runtime_handshake_lineage_mismatch"
    )


@pytest.mark.skipif(
    os.environ.get("FRANCIS_RUN_REAL_DOCKER_PROOF") != "1",
    reason="requires the explicitly authorized isolated Docker Desktop proof",
)
def test_real_fixed_docker_fixture_proof(
    isolation_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ["FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT"] = os.environ["FRANCIS_DOCKER_PROOF_BASE"]
    payload = isolation_fixture["payload"]
    payload["image_manifest_digest"] = os.environ["FRANCIS_DOCKER_MANIFEST_DIGEST"]
    payload["image_platform_digest"] = os.environ["FRANCIS_DOCKER_PLATFORM_DIGEST"]
    payload["image_id"] = os.environ["FRANCIS_DOCKER_IMAGE_ID"]
    payload["image_config_fingerprint"] = os.environ["FRANCIS_DOCKER_IMAGE_CONFIG_FINGERPRINT"]
    payload["engine_id"] = os.environ["FRANCIS_DOCKER_ENGINE_ID"]
    payload["engine_server_fingerprint"] = os.environ["FRANCIS_DOCKER_ENGINE_SERVER_FINGERPRINT"]
    payload["proof_run_id"] = os.environ["FRANCIS_DOCKER_PROOF_RUN_ID"]
    payload["lease_seconds"] = 30
    payload["lease_id"] = f"lease-{payload['proof_run_id']}"
    payload["runtime_nonce"] = f"nonce-{payload['proof_run_id']}"
    payload["operation_input"] = {
        "contract": container_isolation.INPUT_CONTRACT,
        "items": [
            {
                "id": "pilot-001",
                "title": "Verify governed managed-copy runtime lifecycle",
                "priority": "critical",
                "status": "open",
            },
            {
                "id": "pilot-002",
                "title": "Confirm exact cleanup and container absence",
                "priority": "high",
                "status": "open",
            },
            {
                "id": "pilot-003",
                "title": "Preserve fixture and canonical evidence separation",
                "priority": "normal",
                "status": "done",
            },
        ],
    }

    now_ms = int(time.time() * 1000)
    registry = PilotScopeLeaseRegistry()
    registry.issue(
        PilotScopeLease(
            lease_id=payload["lease_id"],
            actor_id=payload["request_actor"],
            package_id="stage18-container-pilot-package",
            package_fingerprint="e" * 64,
            pilot_run_id=payload["proof_run_id"],
            bindings=(
                PilotLeaseBinding(
                    container_isolation.CONTAINER_ISOLATION_SCOPE,
                    container_isolation.CONTAINER_ISOLATION_ROUTE,
                    "POST",
                    container_isolation.CONTAINER_ISOLATION_ACTION,
                ),
                PilotLeaseBinding(
                    container_isolation.RUNTIME_EVIDENCE_SCOPE,
                    container_isolation.RUNTIME_EVIDENCE_ROUTE,
                    "POST",
                    container_isolation.RUNTIME_EVIDENCE_ACTION,
                ),
            ),
            issued_at_ms=now_ms - 1_000,
            expires_at_ms=now_ms + 120_000,
            runtime_nonce=payload["runtime_nonce"],
            operator_decision_fingerprint="f" * 64,
        )
    )
    monkeypatch.setattr(pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(managed_copy_routes, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(container_isolation, "_pilot_lease_context", _REAL_PILOT_LEASE_CONTEXT)
    monkeypatch.setattr(
        managed_copy_routes,
        "managed_copies_status_snapshot",
        lambda: {"stage17_closed_by_receipt": True},
    )
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps(
            {
                payload["request_actor"]: [
                    container_isolation.CONTAINER_ISOLATION_SCOPE,
                    container_isolation.RUNTIME_EVIDENCE_SCOPE,
                ]
            }
        ),
    )
    _write_approval(isolation_fixture)

    client = TestClient(create_app())
    result = client.post(container_isolation.CONTAINER_ISOLATION_ROUTE, json=payload).json()

    assert result["ok"] is True, result
    assert registry.state(payload["lease_id"]) is PilotLeaseState.CONSUMED
    assert result["receipt"]["bounded_cross_tenant_mount_denial"] is True
    assert result["receipt"]["fixture_only"] is False
    assert result["receipt"]["runtime_gate_ready"] is False
    assert result["runtime_evidence"]["receipt"]["requirement_id"] == runtime_evidence.COPY_CREATION_REQUIREMENT
    assert result["output"]["next_action"]["id"] == "pilot-001"
    cleanup = Path(result["proof_root"]) / "receipts" / "cleanup.json"
    assert json.loads(cleanup.read_text(encoding="utf-8"))["status"] == "removed"
    inspected = container_isolation.default_docker_runner(
        [*container_isolation._docker_prefix(), "container", "inspect", result["receipt"]["container_id"]], 10.0
    )
    assert inspected.exit_code != 0

    replay = client.post(container_isolation.CONTAINER_ISOLATION_ROUTE, json=payload).json()
    assert replay["ok"] is False
    assert replay["error"] == "api_permission_denied"
    assert registry.state(payload["lease_id"]) is PilotLeaseState.CONSUMED
