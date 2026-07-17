from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from francis.kernel.paths import data_dir, repo_root
from francis.managed_copy_isolation import latest_managed_copy_isolation_verification_for_provision
from francis.managed_copy_provisioning import managed_copy_provision_for_copy
from francis.managed_copy_runtime import (
    HEARTBEAT_IDENTITY,
    INPUT_CONTRACT,
    OUTPUT_CONTRACT,
    RUNTIME_IDENTITY,
    build_work_briefing,
)
from francis.managed_copy_runtime_start import validate_runtime_start_approval_reference

CONTAINER_ISOLATION_SCOPE = "managed_copies.container_isolation.execute"
CONTAINER_ISOLATION_ACTION = "managed_copies.container_isolation"
CONTAINER_ISOLATION_ROUTE = "/managed-copies/container-isolation"
CONTAINER_ISOLATION_CONTRACT = "stage18_managed_copy_docker_isolation_v2"
FIXED_IMAGE_REPOSITORY = "francis/managed-copy-runtime"
FIXED_IMAGE_TAG = "stage18-v1"
FIXED_PLATFORM = "linux/amd64"
FIXED_CONTAINER_USER = "65532:65532"
RUNTIME_PROGRAM = repo_root() / "src" / "francis" / "managed_copy_runtime.py"
RUNTIME_DOCKERFILE = repo_root() / "infra" / "managed-copy-runtime" / "Dockerfile"
RUNTIME_PROGRAM_CONTAINER_PATH = "/opt/francis/managed_copy_runtime.py"
SECURITY_PROFILE_DIAGNOSTIC_CONTRACT = "stage18_managed_copy_docker_security_profile_diagnostic_v1"
DIAGNOSTIC_PREDECESSOR_PROOF_RUN_ID = "mciso-20260716t170613z"
DIAGNOSTIC_PREDECESSOR_FAILED_RECEIPT_FINGERPRINT = "1add7aa3607770bc7e034c29edbe2252e2ea87ad516b0fa46b852c7393cdb006"
_LOCK = threading.Lock()
_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
_PAYLOAD_FIELDS = frozenset(
    {
        "request_actor",
        "approval_id",
        "runtime_start_approval_id",
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "image_manifest_digest",
        "image_platform_digest",
        "image_id",
        "image_config_fingerprint",
        "engine_id",
        "engine_server_fingerprint",
        "docker_context",
        "proof_run_id",
        "lease_id",
        "runtime_nonce",
        "action_nonce",
        "trace_id",
        "lease_seconds",
        "confirm_container_isolation",
        "operation_input",
    }
)
_APPROVAL_FIELDS = frozenset(
    {"id", "ts", "action", "reason", "payload", "status", "decision", "decision_actor", "decided_ts"}
)
_APPROVAL_PAYLOAD_FIELDS = frozenset(
    {
        "contract",
        "action",
        "request_actor",
        "descriptor",
        "descriptor_fingerprint",
        "action_nonce",
        "trace_id",
        "expires_at_unix_ms",
        "revoked",
    }
)


@dataclass(frozen=True)
class DockerResult:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


DockerRunner = Callable[[list[str], float], DockerResult]
DiagnosticValue = str | int | bool | list[str] | None
_MAX_DIAGNOSTIC_TOKENS = 8
_NUMERIC_USER_PATTERN = re.compile(r"^[1-9][0-9]{0,9}(?::[1-9][0-9]{0,9})?$")


class SecurityComparison(str, Enum):
    EQUIVALENT = "semantically_equivalent"
    WEAKER = "weaker"
    STRONGER = "stronger"
    INVALID = "invalid"


@dataclass(frozen=True)
class SecurityFieldDiagnostic:
    field_name: str
    expected_value: DiagnosticValue
    expected_type: str
    observed_value: DiagnosticValue
    observed_type: str
    normalization_rule: str
    classification: SecurityComparison


def default_docker_runner(argv: list[str], timeout_seconds: float) -> DockerResult:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return DockerResult(tuple(argv), 124, _text(exc.stdout), _text(exc.stderr), timed_out=True)
    except OSError as exc:
        return DockerResult(tuple(argv), 127, "", type(exc).__name__)
    return DockerResult(tuple(argv), completed.returncode, completed.stdout, completed.stderr)


def container_isolation_contract_snapshot() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "francis.stage18.managed_copies.container_isolation_contract",
        "contract": CONTAINER_ISOLATION_CONTRACT,
        "status": "fixed_francis_runtime_container_adapter_available",
        "required_scope": CONTAINER_ISOLATION_SCOPE,
        "approval_action": CONTAINER_ISOLATION_ACTION,
        "runtime_start_approval_also_required": True,
        "pilot_lease_required": True,
        "backend": "docker_desktop_wsl2_linux",
        "fixed_image_repository": FIXED_IMAGE_REPOSITORY,
        "fixed_image_tag": FIXED_IMAGE_TAG,
        "fixed_platform": FIXED_PLATFORM,
        "runtime_identity": RUNTIME_IDENTITY,
        "operation": "tenant_work_briefing",
        "runtime_program_fingerprint": _file_sha256(RUNTIME_PROGRAM),
        "runtime_dockerfile_fingerprint": _file_sha256(RUNTIME_DOCKERFILE),
        "caller_selected_image": False,
        "caller_selected_command": False,
        "network": "none",
        "fixture_only": False,
        "persistent_actor_grant_present": False,
        "runtime_gate_ready": False,
        "stage18_ready": False,
        "routes": {
            "contract": "/managed-copies/container-isolation-contract",
            "execute": "/managed-copies/container-isolation",
        },
    }


