from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from francis.governance.pilot_scope_lease import PilotLeaseBinding
from francis.kernel.paths import data_dir
from francis.managed_copy_pilot_runtime import (
    PILOT_RUNTIME_SCOPE,
    PILOT_RUNTIME_START_ACTION,
    PILOT_RUNTIME_START_ROUTE,
    _startup_receipt,
    _state_dir,
    stop_pilot_runtime,
)
from francis.managed_copy_rogue_recovery_plan import managed_copy_rogue_recovery_plan

ROGUE_RUNTIME_HALT_SCOPE = "managed_copies.rogue_recovery.runtime_halt.execute"
ROGUE_RUNTIME_HALT_ACTION = "managed_copies.rogue_recovery.runtime_halt"
ROGUE_RUNTIME_HALT_ROUTE = "/managed-copies/rogue-recovery-runtime-halt"
ROGUE_RUNTIME_HALT_CONTRACT = "stage18_managed_copy_rogue_runtime_halt_v1"
ROGUE_RUNTIME_HALT_KIND = "francis.stage18.managed_copies.rogue_runtime_halt_receipt"
ROGUE_RUNTIME_HALT_ATTEMPT_KIND = "francis.stage18.managed_copies.rogue_runtime_halt_attempt"

_PAYLOAD_FIELDS = frozenset(
    {
        "request_actor",
        "pilot_lease_id",
        "startup_receipt_id",
        "approval_id",
        "copy_id",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "integrity_evidence_receipt_id",
        "integrity_evidence_fingerprint",
        "rogue_detection_assessment_receipt_id",
        "disposition_receipt_id",
        "disposition_fingerprint",
        "replacement_source",
        "recovery_intent_fingerprint",
        "recovery_plan_fingerprint",
        "confirm_halt",
        "trace_id",
    }
)
_APPROVAL_FIELDS = frozenset({"approval_id", "status", "decision", "action", "payload", "approval_fingerprint"})
_APPROVAL_PAYLOAD_FIELDS = frozenset(
    {"contract", "descriptor", "descriptor_fingerprint", "expires_at_unix_ms", "revoked"}
)
_CLEANUP_FIELDS = frozenset(
    {
        "kind",
        "receipt_id",
        "startup_receipt_id",
        "pilot_run_id",
        "status",
        "pid",
        "process_creation_token",
        "fixture_runtime",
        "recorded_at_unix_ms",
        "receipt_fingerprint",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "actor",
        "copy_id",
        "pilot_run_id",
        "pilot_lease_id",
        "package_id",
        "package_fingerprint",
        "operator_decision_fingerprint",
        "startup_receipt_id",
        "startup_receipt_fingerprint",
        "provisioning_receipt_id",
        "isolation_verification_receipt_id",
        "integrity_evidence_receipt_id",
        "integrity_evidence_fingerprint",
        "rogue_detection_assessment_receipt_id",
        "disposition_receipt_id",
        "disposition_fingerprint",
        "recovery_plan_fingerprint",
        "approval_id",
        "approval_fingerprint",
        "approval_file_identity_fingerprint",
        "descriptor_fingerprint",
        "lease_authority_fingerprint",
        "halt_attempt_fingerprint",
        "cleanup_receipt_fingerprint",
        "trace_id",
        "recorded_at_unix_ms",
        "receipt_fingerprint",
    }
)
_ATTEMPT_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "approval_fingerprint",
        "approval_file_identity_fingerprint",
        "descriptor_fingerprint",
        "lease_authority_fingerprint",
        "startup_receipt_id",
        "startup_receipt_fingerprint",
        "recorded_at_unix_ms",
        "attempt_fingerprint",
    }
)


