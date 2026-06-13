# mypy: disable-error-code=attr-defined
"""Forge synthesis corridor: the governed forward arc after a builder proposal.

Picks up exactly where the local builder stopped (a proposal artifact that was
never applied) and drives it through evidence-only governance bricks toward an
operator-approvable -- but still un-applied -- state:

    review_builder_proposal      builder.proposal.review        (deterministic gate)
    preflight_forge_apply        forge.apply.preflight          (exact-action projection)
    request_forge_apply_approval forge.apply.approval_request   (queues operator approval)
    consume_forge_apply_approval forge.apply.approval_consumption (single-use evidence)
    boundary_forge_apply         forge.apply.boundary           (honest refusal surface)
    plan_forge_validation        forge.validation.plan          (Lab validation projection)

Every brick writes an artifact + receipt and returns evidence. None of them apply
a patch, write to the repo, execute a command, grant execution authority, validate
a candidate, or promote a capability. Apply stays impossible by construction until
a separate governed applier (with atomic write, rollback, receipt sink, and
post-apply Lab validation) exists -- this corridor only proves Francis recognised
the request and declined to apply.

Ingest is a *capability* of Francis, not Francis authority: operator approval
(`approvals.decide`) is never called from here.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from francis.governance import approvals

from . import proposal_review as pr
from .registry import ingest_artifact_root, utc_now, write_ingest_record_artifact
from .service_base import (
    _append_unique,
    _display_payload,
    _load_ingest_record_payload,
    _safe_str,
)

if TYPE_CHECKING:
    from .service import IngestService

_APPLY_ACTION = "francis.forge.apply"
_APPLY_SCOPE = "ingest.forge.apply.execute"

# Controls a future governed applier must satisfy before any apply is real.
_MISSING_APPLIER_CONTROLS = (
    "governed_applier_not_implemented",
    "atomic_write_with_rollback_not_bound",
    "apply_receipt_sink_not_bound",
    "post_apply_lab_validation_not_bound",
    "forbidden_path_write_guard_not_bound",
)


def _artifact_id(value: Any) -> str:
    return _safe_str(value).strip()


def _forge_no_execution_payload(*, reason: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "executed": False,
        "execution_authority": False,
        "ran_repo_scripts": False,
        "network_accessed": False,
        "patch_applied": False,
        "wrote_to_repo": False,
        "candidate_validated": False,
        "capability_promoted": False,
        "reason": reason,
    }
    payload.update(extra)
    return payload


def _read_forge_approval_record(approval_id: str) -> tuple[str, dict[str, Any], Path | None]:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return "invalid", {}, None
    for status, folder in (
        ("approved", approvals.approved_dir()),
        ("pending", approvals.pending_dir()),
        ("rejected", approvals.rejected_dir()),
        ("emergency", approvals.emergency_dir()),
    ):
        path = folder / f"{cleaned}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return "corrupt", {}, path
        return status, payload if isinstance(payload, dict) else {}, path
    return "missing", {}, None


def _preflight_id(builder_run_id: str) -> str:
    return "forge_apply_preflight_" + pr.stable_hash(builder_run_id).split(":", 1)[-1][:12]


def _request_id(builder_run_id: str, approval_id: str) -> str:
    return "forge_apply_approval_request_" + pr.stable_hash([builder_run_id, approval_id]).split(":", 1)[-1][:12]


def _consumption_id(approval_id: str) -> str:
    return "forge_apply_approval_consumption_" + pr.stable_hash(approval_id).split(":", 1)[-1][:12]


def _boundary_id(builder_run_id: str) -> str:
    return "forge_apply_boundary_" + pr.stable_hash(builder_run_id).split(":", 1)[-1][:12]


def _validation_plan_id(builder_run_id: str) -> str:
    return "forge_validation_plan_" + pr.stable_hash(builder_run_id).split(":", 1)[-1][:12]


def _dryrun_id(builder_run_id: str) -> str:
    return "forge_apply_dryrun_" + pr.stable_hash(builder_run_id).split(":", 1)[-1][:12]


# Heavy/irrelevant dirs that are never copied into the scratch tree.
_SCRATCH_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"})
_SCRATCH_MAX_FILES = 2000
_SCRATCH_MAX_FILE_BYTES = 1_000_000


def _copy_source_to_scratch(src_root: Path, dst_root: Path) -> tuple[int, list[str]]:
    """Copy a source tree into a fresh Francis-owned scratch dir (bounded)."""

    if dst_root.exists():
        shutil.rmtree(dst_root, ignore_errors=True)
    dst_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    warnings: list[str] = []
    for path in sorted(src_root.rglob("*")):
        if copied >= _SCRATCH_MAX_FILES:
            warnings.append("scratch_file_limit_reached")
            break
        if any(part in _SCRATCH_SKIP_DIRS for part in path.relative_to(src_root).parts):
            continue
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > _SCRATCH_MAX_FILE_BYTES:
                continue
            rel = path.relative_to(src_root)
            target = dst_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            copied += 1
        except Exception:
            continue
    return copied, warnings


class ForgeSynthesisIngestService:
    # -- brick 1: deterministic proposal review --------------------------------
    def review_builder_proposal(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        proposal_text: str = "",
        *,
        actor: str = "francis/system",
        source_root: str = "",
    ) -> dict[str, Any]:
        """Deterministically evaluate a builder proposal. Never applies anything.

        A verdict is only computed over the *full* proposal text whose sha256
        matches the digest recorded on the builder run. Absent or mismatched text
        yields an honest ``indeterminate`` verdict (no fake clean signal).
        """

        clean_run_id = _safe_str(builder_run_id).strip()
        record = _load_ingest_record_payload("builder_runs", "builder_run", clean_run_id)
        if not record:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "builder_run_unavailable",
                    "builder_run_id": clean_run_id,
                    "execution": _forge_no_execution_payload(reason="builder_run_unavailable"),
                }
            )

        source = self._record_from_source_or_path(source_or_path, actor=actor)
        root = _safe_str(source_root).strip() or source.canonical_path
        recorded_digest = _safe_str(record.get("response_digest")).strip()
        allowed = pr._string_list(record.get("allowed_files"))
        forbidden = pr._string_list(record.get("forbidden_files"))
        max_files = int(record.get("max_files_changed") or 0)

        supplied = _safe_str(proposal_text)
        supplied_digest = pr.text_digest(supplied) if supplied else ""
        digest_verified = bool(supplied) and supplied_digest == recorded_digest

        blockers: list[str] = []
        findings: list[str] = []
        touched: list[str] = []
        outside: list[str] = []
        copy_metrics: dict[str, Any] = {}
        parsed = pr.parse_unified_diff("")
        proposal_kind = "empty"
        verdict = "indeterminate"

        if not supplied:
            blockers.append("no_full_proposal_text_supplied")
        elif not digest_verified:
            blockers.append("supplied_text_digest_mismatch")
        else:
            parsed = pr.parse_unified_diff(supplied)
            if parsed.is_diff:
                proposal_kind = "patch"
            elif supplied.strip():
                proposal_kind = "plan"
            scope_blockers, outside = pr.scope_findings(
                parsed, allowed_files=allowed, forbidden_files=forbidden, max_files_changed=max_files
            )
            blockers.extend(scope_blockers)
            if parsed.is_diff and not parsed.well_formed:
                blockers.extend(f"malformed_diff:{m}" for m in parsed.malformations)
            token_findings = pr.token_scan_findings(parsed.added_lines)
            for f in token_findings:
                # Secret/destructive material blocks; network is a flagged finding.
                if f == "proposal_contains_network_token":
                    findings.append(f)
                else:
                    blockers.append(f)
            copy_findings, copy_metrics = pr.copy_overlap_findings(parsed.added_lines, source_root=root)
            blockers.extend(copy_findings)
            touched = list(parsed.files)
            verdict = "clean" if not blockers else "blocked"

        blockers = sorted(set(blockers))
        findings = sorted(set(findings))
        status = "reviewed" if verdict == "clean" else verdict
        review = pr.BuilderProposalReview(
            id=pr.review_id(clean_run_id),
            builder_run_id=clean_run_id,
            spec_id=_safe_str(record.get("spec_id")).strip(),
            source_id=_safe_str(record.get("source_id")).strip() or source.id,
            candidate_id=_safe_str(record.get("candidate_id")).strip(),
            candidate_name=_safe_str(record.get("candidate_name")).strip(),
            actor=_safe_str(actor).strip() or "francis/system",
            created_at=utc_now(),
            verdict=verdict,
            status=status,
            proposal_kind=proposal_kind,
            digest_verified=digest_verified,
            recorded_response_digest=recorded_digest,
            supplied_text_digest=supplied_digest,
            diff=parsed.to_dict(),
            touched_files=touched,
            files_outside_scope=outside,
            blockers=blockers,
            findings=findings,
            copy_overlap=copy_metrics,
            allowed_files=allowed,
            forbidden_files=forbidden,
            max_files_changed=max_files,
        )
        artifact_path = write_ingest_record_artifact(
            "builder_proposal_reviews", review.id, {"builder_proposal_review": review.to_dict()}
        )
        receipt, receipt_path = self.receipts.write(
            operation="builder.proposal.review",
            source_id=review.source_id,
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=_append_unique([review.source_id, clean_run_id, recorded_digest, supplied_digest]),
            result_status=status,
            warnings=findings,
            errors=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "full_text_digest_gated",
                f"digest_verified:{str(digest_verified).lower()}",
                f"verdict:{verdict}",
                "scope_checked",
                "secret_network_destructive_scanned",
                "third_party_copy_overlap_scanned",
                "patch_not_applied",
                "no_execution",
            ],
        )
        updated_review = pr.BuilderProposalReview.from_dict(
            {**review.to_dict(), "receipts": [str(receipt_path)], "artifact_path": str(artifact_path)}
        )
        assert updated_review is not None
        review = updated_review
        write_ingest_record_artifact(
            "builder_proposal_reviews", review.id, {"builder_proposal_review": review.to_dict()}
        )
        return _display_payload(
            {
                # Mirror the substrate convention: ok only when the proposal is
                # clean. blocked and indeterminate both return ok=False.
                "ok": verdict == "clean",
                "status": status,
                "verdict": verdict,
                "builder_proposal_review": review.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(
                    reason="proposal_reviewed_no_execution", digest_verified=digest_verified
                ),
            }
        )

    # -- brick 2: exact-action apply preflight ---------------------------------
    def preflight_forge_apply(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_run_id = _safe_str(builder_run_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        review = _load_ingest_record_payload(
            "builder_proposal_reviews", "builder_proposal_review", pr.review_id(clean_run_id)
        )
        blockers = _append_unique(
            [],
            *([] if review else ["proposal_review_missing"]),
            *([] if review.get("verdict") == "clean" else ["proposal_review_not_clean"]),
            *_MISSING_APPLIER_CONTROLS,
            _APPLY_SCOPE + "_required",
        )
        action_payload = {
            "action": _APPLY_ACTION,
            "builder_run_id": clean_run_id,
            "review_id": _safe_str(review.get("id")),
            "spec_id": _safe_str(review.get("spec_id")),
            "source_id": _safe_str(review.get("source_id")) or source.id,
            "candidate_id": _safe_str(review.get("candidate_id")),
            "candidate_name": _safe_str(review.get("candidate_name")),
            "touched_files": pr._string_list(review.get("touched_files")),
            "response_digest": _safe_str(review.get("recorded_response_digest")),
            "max_files_changed": int(review.get("max_files_changed") or 0),
        }
        action_hash = pr.stable_hash(action_payload)
        ready_for_request = bool(review) and review.get("verdict") == "clean"
        status = "needs_approval" if ready_for_request else "blocked"
        record = {
            "id": _preflight_id(clean_run_id),
            "builder_run_id": clean_run_id,
            "source_id": action_payload["source_id"],
            "candidate_id": action_payload["candidate_id"],
            "candidate_name": action_payload["candidate_name"],
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": utc_now(),
            "status": status,
            "action": _APPLY_ACTION,
            "action_hash": action_hash,
            "action_payload": action_payload,
            "approval_scope": _APPLY_SCOPE,
            "review_verdict": _safe_str(review.get("verdict")) or "missing",
            "blockers": blockers,
            "missing_applier_controls": list(_MISSING_APPLIER_CONTROLS),
            "patch_applied": False,
            "approval_created": False,
            "approval_consumed": False,
            "wrote_to_repo": False,
            "executed": False,
            "execution_authority": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_apply_preflights", _artifact_id(record["id"]), {"forge_apply_preflight": record}
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.apply.preflight",
            source_id=record["source_id"],
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[record["source_id"], clean_run_id, action_hash],
            result_status=status,
            warnings=blockers,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "proposal_review_readback",
                "exact_action_hash_computed",
                "apply_gate_projected",
                "approval_not_created",
                "patch_not_applied",
                "no_execution",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact(
            "forge_apply_preflights", _artifact_id(record["id"]), {"forge_apply_preflight": record}
        )
        return _display_payload(
            {
                "ok": ready_for_request,
                "status": status,
                "forge_apply_preflight": record,
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(reason="apply_preflight_only_no_execution"),
            }
        )

    # -- brick 3: queue operator apply approval --------------------------------
    def request_forge_apply_approval(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        *,
        actor: str = "francis/system",
        reason: str = "forge_apply_requested",
    ) -> dict[str, Any]:
        clean_run_id = _safe_str(builder_run_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        preflight = _load_ingest_record_payload(
            "forge_apply_preflights", "forge_apply_preflight", _preflight_id(clean_run_id)
        )
        if not preflight or preflight.get("status") != "needs_approval":
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "forge_apply_preflight_not_ready",
                    "builder_run_id": clean_run_id,
                    "blockers": pr._string_list(preflight.get("blockers")) or ["forge_apply_preflight_missing"],
                    "execution": _forge_no_execution_payload(reason="forge_apply_preflight_not_ready"),
                }
            )
        action_hash = _safe_str(preflight.get("action_hash"))
        approval_payload = _display_payload(
            {
                **preflight.get("action_payload", {}),
                "action_hash": action_hash,
                "governance": {
                    "approval_scope": _APPLY_SCOPE,
                    "approval_consumed": False,
                    "patch_applied": False,
                    "wrote_to_repo": False,
                    "execution_authority": False,
                    "candidate_validated": False,
                    "capability_promoted": False,
                },
            }
        )
        approval = approvals.request(
            action=_APPLY_ACTION,
            reason=_safe_str(reason).strip() or "forge_apply_requested",
            payload=approval_payload,
        )
        approval_id = _safe_str(approval.get("id")).strip()
        approval_path = approvals.pending_dir() / f"{approval_id}.json" if approval_id else Path("")
        record = {
            "id": _request_id(clean_run_id, approval_id),
            "builder_run_id": clean_run_id,
            "preflight_id": preflight.get("id"),
            "approval_id": approval_id,
            "source_id": _safe_str(preflight.get("source_id")) or source.id,
            "candidate_id": _safe_str(preflight.get("candidate_id")),
            "candidate_name": _safe_str(preflight.get("candidate_name")),
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": utc_now(),
            "status": "needs_approval",
            "action": _APPLY_ACTION,
            "action_hash": action_hash,
            "approval_scope": _APPLY_SCOPE,
            "approval_path": str(approval_path) if approval_id else "",
            "approval_created": bool(approval_id),
            "approval_consumed": False,
            "patch_applied": False,
            "wrote_to_repo": False,
            "executed": False,
            "execution_authority": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_apply_approval_requests", _artifact_id(record["id"]), {"forge_apply_approval_request": record}
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.apply.approval_request",
            source_id=record["source_id"],
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[record["source_id"], clean_run_id, action_hash, approval_id],
            result_status="needs_approval",
            warnings=["forge_apply_requires_operator_approval"],
            generated_artifact_paths=[str(artifact_path), str(approval_path) if approval_id else ""],
            validation_performed=[
                "apply_preflight_readback",
                "exact_action_approval_requested",
                "approval_not_consumed",
                "patch_not_applied",
                "no_execution",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact(
            "forge_apply_approval_requests", _artifact_id(record["id"]), {"forge_apply_approval_request": record}
        )
        return _display_payload(
            {
                "ok": bool(approval_id),
                "status": "needs_approval",
                "forge_apply_approval_request": record,
                "approval": approval,
                "approval_path": str(approval_path) if approval_id else "",
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(reason="apply_approval_requested_no_execution"),
            }
        )

    # -- brick 4: single-use approval consumption ------------------------------
    def consume_forge_apply_approval(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_run_id = _safe_str(builder_run_id).strip()
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        request = _load_ingest_record_payload(
            "forge_apply_approval_requests",
            "forge_apply_approval_request",
            _request_id(clean_run_id, clean_approval_id),
        )
        approval_status, approval_record, approval_path = _read_forge_approval_record(clean_approval_id)
        # The approval payload (incl. action_hash) is nested under "payload".
        approval_action_hash = _safe_str((approval_record.get("payload") or {}).get("action_hash"))
        existing = _load_ingest_record_payload(
            "forge_apply_approval_consumptions", "forge_apply_approval_consumption", _consumption_id(clean_approval_id)
        )
        blockers = _append_unique(
            [],
            *([] if request else ["forge_apply_approval_request_missing"]),
            *([] if approval_status == "approved" else [f"approval_not_approved:{approval_status}"]),
            *(
                []
                if request and _safe_str(request.get("builder_run_id")) == clean_run_id
                else ["builder_run_identity_mismatch"]
            ),
            *(
                []
                if not request or not approval_record or _safe_str(request.get("action_hash")) == approval_action_hash
                else ["approval_action_hash_mismatch"]
            ),
            *([] if not existing else ["forge_apply_approval_already_consumed"]),
        )
        if blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "forge_apply_approval_consumption_blocked",
                    "builder_run_id": clean_run_id,
                    "approval_id": clean_approval_id,
                    "approval_status": approval_status,
                    "blockers": sorted(set(blockers)),
                    "execution": _forge_no_execution_payload(reason="forge_apply_approval_consumption_blocked"),
                }
            )
        assert request is not None
        now = utc_now()
        record = {
            "id": _consumption_id(clean_approval_id),
            "builder_run_id": clean_run_id,
            "approval_request_id": request.get("id"),
            "approval_id": clean_approval_id,
            "source_id": _safe_str(request.get("source_id")) or source.id,
            "candidate_id": _safe_str(request.get("candidate_id")),
            "candidate_name": _safe_str(request.get("candidate_name")),
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": now,
            "consumed_at": now,
            "status": "consumed",
            "action": _APPLY_ACTION,
            "action_hash": _safe_str(request.get("action_hash")),
            "approval_status": approval_status,
            "approval_path": str(approval_path) if approval_path is not None else "",
            "approval_consumed": True,
            "single_use_enforced": True,
            # Consumption is governance evidence only -- apply stays impossible.
            "patch_applied": False,
            "wrote_to_repo": False,
            "executed": False,
            "execution_authority": False,
            "candidate_validated": False,
            "capability_promoted": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_apply_approval_consumptions",
            _artifact_id(record["id"]),
            {"forge_apply_approval_consumption": record},
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.apply.approval_consumption",
            source_id=record["source_id"],
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[record["source_id"], clean_run_id, clean_approval_id, record["action_hash"]],
            result_status="consumed",
            warnings=["forge_apply_blocked_after_consumption"],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "approval_record_readback",
                "exact_action_hash_matched",
                "single_use_enforced",
                "patch_not_applied",
                "execution_authority_not_granted",
                "no_execution",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact(
            "forge_apply_approval_consumptions",
            _artifact_id(record["id"]),
            {"forge_apply_approval_consumption": record},
        )
        return _display_payload(
            {
                "ok": True,
                "status": "consumed",
                "forge_apply_approval_consumption": record,
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(reason="apply_approval_consumed_no_execution"),
            }
        )

    # -- brick 5: honest apply boundary (refusal surface) ----------------------
    def boundary_forge_apply(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        approval_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        """Even with a consumed approval, applying is refused until a governed
        applier exists. This brick records that refusal as evidence."""

        clean_run_id = _safe_str(builder_run_id).strip()
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        consumption = _load_ingest_record_payload(
            "forge_apply_approval_consumptions", "forge_apply_approval_consumption", _consumption_id(clean_approval_id)
        )
        blockers = _append_unique(
            [],
            *([] if consumption else ["forge_apply_approval_consumption_missing"]),
            *(
                []
                if consumption and _safe_str(consumption.get("builder_run_id")) == clean_run_id
                else ["builder_run_identity_mismatch"]
            ),
            *_MISSING_APPLIER_CONTROLS,
        )
        record = {
            "id": _boundary_id(clean_run_id),
            "builder_run_id": clean_run_id,
            "approval_id": clean_approval_id,
            "consumption_id": _safe_str(consumption.get("id")),
            "source_id": _safe_str(consumption.get("source_id")) or source.id,
            "candidate_id": _safe_str(consumption.get("candidate_id")),
            "candidate_name": _safe_str(consumption.get("candidate_name")),
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": utc_now(),
            "status": "blocked",
            "action": _APPLY_ACTION,
            "approval_consumed": bool(consumption),
            "blockers": sorted(set(blockers)),
            "missing_applier_controls": list(_MISSING_APPLIER_CONTROLS),
            "apply_refused": True,
            "patch_applied": False,
            "wrote_to_repo": False,
            "executed": False,
            "execution_authority": False,
            "candidate_validated": False,
            "capability_promoted": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_apply_boundaries", _artifact_id(record["id"]), {"forge_apply_boundary": record}
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.apply.boundary",
            source_id=record["source_id"],
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[record["source_id"], clean_run_id, clean_approval_id],
            result_status="blocked",
            warnings=sorted(set(blockers)),
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "approval_consumption_readback",
                "apply_refused_no_governed_applier",
                "patch_not_applied",
                "repo_not_written",
                "execution_authority_not_granted",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact(
            "forge_apply_boundaries", _artifact_id(record["id"]), {"forge_apply_boundary": record}
        )
        return _display_payload(
            {
                "ok": False,
                "status": "blocked",
                "error": "forge_apply_refused_no_governed_applier",
                "forge_apply_boundary": record,
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(reason="forge_apply_refused_no_governed_applier"),
            }
        )

    # -- brick 5b: governed dry-run applier (scratch only, repo untouched) ------
    def dryrun_forge_apply(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        approval_id: str,
        proposal_text: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        """Apply a clean, approved, consumed proposal to an ISOLATED Francis-owned
        scratch copy of the source -- never the real repo.

        Requires the full proposal text whose sha256 matches the review's recorded
        digest (no fuzzy/forced application). Enforces the forbidden-path write
        guard. The real source repo is never written; `wrote_to_repo` stays false.
        """

        clean_run_id = _safe_str(builder_run_id).strip()
        clean_approval_id = _safe_str(approval_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        consumption = _load_ingest_record_payload(
            "forge_apply_approval_consumptions", "forge_apply_approval_consumption", _consumption_id(clean_approval_id)
        )
        review = _load_ingest_record_payload(
            "builder_proposal_reviews", "builder_proposal_review", pr.review_id(clean_run_id)
        )
        recorded_digest = _safe_str(review.get("recorded_response_digest"))
        forbidden = pr._string_list(review.get("forbidden_files"))
        supplied = _safe_str(proposal_text)
        supplied_digest = pr.text_digest(supplied) if supplied else ""
        digest_verified = bool(supplied) and supplied_digest == recorded_digest

        gate_blockers = _append_unique(
            [],
            *([] if consumption else ["forge_apply_approval_consumption_missing"]),
            *(
                []
                if consumption and _safe_str(consumption.get("builder_run_id")) == clean_run_id
                else ["builder_run_identity_mismatch"]
            ),
            *([] if review.get("verdict") == "clean" else ["proposal_review_not_clean"]),
        )
        if gate_blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "forge_apply_dryrun_blocked",
                    "builder_run_id": clean_run_id,
                    "blockers": sorted(set(gate_blockers)),
                    "execution": _forge_no_execution_payload(reason="forge_apply_dryrun_blocked"),
                }
            )
        if not digest_verified:
            return _display_payload(
                {
                    "ok": False,
                    "status": "indeterminate",
                    "error": "supplied_text_digest_mismatch" if supplied else "no_full_proposal_text_supplied",
                    "builder_run_id": clean_run_id,
                    "execution": _forge_no_execution_payload(reason="forge_apply_dryrun_indeterminate"),
                }
            )

        dryrun_id = _dryrun_id(clean_run_id)
        scratch_root = ingest_artifact_root() / "forge_dryrun_workspaces" / dryrun_id
        scratch_src = scratch_root / "src"
        copied, copy_warnings = _copy_source_to_scratch(Path(source.canonical_path), scratch_src)
        applied = pr.apply_unified_diff_to_tree(supplied, str(scratch_src), forbidden_files=forbidden)
        file_results = [r.to_dict() for r in applied]
        applied_count = sum(1 for r in applied if r.status == "applied")
        rejected_count = sum(1 for r in applied if r.status == "rejected")
        reject_reasons = sorted({r.reject_reason for r in applied if r.reject_reason})
        if applied and rejected_count == 0:
            status = "dryrun_applied"
        elif applied_count > 0:
            status = "dryrun_partial"
        else:
            status = "dryrun_rejected"

        record = {
            "id": dryrun_id,
            "builder_run_id": clean_run_id,
            "approval_id": clean_approval_id,
            "consumption_id": _safe_str(consumption.get("id")),
            "review_id": _safe_str(review.get("id")),
            "source_id": _safe_str(review.get("source_id")) or source.id,
            "candidate_id": _safe_str(review.get("candidate_id")),
            "candidate_name": _safe_str(review.get("candidate_name")),
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": utc_now(),
            "status": status,
            "supplied_text_digest": supplied_digest,
            "digest_verified": True,
            "scratch_root": str(scratch_root),
            "scratch_files_copied": copied,
            "files": file_results,
            "files_applied": applied_count,
            "files_rejected": rejected_count,
            "reject_reasons": reject_reasons,
            "forbidden_files": forbidden,
            # The whole point: the real repo is never written.
            "wrote_to_repo": False,
            "wrote_to_scratch_only": True,
            "repo_root": source.canonical_path,
            "patch_applied_to_repo": False,
            "executed": False,
            "candidate_validated": False,
            "capability_promoted": False,
            "execution_authority": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_apply_dryruns", _artifact_id(record["id"]), {"forge_apply_dryrun": record}
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.apply.dryrun",
            source_id=record["source_id"],
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[record["source_id"], clean_run_id, clean_approval_id, supplied_digest],
            result_status=status,
            warnings=copy_warnings + reject_reasons,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "approval_consumption_readback",
                "full_text_digest_gated",
                "applied_to_isolated_scratch_only",
                "forbidden_path_write_guard_enforced",
                "real_repo_not_written",
                "no_execution",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact("forge_apply_dryruns", _artifact_id(record["id"]), {"forge_apply_dryrun": record})
        return _display_payload(
            {
                "ok": status != "dryrun_rejected",
                "status": status,
                "forge_apply_dryrun": record,
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(
                    reason="forge_apply_dryrun_scratch_only", wrote_to_scratch_only=True
                ),
            }
        )

    # -- brick 5c: bind the synthesized tree back as a first-class source ------
    def bind_synthesized_source(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        """Register the dry-run scratch tree (proposal applied, repo untouched) as a
        new ingest source so the synthesized capability can be validated through the
        EXISTING governed Lab corridor -- no new execution path, no weakened gate.

        This closes the loop: ingest a repo -> synthesize a Francis-native proposal
        -> apply to scratch -> re-ingest the synthesized tree -> (operator) drive the
        standard acquisition/Lab validation on it. Runs nothing here.
        """

        clean_run_id = _safe_str(builder_run_id).strip()
        origin = self._record_from_source_or_path(source_or_path, actor=actor)
        dryrun = _load_ingest_record_payload("forge_apply_dryruns", "forge_apply_dryrun", _dryrun_id(clean_run_id))
        blockers = _append_unique(
            [],
            *([] if dryrun else ["forge_apply_dryrun_missing"]),
            *(
                []
                if dryrun.get("status") in ("dryrun_applied", "dryrun_partial")
                else ["dryrun_not_applied_to_scratch"]
            ),
            *([] if int(dryrun.get("files_applied") or 0) > 0 else ["no_files_applied_to_scratch"]),
        )
        if blockers:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "bind_synthesized_source_blocked",
                    "builder_run_id": clean_run_id,
                    "blockers": sorted(set(blockers)),
                    "execution": _forge_no_execution_payload(reason="bind_synthesized_source_blocked"),
                }
            )

        scratch_src = str(Path(_safe_str(dryrun.get("scratch_root"))) / "src")
        added = self.add_source(scratch_src, actor=actor)
        if not added.get("ok"):
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "synthesized_source_registration_failed",
                    "builder_run_id": clean_run_id,
                    "detail": added.get("error"),
                    "execution": _forge_no_execution_payload(reason="synthesized_source_registration_failed"),
                }
            )
        synth_source = added["source"]
        synth_source_id = _safe_str(synth_source.get("id"))
        self.inspect_repo(_safe_str(synth_source.get("canonical_path")), actor=actor)
        cands = self.extract_candidates(synth_source_id, actor=actor).get("candidates") or []

        record = {
            "id": "forge_synthesized_source_" + pr.stable_hash([clean_run_id, synth_source_id]).split(":", 1)[-1][:12],
            "builder_run_id": clean_run_id,
            "dryrun_id": _safe_str(dryrun.get("id")),
            "spec_id": _safe_str(dryrun.get("review_id")),  # review carries spec linkage
            # `source_id` is the ORIGIN source so this surfaces in its readback.
            "source_id": origin.id,
            "origin_source_id": origin.id,
            "synthesized_source_id": synth_source_id,
            "synthesized_source_path": _safe_str(synth_source.get("canonical_path")),
            "candidate_count": len(cands),
            "candidate_names": [_safe_str(c.get("name")) for c in cands][:25],
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": utc_now(),
            "status": "bound",
            "validation_path": "standard_acquisition_then_lab_v0_corridor",
            "next_step": f"acquire_source_candidate('{synth_source_id}') then drive the governed Lab corridor",
            "wrote_to_repo": False,
            "executed": False,
            "candidate_validated": False,
            "capability_promoted": False,
            "execution_authority": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_synthesized_sources", _artifact_id(record["id"]), {"forge_synthesized_source": record}
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.synthesized_source.bind",
            source_id=origin.id,
            actor=actor,
            input_paths=[origin.canonical_path, scratch_src],
            input_hashes=[origin.id, clean_run_id, synth_source_id],
            result_status="bound",
            warnings=[],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "dryrun_scratch_readback",
                "synthesized_tree_registered_as_source",
                "synthesized_tree_inspected_read_only",
                "candidates_extracted",
                "routed_to_existing_governed_lab_corridor",
                "no_execution",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact(
            "forge_synthesized_sources", _artifact_id(record["id"]), {"forge_synthesized_source": record}
        )
        return _display_payload(
            {
                "ok": True,
                "status": "bound",
                "forge_synthesized_source": record,
                "synthesized_source": synth_source,
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(reason="synthesized_source_bound_no_execution"),
            }
        )

    # -- brick 6: Lab validation projection ------------------------------------
    def plan_forge_validation(
        self,
        source_or_path: str | Path,
        builder_run_id: str,
        *,
        actor: str = "francis/system",
    ) -> dict[str, Any]:
        clean_run_id = _safe_str(builder_run_id).strip()
        source = self._record_from_source_or_path(source_or_path, actor=actor)
        review = _load_ingest_record_payload(
            "builder_proposal_reviews", "builder_proposal_review", pr.review_id(clean_run_id)
        )
        spec_id = _safe_str(review.get("spec_id"))
        spec = _load_ingest_record_payload("capability_specs", "capability_spec", spec_id) if spec_id else {}
        raw_validation = spec.get("validation")
        validation = dict(raw_validation) if isinstance(raw_validation, dict) else {}
        validation_commands = pr._string_list(validation.get("validation_commands"))
        record = {
            "id": _validation_plan_id(clean_run_id),
            "builder_run_id": clean_run_id,
            "review_id": _safe_str(review.get("id")),
            "spec_id": spec_id,
            "source_id": _safe_str(review.get("source_id")) or source.id,
            "candidate_id": _safe_str(review.get("candidate_id")),
            "candidate_name": _safe_str(review.get("candidate_name")),
            "actor": _safe_str(actor).strip() or "francis/system",
            "created_at": utc_now(),
            "status": "planned",
            "review_verdict": _safe_str(review.get("verdict")) or "missing",
            "validation_commands": validation_commands,
            "acceptance_criteria": pr._string_list(validation.get("acceptance_criteria")),
            "promotion_requirements": pr._string_list(validation.get("promotion_requirements")),
            "validation_path": "francis_lab_v0_sandboxed_rebuild_run_test",
            "requires_applied_proposal_first": True,
            "requires_separate_lab_execution_approval": True,
            "patch_applied": False,
            "executed": False,
            "candidate_validated": False,
            "capability_promoted": False,
            "execution_authority": False,
            "schema_version": 1,
        }
        artifact_path = write_ingest_record_artifact(
            "forge_validation_plans", _artifact_id(record["id"]), {"forge_validation_plan": record}
        )
        receipt, receipt_path = self.receipts.write(
            operation="forge.validation.plan",
            source_id=record["source_id"],
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[record["source_id"], clean_run_id, spec_id],
            result_status="planned",
            warnings=[],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "proposal_review_readback",
                "capability_spec_validation_readback",
                "lab_validation_path_projected",
                "no_execution",
            ],
        )
        record["receipts"] = [str(receipt_path)]
        write_ingest_record_artifact(
            "forge_validation_plans", _artifact_id(record["id"]), {"forge_validation_plan": record}
        )
        return _display_payload(
            {
                "ok": True,
                "status": "planned",
                "forge_validation_plan": record,
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "execution": _forge_no_execution_payload(reason="validation_plan_only_no_execution"),
            }
        )

    # -- synthesis orchestrator (ingest pushes the whole corridor) -------------
    def _run_builder_for_synthesis(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
        client: Any | None = None,
        allowed_files: list[str] | None = None,
        forbidden_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the builder for the orchestrator. Uses the production localhost
        Ollama path unless a deterministic ``client`` is injected (tests)."""

        if client is None:
            return self.run_local_ollama_builder(
                source_or_path, candidate_ref, actor=actor, allowed_files=allowed_files, forbidden_files=forbidden_files
            )
        compiled = self.compile_capability_spec(
            source_or_path, candidate_ref, actor=actor, allowed_files=allowed_files, forbidden_files=forbidden_files
        )
        if not compiled.get("ok"):
            return compiled
        from .local_builder import (
            FrancisCapabilitySpec,
            LocalOllamaBuilder,
            OllamaBuilderConfig,
            OllamaBuildRequest,
        )

        spec = FrancisCapabilitySpec.from_dict(compiled.get("capability_spec"))
        if spec is None:
            return {"ok": False, "status": "failed", "error": "capability_spec_unavailable"}
        result = LocalOllamaBuilder(
            config=OllamaBuilderConfig(host="http://127.0.0.1:11434", model="injected"),
            client=client,
            receipt_writer=self.receipts,
        ).run(OllamaBuildRequest.from_spec(spec), actor=actor)
        return result.to_dict()

    def synthesize_capability(
        self,
        source_or_path: str | Path,
        candidate_ref: str = "",
        *,
        actor: str = "francis/system",
        builder_client: Any | None = None,
        allowed_files: list[str] | None = None,
        forbidden_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """Push a candidate through native synthesis to the apply approval gate."""

        from .forge_orchestrator import ForgeSynthesisOrchestrator

        return ForgeSynthesisOrchestrator(cast("IngestService", self)).synthesize_capability(
            source_or_path,
            candidate_ref,
            actor=actor,
            builder_client=builder_client,
            allowed_files=allowed_files,
            forbidden_files=forbidden_files,
        )

    def continue_synthesis_after_approval(self, run_id: str, *, actor: str = "francis/system") -> dict[str, Any]:
        """Resume a paused synthesis run after the operator approved the apply gate."""

        from .forge_orchestrator import ForgeSynthesisOrchestrator

        return ForgeSynthesisOrchestrator(cast("IngestService", self)).continue_synthesis_after_approval(
            run_id, actor=actor
        )
