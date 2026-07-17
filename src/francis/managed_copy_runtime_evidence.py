from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

RUNTIME_EVIDENCE_CONTRACT = "stage18_managed_copy_runtime_evidence_v1"
RUNTIME_EVIDENCE_RECEIPT_KIND = "francis.stage18.managed_copies.runtime_evidence_receipt"
COPY_CREATION_REQUIREMENT = "copy_creation_runtime_proof"
COPY_CREATION_PROOF_KIND = "managed_copy_creation_runtime_receipt"
COPY_CREATION_SOURCE_MISSING = "stage18_copy_creation_runtime_startup_receipt_missing"
TENANT_ISOLATION_REQUIREMENT = "tenant_isolation_runtime_proof"
TENANT_ISOLATION_PROOF_KIND = "tenant_isolation_runtime_receipt"
# Compatibility alias for older callers; the producer now exists but no source receipt is present by default.
SOURCE_NOT_IMPLEMENTED = COPY_CREATION_SOURCE_MISSING
KNOWN_REQUIREMENTS = frozenset(
    {
        COPY_CREATION_REQUIREMENT,
        TENANT_ISOLATION_REQUIREMENT,
        "safe_delta_runtime_proof",
        "rogue_recovery_runtime_proof",
        "sla_runtime_proof",
        "role_authority_runtime_proof",
        "decommission_runtime_proof",
    }
)
EXPECTED_PAYLOAD_FIELDS = frozenset(
    {
        "request_actor",
        "requirement_id",
        "proof_kind",
        "source_receipt_id",
        "source_receipt_fingerprint",
        "trace_id",
        "dry_run",
        "record_fingerprint",
        "confirm_runtime_evidence",
    }
)
RECEIPT_FIELDS = frozenset(
    {
        "kind",
        "contract",
        "receipt_id",
        "status",
        "actor",
        "requirement_id",
        "proof_kind",
        "trace_id",
        "source_receipt_id",
        "source_receipt_fingerprint",
        "source_lineage_hash",
        "current_state_hash",
        "evidence_class",
        "record_fingerprint",
        "recorded_at_unix_ms",
        "governance",
    }
)
GOVERNANCE_FIELDS = frozenset(
    {
        "runtime_evidence_receipt",
        "trace_linked",
        "redacted",
        "contains_raw_private_data",
        "writes_tenant_state",
        "writes_registry",
        "writes_memory",
        "runs_tools",
        "runs_shell",
        "runs_git",
        "launches_browser",
        "captures_screen",
        "external_action",
        "grants_execution_authority",
        "grants_mutation_authority",
        "marks_stage_closed",
    }
)
_RECORD_LOCK = threading.Lock()
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")

SourceVerifier = Callable[[str, str], dict[str, Any]]


def receipt_directory() -> Path:
    return data_dir() / "logs" / "managed_copies" / "runtime_evidence"


def verify_copy_creation_runtime_source(
    source_receipt_id: str,
    source_receipt_fingerprint: str,
) -> dict[str, Any]:
    """Validate independently loaded managed-copy startup evidence."""
    from francis.managed_copy_runtime_start import verify_runtime_startup_source

    return verify_runtime_startup_source(source_receipt_id, source_receipt_fingerprint)


def verify_tenant_isolation_runtime_source(source_receipt_id: str, source_receipt_fingerprint: str) -> dict[str, Any]:
    from francis.managed_copy_tenant_isolation_evidence import verify_tenant_isolation_runtime_source as verify

    return verify(source_receipt_id, source_receipt_fingerprint)


def _source_verifier(requirement_id: str) -> SourceVerifier | None:
    return {
        COPY_CREATION_REQUIREMENT: verify_copy_creation_runtime_source,
        TENANT_ISOLATION_REQUIREMENT: verify_tenant_isolation_runtime_source,
    }.get(requirement_id)


def _proof_kind(requirement_id: str) -> str:
    return {
        COPY_CREATION_REQUIREMENT: COPY_CREATION_PROOF_KIND,
        TENANT_ISOLATION_REQUIREMENT: TENANT_ISOLATION_PROOF_KIND,
    }.get(requirement_id, "")