@dataclass
class _ApprovalFileIdentity:
    path: Path
    stream: BinaryIO
    stat_result: os.stat_result
    content_fingerprint: str

    @classmethod
    def acquire(cls, path: Path) -> _ApprovalFileIdentity | None:
        try:
            stream = path.open("rb")
            stat_result = os.fstat(stream.fileno())
            content = stream.read()
            path_stat = os.stat(path, follow_symlinks=False)
        except OSError:
            try:
                stream.close()
            except (OSError, UnboundLocalError):
                pass
            return None
        if not os.path.samestat(stat_result, path_stat) or path.is_symlink():
            stream.close()
            return None
        return cls(path, stream, stat_result, hashlib.sha256(content).hexdigest())

    def verify(self) -> bool:
        try:
            held_stat = os.fstat(self.stream.fileno())
            path_stat = os.stat(self.path, follow_symlinks=False)
            self.stream.seek(0)
            content_fingerprint = hashlib.sha256(self.stream.read()).hexdigest()
        except OSError:
            return False
        return bool(
            os.path.samestat(self.stat_result, held_stat)
            and os.path.samestat(held_stat, path_stat)
            and not self.path.is_symlink()
            and content_fingerprint == self.content_fingerprint
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            {
                "device": int(self.stat_result.st_dev),
                "inode": int(self.stat_result.st_ino),
                "content_fingerprint": self.content_fingerprint,
            }
        )

    def close(self) -> None:
        self.stream.close()


def execute_rogue_runtime_halt(
    payload: dict[str, Any],
    *,
    actor: str,
    authority: dict[str, Any],
) -> dict[str, Any]:
    if set(payload) != _PAYLOAD_FIELDS:
        return _blocked("managed_copy_rogue_runtime_halt_payload_schema_invalid")
    if _identifier(payload.get("request_actor")) != _identifier(actor) or payload.get("confirm_halt") is not True:
        return _blocked("managed_copy_rogue_runtime_halt_confirmation_invalid")
    if not _authority_matches(payload, actor=actor, authority=authority):
        return _blocked("managed_copy_rogue_runtime_halt_lease_authority_invalid")

    plan = managed_copy_rogue_recovery_plan(_plan_payload(payload), actor=actor)
    if plan.get("ok") is not True or plan.get("plan_fingerprint") != payload.get("recovery_plan_fingerprint"):
        return _blocked("managed_copy_rogue_runtime_halt_recovery_plan_mismatch")

    startup = _startup_receipt(_identifier(payload.get("startup_receipt_id")))
    if not startup:
        return _blocked("managed_copy_rogue_runtime_halt_startup_receipt_invalid")
    if not _startup_matches(payload, startup, actor=actor) or startup.get("pilot_run_id") != authority.get(
        "pilot_run_id"
    ):
        return _blocked("managed_copy_rogue_runtime_halt_startup_lineage_mismatch")

    descriptor = _descriptor(payload, startup=startup, actor=actor, authority=authority)
    descriptor_fingerprint = _fingerprint(descriptor)
    approval_path = data_dir() / "approvals" / "approved" / f"{_identifier(payload.get('approval_id'))}.json"
    approval = _read_json(approval_path)
    blocker = _approval_blocker(
        approval,
        approval_id=_identifier(payload.get("approval_id")),
        descriptor=descriptor,
        descriptor_fingerprint=descriptor_fingerprint,
    )
    if blocker:
        return _blocked(blocker)
    approval_identity = _ApprovalFileIdentity.acquire(approval_path)
    if approval_identity is None or not approval_identity.verify():
        return _blocked("managed_copy_rogue_runtime_halt_approval_identity_invalid")

    receipt_id = f"mcrrh_{_fingerprint({'approval': approval['approval_fingerprint'], 'descriptor': descriptor_fingerprint})[:24]}"
    receipt_path = rogue_runtime_halt_receipt_directory() / f"{receipt_id}.json"
    try:
        if not approval_identity.verify():
            return _blocked("managed_copy_rogue_runtime_halt_approval_changed_under_authority")
        existing = _read_json(receipt_path)
        if existing:
            verification = verify_rogue_runtime_halt_receipt(
                receipt_id,
                existing.get("receipt_fingerprint"),
                expected=payload,
            )
            return (
                {"ok": True, "status": "halted", "receipt": existing, "idempotent_replay": True}
                if verification.get("valid") is True
                and existing.get("descriptor_fingerprint") == descriptor_fingerprint
                else _blocked("managed_copy_rogue_runtime_halt_conflicting_replay")
            )
        return _perform_owned_halt(
            payload,
            actor=actor,
            authority=authority,
            startup=startup,
            approval=approval,
            approval_identity=approval_identity,
            descriptor_fingerprint=descriptor_fingerprint,
            receipt_id=receipt_id,
            receipt_path=receipt_path,
        )
    finally:
        approval_identity.close()