def container_isolation_proposal(payload: dict[str, Any], *, actor: str, stage17_closed: bool) -> dict[str, Any]:
    blockers: list[str] = []
    if set(payload) != _PAYLOAD_FIELDS:
        blockers.append("managed_copy_container_isolation_payload_schema_invalid")
    safe_actor = _identifier(actor)
    if not safe_actor or _identifier(payload.get("request_actor")) != safe_actor:
        blockers.append("managed_copy_container_isolation_actor_mismatch")
    if not stage17_closed:
        blockers.append("stage17_prerequisite_not_closed")
    if type(payload.get("confirm_container_isolation")) is not bool:
        blockers.append("managed_copy_container_isolation_confirmation_invalid")
    lease_seconds = _exact_int(payload.get("lease_seconds"), minimum=2, maximum=30)
    keys = (
        "approval_id",
        "runtime_start_approval_id",
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "engine_id",
        "docker_context",
        "proof_run_id",
        "lease_id",
        "runtime_nonce",
        "action_nonce",
        "trace_id",
    )
    values = {key: _identifier(payload.get(key)) for key in keys}
    digests = {key: _digest(payload.get(key)) for key in ("image_manifest_digest", "image_platform_digest", "image_id")}
    digests.update({key: _hash(payload.get(key)) for key in ("image_config_fingerprint", "engine_server_fingerprint")})
    if not all(values.values()) or not all(digests.values()) or lease_seconds == 0:
        blockers.append("managed_copy_container_isolation_binding_invalid")
    if values.get("docker_context") != "desktop-linux":
        blockers.append("managed_copy_container_isolation_context_invalid")
    lease_context = _pilot_lease_context(values.get("lease_id", ""))
    if (
        not lease_context
        or lease_context.get("actor_id") != safe_actor
        or lease_context.get("pilot_run_id") != values.get("proof_run_id")
    ):
        blockers.append("managed_copy_container_isolation_pilot_lease_lineage_invalid")
    if len(set(digests.get(key) for key in ("image_manifest_digest", "image_platform_digest", "image_id"))) != 1:
        blockers.append("managed_copy_container_isolation_fixed_image_mismatch")
    try:
        operation_preview = build_work_briefing(payload.get("operation_input"))
    except ValueError as exc:
        blockers.append(str(exc))
        operation_preview = {}

    provision: dict[str, Any] = {}
    isolation: dict[str, Any] = {}
    if not blockers:
        provision = managed_copy_provision_for_copy(
            values["copy_id"], provisioning_receipt_id=values["provisioning_receipt_id"]
        )
        if not provision:
            blockers.append("managed_copy_container_isolation_provision_invalid")
        else:
            isolation = latest_managed_copy_isolation_verification_for_provision(
                values["provisioning_receipt_id"],
                provision_fingerprint=_text(provision.get("provision_fingerprint")),
                copy_id=values["copy_id"],
            )
            if (
                not isolation
                or _text(isolation.get("receipt_id")) != values["isolation_verification_receipt_id"]
                or isolation.get("live_state_aligned") is not True
            ):
                blockers.append("managed_copy_container_isolation_lineage_invalid")

    runtime_approval: dict[str, Any] = {}
    if not blockers:
        runtime_approval = validate_runtime_start_approval_reference(
            values["runtime_start_approval_id"],
            actor=safe_actor,
            copy_id=values["copy_id"],
            provisioning_receipt_id=values["provisioning_receipt_id"],
            provision_fingerprint=_text(provision.get("provision_fingerprint")),
            isolation_verification_receipt_id=values["isolation_verification_receipt_id"],
            isolation_verification_fingerprint=_text(isolation.get("verification_fingerprint")),
        )
        if not runtime_approval.get("valid"):
            blockers.append("managed_copy_container_isolation_runtime_start_approval_invalid")

    descriptor: dict[str, Any] = {}
    descriptor_fingerprint = ""
    if not blockers:
        descriptor = _descriptor(
            payload,
            values=values,
            digests=digests,
            provision=provision,
            isolation=isolation,
            runtime_approval=runtime_approval,
            operation_preview=operation_preview,
            lease_context=lease_context,
        )
        descriptor_fingerprint = _fingerprint(descriptor)
        approval = _approval(values["approval_id"])
        blocker = _approval_blocker(
            approval,
            actor=safe_actor,
            descriptor=descriptor,
            descriptor_fingerprint=descriptor_fingerprint,
            action_nonce=values["action_nonce"],
            trace_id=values["trace_id"],
        )
        if blocker:
            blockers.append(blocker)
    return {
        "ok": not blockers,
        "status": "approved" if not blockers else "blocked",
        "error": blockers[0] if blockers else "",
        "blockers": blockers,
        "actor": safe_actor,
        "approval_id": values.get("approval_id", ""),
        "descriptor": descriptor,
        "descriptor_fingerprint": descriptor_fingerprint,
        "writes_receipt": False,
        "starts_container": False,
        "fixture_only": False,
        "runtime_gate_ready": False,
        "stage18_ready": False,
    }


def execute_container_isolation(
    payload: dict[str, Any],
    *,
    actor: str,
    stage17_closed: bool,
    run: DockerRunner = default_docker_runner,
) -> dict[str, Any]:
    initial = container_isolation_proposal(payload, actor=actor, stage17_closed=stage17_closed)
    if not initial["ok"]:
        return initial
    if payload.get("confirm_container_isolation") is not True:
        return _blocked(initial, "managed_copy_container_isolation_confirmation_required")
    with _LOCK:
        final = container_isolation_proposal(payload, actor=actor, stage17_closed=stage17_closed)
        if not final["ok"] or final["descriptor_fingerprint"] != initial["descriptor_fingerprint"]:
            return _blocked(initial, "managed_copy_container_isolation_changed_under_lock")
        return _execute(final, operation_input=payload["operation_input"], run=run)