def plan_runtime_evidence(
    payload: dict[str, Any],
    *,
    actor: str,
    stage17_closed: bool,
    source_verifier: SourceVerifier | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if set(payload) != EXPECTED_PAYLOAD_FIELDS:
        blockers.append("stage18_runtime_evidence_payload_schema_invalid")

    requirement_id = _identifier(payload.get("requirement_id"))
    proof_kind = _identifier(payload.get("proof_kind"))
    source_receipt_id = _identifier(payload.get("source_receipt_id"))
    source_receipt_fingerprint = _exact_hash(payload.get("source_receipt_fingerprint"))
    trace_id = _identifier(payload.get("trace_id"))
    payload_actor = _identifier(payload.get("request_actor"))
    safe_actor = _redacted_text(actor) if _identifier(actor) else ""

    if not stage17_closed:
        blockers.append("stage17_prerequisite_not_closed")
    if requirement_id not in KNOWN_REQUIREMENTS:
        blockers.append("stage18_runtime_evidence_requirement_unknown")
    elif not _source_verifier(requirement_id):
        blockers.append("stage18_runtime_evidence_requirement_not_supported")
    if _proof_kind(requirement_id) and proof_kind != _proof_kind(requirement_id):
        blockers.append("stage18_runtime_evidence_proof_kind_mismatch")
    if (
        not safe_actor
        or payload_actor != safe_actor
        or not source_receipt_id
        or not source_receipt_fingerprint
        or not trace_id
    ):
        blockers.append("stage18_runtime_evidence_required_binding_missing")
    if type(payload.get("dry_run")) is not bool:
        blockers.append("stage18_runtime_evidence_dry_run_invalid")
    if type(payload.get("confirm_runtime_evidence")) is not bool:
        blockers.append("stage18_runtime_evidence_confirmation_invalid")
    if payload.get("dry_run") is True:
        if payload.get("record_fingerprint") != "" or payload.get("confirm_runtime_evidence") is not False:
            blockers.append("stage18_runtime_evidence_dry_run_fields_invalid")
    elif payload.get("dry_run") is False and not _exact_hash(payload.get("record_fingerprint")):
        blockers.append("stage18_runtime_evidence_record_fingerprint_invalid")

    source = _blocked_source("stage18_runtime_evidence_source_not_checked")
    if not blockers:
        verifier = source_verifier or _source_verifier(requirement_id)
        assert verifier is not None
        source = verifier(source_receipt_id, source_receipt_fingerprint)
        if not _valid_source_result(source):
            blockers.append(_exact_text(source.get("blocker")) or "stage18_runtime_evidence_source_invalid")

    binding = {
        "contract": RUNTIME_EVIDENCE_CONTRACT,
        "actor": safe_actor,
        "requirement_id": requirement_id,
        "proof_kind": proof_kind,
        "trace_id": trace_id,
        "source_receipt_id": source_receipt_id,
        "source_receipt_fingerprint": source_receipt_fingerprint,
        "source_lineage_hash": _exact_hash(source.get("source_lineage_hash")),
        "current_state_hash": _exact_hash(source.get("current_state_hash")),
        "evidence_class": _exact_text(source.get("evidence_class")),
    }
    fingerprint = _fingerprint(binding) if not blockers else ""
    return {
        "ok": not blockers,
        "status": "record_ready" if not blockers else "blocked",
        "error": blockers[0] if blockers else "",
        "blockers": blockers,
        **binding,
        "record_fingerprint": fingerprint,
        "receipt_ready": False,
        "writes_receipt": False,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage_closed": False,
    }


def record_runtime_evidence(
    payload: dict[str, Any],
    *,
    actor: str,
    stage17_closed: bool,
    source_verifier: SourceVerifier | None = None,
) -> dict[str, Any]:
    requirement_id = _identifier(payload.get("requirement_id"))
    verifier = source_verifier or _source_verifier(requirement_id)
    plan = plan_runtime_evidence(
        payload,
        actor=actor,
        stage17_closed=stage17_closed,
        source_verifier=verifier,
    )
    if not plan["ok"]:
        return plan
    if payload.get("dry_run") is not False:
        return plan
    if payload.get("confirm_runtime_evidence") is not True:
        return _blocked_from_plan(plan, "stage18_runtime_evidence_confirmation_required")
    if _exact_hash(payload.get("record_fingerprint")) != plan["record_fingerprint"]:
        return _blocked_from_plan(plan, "stage18_runtime_evidence_fingerprint_mismatch")

    with _RECORD_LOCK:
        with _cross_process_receipt_lock() as acquired:
            if not acquired:
                return _blocked_from_plan(plan, "stage18_runtime_evidence_write_lock_unavailable")
            assert verifier is not None
            final_source = verifier(plan["source_receipt_id"], plan["source_receipt_fingerprint"])
            if not _valid_source_result(final_source) or not _source_matches_plan(final_source, plan):
                return _blocked_from_plan(plan, "stage18_runtime_evidence_source_changed_under_lock")

            receipt_id = f"mcre_{plan['record_fingerprint'][:24]}"
            path = receipt_directory() / f"{receipt_id}.json"
            receipt = _build_receipt(plan, receipt_id=receipt_id)
            if path.exists():
                existing = _read_json(path)
                if existing == receipt or _same_receipt_without_timestamp(existing, receipt):
                    return _recorded_result(existing, writes_receipt=False, status="already_recorded")
                return _blocked_from_plan(plan, "stage18_runtime_evidence_conflicting_replay")
            try:
                with path.open("x", encoding="utf-8") as handle:
                    json.dump(receipt, handle, indent=2, sort_keys=True, ensure_ascii=True)
                    handle.write("\n")
            except FileExistsError:
                return _blocked_from_plan(plan, "stage18_runtime_evidence_conflicting_replay")
            return _recorded_result(receipt, writes_receipt=True, status="recorded")


def load_runtime_evidence_receipts(*, limit: int = 100) -> list[dict[str, Any]]:
    root = receipt_directory()
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime_ns)[-max(1, limit) :]:
        item = _read_json(path)
        if valid_runtime_evidence_receipt(item):
            items.append(item)
    return items


