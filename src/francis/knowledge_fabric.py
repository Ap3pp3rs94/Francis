from __future__ import annotations

from typing import Any

from francis.apprenticeship import apprenticeship_stage11_operator_stage_closure_decision_readback

STAGE12_KNOWLEDGE_FABRIC_STAGE = "Stage 12 / Knowledge Fabric"
KNOWLEDGE_FABRIC_STATUS_KIND = "francis.stage12.knowledge_fabric.status"
KNOWLEDGE_FABRIC_ARTIFACT_INDEX_CONTRACT_KIND = "francis.stage12.knowledge_fabric.artifact_index_contract"


def knowledge_fabric_status_snapshot() -> dict[str, Any]:
    stage11 = apprenticeship_stage11_operator_stage_closure_decision_readback(limit=5)
    stage11_closed = bool(stage11.get("stage11_closed_by_receipt"))
    artifact_contract = knowledge_fabric_artifact_index_contract()
    artifact_contract_ready = bool(artifact_contract.get("artifact_index_contract_ready"))
    deliverables = [
        _deliverable(
            "stage11_ledger_closure_backstop",
            "Stage 11 Apprenticeship closure receipt readback is present",
            stage11_closed,
            "ready" if stage11_closed else "blocked",
            "stage11_ledger_closure",
        ),
        _deliverable(
            "artifact_index_contract",
            "Artifact classes and citation fields are explicit before indexing",
            artifact_contract_ready,
            "ready" if artifact_contract_ready else "blocked",
            "stage12_artifact_index_contract",
        ),
        _deliverable(
            "retrieval_layer",
            "Retrieval can return bounded local evidence references",
            False,
            "pending",
            "stage12_retrieval_layer",
        ),
        _deliverable(
            "local_evidence_citations",
            "Answers can cite local evidence without exposing raw secrets",
            False,
            "pending",
            "stage12_local_evidence_citations",
        ),
        _deliverable(
            "retention_model",
            "Indexed artifacts carry retention policy and expiry posture",
            False,
            "pending",
            "stage12_retention_model",
        ),
    ]
    ready_count = sum(1 for item in deliverables if bool(item["ready"]))
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_STATUS_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "stage12_artifact_index_contract_ready"
        if stage11_closed and artifact_contract_ready
        else "awaiting_stage11_ledger_closure",
        "stage11_closed_by_receipt": stage11_closed,
        "stage11_latest_closure_receipt_id": _safe_text(stage11.get("latest_receipt_id")),
        "artifact_index_contract_ready": artifact_contract_ready,
        "artifact_indexing_active": False,
        "retrieval_layer_ready": False,
        "local_evidence_citations_ready": False,
        "retention_model_ready": False,
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/knowledge-fabric/status",
            "artifact_index_contract": "/knowledge-fabric/artifact-index-contract",
            "memory_timeline": "/memory/timeline/list",
            "artifact_inspection": "/artifacts/inspect",
            "continuity_ledger": "/continuity/ledger",
        },
        "governance": {
            "read_only": True,
            "requires_stage11_ledger_closure": True,
            "does_not_index_files": True,
            "does_not_write_memory": True,
            "does_not_replicate_data": True,
            "does_not_grant_authority": True,
        },
        "next_smallest_truthful_gap": "stage12_artifact_index_projection"
        if stage11_closed and artifact_contract_ready
        else "stage11_ledger_closure",
    }