def _perform_owned_halt(
    payload: dict[str, Any],
    *,
    actor: str,
    authority: dict[str, Any],
    startup: dict[str, Any],
    approval: dict[str, Any],
    approval_identity: _ApprovalFileIdentity,
    descriptor_fingerprint: str,
    receipt_id: str,
    receipt_path: Path,
) -> dict[str, Any]:
    attempt_path = rogue_runtime_halt_receipt_directory() / f"{receipt_id}.attempt.json"
    attempt = {
        "kind": ROGUE_RUNTIME_HALT_ATTEMPT_KIND,
        "contract": ROGUE_RUNTIME_HALT_CONTRACT,
        "receipt_id": receipt_id,
        "approval_fingerprint": approval["approval_fingerprint"],
        "approval_file_identity_fingerprint": approval_identity.fingerprint,
        "descriptor_fingerprint": descriptor_fingerprint,
        "lease_authority_fingerprint": authority["lease_authority_fingerprint"],
        "startup_receipt_id": startup["receipt_id"],
        "startup_receipt_fingerprint": startup["startup_fingerprint"],
        "recorded_at_unix_ms": int(time.time() * 1000),
        "attempt_fingerprint": "",
    }
    attempt["attempt_fingerprint"] = _fingerprint_without(attempt, "attempt_fingerprint")
    existing_attempt = _read_json(attempt_path)
    if existing_attempt and (
        not _valid_halt_attempt(existing_attempt) or _attempt_binding(existing_attempt) != _attempt_binding(attempt)
    ):
        return _blocked("managed_copy_rogue_runtime_halt_conflicting_attempt")

    state_directory = _state_dir(startup)
    prior_cleanup = _read_json(state_directory / "cleanup.json") if state_directory else {}
    if _valid_cleanup_receipt(prior_cleanup, startup=startup) and not existing_attempt:
        return _blocked("managed_copy_rogue_runtime_halt_runtime_already_stopped_without_halt_attempt")
    if not existing_attempt:
        try:
            _write_immutable(attempt_path, attempt)
        except OSError:
            return _blocked("managed_copy_rogue_runtime_halt_attempt_write_failed")

    stopped = (
        {"ok": True, "status": prior_cleanup["status"], "receipt": prior_cleanup}
        if _valid_cleanup_receipt(prior_cleanup, startup=startup)
        else stop_pilot_runtime(
            {
                "request_actor": actor,
                "pilot_lease_id": payload["pilot_lease_id"],
                "startup_receipt_id": payload["startup_receipt_id"],
                "confirm_stop": True,
            },
            actor=actor,
            seal_lease=False,
        )
    )
    cleanup = stopped.get("receipt")
    if (
        stopped.get("ok") is not True
        or not isinstance(cleanup, dict)
        or not _valid_cleanup_receipt(cleanup, startup=startup)
    ):
        return _blocked(_text(stopped.get("error")) or "managed_copy_rogue_runtime_halt_owned_stop_failed")
    if not approval_identity.verify():
        return _blocked("managed_copy_rogue_runtime_halt_approval_changed_under_authority")

    receipt = {
        "kind": ROGUE_RUNTIME_HALT_KIND,
        "contract": ROGUE_RUNTIME_HALT_CONTRACT,
        "receipt_id": receipt_id,
        "status": "halted",
        "actor": actor,
        "copy_id": startup["copy_id"],
        "pilot_run_id": startup["pilot_run_id"],
        "pilot_lease_id": startup["pilot_lease_id"],
        "package_id": authority["package_id"],
        "package_fingerprint": authority["package_fingerprint"],
        "operator_decision_fingerprint": authority["operator_decision_fingerprint"],
        "startup_receipt_id": startup["receipt_id"],
        "startup_receipt_fingerprint": startup["startup_fingerprint"],
        "provisioning_receipt_id": startup["provisioning_receipt_id"],
        "isolation_verification_receipt_id": startup["isolation_verification_receipt_id"],
        "integrity_evidence_receipt_id": payload["integrity_evidence_receipt_id"],
        "integrity_evidence_fingerprint": payload["integrity_evidence_fingerprint"],
        "rogue_detection_assessment_receipt_id": payload["rogue_detection_assessment_receipt_id"],
        "disposition_receipt_id": payload["disposition_receipt_id"],
        "disposition_fingerprint": payload["disposition_fingerprint"],
        "recovery_plan_fingerprint": payload["recovery_plan_fingerprint"],
        "approval_id": approval["approval_id"],
        "approval_fingerprint": approval["approval_fingerprint"],
        "approval_file_identity_fingerprint": approval_identity.fingerprint,
        "descriptor_fingerprint": descriptor_fingerprint,
        "lease_authority_fingerprint": authority["lease_authority_fingerprint"],
        "halt_attempt_fingerprint": (
            existing_attempt["attempt_fingerprint"] if existing_attempt else attempt["attempt_fingerprint"]
        ),
        "cleanup_receipt_fingerprint": _hash(cleanup),
        "trace_id": payload["trace_id"],
        "recorded_at_unix_ms": int(time.time() * 1000),
        "receipt_fingerprint": "",
    }
    receipt["receipt_fingerprint"] = _fingerprint_without(receipt, "receipt_fingerprint")
    try:
        _write_immutable(receipt_path, receipt)
    except OSError:
        return _blocked("managed_copy_rogue_runtime_halt_receipt_write_failed")
    return {"ok": True, "status": "halted", "receipt": receipt, "idempotent_replay": False}