def _execute(plan: dict[str, Any], *, operation_input: object, run: DockerRunner) -> dict[str, Any]:
    d = plan["descriptor"]
    preflight = _docker_preflight(run, d)
    if preflight:
        return _blocked(plan, preflight)
    root = _create_proof_root(d["proof_run_id"])
    if root is None:
        return _blocked(plan, "managed_copy_container_proof_root_unsafe_or_in_use")
    receipts = root / "receipts"
    state = root / "state"
    tenant = root / "tenant"
    for path in (receipts, state, tenant):
        path.mkdir()
    _write_text_immutable(tenant / "work_items.json", json.dumps(operation_input, sort_keys=True) + "\n")
    name = f"francis-mciso-{d['proof_run_id'].lower()}"
    image = f"{FIXED_IMAGE_REPOSITORY}:{FIXED_IMAGE_TAG}"
    create_argv = _create_argv(d, name=name, image=image, root=root)
    source_snapshot = _mount_source_snapshot(root, descriptor=d)
    if not source_snapshot:
        return _blocked(plan, "managed_copy_container_mount_source_unsafe")
    attempt = _receipt(
        plan, "launch_attempt", {"container_name": name, "command_fingerprint": _fingerprint(create_argv)}
    )
    _write_immutable(receipts / "launch-attempt.json", attempt)
    created = run(create_argv, 30.0)
    if created.exit_code != 0:
        recovered_id = _recover_container_id(run, name, retry=created.timed_out)
        if recovered_id:
            cleanup_status = _cleanup_exact(run, recovered_id, name=name, receipts=receipts, plan=plan)
            if cleanup_status != "removed":
                _fail(plan, receipts, "managed_copy_container_create_failed_cleanup_failed", created)
                return {
                    "ok": False,
                    "status": "cleanup_required",
                    "error": "managed_copy_container_create_failed_cleanup_failed",
                    "proof_root": str(root),
                }
        elif created.timed_out:
            _fail(plan, receipts, "managed_copy_container_create_timeout_cleanup_unverified", created)
            return {
                "ok": False,
                "status": "cleanup_required",
                "error": "managed_copy_container_create_timeout_cleanup_unverified",
                "proof_root": str(root),
            }
        return _fail(plan, receipts, "managed_copy_container_create_failed", created)
    container_id = _container_id(created.stdout)
    if not container_id:
        recovered = _inspect(run, name)
        recovered_id = _container_id_from_inspect(recovered)
        if recovered_id:
            cleanup_status = _cleanup_exact(run, recovered_id, name=name, receipts=receipts, plan=plan)
            if cleanup_status != "removed":
                _fail(plan, receipts, "managed_copy_container_id_invalid_cleanup_failed", created)
                return {
                    "ok": False,
                    "status": "cleanup_required",
                    "error": "managed_copy_container_id_invalid_cleanup_failed",
                    "proof_root": str(root),
                }
            return _fail(plan, receipts, "managed_copy_container_id_invalid", created)
        _fail(plan, receipts, "managed_copy_container_id_invalid_cleanup_unverified", created)
        return {
            "ok": False,
            "status": "cleanup_required",
            "error": "managed_copy_container_id_invalid_cleanup_unverified",
            "proof_root": str(root),
        }
    try:
        if _mount_source_snapshot(root, descriptor=d) != source_snapshot:
            return _fail(plan, receipts, "managed_copy_container_mount_source_changed", created)
        inspected = _inspect(run, container_id)
        blocker = _inspect_blocker(inspected, d, name=name, root=root)
        if blocker:
            if blocker == "managed_copy_container_security_profile_mismatch":
                _write_security_profile_diagnostic(receipts, plan=plan, inspected=inspected)
            return _fail(plan, receipts, blocker, inspected)
        started = run([*_docker_prefix(), "container", "start", container_id], 15.0)
        if started.exit_code != 0:
            return _fail(plan, receipts, "managed_copy_container_start_failed", started)
        deadline = time.monotonic() + min(10.0, float(d["lease_seconds"]))
        records: dict[str, dict[str, Any]] = {}
        while time.monotonic() < deadline:
            records = {
                name: _read_json(state / f"{name}.json") for name in ("handshake", "heartbeat", "operation", "briefing")
            }
            if not _runtime_records_blocker(records, d, operation_input=operation_input):
                break
            time.sleep(0.1)
        records_blocker = _runtime_records_blocker(records, d, operation_input=operation_input)
        if records_blocker:
            return _fail(plan, receipts, records_blocker, started)
        inspected = _inspect(run, container_id)
        blocker = _inspect_blocker(inspected, d, name=name, root=root, require_running=True)
        if blocker:
            if blocker == "managed_copy_container_security_profile_mismatch":
                _write_security_profile_diagnostic(receipts, plan=plan, inspected=inspected)
            return _fail(plan, receipts, blocker, inspected)
        runtime_pid = _container_runtime_pid(inspected)
        records_blocker = _runtime_records_blocker(
            records, d, operation_input=operation_input, expected_pid=runtime_pid
        )
        if records_blocker:
            return _fail(plan, receipts, records_blocker, inspected)
        proof = _receipt(
            plan,
            "ready",
            {
                "container_id": container_id,
                "container_name": name,
                "image_id": d["image_id"],
                "image_platform_digest": d["image_platform_digest"],
                "mount_set_fingerprint": d["mount_set_fingerprint"],
                "security_profile_fingerprint": d["security_profile_fingerprint"],
                "handshake_fingerprint": _fingerprint(records["handshake"]),
                "heartbeat_fingerprint": _fingerprint(records["heartbeat"]),
                "operation_receipt_fingerprint": records["operation"]["receipt_fingerprint"],
                "output_fingerprint": records["briefing"]["output_fingerprint"],
                "bounded_cross_tenant_mount_denial": True,
                "cross_tenant_production_isolation_proven": False,
                "fixture_only": False,
                "evidence_class": "isolated_non_fixture_francis_runtime",
                "runtime_gate_ready": False,
                "stage18_ready": False,
            },
        )
        _write_immutable(receipts / "ready.json", proof)
        return {
            "ok": True,
            "status": "runtime_ready",
            "receipt": proof,
            "output": records["briefing"],
            "proof_root": str(root),
        }
    finally:
        cleanup_status = _cleanup_exact(run, container_id, name=name, receipts=receipts, plan=plan)
        if cleanup_status != "removed":
            return {
                "ok": False,
                "status": "cleanup_required",
                "error": "managed_copy_container_cleanup_failed",
                "proof_root": str(root),
            }


def _create_argv(d: dict[str, Any], *, name: str, image: str, root: Path) -> list[str]:
    tenant = str((root / "tenant").resolve())
    state = str((root / "state").resolve())
    return [
        *_docker_prefix(),
        "container",
        "create",
        "--name",
        name,
        "--pull",
        "never",
        "--platform",
        FIXED_PLATFORM,
        "--label",
        f"francis.proof_run_id={d['proof_run_id']}",
        "--label",
        f"francis.tenant_key={d['tenant_key']}",
        "--label",
        f"francis.copy_id={d['copy_id']}",
        "--label",
        f"francis.approval_id={d['approval_id']}",
        "--user",
        FIXED_CONTAINER_USER,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--restart",
        "no",
        "--pids-limit",
        "32",
        "--memory",
        "64m",
        "--cpus",
        "0.25",
        "--tmpfs",
        "/tmp:rw,noexec,nodev,nosuid,size=1m",
        "--mount",
        f"type=bind,src={tenant},dst=/francis/tenant,readonly",
        "--mount",
        f"type=bind,src={state},dst=/francis/state",
        image,
        *_runtime_cmd(d),
    ]