def knowledge_fabric_artifact_index_contract() -> dict[str, Any]:
    stage11 = apprenticeship_stage11_operator_stage_closure_decision_readback(limit=5)
    stage11_closed = bool(stage11.get("stage11_closed_by_receipt"))
    artifact_classes = [
        _artifact_class(
            "receipts",
            "Governed decision, approval, and stage-closure receipts",
            ("/approvals", "/apprenticeship/stage-closure-decisions"),
            ("receipt_id", "actor", "decision", "recorded_ts", "source_id", "governance"),
            "receipt_id",
        ),
        _artifact_class(
            "missions",
            "Mission and operation continuity records",
            ("/missions", "/continuity/briefing"),
            ("mission_id", "operation_id", "trace_id", "run_id", "artifact_dir"),
            "mission_id",
        ),
        _artifact_class(
            "incidents",
            "Observer incident snapshots and remediation context",
            ("/continuity/briefing",),
            ("incident_id", "source_id", "observed_at", "status", "severity"),
            "incident_id",
        ),
        _artifact_class(
            "staged_capabilities",
            "Forge candidates and capability handoff evidence",
            ("/forge", "/apprenticeship/forge-handoff-receipts"),
            ("capability_id", "receipt_id", "risk_tier", "documentation_review", "test_candidate_review"),
            "receipt_id",
        ),
        _artifact_class(
            "observations",
            "Telemetry, observer, and operator-visible state observations",
            ("/telemetry/status", "/continuity/briefing"),
            ("source_id", "observed_ts", "status", "trace_id", "artifact_dir"),
            "source_id",
        ),
        _artifact_class(
            "teaching_outputs",
            "Apprenticeship teaching, replay, skillization, and handoff receipts",
            (
                "/apprenticeship/teaching-session-receipts",
                "/apprenticeship/replay-receipts",
                "/apprenticeship/skillization-artifact-receipts",
                "/apprenticeship/forge-handoff-receipts",
            ),
            ("receipt_id", "teaching_session_receipt_id", "replay_receipt_id", "skillization_artifact_receipt_id"),
            "receipt_id",
        ),
        _artifact_class(
            "execution_traces",
            "Execution, supervised operation, and artifact handles",
            ("/operations", "/artifacts/inspect"),
            ("operation_id", "trace_id", "run_id", "artifact_dir", "approval_id"),
            "trace_id",
        ),
    ]
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_ARTIFACT_INDEX_CONTRACT_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "ready" if stage11_closed else "blocked",
        "artifact_index_contract_ready": stage11_closed,
        "stage11_closed_by_receipt": stage11_closed,
        "stage11_latest_closure_receipt_id": _safe_text(stage11.get("latest_receipt_id")),
        "artifact_classes": artifact_classes,
        "artifact_class_count": len(artifact_classes),
        "required_citation_fields": [
            "artifact_class",
            "source_route",
            "reference_id",
            "local_handle",
            "evidence_summary",
            "observed_ts",
            "redacted",
        ],
        "citation_rules": {
            "local_evidence_only": True,
            "must_include_reference_id": True,
            "must_include_source_route": True,
            "must_redact_secret_text": True,
            "must_preserve_trace_lineage": True,
            "may_not_claim_unindexed_evidence": True,
        },
        "retention_contract": {
            "required": True,
            "fields": ["policy", "class", "until", "ttl_seconds"],
            "default_next_gap": "stage12_retention_model",
        },
        "existing_read_surfaces": {
            "memory_timeline": "/memory/timeline/list",
            "artifact_inspection": "/artifacts/inspect",
            "continuity_ledger": "/continuity/ledger",
        },
        "writes_index": False,
        "writes_memory": False,
        "scans_files": False,
        "replicates_data": False,
        "grants_authority": False,
        "governance": {
            "read_only": True,
            "requires_stage11_ledger_closure": True,
            "artifact_classes_explicit": True,
            "citation_contract_explicit": True,
            "retention_contract_explicit": True,
            "does_not_write_index": True,
            "does_not_write_memory": True,
            "does_not_scan_files": True,
            "does_not_replicate_data": True,
            "grants_authority": False,
        },
        "next_smallest_truthful_gap": "stage12_artifact_index_projection"
        if stage11_closed
        else "stage11_ledger_closure",
    }


def _artifact_class(
    artifact_id: str,
    description: str,
    source_routes: tuple[str, ...],
    citation_fields: tuple[str, ...],
    primary_reference_field: str,
) -> dict[str, Any]:
    return {
        "id": artifact_id,
        "description": description,
        "source_routes": list(source_routes),
        "citation_fields": list(citation_fields),
        "primary_reference_field": primary_reference_field,
        "index_status": "contract_only",
        "requires_redaction": True,
        "requires_retention": True,
        "requires_trace_lineage": True,
    }


def _deliverable(
    deliverable_id: str,
    label: str,
    ready: bool,
    status: str,
    next_gap: str,
) -> dict[str, Any]:
    return {
        "id": deliverable_id,
        "label": label,
        "ready": ready,
        "status": status,
        "next_smallest_truthful_gap": next_gap,
    }


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""