def verify_rogue_runtime_halt_receipt(
    receipt_id: object,
    receipt_fingerprint: object,
    *,
    expected: dict[str, Any],
) -> dict[str, Any]:
    safe_id = _identifier(receipt_id)
    if not safe_id or not _sha(receipt_fingerprint):
        return _blocked("stage18_rogue_recovery_runtime_halt_receipt_binding_invalid")
    receipt = _read_json(rogue_runtime_halt_receipt_directory() / f"{safe_id}.json")
    if not valid_rogue_runtime_halt_receipt(receipt) or receipt.get("receipt_fingerprint") != receipt_fingerprint:
        return _blocked("stage18_rogue_recovery_runtime_halt_receipt_invalid")
    startup = _startup_receipt(_identifier(receipt.get("startup_receipt_id")))
    state_directory = _state_dir(startup) if startup else None
    cleanup = _read_json(state_directory / "cleanup.json") if state_directory else {}
    attempt = _read_json(rogue_runtime_halt_receipt_directory() / f"{safe_id}.attempt.json")
    if (
        not startup
        or startup.get("startup_fingerprint") != receipt.get("startup_receipt_fingerprint")
        or not _valid_halt_attempt(attempt)
        or attempt.get("attempt_fingerprint") != receipt.get("halt_attempt_fingerprint")
        or attempt.get("receipt_id") != receipt.get("receipt_id")
        or attempt.get("approval_fingerprint") != receipt.get("approval_fingerprint")
        or attempt.get("approval_file_identity_fingerprint") != receipt.get("approval_file_identity_fingerprint")
        or attempt.get("descriptor_fingerprint") != receipt.get("descriptor_fingerprint")
        or attempt.get("lease_authority_fingerprint") != receipt.get("lease_authority_fingerprint")
        or attempt.get("startup_receipt_id") != receipt.get("startup_receipt_id")
        or attempt.get("startup_receipt_fingerprint") != receipt.get("startup_receipt_fingerprint")
        or not _valid_cleanup_receipt(cleanup, startup=startup)
        or _hash(cleanup) != receipt.get("cleanup_receipt_fingerprint")
    ):
        return _blocked("stage18_rogue_recovery_runtime_halt_cleanup_lineage_invalid")
    descriptor = _descriptor(
        receipt,
        startup=startup,
        actor=_identifier(receipt.get("actor")),
        authority=receipt,
    )
    descriptor_fingerprint = _fingerprint(descriptor)
    approval = _read_json(data_dir() / "approvals" / "approved" / f"{_identifier(receipt.get('approval_id'))}.json")
    approval_identity = _ApprovalFileIdentity.acquire(
        data_dir() / "approvals" / "approved" / f"{_identifier(receipt.get('approval_id'))}.json"
    )
    if (
        descriptor_fingerprint != receipt.get("descriptor_fingerprint")
        or approval.get("approval_fingerprint") != receipt.get("approval_fingerprint")
        or approval_identity is None
        or approval_identity.fingerprint != receipt.get("approval_file_identity_fingerprint")
        or _approval_blocker(
            approval,
            approval_id=_identifier(receipt.get("approval_id")),
            descriptor=descriptor,
            descriptor_fingerprint=descriptor_fingerprint,
            require_current=False,
        )
    ):
        if approval_identity is not None:
            approval_identity.close()
        return _blocked("stage18_rogue_recovery_runtime_halt_approval_lineage_invalid")
    approval_identity.close()
    bindings = {
        "copy_id": expected.get("copy_id"),
        "provisioning_receipt_id": expected.get("provisioning_receipt_id"),
        "isolation_verification_receipt_id": expected.get("isolation_verification_receipt_id"),
        "integrity_evidence_receipt_id": expected.get("integrity_evidence_receipt_id"),
        "integrity_evidence_fingerprint": expected.get("integrity_evidence_fingerprint"),
        "rogue_detection_assessment_receipt_id": expected.get("rogue_detection_assessment_receipt_id"),
        "disposition_receipt_id": expected.get("disposition_receipt_id"),
        "disposition_fingerprint": expected.get("disposition_fingerprint"),
        "recovery_plan_fingerprint": expected.get("recovery_plan_fingerprint"),
    }
    if any(receipt.get(key) != value for key, value in bindings.items()):
        return _blocked("stage18_rogue_recovery_runtime_halt_lineage_invalid")
    return {"valid": True, "blocker": "", "receipt": receipt}