def valid_runtime_evidence_receipt(item: dict[str, Any]) -> bool:
    governance = item.get("governance")
    if set(item) != RECEIPT_FIELDS or not isinstance(governance, dict) or set(governance) != GOVERNANCE_FIELDS:
        return False
    if type(item.get("recorded_at_unix_ms")) is not int:
        return False
    expected_governance = _receipt_governance()
    if governance != expected_governance:
        return False
    if item.get("kind") != RUNTIME_EVIDENCE_RECEIPT_KIND or item.get("contract") != RUNTIME_EVIDENCE_CONTRACT:
        return False
    requirement_id = _identifier(item.get("requirement_id"))
    if item.get("status") != "recorded" or not _source_verifier(requirement_id):
        return False
    if item.get("proof_kind") != _proof_kind(requirement_id):
        return False
    for key in (
        "receipt_id",
        "actor",
        "trace_id",
        "source_receipt_id",
        "source_receipt_fingerprint",
        "source_lineage_hash",
        "current_state_hash",
        "evidence_class",
        "record_fingerprint",
    ):
        if not _identifier(item.get(key)) and key not in {
            "source_receipt_fingerprint",
            "source_lineage_hash",
            "current_state_hash",
            "record_fingerprint",
        }:
            return False
        if key in {
            "source_receipt_fingerprint",
            "source_lineage_hash",
            "current_state_hash",
            "record_fingerprint",
        } and not _exact_hash(item.get(key)):
            return False
    fingerprint_binding = {
        key: item[key]
        for key in (
            "contract",
            "actor",
            "requirement_id",
            "proof_kind",
            "trace_id",
            "source_receipt_id",
            "source_receipt_fingerprint",
            "source_lineage_hash",
            "current_state_hash",
            "evidence_class",
        )
    }
    return item["record_fingerprint"] == _fingerprint(fingerprint_binding) and item["receipt_id"] == (
        f"mcre_{item['record_fingerprint'][:24]}"
    )


def receipt_satisfies_runtime_requirement(
    item: dict[str, Any],
    *,
    source_verifier: SourceVerifier | None = None,
) -> bool:
    requirement_id = _identifier(item.get("requirement_id"))
    verifier = source_verifier or _source_verifier(requirement_id)
    if not valid_runtime_evidence_receipt(item) or item.get("evidence_class") != "canonical_runtime":
        return False
    if verifier is None:
        return False
    source = verifier(item["source_receipt_id"], item["source_receipt_fingerprint"])
    return _valid_source_result(source) and _source_matches_plan(source, item)