def _runtime_cmd(d: dict[str, Any]) -> list[str]:
    return [
        "--tenant-root",
        "/francis",
        "--state-dir",
        "/francis/state",
        "--input-path",
        "/francis/tenant/work_items.json",
        "--copy-id",
        d["copy_id"],
        "--tenant-key",
        d["tenant_key"],
        "--pilot-run-id",
        d["proof_run_id"],
        "--runtime-nonce",
        d["runtime_nonce"],
        "--lease-seconds",
        str(d["lease_seconds"]),
    ]


def _docker_prefix() -> list[str]:
    return ["docker", "--context", "desktop-linux"]


def _docker_preflight(run: DockerRunner, descriptor: dict[str, Any]) -> str:
    if (
        _file_sha256(RUNTIME_PROGRAM) != descriptor["runtime_program_fingerprint"]
        or _file_sha256(RUNTIME_DOCKERFILE) != descriptor["runtime_dockerfile_fingerprint"]
    ):
        return "managed_copy_container_runtime_image_source_changed_before_launch"
    context = run(["docker", "context", "inspect", "desktop-linux"], 10.0)
    if context.exit_code != 0:
        return "managed_copy_container_context_unavailable"
    try:
        contexts = json.loads(context.stdout)
    except json.JSONDecodeError:
        return "managed_copy_container_context_invalid"
    if not isinstance(contexts, list) or len(contexts) != 1 or contexts[0].get("Name") != "desktop-linux":
        return "managed_copy_container_context_invalid"
    version = run([*_docker_prefix(), "version", "--format", "{{json .Server}}"], 10.0)
    info = run([*_docker_prefix(), "info", "--format", "{{json .}}"], 10.0)
    image = run(
        [*_docker_prefix(), "image", "inspect", f"{FIXED_IMAGE_REPOSITORY}:{FIXED_IMAGE_TAG}"],
        10.0,
    )
    if any(result.exit_code != 0 for result in (version, info, image)):
        return "managed_copy_container_docker_preflight_failed"
    try:
        server = json.loads(version.stdout)
        engine = json.loads(info.stdout)
        images = json.loads(image.stdout)
        inspected_image = images[0] if isinstance(images, list) and len(images) == 1 else {}
    except (json.JSONDecodeError, IndexError, TypeError):
        return "managed_copy_container_docker_preflight_invalid"
    if (
        not isinstance(server, dict)
        or server.get("Os") != "linux"
        or server.get("Arch") != "amd64"
        or _fingerprint(server) != descriptor["engine_server_fingerprint"]
        or engine.get("ID") != descriptor["engine_id"]
    ):
        return "managed_copy_container_engine_identity_mismatch"
    image_labels = (inspected_image.get("Config") or {}).get("Labels") or {}
    if (
        inspected_image.get("Id") != descriptor["image_id"]
        or inspected_image.get("Os") != "linux"
        or inspected_image.get("Architecture") != "amd64"
        or _fingerprint(inspected_image.get("Config")) != descriptor["image_config_fingerprint"]
        or image_labels.get("francis.runtime.contract") != RUNTIME_IDENTITY
        or image_labels.get("francis.runtime.program_sha256") != descriptor["runtime_program_fingerprint"]
        or (inspected_image.get("Config") or {}).get("User") != FIXED_CONTAINER_USER
        or (inspected_image.get("Config") or {}).get("Entrypoint") != ["python", RUNTIME_PROGRAM_CONTAINER_PATH]
    ):
        return "managed_copy_container_image_identity_mismatch"
    return ""


def _proof_base() -> Path:
    configured = os.environ.get("FRANCIS_MANAGED_COPY_DOCKER_PROOF_ROOT", "").strip()
    if configured:
        return Path(configured)
    if sys.platform == "win32":
        return Path(r"D:\Francis-support\proof-journeys\MC-ISO-001")
    return data_dir() / "managed_copy_container_proofs"


def _create_proof_root(proof_run_id: str) -> Path | None:
    base = _proof_base()
    try:
        if not _safe_existing_chain(base):
            return None
        base.mkdir(parents=True, exist_ok=True)
        if not _safe_existing_chain(base):
            return None
        resolved_base = base.resolve(strict=True)
        root = base / proof_run_id
        if root.exists() or root.resolve(strict=False).parent != resolved_base:
            return None
        root.mkdir()
        if not _safe_existing_chain(root) or root.resolve(strict=True).parent != resolved_base:
            return None
        return root
    except OSError:
        return None


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & 0x400)


def _safe_existing_chain(path: Path) -> bool:
    current = path.absolute()
    existing = [current, *current.parents]
    return all(not candidate.exists() or not _is_reparse(candidate) for candidate in existing)