def valid_rogue_runtime_halt_receipt(receipt: dict[str, Any]) -> bool:
    return bool(
        set(receipt) == _RECEIPT_FIELDS
        and receipt.get("kind") == ROGUE_RUNTIME_HALT_KIND
        and receipt.get("contract") == ROGUE_RUNTIME_HALT_CONTRACT
        and receipt.get("status") == "halted"
        and all(
            _identifier(receipt.get(field))
            for field in (
                "receipt_id",
                "actor",
                "copy_id",
                "pilot_run_id",
                "pilot_lease_id",
                "package_id",
                "startup_receipt_id",
                "provisioning_receipt_id",
                "isolation_verification_receipt_id",
                "integrity_evidence_receipt_id",
                "rogue_detection_assessment_receipt_id",
                "disposition_receipt_id",
                "approval_id",
                "trace_id",
            )
        )
        and all(
            _sha(receipt.get(field))
            for field in (
                "startup_receipt_fingerprint",
                "package_fingerprint",
                "operator_decision_fingerprint",
                "integrity_evidence_fingerprint",
                "disposition_fingerprint",
                "recovery_plan_fingerprint",
                "approval_fingerprint",
                "approval_file_identity_fingerprint",
                "descriptor_fingerprint",
                "lease_authority_fingerprint",
                "halt_attempt_fingerprint",
                "cleanup_receipt_fingerprint",
                "receipt_fingerprint",
            )
        )
        and type(receipt.get("recorded_at_unix_ms")) is int
        and receipt["recorded_at_unix_ms"] > 0
        and receipt["receipt_fingerprint"] == _fingerprint_without(receipt, "receipt_fingerprint")
    )


def rogue_runtime_halt_receipt_directory() -> Path:
    return data_dir() / "logs" / "managed_copies" / "rogue_runtime_halts"


