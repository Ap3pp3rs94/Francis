# mypy: disable-error-code=attr-defined
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value

from ..ingest.repo_adapter import detect_repo
from ..ingest.source import (
    canonical_path,
    classify_source,
    display_path,
    source_fingerprint,
    source_id_for_path,
    source_metadata_from_scan,
)
from ..shared.models import (
    CapabilityCandidate,
    RepoMap,
    SourcePermissionProfile,
    SourceRecord,
)
from ..lab.lab import current_lab_boundary
from .registry import (
    CapabilityRegistry,
    ingest_artifact_root,
    utc_now,
    write_ingest_artifact,
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return list(value)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _display_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(payload)
    return redacted if isinstance(redacted, dict) else {}


def _bounded_limit(value: int, *, default: int = 100, maximum: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 1), maximum)


def _source_id_for_artifact(payload: dict[str, Any], record_key: str, *, direct_payload: bool) -> str:
    if direct_payload:
        return _safe_str(payload.get("source_id")).strip()
    record = _as_dict(payload.get(record_key))
    return _safe_str(record.get("source_id")).strip()


def _artifact_readbacks(
    kind: str,
    record_key: str,
    *,
    source_id: str,
    limit: int,
    direct_payload: bool = False,
) -> list[dict[str, Any]]:
    root = ingest_artifact_root() / kind
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    paths = sorted(root.glob("*.json"), key=lambda current: current.stat().st_mtime, reverse=True)
    for path in paths:
        payload = _read_json(path)
        if not payload:
            continue
        artifact_source_id = _source_id_for_artifact(payload, record_key, direct_payload=direct_payload)
        if source_id and artifact_source_id != source_id:
            continue
        if direct_payload:
            item = {"artifact_path": str(path), record_key: payload}
        else:
            item = {"artifact_path": str(path), record_key: _as_dict(payload.get(record_key))}
        items.append(item)
        if len(items) >= limit:
            break
    return items