def _build_receipt(plan: dict[str, Any], *, receipt_id: str) -> dict[str, Any]:
    return {
        "kind": RUNTIME_EVIDENCE_RECEIPT_KIND,
        "contract": RUNTIME_EVIDENCE_CONTRACT,
        "receipt_id": receipt_id,
        "status": "recorded",
        "actor": plan["actor"],
        "requirement_id": plan["requirement_id"],
        "proof_kind": plan["proof_kind"],
        "trace_id": plan["trace_id"],
        "source_receipt_id": plan["source_receipt_id"],
        "source_receipt_fingerprint": plan["source_receipt_fingerprint"],
        "source_lineage_hash": plan["source_lineage_hash"],
        "current_state_hash": plan["current_state_hash"],
        "evidence_class": plan["evidence_class"],
        "record_fingerprint": plan["record_fingerprint"],
        "recorded_at_unix_ms": int(time.time() * 1000),
        "governance": _receipt_governance(),
    }


def _receipt_governance() -> dict[str, bool]:
    return {
        "runtime_evidence_receipt": True,
        "trace_linked": True,
        "redacted": True,
        "contains_raw_private_data": False,
        "writes_tenant_state": False,
        "writes_registry": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "launches_browser": False,
        "captures_screen": False,
        "external_action": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage_closed": False,
    }


def _valid_source_result(source: dict[str, Any]) -> bool:
    return (
        set(source) == {"valid", "blocker", "evidence_class", "source_lineage_hash", "current_state_hash"}
        and source.get("valid") is True
        and source.get("blocker") == ""
        and source.get("evidence_class") in {"canonical_runtime", "fixture_software_only"}
        and bool(_exact_hash(source.get("source_lineage_hash")))
        and bool(_exact_hash(source.get("current_state_hash")))
    )


def _source_matches_plan(source: dict[str, Any], plan: dict[str, Any]) -> bool:
    return all(
        _exact_text(source.get(key)) == _exact_text(plan.get(key))
        for key in ("evidence_class", "source_lineage_hash", "current_state_hash")
    )


def _blocked_source(blocker: str) -> dict[str, Any]:
    return {
        "valid": False,
        "blocker": blocker,
        "evidence_class": "",
        "source_lineage_hash": "",
        "current_state_hash": "",
    }


def _blocked_from_plan(plan: dict[str, Any], error: str) -> dict[str, Any]:
    return {**plan, "ok": False, "status": "blocked", "error": error, "blockers": [error]}


def _recorded_result(receipt: dict[str, Any], *, writes_receipt: bool, status: str) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "error": "",
        "receipt": receipt,
        "receipt_id": receipt["receipt_id"],
        "actor": receipt["actor"],
        "requirement_id": receipt["requirement_id"],
        "proof_kind": receipt["proof_kind"],
        "trace_id": receipt["trace_id"],
        "record_fingerprint": receipt["record_fingerprint"],
        "receipt_ready": False,
        "writes_receipt": writes_receipt,
        "writes_tenant_state": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage_closed": False,
    }


def _same_receipt_without_timestamp(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not valid_runtime_evidence_receipt(left):
        return False
    return {key: value for key, value in left.items() if key != "recorded_at_unix_ms"} == {
        key: value for key, value in right.items() if key != "recorded_at_unix_ms"
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


@contextmanager
def _cross_process_receipt_lock():
    root = receipt_directory()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".write.lock"
    try:
        with lock_path.open("x", encoding="utf-8") as handle:
            handle.write(f"{threading.get_native_id()}\n")
    except FileExistsError:
        yield False
        return
    try:
        yield True
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _fingerprint(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exact_hash(value: Any) -> str:
    text = _exact_text(value).lower()
    return text if len(text) == 64 and all(char in "0123456789abcdef" for char in text) else ""


def _exact_text(value: Any) -> str:
    return value.strip()[:240] if type(value) is str else ""


def _identifier(value: Any) -> str:
    text = _exact_text(value)
    if not _IDENTIFIER.fullmatch(text) or redact_secret_text(text) != text:
        return ""
    return text


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_exact_text(value)).strip()[:240]