def rogue_runtime_halt_lease_bindings() -> tuple[PilotLeaseBinding, ...]:
    return (
        PilotLeaseBinding(
            PILOT_RUNTIME_SCOPE,
            PILOT_RUNTIME_START_ROUTE,
            "POST",
            PILOT_RUNTIME_START_ACTION,
        ),
        PilotLeaseBinding(
            ROGUE_RUNTIME_HALT_SCOPE,
            ROGUE_RUNTIME_HALT_ROUTE,
            "POST",
            ROGUE_RUNTIME_HALT_ACTION,
        ),
    )


def _descriptor(
    payload: dict[str, Any],
    *,
    startup: dict[str, Any],
    actor: str,
    authority: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract": ROGUE_RUNTIME_HALT_CONTRACT,
        "action": ROGUE_RUNTIME_HALT_ACTION,
        "actor": actor,
        "copy_id": startup["copy_id"],
        "pilot_run_id": startup["pilot_run_id"],
        "pilot_lease_id": startup["pilot_lease_id"],
        "package_id": authority["package_id"],
        "package_fingerprint": authority["package_fingerprint"],
        "operator_decision_fingerprint": authority["operator_decision_fingerprint"],
        "startup_receipt_id": startup["receipt_id"],
        "startup_receipt_fingerprint": startup["startup_fingerprint"],
        "runtime_identity_fingerprint": _fingerprint(
            {
                "pid": startup["pid"],
                "process_creation_token": startup["process_creation_token"],
                "runtime_identity": startup["runtime_identity"],
            }
        ),
        "provisioning_receipt_id": startup["provisioning_receipt_id"],
        "isolation_verification_receipt_id": startup["isolation_verification_receipt_id"],
        "integrity_evidence_receipt_id": payload["integrity_evidence_receipt_id"],
        "integrity_evidence_fingerprint": payload["integrity_evidence_fingerprint"],
        "rogue_detection_assessment_receipt_id": payload["rogue_detection_assessment_receipt_id"],
        "disposition_receipt_id": payload["disposition_receipt_id"],
        "disposition_fingerprint": payload["disposition_fingerprint"],
        "recovery_plan_fingerprint": payload["recovery_plan_fingerprint"],
        "trace_id": payload["trace_id"],
    }


def _plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_actor": payload["request_actor"],
        "copy_id": payload["copy_id"],
        "provisioning_receipt_id": payload["provisioning_receipt_id"],
        "isolation_verification_receipt_id": payload["isolation_verification_receipt_id"],
        "integrity_evidence_receipt_id": payload["integrity_evidence_receipt_id"],
        "rogue_detection_assessment_receipt_id": payload["rogue_detection_assessment_receipt_id"],
        "disposition_receipt_id": payload["disposition_receipt_id"],
        "replacement_source": payload["replacement_source"],
        "dry_run": True,
        "recovery_intent_fingerprint": payload["recovery_intent_fingerprint"],
    }


def _startup_matches(payload: dict[str, Any], startup: dict[str, Any], *, actor: str) -> bool:
    return bool(
        startup.get("actor") == actor
        and startup.get("receipt_id") == payload.get("startup_receipt_id")
        and startup.get("copy_id") == payload.get("copy_id")
        and startup.get("pilot_lease_id") == payload.get("pilot_lease_id")
        and startup.get("provisioning_receipt_id") == payload.get("provisioning_receipt_id")
        and startup.get("isolation_verification_receipt_id") == payload.get("isolation_verification_receipt_id")
    )


def _authority_matches(
    payload: dict[str, Any],
    *,
    actor: str,
    authority: dict[str, Any],
) -> bool:
    return bool(
        authority.get("valid") is True
        and authority.get("actor_id") == actor
        and authority.get("lease_id") == payload.get("pilot_lease_id")
        and _identifier(authority.get("pilot_run_id"))
        and _identifier(authority.get("package_id"))
        and _sha(authority.get("package_fingerprint"))
        and _sha(authority.get("operator_decision_fingerprint"))
        and _sha(authority.get("lease_authority_fingerprint"))
        and authority.get("operation_consumed_binding_count") == 2
    )