def _mount_source_snapshot(root: Path, *, descriptor: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    sources = {
        "tenant": root / "tenant",
        "state": root / "state",
    }
    snapshot: dict[str, tuple[Any, ...]] = {}
    try:
        resolved_root = root.resolve(strict=True)
        for key, path in sources.items():
            if not _safe_existing_chain(path) or path.resolve(strict=True).parent not in {
                resolved_root,
                (resolved_root / "tenant"),
            }:
                return {}
            stat = path.lstat()
            snapshot[key] = (
                str(path.resolve(strict=True)).casefold(),
                stat.st_dev,
                stat.st_ino,
                stat.st_mode,
                stat.st_size,
                stat.st_mtime_ns,
                getattr(stat, "st_file_attributes", 0),
            )
        if _file_sha256(root / "tenant" / "work_items.json") != descriptor["operation_input_file_fingerprint"]:
            return {}
    except OSError:
        return {}
    return snapshot


def _container_id_from_inspect(result: DockerResult) -> str:
    if result.exit_code != 0:
        return ""
    try:
        values = json.loads(result.stdout)
        return _container_id(values[0].get("Id")) if isinstance(values, list) and len(values) == 1 else ""
    except (json.JSONDecodeError, AttributeError, TypeError):
        return ""


def _recover_container_id(run: DockerRunner, name: str, *, retry: bool) -> str:
    attempts = 5 if retry else 1
    for attempt in range(attempts):
        container_id = _container_id_from_inspect(_inspect(run, name))
        if container_id:
            return container_id
        if attempt + 1 < attempts:
            time.sleep(0.1)
    return ""


def _descriptor(
    payload: dict[str, Any],
    *,
    values: dict[str, str],
    digests: dict[str, str],
    provision: dict[str, Any],
    isolation: dict[str, Any],
    runtime_approval: dict[str, Any],
    operation_preview: dict[str, Any],
    lease_context: dict[str, str],
) -> dict[str, Any]:
    security = {
        "network": "none",
        "read_only_root": True,
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "user": FIXED_CONTAINER_USER,
        "memory_bytes": 67_108_864,
        "nano_cpus": 250_000_000,
        "pids_limit": 32,
        "restart": "no",
    }
    mounts = ["tenant_input:ro", "runtime_state:rw"]
    return {
        "contract": CONTAINER_ISOLATION_CONTRACT,
        "approval_id": values["approval_id"],
        "runtime_start_approval_id": values["runtime_start_approval_id"],
        "runtime_start_approval_fingerprint": _text(runtime_approval.get("approval_fingerprint")),
        "tenant_key": _text(provision.get("tenant_key")),
        "copy_id": values["copy_id"],
        "provisioning_receipt_id": values["provisioning_receipt_id"],
        "provision_fingerprint": _text(provision.get("provision_fingerprint")),
        "isolation_verification_receipt_id": values["isolation_verification_receipt_id"],
        "isolation_verification_fingerprint": _text(isolation.get("verification_fingerprint")),
        "docker_context": values["docker_context"],
        "engine_id": values["engine_id"],
        "engine_server_fingerprint": digests["engine_server_fingerprint"],
        "image_repository": FIXED_IMAGE_REPOSITORY,
        "image_tag": FIXED_IMAGE_TAG,
        "image_manifest_digest": digests["image_manifest_digest"],
        "image_platform_digest": digests["image_platform_digest"],
        "image_id": digests["image_id"],
        "image_config_fingerprint": digests["image_config_fingerprint"],
        "platform": FIXED_PLATFORM,
        "runtime_program_fingerprint": _file_sha256(RUNTIME_PROGRAM),
        "runtime_dockerfile_fingerprint": _file_sha256(RUNTIME_DOCKERFILE),
        "entrypoint_fingerprint": _fingerprint(["python", RUNTIME_PROGRAM_CONTAINER_PATH]),
        "mount_set_fingerprint": _fingerprint(mounts),
        "security_profile_fingerprint": _fingerprint(security),
        "runtime_identity": RUNTIME_IDENTITY,
        "heartbeat_identity": HEARTBEAT_IDENTITY,
        "input_contract": INPUT_CONTRACT,
        "output_contract": OUTPUT_CONTRACT,
        "operation": "tenant_work_briefing",
        "operation_input_fingerprint": operation_preview["input_fingerprint"],
        "operation_input_file_fingerprint": _sha256_text(json.dumps(payload["operation_input"], sort_keys=True) + "\n"),
        "proof_run_id": values["proof_run_id"],
        "lease_id": values["lease_id"],
        "pilot_package_id": lease_context["package_id"],
        "pilot_package_fingerprint": lease_context["package_fingerprint"],
        "pilot_operator_decision_fingerprint": lease_context["operator_decision_fingerprint"],
        "runtime_nonce": values["runtime_nonce"],
        "action_nonce": values["action_nonce"],
        "trace_id": values["trace_id"],
        "lease_seconds": _exact_int(payload["lease_seconds"], minimum=2, maximum=30),
        "fixture_only": False,
    }


def _inspect(run: DockerRunner, container_id: str) -> DockerResult:
    return run([*_docker_prefix(), "container", "inspect", container_id], 10.0)


def _security_profile_diagnostics(item: dict[str, Any]) -> tuple[SecurityFieldDiagnostic, ...]:
    raw_config = item.get("Config")
    config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
    raw_host = item.get("HostConfig")
    host: dict[str, Any] = raw_host if isinstance(raw_host, dict) else {}
    raw_restart = host.get("RestartPolicy")
    restart: dict[str, Any] = raw_restart if isinstance(raw_restart, dict) else {}
    diagnostics: list[SecurityFieldDiagnostic] = []

    def scalar(
        field_name: str,
        observed: Any,
        expected: str | int | bool,
        rule: str,
        classification: Callable[[Any], SecurityComparison],
    ) -> None:
        expected_type = _diagnostic_type(expected)
        observed_type = _diagnostic_type(observed)
        valid_type = type(observed) is type(expected)
        if valid_type and observed == expected:
            return
        normalized = _bounded_scalar_observation(field_name, observed, observed_type)
        diagnostics.append(
            SecurityFieldDiagnostic(
                field_name,
                expected,
                expected_type,
                normalized,
                observed_type,
                rule,
                classification(observed) if valid_type else SecurityComparison.INVALID,
            )
        )

    scalar(
        "Config.User",
        config.get("User"),
        FIXED_CONTAINER_USER,
        "exact_non_root_numeric_uid_gid",
        lambda value: SecurityComparison.WEAKER,
    )
    scalar(
        "HostConfig.Privileged",
        host.get("Privileged"),
        False,
        "exact_boolean_false",
        lambda value: SecurityComparison.WEAKER if value is True else SecurityComparison.INVALID,
    )
    _collection_diagnostic(
        diagnostics,
        field_name="HostConfig.CapDrop",
        observed=host.get("CapDrop"),
        expected=["ALL"],
        rule="uppercase_sorted_unique_tokens",
        normalize=lambda values: sorted({value.upper() for value in values}),
        none_is_empty=False,
        classify=lambda values: SecurityComparison.STRONGER if "ALL" in values else SecurityComparison.WEAKER,
    )
    _collection_diagnostic(
        diagnostics,
        field_name="HostConfig.CapAdd",
        observed=host.get("CapAdd"),
        expected=[],
        rule="null_or_empty_to_empty_uppercase_sorted_unique_tokens",
        normalize=lambda values: sorted({value.upper() for value in values}),
        none_is_empty=True,
        classify=lambda values: SecurityComparison.WEAKER if values else SecurityComparison.EQUIVALENT,
    )
    _collection_diagnostic(
        diagnostics,
        field_name="HostConfig.SecurityOpt",
        observed=host.get("SecurityOpt"),
        expected=["no-new-privileges:true"],
        rule="lowercase_sorted_unique_tokens_explicit_colon_or_equals_true_equivalence",
        normalize=lambda values: sorted(
            {
                "no-new-privileges:true"
                if value.lower() in {"no-new-privileges", "no-new-privileges=true"}
                else value.lower()
                for value in values
            }
        ),
        none_is_empty=False,
        classify=lambda values: (
            SecurityComparison.EQUIVALENT if values == ["no-new-privileges:true"] else SecurityComparison.WEAKER
        ),
        accepted_observed_forms=(["no-new-privileges:true"], ["no-new-privileges=true"]),
    )
    scalar(
        "HostConfig.ReadonlyRootfs",
        host.get("ReadonlyRootfs"),
        True,
        "exact_boolean_true",
        lambda value: SecurityComparison.WEAKER if value is False else SecurityComparison.INVALID,
    )
    scalar(
        "HostConfig.NetworkMode",
        host.get("NetworkMode"),
        "none",
        "lowercase_exact_none",
        lambda value: SecurityComparison.WEAKER,
    )
    scalar(
        "HostConfig.RestartPolicy.Name",
        restart.get("Name"),
        "no",
        "lowercase_exact_no",
        lambda value: SecurityComparison.WEAKER,
    )
    for field_name, observed, expected in (
        ("HostConfig.Memory", host.get("Memory"), 67_108_864),
        ("HostConfig.NanoCpus", host.get("NanoCpus"), 250_000_000),
        ("HostConfig.PidsLimit", host.get("PidsLimit"), 32),
    ):
        scalar(
            field_name,
            observed,
            expected,
            "exact_positive_integer_limit",
            _resource_limit_classification(expected),
        )
    return tuple(sorted(diagnostics, key=lambda item: item.field_name))


def _resource_limit_classification(expected: int) -> Callable[[Any], SecurityComparison]:
    def classify(value: Any) -> SecurityComparison:
        if type(value) is not int or value <= 0:
            return SecurityComparison.INVALID
        return SecurityComparison.STRONGER if value < expected else SecurityComparison.WEAKER

    return classify


def _collection_diagnostic(
    diagnostics: list[SecurityFieldDiagnostic],
    *,
    field_name: str,
    observed: Any,
    expected: list[str],
    rule: str,
    normalize: Callable[[list[str]], list[str]],
    none_is_empty: bool,
    classify: Callable[[list[str]], SecurityComparison],
    accepted_observed_forms: tuple[list[str], ...] | None = None,
) -> None:
    if observed is None and none_is_empty:
        values: list[str] | None = []
        observed_type = "null"
    elif isinstance(observed, list) and all(isinstance(value, str) for value in observed):
        values = normalize(observed)
        observed_type = "string_list"
    else:
        values = None
        observed_type = _diagnostic_type(observed)
    normalized_observed = [value.lower() for value in observed] if isinstance(observed, list) else None
    accepted = values == expected and (
        accepted_observed_forms is None or normalized_observed in accepted_observed_forms
    )
    if accepted:
        return
    diagnostics.append(
        SecurityFieldDiagnostic(
            field_name,
            expected,
            "string_list",
            _bounded_collection_observation(field_name, values),
            observed_type,
            rule,
            classify(values) if values is not None else SecurityComparison.INVALID,
        )
    )


def _bounded_scalar_observation(field_name: str, observed: Any, observed_type: str) -> DiagnosticValue:
    if observed_type in {"integer", "boolean"}:
        return observed
    if observed_type != "string":
        return None
    allowed = {
        "Config.User": bool(_NUMERIC_USER_PATTERN.fullmatch(observed)),
        "HostConfig.NetworkMode": observed in {"none", "bridge", "host", "default"},
        "HostConfig.RestartPolicy.Name": observed in {"no", "always", "unless-stopped", "on-failure"},
    }
    return observed if allowed.get(field_name, False) else f"sha256:{_fingerprint(observed)}"


def _bounded_collection_observation(field_name: str, values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    safe_values: list[str] = []
    for value in values:
        if field_name in {"HostConfig.CapDrop", "HostConfig.CapAdd"} and value == "ALL":
            safe_values.append(value)
        elif field_name == "HostConfig.SecurityOpt" and value == "no-new-privileges:true":
            safe_values.append(value)
        else:
            safe_values.append(f"sha256:{_fingerprint(value)}")
    if len(safe_values) <= _MAX_DIAGNOSTIC_TOKENS:
        return safe_values
    retained = safe_values[:_MAX_DIAGNOSTIC_TOKENS]
    retained.append(f"overflow:{len(safe_values) - _MAX_DIAGNOSTIC_TOKENS}:sha256:{_fingerprint(safe_values)}")
    return retained


def _diagnostic_type(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "string_list"
    return "invalid"


def _diagnostics_from_inspect(result: DockerResult) -> tuple[SecurityFieldDiagnostic, ...]:
    if result.exit_code != 0:
        return ()
    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ()
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return ()
    return _security_profile_diagnostics(items[0])


def _inspect_blocker(
    result: DockerResult, d: dict[str, Any], *, name: str, root: Path, require_running: bool = False
) -> str:
    if result.exit_code != 0:
        return "managed_copy_container_inspect_failed"
    try:
        items = json.loads(result.stdout)
        item = items[0] if isinstance(items, list) and len(items) == 1 else {}
    except json.JSONDecodeError:
        return "managed_copy_container_inspect_invalid"
    host = item.get("HostConfig", {})
    config = item.get("Config", {})
    state = item.get("State", {})
    if _text(item.get("Name")).lstrip("/") != name or _text(item.get("Image")).lower() != d["image_id"]:
        return "managed_copy_container_identity_mismatch"
    labels = config.get("Labels") or {}
    expected_labels = {
        "francis.proof_run_id": d["proof_run_id"],
        "francis.tenant_key": d["tenant_key"],
        "francis.copy_id": d["copy_id"],
        "francis.approval_id": d["approval_id"],
    }
    if any(labels.get(k) != v for k, v in expected_labels.items()):
        return "managed_copy_container_label_mismatch"
    if _security_profile_diagnostics(item):
        return "managed_copy_container_security_profile_mismatch"
    if config.get("Entrypoint") != ["python", RUNTIME_PROGRAM_CONTAINER_PATH] or config.get("Cmd") != _runtime_cmd(d):
        return "managed_copy_container_command_mismatch"
    tmpfs = host.get("Tmpfs") or {}
    if set(tmpfs) != {"/tmp"} or set(_text(tmpfs.get("/tmp")).split(",")) != {
        "rw",
        "noexec",
        "nodev",
        "nosuid",
        "size=1m",
    }:
        return "managed_copy_container_tmpfs_mismatch"
    mounts = item.get("Mounts") or []
    destinations = {m.get("Destination"): bool(m.get("RW")) for m in mounts}
    if destinations != {
        "/francis/tenant": False,
        "/francis/state": True,
    }:
        return "managed_copy_container_mount_set_mismatch"
    sources = {str(Path(_text(m.get("Source"))).resolve()).casefold() for m in mounts}
    allowed = {str((root / p).resolve()).casefold() for p in ("tenant", "state")}
    if sources != allowed or any("docker.sock" in source for source in sources):
        return "managed_copy_container_mount_source_mismatch"
    if require_running and state.get("Running") is not True:
        return "managed_copy_container_not_running"
    return ""


def _cleanup_exact(run: DockerRunner, container_id: str, *, name: str, receipts: Path, plan: dict[str, Any]) -> str:
    inspected = _inspect(run, container_id)
    identity_ok = False
    if inspected.exit_code == 0:
        try:
            item = json.loads(inspected.stdout)[0]
            identity_ok = _cleanup_identity_matches(
                item,
                container_id=container_id,
                name=name,
                descriptor=plan["descriptor"],
            )
        except (json.JSONDecodeError, IndexError, TypeError):
            identity_ok = False
    status = "identity_mismatch"
    if identity_ok:
        run([*_docker_prefix(), "container", "stop", "--timeout", "3", container_id], 10.0)
        removed = run([*_docker_prefix(), "container", "rm", container_id], 10.0)
        status = "removed" if removed.exit_code == 0 else "cleanup_required"
    receipt = _receipt(plan, "cleanup", {"container_id": container_id, "container_name": name, "status": status})
    try:
        _write_immutable(receipts / "cleanup.json", receipt)
    except (OSError, FileExistsError):
        return "cleanup_receipt_failed"
    return status


def _cleanup_identity_matches(
    item: dict[str, Any], *, container_id: str, name: str, descriptor: dict[str, Any]
) -> bool:
    raw_config = item.get("Config")
    config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
    raw_labels = config.get("Labels")
    labels: dict[str, Any] = raw_labels if isinstance(raw_labels, dict) else {}
    expected_labels = {
        "francis.proof_run_id": descriptor["proof_run_id"],
        "francis.tenant_key": descriptor["tenant_key"],
        "francis.copy_id": descriptor["copy_id"],
        "francis.approval_id": descriptor["approval_id"],
    }
    return bool(
        _text(item.get("Id")) == container_id
        and _text(item.get("Name")).lstrip("/") == name
        and _text(item.get("Image")) == descriptor["image_id"]
        and config.get("Entrypoint") == ["python", RUNTIME_PROGRAM_CONTAINER_PATH]
        and config.get("Cmd") == _runtime_cmd(descriptor)
        and all(labels.get(key) == value for key, value in expected_labels.items())
    )


def _container_runtime_pid(result: DockerResult) -> int:
    try:
        items = json.loads(result.stdout)
        value = items[0]["State"]["Pid"] if result.exit_code == 0 and len(items) == 1 else 0
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        return 0
    return value if type(value) is int and value > 0 else 0


def _runtime_records_blocker(
    records: dict[str, dict[str, Any]],
    d: dict[str, Any],
    *,
    operation_input: object,
    expected_pid: int = 0,
) -> str:
    handshake = records.get("handshake") or {}
    heartbeat = records.get("heartbeat") or {}
    operation = records.get("operation") or {}
    briefing = records.get("briefing") or {}
    common = {
        "copy_id": d["copy_id"],
        "tenant_key": d["tenant_key"],
        "pilot_run_id": d["proof_run_id"],
        "runtime_nonce_hash": _sha256_text(d["runtime_nonce"]),
    }
    if handshake.get("runtime_identity") != RUNTIME_IDENTITY or handshake.get("fixture_runtime") is not False:
        return "managed_copy_container_runtime_handshake_missing_or_invalid"
    if any(handshake.get(key) != value for key, value in common.items()):
        return "managed_copy_container_runtime_handshake_lineage_mismatch"
    if expected_pid and handshake.get("pid") != expected_pid:
        return "managed_copy_container_runtime_process_identity_mismatch"
    observed_at = heartbeat.get("observed_at_unix_ms")
    if (
        heartbeat.get("heartbeat_identity") != HEARTBEAT_IDENTITY
        or heartbeat.get("ready") is not True
        or heartbeat.get("operation_completed") is not True
        or type(heartbeat.get("sequence")) is not int
        or heartbeat["sequence"] <= 0
        or type(observed_at) is not int
        or not 0 <= int(time.time() * 1000) - observed_at <= 3_000
    ):
        return "managed_copy_container_runtime_heartbeat_missing_or_invalid"
    if any(heartbeat.get(key) != value for key, value in common.items()):
        return "managed_copy_container_runtime_heartbeat_lineage_mismatch"
    expected_briefing = build_work_briefing(operation_input)
    if briefing != expected_briefing or briefing.get("input_fingerprint") != d["operation_input_fingerprint"]:
        return "managed_copy_container_runtime_output_invalid"
    receipt_fingerprint = operation.get("receipt_fingerprint")
    if (
        operation.get("operation") != "tenant_work_briefing"
        or operation.get("status") != "completed"
        or operation.get("fixture_runtime") is not False
        or operation.get("input_fingerprint") != briefing.get("input_fingerprint")
        or operation.get("output_fingerprint") != briefing.get("output_fingerprint")
        or any(operation.get(key) != value for key, value in common.items())
        or not isinstance(receipt_fingerprint, str)
        or receipt_fingerprint
        != _fingerprint({key: value for key, value in operation.items() if key != "receipt_fingerprint"})
    ):
        return "managed_copy_container_runtime_operation_invalid"
    return ""


def _approval(approval_id: str) -> dict[str, Any]:
    return _read_json(data_dir() / "approvals" / "approved" / f"{approval_id}.json")


def _pilot_lease_context(lease_id: str) -> dict[str, str]:
    from francis.managed_copy_pilot_runtime import PILOT_RUNTIME_LEASES

    return PILOT_RUNTIME_LEASES.lease_context(lease_id)


def _approval_blocker(
    approval: dict[str, Any],
    *,
    actor: str,
    descriptor: dict[str, Any],
    descriptor_fingerprint: str,
    action_nonce: str,
    trace_id: str,
) -> str:
    if not approval:
        return "managed_copy_container_isolation_approval_missing"
    if set(approval) != _APPROVAL_FIELDS or approval.get("action") != CONTAINER_ISOLATION_ACTION:
        return "managed_copy_container_isolation_approval_schema_invalid"
    payload = approval.get("payload")
    if not isinstance(payload, dict) or set(payload) != _APPROVAL_PAYLOAD_FIELDS:
        return "managed_copy_container_isolation_approval_schema_invalid"
    if approval.get("status") != "approved" or approval.get("decision") != "approve":
        return "managed_copy_container_isolation_approval_not_approved"
    if payload.get("revoked") is not False:
        return "managed_copy_container_isolation_approval_revoked"
    if type(payload.get("expires_at_unix_ms")) is not int or payload["expires_at_unix_ms"] <= int(time.time() * 1000):
        return "managed_copy_container_isolation_approval_expired"
    expected = {
        "contract": CONTAINER_ISOLATION_CONTRACT,
        "action": CONTAINER_ISOLATION_ACTION,
        "request_actor": actor,
        "descriptor": descriptor,
        "descriptor_fingerprint": descriptor_fingerprint,
        "action_nonce": action_nonce,
        "trace_id": trace_id,
    }
    if any(payload.get(k) != v for k, v in expected.items()):
        return "managed_copy_container_isolation_approval_binding_mismatch"
    return ""


def _receipt(plan: dict[str, Any], event: str, fields: dict[str, Any]) -> dict[str, Any]:
    d = plan["descriptor"]
    base = {
        "kind": f"francis.stage18.managed_copies.container_isolation_{event}_receipt",
        "contract": CONTAINER_ISOLATION_CONTRACT,
        "receipt_id": f"mcir_{event}_{_fingerprint({'descriptor': plan['descriptor_fingerprint'], 'event': event})[:24]}",
        "event": event,
        "actor": plan["actor"],
        "approval_id": plan["approval_id"],
        "runtime_start_approval_id": d["runtime_start_approval_id"],
        "descriptor_fingerprint": plan["descriptor_fingerprint"],
        "tenant_key": d["tenant_key"],
        "copy_id": d["copy_id"],
        "proof_run_id": d["proof_run_id"],
        "lease_id": d["lease_id"],
        "trace_id": d["trace_id"],
        "recorded_at_unix_ms": int(time.time() * 1000),
    }
    base.update(fields)
    base["receipt_fingerprint"] = _fingerprint(base)
    return base


def _security_profile_diagnostic_receipt(
    plan: dict[str, Any], diagnostics: tuple[SecurityFieldDiagnostic, ...], *, recorded_at_unix_ms: int
) -> dict[str, Any]:
    mismatches = [
        {
            "field_name": diagnostic.field_name,
            "expected_value": diagnostic.expected_value,
            "expected_type": diagnostic.expected_type,
            "observed_normalized_value": diagnostic.observed_value,
            "observed_type": diagnostic.observed_type,
            "normalization_rule": diagnostic.normalization_rule,
            "classification": diagnostic.classification.value,
        }
        for diagnostic in diagnostics
    ]
    receipt = {
        "kind": "francis.stage18.managed_copies.container_security_profile_diagnostic_receipt",
        "contract": SECURITY_PROFILE_DIAGNOSTIC_CONTRACT,
        "proof_run_id": plan["descriptor"]["proof_run_id"],
        "predecessor_proof_run_id": DIAGNOSTIC_PREDECESSOR_PROOF_RUN_ID,
        "predecessor_failed_receipt_fingerprint": DIAGNOSTIC_PREDECESSOR_FAILED_RECEIPT_FINGERPRINT,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "recorded_at_unix_ms": recorded_at_unix_ms,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    return receipt


def _write_security_profile_diagnostic(
    receipts: Path, *, plan: dict[str, Any], inspected: DockerResult
) -> dict[str, Any]:
    diagnostics = _diagnostics_from_inspect(inspected)
    if not diagnostics:
        return {}
    receipt = _security_profile_diagnostic_receipt(
        plan,
        diagnostics,
        recorded_at_unix_ms=int(time.time() * 1000),
    )
    _write_immutable(receipts / "security-profile-diagnostic.json", receipt)
    return receipt


def _fail(plan: dict[str, Any], receipts: Path, blocker: str, result: DockerResult) -> dict[str, Any]:
    receipt = _receipt(plan, "failed", {"status": "failed", "blocker": blocker, "docker_exit_code": result.exit_code})
    _write_immutable(receipts / "failed.json", receipt)
    return {"ok": False, "status": "failed", "error": blocker, "receipt": receipt}


def _blocked(plan: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        **plan,
        "ok": False,
        "status": "blocked",
        "error": blocker,
        "blockers": [*plan.get("blockers", []), blocker],
    }


def _write_immutable(path: Path, value: dict[str, Any]) -> None:
    if _is_reparse(path.parent) or path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_text_immutable(path: Path, value: str) -> None:
    _write_bytes_immutable(path, value.encode("utf-8"))


def _write_bytes_immutable(path: Path, value: bytes) -> None:
    if _is_reparse(path.parent) or path.exists():
        raise FileExistsError(path)
    with path.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _container_id(value: str) -> str:
    candidate = value.strip().lower()
    return candidate if len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate) else ""


def _identifier(value: Any) -> str:
    text = _text(value)
    return text if 1 <= len(text) <= 128 and all(char in _IDENTIFIER_CHARS for char in text) else ""


def _digest(value: Any) -> str:
    text = _text(value).lower()
    return (
        text
        if text.startswith("sha256:") and len(text) == 71 and all(c in "0123456789abcdef" for c in text[7:])
        else ""
    )


def _hash(value: Any) -> str:
    text = _text(value).lower()
    return text if len(text) == 64 and all(c in "0123456789abcdef" for c in text) else ""


def _exact_int(value: Any, *, minimum: int, maximum: int) -> int:
    return value if type(value) is int and minimum <= value <= maximum else 0


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