def _load_ingest_record_payload(kind: str, record_key: str, record_id: str) -> dict[str, Any]:
    cleaned = _safe_str(record_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return {}
    path = ingest_artifact_root() / kind / f"{cleaned}.json"
    if not path.exists():
        return {}
    return _as_dict(_read_json(path).get(record_key))


def _capability_candidate_readbacks(
    registry: CapabilityRegistry,
    *,
    source_ids: set[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    raw = registry.load()
    candidates = _as_dict(raw.get("candidates"))
    out: list[dict[str, Any]] = []
    for value in candidates.values():
        candidate = CapabilityCandidate.from_dict(value)
        if candidate is None:
            continue
        if source_ids is not None and candidate.source_id not in source_ids:
            continue
        out.append(candidate.to_dict())
        if len(out) >= limit:
            break
    return sorted(out, key=lambda item: (_safe_str(item.get("source_id")), _safe_str(item.get("id"))))


def _append_unique(items: list[str], *values: str) -> list[str]:
    out = list(items)
    seen = set(out)
    for value in values:
        clean = _safe_str(value).strip()
        if clean and clean not in seen:
            out.append(clean)
            seen.add(clean)
    return out


def _no_lab_execution_payload(*, reason: str = "ingest_only") -> dict[str, Any]:
    return {
        "executed": False,
        "repo_code_executed": False,
        "ran_build": False,
        "ran_tests": False,
        "ran_provider": False,
        "network_accessed": False,
        "wrote_to_repo": False,
        "receipt_required_before_execution": True,
        "execution_authority": False,
        "reason": reason,
    }


class BaseIngestService:
    def readback(
        self,
        *,
        source_id: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        clean_source_id = _safe_str(source_id).strip()
        safe_limit = _bounded_limit(limit)
        sources = self.sources.list()
        if clean_source_id:
            sources = [source for source in sources if source.id == clean_source_id]

        source_ids = {source.id for source in sources}
        candidates = _capability_candidate_readbacks(
            self.capabilities,
            source_ids=source_ids if clean_source_id else None,
            limit=safe_limit,
        )
        repo_maps = _artifact_readbacks(
            "repo_maps",
            "repo_map",
            source_id=clean_source_id,
            limit=safe_limit,
            direct_payload=True,
        )
        lab_preflights = _artifact_readbacks("lab_preflights", "preflight", source_id=clean_source_id, limit=safe_limit)
        approval_consumption_preflights = _artifact_readbacks(
            "lab_approval_consumption_preflights",
            "approval_consumption",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        approval_consumptions = _artifact_readbacks(
            "lab_approval_consumptions",
            "approval_consumption_record",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        noop_runner_envelopes = _artifact_readbacks(
            "lab_noop_runner_envelopes",
            "noop_runner_envelope",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        noop_runner_transcripts = _artifact_readbacks(
            "lab_noop_runner_transcripts",
            "noop_runner_transcript",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        noop_runner_identity_bindings = _artifact_readbacks(
            "lab_noop_runner_identity_bindings",
            "noop_runner_identity_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        source_mount_readiness = _artifact_readbacks(
            "lab_source_mount_readiness",
            "source_mount_readiness",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        source_mount_contracts = _artifact_readbacks(
            "lab_source_mount_contracts",
            "source_mount_contract",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        approval_consumption_handoffs = _artifact_readbacks(
            "lab_approval_consumption_handoffs",
            "approval_handoff",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        execution_receipt_sink_reservations = _artifact_readbacks(
            "lab_execution_receipt_sink_reservations",
            "receipt_sink_reservation",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_command_allowlists = _artifact_readbacks(
            "lab_runner_command_allowlists",
            "runner_command_allowlist",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_command_allowlist_declarations = _artifact_readbacks(
            "lab_runner_command_allowlist_declarations",
            "runner_command_allowlist_declaration",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_command_allowlist_enforcements = _artifact_readbacks(
            "lab_cmd_allowlist_enforcements",
            "runner_command_allowlist_enforcement",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_sandbox_readiness = _artifact_readbacks(
            "lab_sandbox_readiness",
            "runner_sandbox_readiness",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_contracts = _artifact_readbacks(
            "lab_sandbox_provider_contracts",
            "sandbox_provider_contract",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_bindings = _artifact_readbacks(
            "lab_sandbox_provider_bindings",
            "sandbox_provider_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_selections = _artifact_readbacks(
            "lab_sandbox_provider_selections",
            "sandbox_provider_selection",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_verifier_preflights = _artifact_readbacks(
            "lab_sandbox_provider_verifier_preflights",
            "sandbox_provider_verifier",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_preflights = _artifact_readbacks(
            "lab_sandbox_provider_runtime_probe_preflights",
            "sandbox_provider_runtime_probe",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_harness_preflights = _artifact_readbacks(
            "lab_runtime_probe_harness_preflights",
            "sandbox_provider_runtime_probe_harness",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_runner_readiness = _artifact_readbacks(
            "lab_runtime_probe_runner_readiness",
            "sandbox_provider_runtime_probe_runner_readiness",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_runner_bindings = _artifact_readbacks(
            "lab_runtime_probe_runner_bindings",
            "sandbox_provider_runtime_probe_runner_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_runner_enforcements = _artifact_readbacks(
            "lab_runtime_probe_runner_enforcements",
            "sandbox_provider_runtime_probe_runner_enforcement",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_execution_boundaries = _artifact_readbacks(
            "lab_runtime_probe_execution_boundaries",
            "sandbox_provider_runtime_probe_execution_boundary",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_refusals = _artifact_readbacks(
            "lab_runtime_probe_refusals",
            "sandbox_provider_runtime_probe_refusal",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_approval_requests = _artifact_readbacks(
            "lab_runtime_probe_approval_requests",
            "sandbox_provider_runtime_probe_approval_request",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_approval_consumptions = _artifact_readbacks(
            "lab_runtime_probe_approval_consumptions",
            "sandbox_provider_runtime_probe_approval_consumption",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_invocation_boundaries = _artifact_readbacks(
            "lab_runtime_probe_invocation_boundaries",
            "sandbox_provider_runtime_probe_invocation_boundary",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_runner_pre_execution_boundaries = _artifact_readbacks(
            "lab_runtime_probe_preexec_boundaries",
            "sandbox_provider_runtime_probe_runner_pre_execution_boundary",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandbox_provider_runtime_probe_runner_control_bindings = _artifact_readbacks(
            "lab_runtime_probe_control_bindings",
            "sandbox_provider_runtime_probe_runner_control_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandboxed_rebuild_run_test_boundaries = _artifact_readbacks(
            "lab_sandboxed_rebuild_run_test_boundaries",
            "sandboxed_rebuild_run_test_boundary",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandboxed_rebuild_run_test_approval_requests = _artifact_readbacks(
            "lab_sandboxed_rebuild_run_test_approval_requests",
            "sandboxed_rebuild_run_test_approval_request",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandboxed_rebuild_run_test_approval_consumptions = _artifact_readbacks(
            "lab_sandboxed_rebuild_run_test_approval_consumptions",
            "sandboxed_rebuild_run_test_approval_consumption",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandboxed_rebuild_run_test_runner_bindings = _artifact_readbacks(
            "lab_sandboxed_rebuild_run_test_runner_bindings",
            "sandboxed_rebuild_run_test_runner_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        sandboxed_rebuild_run_test_sandbox_policies = _artifact_readbacks(
            "lab_sandboxed_rebuild_run_test_sandbox_policies",
            "sandboxed_rebuild_run_test_sandbox_policy",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        execution_receipt_write_readiness = _artifact_readbacks(
            "lab_receipt_write_readiness",
            "execution_receipt_write_readiness",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        execution_receipt_prewrite_bindings = _artifact_readbacks(
            "lab_receipt_prewrite_bindings",
            "execution_receipt_prewrite_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        execution_receipt_writer_preflights = _artifact_readbacks(
            "lab_receipt_writer_preflights",
            "execution_receipt_writer_preflight",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        run_boundary_preflights = _artifact_readbacks(
            "lab_run_boundary_preflights",
            "run_boundary_preflight",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        execution_receipts = _artifact_readbacks(
            "lab_execution_receipts",
            "execution_receipt",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_contracts = _artifact_readbacks(
            "lab_runner_contracts",
            "runner_contract",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_readiness = _artifact_readbacks(
            "lab_runner_readiness",
            "runner_readiness",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_bindings = _artifact_readbacks(
            "lab_runner_bindings",
            "runner_binding",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        runner_enforcements = _artifact_readbacks(
            "lab_runner_enforcement_preflights",
            "runner_enforcement",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        lab_execution_runs = _artifact_readbacks(
            "lab_execution_runs",
            "lab_execution_run",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        acquisitions = _artifact_readbacks(
            "acquisitions",
            "ingest_acquisition_run",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        capability_specs = _artifact_readbacks(
            "capability_specs",
            "capability_spec",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        builder_runs = _artifact_readbacks(
            "builder_runs",
            "builder_run",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        builder_proposal_reviews = _artifact_readbacks(
            "builder_proposal_reviews",
            "builder_proposal_review",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_apply_preflights = _artifact_readbacks(
            "forge_apply_preflights",
            "forge_apply_preflight",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_apply_approval_requests = _artifact_readbacks(
            "forge_apply_approval_requests",
            "forge_apply_approval_request",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_apply_approval_consumptions = _artifact_readbacks(
            "forge_apply_approval_consumptions",
            "forge_apply_approval_consumption",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_apply_boundaries = _artifact_readbacks(
            "forge_apply_boundaries",
            "forge_apply_boundary",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_validation_plans = _artifact_readbacks(
            "forge_validation_plans",
            "forge_validation_plan",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_synthesis_runs = _artifact_readbacks(
            "forge_synthesis_runs",
            "forge_synthesis_run",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_apply_dryruns = _artifact_readbacks(
            "forge_apply_dryruns",
            "forge_apply_dryrun",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        forge_synthesized_sources = _artifact_readbacks(
            "forge_synthesized_sources",
            "forge_synthesized_source",
            source_id=clean_source_id,
            limit=safe_limit,
        )
        return _display_payload(
            {
                "ok": True,
                "kind": "francis.ingest.readback",
                "status": "readback",
                "source_id": clean_source_id,
                "limit": safe_limit,
                "sources": [source.to_dict() for source in sources[:safe_limit]],
                "repo_maps": repo_maps,
                "capability_candidates": candidates,
                "lab_preflights": lab_preflights,
                "approval_consumption_preflights": approval_consumption_preflights,
                "approval_consumptions": approval_consumptions,
                "noop_runner_envelopes": noop_runner_envelopes,
                "noop_runner_transcripts": noop_runner_transcripts,
                "noop_runner_identity_bindings": noop_runner_identity_bindings,
                "source_mount_readiness": source_mount_readiness,
                "source_mount_contracts": source_mount_contracts,
                "approval_consumption_handoffs": approval_consumption_handoffs,
                "execution_receipt_sink_reservations": execution_receipt_sink_reservations,
                "runner_command_allowlists": runner_command_allowlists,
                "runner_command_allowlist_declarations": runner_command_allowlist_declarations,
                "runner_command_allowlist_enforcements": runner_command_allowlist_enforcements,
                "runner_sandbox_readiness": runner_sandbox_readiness,
                "sandbox_provider_contracts": sandbox_provider_contracts,
                "sandbox_provider_bindings": sandbox_provider_bindings,
                "sandbox_provider_selections": sandbox_provider_selections,
                "sandbox_provider_verifier_preflights": sandbox_provider_verifier_preflights,
                "sandbox_provider_runtime_probe_preflights": sandbox_provider_runtime_probe_preflights,
                "sandbox_provider_runtime_probe_harness_preflights": (
                    sandbox_provider_runtime_probe_harness_preflights
                ),
                "sandbox_provider_runtime_probe_runner_readiness": (sandbox_provider_runtime_probe_runner_readiness),
                "sandbox_provider_runtime_probe_runner_bindings": (sandbox_provider_runtime_probe_runner_bindings),
                "sandbox_provider_runtime_probe_runner_enforcements": (
                    sandbox_provider_runtime_probe_runner_enforcements
                ),
                "sandbox_provider_runtime_probe_execution_boundaries": (
                    sandbox_provider_runtime_probe_execution_boundaries
                ),
                "sandbox_provider_runtime_probe_refusals": sandbox_provider_runtime_probe_refusals,
                "sandbox_provider_runtime_probe_approval_requests": (sandbox_provider_runtime_probe_approval_requests),
                "sandbox_provider_runtime_probe_approval_consumptions": (
                    sandbox_provider_runtime_probe_approval_consumptions
                ),
                "sandbox_provider_runtime_probe_invocation_boundaries": (
                    sandbox_provider_runtime_probe_invocation_boundaries
                ),
                "sandbox_provider_runtime_probe_runner_pre_execution_boundaries": (
                    sandbox_provider_runtime_probe_runner_pre_execution_boundaries
                ),
                "sandbox_provider_runtime_probe_runner_control_bindings": (
                    sandbox_provider_runtime_probe_runner_control_bindings
                ),
                "sandboxed_rebuild_run_test_boundaries": sandboxed_rebuild_run_test_boundaries,
                "sandboxed_rebuild_run_test_approval_requests": sandboxed_rebuild_run_test_approval_requests,
                "sandboxed_rebuild_run_test_approval_consumptions": (sandboxed_rebuild_run_test_approval_consumptions),
                "sandboxed_rebuild_run_test_runner_bindings": sandboxed_rebuild_run_test_runner_bindings,
                "sandboxed_rebuild_run_test_sandbox_policies": sandboxed_rebuild_run_test_sandbox_policies,
                "execution_receipt_write_readiness": execution_receipt_write_readiness,
                "execution_receipt_prewrite_bindings": execution_receipt_prewrite_bindings,
                "execution_receipt_writer_preflights": execution_receipt_writer_preflights,
                "run_boundary_preflights": run_boundary_preflights,
                "execution_receipts": execution_receipts,
                "runner_contracts": runner_contracts,
                "runner_readiness": runner_readiness,
                "runner_bindings": runner_bindings,
                "runner_enforcements": runner_enforcements,
                "lab_execution_runs": lab_execution_runs,
                "acquisitions": acquisitions,
                "capability_specs": capability_specs,
                "builder_runs": builder_runs,
                "builder_proposal_reviews": builder_proposal_reviews,
                "forge_apply_preflights": forge_apply_preflights,
                "forge_apply_approval_requests": forge_apply_approval_requests,
                "forge_apply_approval_consumptions": forge_apply_approval_consumptions,
                "forge_apply_boundaries": forge_apply_boundaries,
                "forge_validation_plans": forge_validation_plans,
                "forge_synthesis_runs": forge_synthesis_runs,
                "forge_apply_dryruns": forge_apply_dryruns,
                "forge_synthesized_sources": forge_synthesized_sources,
                "counts": {
                    "sources": len(sources[:safe_limit]),
                    "repo_maps": len(repo_maps),
                    "capability_candidates": len(candidates),
                    "lab_preflights": len(lab_preflights),
                    "approval_consumption_preflights": len(approval_consumption_preflights),
                    "approval_consumptions": len(approval_consumptions),
                    "noop_runner_envelopes": len(noop_runner_envelopes),
                    "noop_runner_transcripts": len(noop_runner_transcripts),
                    "noop_runner_identity_bindings": len(noop_runner_identity_bindings),
                    "source_mount_readiness": len(source_mount_readiness),
                    "source_mount_contracts": len(source_mount_contracts),
                    "approval_consumption_handoffs": len(approval_consumption_handoffs),
                    "execution_receipt_sink_reservations": len(execution_receipt_sink_reservations),
                    "runner_command_allowlists": len(runner_command_allowlists),
                    "runner_command_allowlist_declarations": len(runner_command_allowlist_declarations),
                    "runner_command_allowlist_enforcements": len(runner_command_allowlist_enforcements),
                    "runner_sandbox_readiness": len(runner_sandbox_readiness),
                    "sandbox_provider_contracts": len(sandbox_provider_contracts),
                    "sandbox_provider_bindings": len(sandbox_provider_bindings),
                    "sandbox_provider_selections": len(sandbox_provider_selections),
                    "sandbox_provider_verifier_preflights": len(sandbox_provider_verifier_preflights),
                    "sandbox_provider_runtime_probe_preflights": len(sandbox_provider_runtime_probe_preflights),
                    "sandbox_provider_runtime_probe_harness_preflights": len(
                        sandbox_provider_runtime_probe_harness_preflights
                    ),
                    "sandbox_provider_runtime_probe_runner_readiness": len(
                        sandbox_provider_runtime_probe_runner_readiness
                    ),
                    "sandbox_provider_runtime_probe_runner_bindings": len(
                        sandbox_provider_runtime_probe_runner_bindings
                    ),
                    "sandbox_provider_runtime_probe_runner_enforcements": len(
                        sandbox_provider_runtime_probe_runner_enforcements
                    ),
                    "sandbox_provider_runtime_probe_execution_boundaries": len(
                        sandbox_provider_runtime_probe_execution_boundaries
                    ),
                    "sandbox_provider_runtime_probe_refusals": len(sandbox_provider_runtime_probe_refusals),
                    "sandbox_provider_runtime_probe_approval_requests": len(
                        sandbox_provider_runtime_probe_approval_requests
                    ),
                    "sandbox_provider_runtime_probe_approval_consumptions": len(
                        sandbox_provider_runtime_probe_approval_consumptions
                    ),
                    "sandbox_provider_runtime_probe_invocation_boundaries": len(
                        sandbox_provider_runtime_probe_invocation_boundaries
                    ),
                    "sandbox_provider_runtime_probe_runner_pre_execution_boundaries": len(
                        sandbox_provider_runtime_probe_runner_pre_execution_boundaries
                    ),
                    "sandbox_provider_runtime_probe_runner_control_bindings": len(
                        sandbox_provider_runtime_probe_runner_control_bindings
                    ),
                    "sandboxed_rebuild_run_test_boundaries": len(sandboxed_rebuild_run_test_boundaries),
                    "sandboxed_rebuild_run_test_approval_requests": len(sandboxed_rebuild_run_test_approval_requests),
                    "sandboxed_rebuild_run_test_approval_consumptions": len(
                        sandboxed_rebuild_run_test_approval_consumptions
                    ),
                    "sandboxed_rebuild_run_test_runner_bindings": len(sandboxed_rebuild_run_test_runner_bindings),
                    "sandboxed_rebuild_run_test_sandbox_policies": len(sandboxed_rebuild_run_test_sandbox_policies),
                    "execution_receipt_write_readiness": len(execution_receipt_write_readiness),
                    "execution_receipt_prewrite_bindings": len(execution_receipt_prewrite_bindings),
                    "execution_receipt_writer_preflights": len(execution_receipt_writer_preflights),
                    "run_boundary_preflights": len(run_boundary_preflights),
                    "execution_receipts": len(execution_receipts),
                    "runner_contracts": len(runner_contracts),
                    "runner_readiness": len(runner_readiness),
                    "runner_bindings": len(runner_bindings),
                    "runner_enforcements": len(runner_enforcements),
                    "lab_execution_runs": len(lab_execution_runs),
                    "acquisitions": len(acquisitions),
                    "capability_specs": len(capability_specs),
                    "builder_runs": len(builder_runs),
                    "builder_proposal_reviews": len(builder_proposal_reviews),
                    "forge_apply_preflights": len(forge_apply_preflights),
                    "forge_apply_approval_requests": len(forge_apply_approval_requests),
                    "forge_apply_approval_consumptions": len(forge_apply_approval_consumptions),
                    "forge_apply_boundaries": len(forge_apply_boundaries),
                    "forge_validation_plans": len(forge_validation_plans),
                    "forge_synthesis_runs": len(forge_synthesis_runs),
                    "forge_apply_dryruns": len(forge_apply_dryruns),
                    "forge_synthesized_sources": len(forge_synthesized_sources),
                },
                "execution": _no_lab_execution_payload(reason="readback_only_no_execution"),
                "receipts_written": False,
                "artifacts_written": False,
            }
        )

    def add_source(
        self,
        path: str | Path,
        *,
        actor: str = "francis/system",
        inspect_repos: bool = True,
    ) -> dict[str, Any]:
        target = canonical_path(path)
        if not target.exists():
            receipt, receipt_path = self.receipts.write(
                operation="source.add",
                source_id="",
                actor=actor,
                input_paths=[display_path(path)],
                result_status="failed",
                errors=["source_path_not_found"],
                validation_performed=["path_exists_check"],
            )
            return {
                "ok": False,
                "status": "failed",
                "error": "source_path_not_found",
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
            }

        source_type = classify_source(target)
        fingerprint, scan = source_fingerprint(target)
        source_id = source_id_for_path(target, source_type)
        existing = self.sources.get(source_id)
        created_at = existing.created_at if existing is not None else utc_now()
        metadata = source_metadata_from_scan(scan)
        metadata["classification"] = {
            "type": source_type,
            "repo_detection": detect_repo(target) if target.is_dir() else {"is_repo": False, "reason": "not_directory"},
            "inspection_mode": "read_only_no_network_no_execution",
        }
        metadata["lab_boundary"] = current_lab_boundary().to_dict()
        record = SourceRecord(
            id=source_id,
            type=source_type,
            original_path=display_path(path),
            canonical_path=str(target),
            created_at=created_at,
            updated_at=utc_now(),
            fingerprint=fingerprint,
            status="indexed",
            permissions=SourcePermissionProfile(),
            metadata=metadata,
            derived_artifacts=list(existing.derived_artifacts) if existing is not None else [],
            receipts=list(existing.receipts) if existing is not None else [],
        )
        receipt, receipt_path = self.receipts.write(
            operation="source.add",
            source_id=source_id,
            actor=actor,
            input_paths=[record.canonical_path],
            input_hashes=[fingerprint],
            files_inspected_count=len(scan.files),
            result_status="indexed",
            warnings=scan.warnings,
            generated_artifact_paths=[],
            validation_performed=["path_exists_check", "bounded_fingerprint_scan", "repo_marker_classification"],
        )
        record = replace(record, receipts=_append_unique(record.receipts, str(receipt_path)))
        repo_result: dict[str, Any] | None = None
        if source_type == "repo" and inspect_repos:
            repo_result = self.inspect_repo(source_id, actor=actor, _record=record)
            refreshed = self.sources.get(source_id)
            if refreshed is not None:
                record = refreshed
        else:
            self.sources.upsert(record)
        return _display_payload(
            {
                "ok": True,
                "status": record.status,
                "source": record.to_dict(),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "repo": repo_result,
            }
        )

    def inspect_repo(
        self,
        source_or_path: str | Path,
        *,
        actor: str = "francis/system",
        _record: SourceRecord | None = None,
    ) -> dict[str, Any]:
        record = _record or self._record_from_source_or_path(source_or_path, actor=actor)
        if record.type != "repo":
            receipt, receipt_path = self.receipts.write(
                operation="repo.inspect",
                source_id=record.id,
                actor=actor,
                input_paths=[record.canonical_path],
                input_hashes=[record.fingerprint],
                result_status="failed",
                errors=["source_is_not_repo"],
                validation_performed=["source_type_check"],
            )
            updated = replace(record, status="failed", receipts=_append_unique(record.receipts, str(receipt_path)))
            self.sources.upsert(updated)
            return {
                "ok": False,
                "status": "failed",
                "error": "source_is_not_repo",
                "source": updated.to_dict(),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
            }

        repo_map = self.repo_adapter.inspect(record.canonical_path, source_id=record.id)
        repo_map_path = write_ingest_artifact("repo_maps", record.id, repo_map.to_dict())
        candidates_result = self.extract_candidates(record.id, repo_map=repo_map, actor=actor, _record=record)
        generated_artifacts = [str(repo_map_path)]
        candidate_artifact_path = _safe_str(candidates_result.get("artifact_path")).strip()
        if candidate_artifact_path:
            generated_artifacts.append(candidate_artifact_path)
        receipt, receipt_path = self.receipts.write(
            operation="repo.inspect",
            source_id=record.id,
            actor=actor,
            input_paths=[record.canonical_path],
            input_hashes=[record.fingerprint],
            files_inspected_count=repo_map.files_inspected_count,
            result_status="inspected",
            warnings=repo_map.warnings,
            generated_artifact_paths=generated_artifacts,
            validation_performed=[
                "bounded_repo_map_scan",
                "manifest_read_only_parse",
                "local_git_metadata_probe_no_network",
                "risk_signal_extraction",
            ],
        )
        metadata = {
            **record.metadata,
            "repo_map_path": str(repo_map_path),
            "repo_risk_signal_count": len(repo_map.risk_signals),
            "capability_candidate_artifact_path": candidate_artifact_path,
            "capability_candidate_count": len(candidates_result.get("candidates") or []),
            "last_repo_inspection_receipt_path": str(receipt_path),
            "last_capability_extraction_receipt_path": _safe_str(candidates_result.get("receipt_path")).strip(),
        }
        artifacts = _append_unique(record.derived_artifacts, str(repo_map_path), candidate_artifact_path)
        receipts = _append_unique(record.receipts, str(receipt_path))
        candidate_receipt_path = _safe_str(candidates_result.get("receipt_path")).strip()
        if candidate_receipt_path:
            receipts = _append_unique(receipts, candidate_receipt_path)
        updated = replace(
            record,
            status="indexed",
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=artifacts,
            receipts=receipts,
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": "inspected",
                "source": updated.to_dict(),
                "repo_map": repo_map.to_dict(),
                "repo_map_path": str(repo_map_path),
                "candidates": candidates_result.get("candidates") or [],
                "candidate_artifact_path": candidate_artifact_path,
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": {
                    "ran_repo_scripts": False,
                    "ran_install": False,
                    "ran_build": False,
                    "ran_tests": False,
                    "network_accessed": False,
                    "lab_boundary": current_lab_boundary().to_dict(),
                },
            }
        )

    def extract_candidates(
        self,
        source_or_path: str | Path,
        *,
        repo_map: RepoMap | None = None,
        actor: str = "francis/system",
        _record: SourceRecord | None = None,
    ) -> dict[str, Any]:
        record = _record or self._record_from_source_or_path(source_or_path, actor=actor)
        loaded_map = repo_map or self._load_repo_map(record)
        if loaded_map is None:
            inspected = self.inspect_repo(record.id, actor=actor, _record=record)
            loaded_map = RepoMap.from_dict(inspected.get("repo_map"))
            if loaded_map is None:
                return {
                    "ok": False,
                    "status": "failed",
                    "error": "repo_map_unavailable",
                    "source": record.to_dict(),
                }
        candidates = self.extractor.extract(loaded_map)
        candidate_dicts = [candidate.to_dict() for candidate in candidates]
        artifact_path = write_ingest_artifact(
            "capabilities", record.id, {"source_id": record.id, "candidates": candidate_dicts}
        )
        receipt, receipt_path = self.receipts.write(
            operation="capability.extract",
            source_id=record.id,
            actor=actor,
            input_paths=[record.canonical_path],
            input_hashes=[record.fingerprint],
            files_inspected_count=loaded_map.files_inspected_count,
            result_status="drafted",
            warnings=loaded_map.warnings,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=["capability_candidate_extraction_no_execution"],
        )
        candidates_with_receipt: list[CapabilityCandidate] = [
            replace(candidate, receipts=_append_unique(candidate.receipts, str(receipt_path)))
            for candidate in candidates
        ]
        self.capabilities.replace_for_source(record.id, candidates_with_receipt)
        metadata = {
            **record.metadata,
            "capability_candidate_artifact_path": str(artifact_path),
            "capability_candidate_count": len(candidates_with_receipt),
            "last_capability_extraction_receipt_path": str(receipt_path),
        }
        updated = replace(
            record,
            status="indexed",
            updated_at=utc_now(),
            metadata=metadata,
            derived_artifacts=_append_unique(record.derived_artifacts, str(artifact_path)),
            receipts=_append_unique(record.receipts, str(receipt_path)),
        )
        self.sources.upsert(updated)
        return _display_payload(
            {
                "ok": True,
                "status": "drafted",
                "source": updated.to_dict(),
                "candidates": [candidate.to_dict() for candidate in candidates_with_receipt],
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": {
                    "registered_for_use": False,
                    "promoted": False,
                    "validated": False,
                    "ran_repo_scripts": False,
                    "lab_boundary": current_lab_boundary().to_dict(),
                },
            }
        )

    def _record_from_source_or_path(self, value: str | Path, *, actor: str) -> SourceRecord:
        text = _safe_str(value).strip()
        record = self.sources.get(text)
        if record is not None:
            return record
        target = canonical_path(value)
        if target.exists():
            source_type = classify_source(target)
            record = self.sources.get(source_id_for_path(target, source_type))
            if record is not None:
                return record
        result = self.add_source(value, actor=actor, inspect_repos=False)
        raw_source = result.get("source")
        record = SourceRecord.from_dict(raw_source)
        if record is None:
            raise ValueError(_safe_str(result.get("error")).strip() or "source_record_unavailable")
        return record

    def _load_repo_map(self, record: SourceRecord) -> RepoMap | None:
        raw_path = _safe_str(record.metadata.get("repo_map_path")).strip()
        if raw_path:
            loaded = RepoMap.from_dict(_read_json(raw_path))
            if loaded is not None:
                return loaded
        return None

    def _candidate_from_ref(
        self,
        record: SourceRecord,
        candidate_ref: str,
        *,
        actor: str,
    ) -> CapabilityCandidate | None:
        candidates = self.capabilities.list_for_source(record.id)
        if not candidates:
            result = self.extract_candidates(record.id, actor=actor, _record=record)
            candidates = []
            for item in result.get("candidates") or []:
                candidate = CapabilityCandidate.from_dict(item)
                if candidate is not None:
                    candidates.append(candidate)
        target = _safe_str(candidate_ref).strip()
        target_lower = target.lower()
        for candidate in candidates:
            if candidate.id == target or candidate.name.lower() == target_lower:
                return candidate
        return None

    def _replace_candidate(
        self,
        source_id: str,
        candidate_id: str,
        updated_candidate: CapabilityCandidate,
    ) -> None:
        candidates = self.capabilities.list_for_source(source_id)
        replaced = False
        out: list[CapabilityCandidate] = []
        for candidate in candidates:
            if candidate.id == candidate_id:
                out.append(updated_candidate)
                replaced = True
            else:
                out.append(candidate)
        if not replaced:
            out.append(updated_candidate)
        self.capabilities.replace_for_source(source_id, out)