def _approval_blocker(
    approval: dict[str, Any],
    *,
    approval_id: str,
    descriptor: dict[str, Any],
    descriptor_fingerprint: str,
    require_current: bool = True,
) -> str:
    payload = approval.get("payload")
    if (
        set(approval) != _APPROVAL_FIELDS
        or not isinstance(payload, dict)
        or set(payload) != _APPROVAL_PAYLOAD_FIELDS
        or approval.get("approval_id") != approval_id
        or approval.get("status") != "approved"
        or approval.get("decision") not in {"approve", "approved"}
        or approval.get("action") != ROGUE_RUNTIME_HALT_ACTION
        or approval.get("approval_fingerprint") != _fingerprint_without(approval, "approval_fingerprint")
        or payload.get("contract") != ROGUE_RUNTIME_HALT_CONTRACT
        or payload.get("descriptor") != descriptor
        or payload.get("descriptor_fingerprint") != descriptor_fingerprint
        or payload.get("revoked") is not False
    ):
        return "managed_copy_rogue_runtime_halt_approval_binding_mismatch"
    expires = payload.get("expires_at_unix_ms")
    if type(expires) is not int or expires <= 0:
        return "managed_copy_rogue_runtime_halt_approval_expired"
    if require_current and expires <= int(time.time() * 1000):
        return "managed_copy_rogue_runtime_halt_approval_expired"
    return ""


def _valid_cleanup_receipt(cleanup: dict[str, Any], *, startup: dict[str, Any]) -> bool:
    return bool(
        set(cleanup) == _CLEANUP_FIELDS
        and cleanup.get("kind") == "francis.stage18.managed_copies.pilot_runtime_cleanup_receipt"
        and cleanup.get("startup_receipt_id") == startup.get("receipt_id")
        and cleanup.get("pilot_run_id") == startup.get("pilot_run_id")
        and cleanup.get("status") in {"stopped", "already_exited"}
        and cleanup.get("pid") == startup.get("pid")
        and cleanup.get("process_creation_token") == startup.get("process_creation_token")
        and cleanup.get("fixture_runtime") is False
        and type(cleanup.get("recorded_at_unix_ms")) is int
        and cleanup["recorded_at_unix_ms"] > 0
        and _sha(cleanup.get("receipt_fingerprint"))
        and cleanup["receipt_fingerprint"] == _fingerprint_without(cleanup, "receipt_fingerprint")
    )


def _valid_halt_attempt(attempt: dict[str, Any]) -> bool:
    return bool(
        set(attempt) == _ATTEMPT_FIELDS
        and attempt.get("kind") == ROGUE_RUNTIME_HALT_ATTEMPT_KIND
        and attempt.get("contract") == ROGUE_RUNTIME_HALT_CONTRACT
        and _identifier(attempt.get("receipt_id"))
        and _identifier(attempt.get("startup_receipt_id"))
        and all(
            _sha(attempt.get(field))
            for field in (
                "approval_fingerprint",
                "approval_file_identity_fingerprint",
                "descriptor_fingerprint",
                "lease_authority_fingerprint",
                "startup_receipt_fingerprint",
                "attempt_fingerprint",
            )
        )
        and type(attempt.get("recorded_at_unix_ms")) is int
        and attempt["recorded_at_unix_ms"] > 0
        and attempt["attempt_fingerprint"] == _fingerprint_without(attempt, "attempt_fingerprint")
    )


def _attempt_binding(attempt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in attempt.items() if key not in {"recorded_at_unix_ms", "attempt_fingerprint"}}


def _write_immutable(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _fingerprint_without(value: dict[str, Any], field: str) -> str:
    return _fingerprint({key: item for key, item in value.items() if key != field})


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _hash(value: Any) -> str:
    return _fingerprint(value)


def _identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    safe = value.strip()
    return (
        safe if 1 <= len(safe) <= 160 and all(character.isalnum() or character in "._:-" for character in safe) else ""
    )


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _blocked(error: str) -> dict[str, Any]:
    return {"ok": False, "status": "blocked", "error": error}
