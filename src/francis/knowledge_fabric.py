from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.apprenticeship import apprenticeship_stage11_operator_stage_closure_decision_readback
from francis.chat.continuity.ledger import tail as continuity_tail
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

STAGE12_KNOWLEDGE_FABRIC_STAGE = "Stage 12 / Knowledge Fabric"
KNOWLEDGE_FABRIC_STATUS_KIND = "francis.stage12.knowledge_fabric.status"
KNOWLEDGE_FABRIC_ARTIFACT_INDEX_CONTRACT_KIND = "francis.stage12.knowledge_fabric.artifact_index_contract"
KNOWLEDGE_FABRIC_ARTIFACT_INDEX_PROJECTION_KIND = "francis.stage12.knowledge_fabric.artifact_index_projection"
KNOWLEDGE_FABRIC_RETRIEVAL_PREVIEW_KIND = "francis.stage12.knowledge_fabric.retrieval_preview"
KNOWLEDGE_FABRIC_LOCAL_EVIDENCE_CITATIONS_KIND = "francis.stage12.knowledge_fabric.local_evidence_citations"
KNOWLEDGE_FABRIC_RETENTION_MODEL_KIND = "francis.stage12.knowledge_fabric.retention_model"
KNOWLEDGE_FABRIC_COMPLETION_REVIEW_KIND = "francis.stage12.knowledge_fabric.completion_review"
KNOWLEDGE_FABRIC_STAGE_CLOSURE_DECISION_KIND = "francis.stage12.knowledge_fabric.stage12_closure_decision_receipt"
KNOWLEDGE_FABRIC_STAGE_CLOSURE_DECISIONS_KIND = "francis.stage12.knowledge_fabric.stage12_closure_decision_receipts"
KNOWLEDGE_FABRIC_STAGE_CLOSURE_SCOPE = "knowledge_fabric.stage12.closure.write"


def knowledge_fabric_status_snapshot() -> dict[str, Any]:
    stage11 = apprenticeship_stage11_operator_stage_closure_decision_readback(limit=5)
    stage11_closed = bool(stage11.get("stage11_closed_by_receipt"))
    stage12_closure = knowledge_fabric_stage12_operator_stage_closure_decision_readback(limit=5)
    stage12_closed = bool(stage12_closure.get("stage12_closed_by_receipt"))
    artifact_contract = knowledge_fabric_artifact_index_contract()
    artifact_contract_ready = bool(artifact_contract.get("artifact_index_contract_ready"))
    artifact_projection = knowledge_fabric_artifact_index_projection(limit=1, memory_limit=5, ledger_limit=5)
    artifact_projection_ready = bool(artifact_projection.get("artifact_index_projection_ready"))
    retrieval_preview = knowledge_fabric_retrieval_preview(query="", limit=1, memory_limit=5, ledger_limit=5)
    retrieval_layer_ready = bool(retrieval_preview.get("retrieval_layer_ready"))
    local_citations = knowledge_fabric_local_evidence_citations(query="", limit=1, memory_limit=5, ledger_limit=5)
    local_evidence_citations_ready = bool(local_citations.get("local_evidence_citations_ready"))
    retention_model = knowledge_fabric_retention_model(query="", limit=1, memory_limit=5, ledger_limit=5)
    retention_model_ready = bool(retention_model.get("retention_model_ready"))
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
            "artifact_index_projection",
            "Existing local evidence can be projected into bounded citations",
            artifact_projection_ready,
            "ready" if artifact_projection_ready else "pending",
            "stage12_artifact_index_projection",
        ),
        _deliverable(
            "retrieval_layer",
            "Retrieval can return bounded local evidence references",
            retrieval_layer_ready,
            "ready" if retrieval_layer_ready else "pending",
            "stage12_retrieval_layer",
        ),
        _deliverable(
            "local_evidence_citations",
            "Answers can cite local evidence without exposing raw secrets",
            local_evidence_citations_ready,
            "ready" if local_evidence_citations_ready else "pending",
            "stage12_local_evidence_citations",
        ),
        _deliverable(
            "retention_model",
            "Indexed artifacts carry retention policy and expiry posture",
            retention_model_ready,
            "ready" if retention_model_ready else "pending",
            "stage12_retention_model",
        ),
    ]
    ready_count = sum(1 for item in deliverables if bool(item["ready"]))
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_STATUS_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "stage12_closed_by_receipt"
        if stage12_closed
        else "stage12_retention_model_ready"
        if stage11_closed
        and artifact_contract_ready
        and artifact_projection_ready
        and retrieval_layer_ready
        and local_evidence_citations_ready
        and retention_model_ready
        else "stage12_local_evidence_citation_surface_ready"
        if stage11_closed
        and artifact_contract_ready
        and artifact_projection_ready
        and retrieval_layer_ready
        and local_evidence_citations_ready
        else "stage12_retrieval_layer_ready"
        if stage11_closed and artifact_contract_ready and artifact_projection_ready and retrieval_layer_ready
        else "stage12_artifact_index_projection_ready"
        if stage11_closed and artifact_contract_ready and artifact_projection_ready
        else "stage12_artifact_index_contract_ready"
        if stage11_closed and artifact_contract_ready
        else "awaiting_stage11_ledger_closure",
        "stage11_closed_by_receipt": stage11_closed,
        "stage11_latest_closure_receipt_id": _safe_text(stage11.get("latest_receipt_id")),
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(stage12_closure.get("latest_receipt_id")),
        "artifact_index_contract_ready": artifact_contract_ready,
        "artifact_index_projection_ready": artifact_projection_ready,
        "artifact_index_projection_count": _safe_int(artifact_projection.get("total")),
        "artifact_indexing_active": False,
        "retrieval_layer_ready": retrieval_layer_ready,
        "local_evidence_citations_ready": local_evidence_citations_ready,
        "retention_model_ready": retention_model_ready,
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "routes": {
            "status": "/knowledge-fabric/status",
            "artifact_index_contract": "/knowledge-fabric/artifact-index-contract",
            "artifact_index_projection": "/knowledge-fabric/artifact-index-projection",
            "retrieval_preview": "/knowledge-fabric/retrieval-preview",
            "local_evidence_citations": "/knowledge-fabric/local-evidence-citations",
            "retention_model": "/knowledge-fabric/retention-model",
            "completion_review": "/knowledge-fabric/completion-review",
            "stage_closure_decisions": "/knowledge-fabric/stage-closure-decisions",
            "stage_closure_decision": "/knowledge-fabric/stage-closure-decision",
            "memory_timeline": "/memory/timeline/list",
            "artifact_inspection": "/artifacts/inspect",
            "continuity_ledger": "/continuity/ledger",
        },
        "governance": {
            "read_only": True,
            "requires_stage11_ledger_closure": True,
            "does_not_index_files": True,
            "does_not_write_memory": True,
            "does_not_delete_data": True,
            "does_not_mutate_retention": True,
            "does_not_replicate_data": True,
            "does_not_grant_authority": True,
        },
        "next_smallest_truthful_gap": "stage12_ledger_closure"
        if stage12_closed
        else "stage12_completion_review"
        if stage11_closed
        and artifact_contract_ready
        and artifact_projection_ready
        and retrieval_layer_ready
        and local_evidence_citations_ready
        and retention_model_ready
        else "stage12_retention_model"
        if stage11_closed
        and artifact_contract_ready
        and artifact_projection_ready
        and retrieval_layer_ready
        and local_evidence_citations_ready
        else "stage12_local_evidence_citation_surface"
        if stage11_closed and artifact_contract_ready and artifact_projection_ready and retrieval_layer_ready
        else "stage12_retrieval_layer"
        if stage11_closed and artifact_contract_ready and artifact_projection_ready
        else "stage12_artifact_index_projection"
        if stage11_closed and artifact_contract_ready
        else "stage11_ledger_closure",
    }


def read_knowledge_fabric_stage12_operator_stage_closure_decisions(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_stage12_operator_stage_closure_decision_path(), limit=_safe_limit(limit, default=20))


def knowledge_fabric_stage12_operator_stage_closure_decision_readback(*, limit: int = 20) -> dict[str, Any]:
    items = read_knowledge_fabric_stage12_operator_stage_closure_decisions(limit=limit)
    latest = items[-1] if items else {}
    stage12_closed = bool(latest.get("stage12_closed_by_receipt"))
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_STAGE_CLOSURE_DECISIONS_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "closed" if stage12_closed else "open" if items else "empty",
        "items": items,
        "count": len(items),
        "latest_receipt_id": _safe_text(latest.get("receipt_id")),
        "latest_decision": _safe_text(latest.get("decision")),
        "stage12_closed_by_receipt": stage12_closed,
        "marks_runtime_stage_state": False,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_memory": False,
        "writes_index": False,
        "deletes_data": False,
        "mutates_retention": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "stage_closure_decision_receipt_readback": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_memory": True,
            "does_not_write_index": True,
            "does_not_delete_data": True,
            "does_not_mutate_retention": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage12_ledger_closure"
        if stage12_closed
        else "stage12_operator_stage_closure_decision"
        if items
        else "stage12_completion_review",
    }


def knowledge_fabric_completion_review(
    *,
    query: Any = "",
    limit: int = 25,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    safe_query = _redact_text(query)[:500]
    safe_limit = _safe_limit(limit, default=25)
    status = knowledge_fabric_status_snapshot()
    projection = knowledge_fabric_artifact_index_projection(
        limit=safe_limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    retrieval = knowledge_fabric_retrieval_preview(
        query=safe_query,
        limit=safe_limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    citations = knowledge_fabric_local_evidence_citations(
        query=safe_query,
        limit=safe_limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    retention = knowledge_fabric_retention_model(
        query=safe_query,
        limit=safe_limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    citation_items = [item for item in _as_list(citations.get("citations")) if isinstance(item, dict)]
    projection_items = [item for item in _as_list(projection.get("citations")) if isinstance(item, dict)]
    checks = _completion_review_checks(
        status=status,
        projection=projection,
        retrieval=retrieval,
        citations=citations,
        retention=retention,
        citation_items=citation_items,
        projection_items=projection_items,
    )
    review_ready = all(bool(check.get("passed")) for check in checks)
    stage12_closure = knowledge_fabric_stage12_operator_stage_closure_decision_readback(limit=5)
    stage12_closed = bool(stage12_closure.get("stage12_closed_by_receipt"))
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_COMPLETION_REVIEW_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "ready" if review_ready else "blocked",
        "query": safe_query,
        "stage12_completion_review_ready": review_ready,
        "stage_closure_decision_required": review_ready and not stage12_closed,
        "stage11_closed_by_receipt": bool(status.get("stage11_closed_by_receipt")),
        "stage11_latest_closure_receipt_id": _safe_text(status.get("stage11_latest_closure_receipt_id")),
        "stage12_closed_by_receipt": stage12_closed,
        "stage12_latest_closure_receipt_id": _safe_text(stage12_closure.get("latest_receipt_id")),
        "artifact_index_contract_ready": bool(status.get("artifact_index_contract_ready")),
        "artifact_index_projection_ready": bool(projection.get("artifact_index_projection_ready")),
        "artifact_index_projection_count": _safe_int(projection.get("total")),
        "retrieval_layer_ready": bool(retrieval.get("retrieval_layer_ready")),
        "retrieval_total": _safe_int(retrieval.get("total")),
        "local_evidence_citations_ready": bool(citations.get("local_evidence_citations_ready")),
        "citation_total": len(citation_items),
        "retention_model_ready": bool(retention.get("retention_model_ready")),
        "retention_declared_count": _safe_int(retention.get("retention_declared_count")),
        "retention_missing_count": _safe_int(retention.get("retention_missing_count")),
        "artifact_class_counts": _count_by(projection_items, "artifact_class"),
        "source_counts": _count_by(projection_items, "source_route"),
        "retention_policy_counts": _as_dict(retention.get("retention_policy_counts")),
        "done_criteria": {
            "francis_cites_local_evidence": bool(citation_items),
            "memory_becomes_operational": bool(projection_items),
            "recommendations_and_summaries_are_grounded": bool(citation_items)
            and bool(retrieval.get("retrieval_layer_ready")),
            "cross_artifact_continuity_becomes_real": _cross_artifact_continuity_ready(projection_items),
        },
        "checks": checks,
        "reads_memory_timeline": bool(projection.get("reads_memory_timeline")),
        "reads_continuity_ledger": bool(projection.get("reads_continuity_ledger")),
        "writes_memory": False,
        "writes_index": False,
        "writes_receipts": False,
        "generates_answer": False,
        "uses_model": False,
        "scans_files": False,
        "replicates_data": False,
        "deletes_data": False,
        "mutates_retention": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "marks_stage_closed": False,
        "governance": _completion_review_governance(),
        "routes": _as_dict(status.get("routes")),
        "next_smallest_truthful_gap": "stage12_ledger_closure"
        if stage12_closed
        else "stage12_operator_stage_closure_decision"
        if review_ready
        else _completion_review_next_gap(checks=checks, status=status),
    }


def record_knowledge_fabric_stage12_operator_stage_closure_decision(
    *,
    actor: Any,
    reason: Any,
    decision: Any,
    review: dict[str, Any],
    notes: Any = "",
) -> dict[str, Any]:
    safe_decision = _safe_stage12_closure_decision(decision)
    closure_ready = bool(review.get("stage12_completion_review_ready"))
    stage12_closed_by_receipt = safe_decision == "close_stage12" and closure_ready
    receipt_id = f"knowledge_fabric_stage12_closure_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_STAGE_CLOSURE_DECISION_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "capture_mode": "explicit_operator_stage_closure_decision",
        "target": "stage12_knowledge_fabric",
        "actor": _redact_text(actor)[:240],
        "reason": _redact_text(reason)[:500],
        "decision": safe_decision,
        "notes": _redact_text(notes)[:500],
        "review_status": _safe_text(review.get("status")),
        "completion_review_ready": closure_ready,
        "stage11_closure_receipt_id": _safe_text(review.get("stage11_latest_closure_receipt_id")),
        "artifact_index_projection_count": _safe_int(review.get("artifact_index_projection_count")),
        "retrieval_total": _safe_int(review.get("retrieval_total")),
        "citation_total": _safe_int(review.get("citation_total")),
        "retention_declared_count": _safe_int(review.get("retention_declared_count")),
        "retention_missing_count": _safe_int(review.get("retention_missing_count")),
        "source_counts": _as_dict(review.get("source_counts")),
        "retention_policy_counts": _as_dict(review.get("retention_policy_counts")),
        "done_criteria": _as_dict(review.get("done_criteria")),
        "stage12_closed_by_receipt": stage12_closed_by_receipt,
        "marks_runtime_stage_state": False,
        "recorded_ts": _now_s(),
        "writes_receipt": True,
        "writes_memory": False,
        "writes_index": False,
        "deletes_data": False,
        "mutates_retention": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "permission_scope": KNOWLEDGE_FABRIC_STAGE_CLOSURE_SCOPE,
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "completion_review_ready": closure_ready,
            "requires_stage11_ledger_closure": True,
            "requires_artifact_index_projection": True,
            "requires_retrieval_layer": True,
            "requires_local_evidence_citations": True,
            "requires_retention_model": True,
            "requires_projected_local_evidence": True,
            "requires_cross_artifact_continuity": True,
            "requires_declared_retention_for_review": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_memory": True,
            "does_not_write_index": True,
            "does_not_delete_data": True,
            "does_not_mutate_retention": True,
            "does_not_run_tools": True,
            "does_not_run_shell": True,
            "does_not_run_git": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": "stage12_ledger_closure"
        if stage12_closed_by_receipt
        else "stage12_operator_stage_closure_decision",
    }
    _append_jsonl(_stage12_operator_stage_closure_decision_path(), payload)
    audit_record(
        "knowledge_fabric.stage12_closure_decision_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        receipt_id=receipt_id,
        decision=safe_decision,
        stage12_closed_by_receipt=stage12_closed_by_receipt,
    )
    return payload


def knowledge_fabric_retention_model(
    *,
    query: Any = "",
    limit: int = 10,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    safe_query = _redact_text(query)[:500]
    safe_limit = _safe_limit(limit, default=10)
    citations = knowledge_fabric_local_evidence_citations(
        query=query,
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    if not bool(citations.get("local_evidence_citations_ready")):
        return {
            "ok": True,
            "kind": KNOWLEDGE_FABRIC_RETENTION_MODEL_KIND,
            "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
            "source_id": "knowledge_fabric",
            "status": "blocked",
            "query": safe_query,
            "retention_model_ready": False,
            "local_evidence_citations_ready": False,
            "stage11_closed_by_receipt": bool(citations.get("stage11_closed_by_receipt")),
            "items": [],
            "total": 0,
            "limit": safe_limit,
            "truncated": False,
            "retention_declared_count": 0,
            "retention_missing_count": 0,
            "retention_policy_counts": {},
            "writes_memory": False,
            "writes_index": False,
            "generates_answer": False,
            "uses_model": False,
            "scans_files": False,
            "replicates_data": False,
            "deletes_data": False,
            "mutates_retention": False,
            "grants_authority": False,
            "governance": _retention_model_governance(),
            "next_smallest_truthful_gap": _safe_text(citations.get("next_smallest_truthful_gap"))
            or "stage12_local_evidence_citation_surface",
        }

    items = [_retention_model_item(item) for item in _as_list(citations.get("citations")) if isinstance(item, dict)]
    declared_count = sum(1 for item in items if bool(item.get("retention_declared")))
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_RETENTION_MODEL_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "ready" if items else "empty",
        "query": safe_query,
        "retention_model_ready": True,
        "local_evidence_citations_ready": True,
        "stage11_closed_by_receipt": bool(citations.get("stage11_closed_by_receipt")),
        "items": items,
        "total": len(items),
        "citation_total": _safe_int(citations.get("total")),
        "limit": safe_limit,
        "truncated": bool(citations.get("truncated")),
        "retention_declared_count": declared_count,
        "retention_missing_count": max(0, len(items) - declared_count),
        "retention_policy_counts": _count_by(items, "retention_policy"),
        "writes_memory": False,
        "writes_index": False,
        "generates_answer": False,
        "uses_model": False,
        "scans_files": False,
        "replicates_data": False,
        "deletes_data": False,
        "mutates_retention": False,
        "grants_authority": False,
        "governance": _retention_model_governance(),
        "next_smallest_truthful_gap": "stage12_completion_review",
    }


def knowledge_fabric_local_evidence_citations(
    *,
    query: Any = "",
    limit: int = 10,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    retrieval = knowledge_fabric_retrieval_preview(
        query=query,
        limit=limit,
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    safe_query = _redact_text(query)[:500]
    if not bool(retrieval.get("retrieval_layer_ready")):
        return {
            "ok": True,
            "kind": KNOWLEDGE_FABRIC_LOCAL_EVIDENCE_CITATIONS_KIND,
            "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
            "source_id": "knowledge_fabric",
            "status": "blocked",
            "query": safe_query,
            "local_evidence_citations_ready": False,
            "stage11_closed_by_receipt": bool(retrieval.get("stage11_closed_by_receipt")),
            "items": [],
            "citations": [],
            "total": 0,
            "limit": _safe_limit(limit, default=10),
            "truncated": False,
            "writes_memory": False,
            "writes_index": False,
            "generates_answer": False,
            "uses_model": False,
            "scans_files": False,
            "replicates_data": False,
            "grants_authority": False,
            "governance": _local_evidence_citation_governance(),
            "next_smallest_truthful_gap": _safe_text(retrieval.get("next_smallest_truthful_gap"))
            or "stage12_retrieval_layer",
        }

    citations = [_citation_surface_item(item) for item in _as_list(retrieval.get("items")) if isinstance(item, dict)]
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_LOCAL_EVIDENCE_CITATIONS_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "ready" if citations else "empty",
        "query": safe_query,
        "local_evidence_citations_ready": True,
        "stage11_closed_by_receipt": bool(retrieval.get("stage11_closed_by_receipt")),
        "items": citations,
        "citations": citations,
        "total": len(citations),
        "limit": _safe_limit(limit, default=10),
        "truncated": bool(retrieval.get("truncated")),
        "retrieval_total": _safe_int(retrieval.get("total")),
        "writes_memory": False,
        "writes_index": False,
        "generates_answer": False,
        "uses_model": False,
        "scans_files": False,
        "replicates_data": False,
        "grants_authority": False,
        "governance": _local_evidence_citation_governance(),
        "next_smallest_truthful_gap": "stage12_retention_model",
    }


def knowledge_fabric_retrieval_preview(
    *,
    query: Any = "",
    limit: int = 10,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    safe_query = _redact_text(query)[:500]
    safe_limit = _safe_limit(limit, default=10)
    projection = knowledge_fabric_artifact_index_projection(
        limit=max(safe_limit, 50),
        memory_limit=memory_limit,
        ledger_limit=ledger_limit,
    )
    if not bool(projection.get("artifact_index_projection_ready")):
        return {
            "ok": True,
            "kind": KNOWLEDGE_FABRIC_RETRIEVAL_PREVIEW_KIND,
            "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
            "source_id": "knowledge_fabric",
            "status": "blocked",
            "query": safe_query,
            "retrieval_layer_ready": False,
            "stage11_closed_by_receipt": bool(projection.get("stage11_closed_by_receipt")),
            "items": [],
            "citations": [],
            "total": 0,
            "limit": safe_limit,
            "truncated": False,
            "retrieval_mode": "bounded_lexical_local_citation_preview",
            "uses_embeddings": False,
            "uses_model": False,
            "writes_memory": False,
            "writes_index": False,
            "scans_files": False,
            "replicates_data": False,
            "grants_authority": False,
            "governance": _retrieval_preview_governance(),
            "next_smallest_truthful_gap": _safe_text(projection.get("next_smallest_truthful_gap"))
            or "stage12_artifact_index_projection",
        }

    terms = _query_terms(safe_query)
    candidates = [_scored_retrieval_item(item, terms=terms) for item in _as_list(projection.get("citations"))]
    candidates = [item for item in candidates if item and (not terms or int(item.get("match_score") or 0) > 0)]
    candidates.sort(
        key=lambda item: (
            _safe_int(item.get("match_score")),
            _safe_int(item.get("observed_ts")),
            _safe_text(item.get("reference_id")),
        ),
        reverse=True,
    )
    page = candidates[:safe_limit]
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_RETRIEVAL_PREVIEW_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "ready" if page else "empty",
        "query": safe_query,
        "terms": terms,
        "retrieval_layer_ready": True,
        "stage11_closed_by_receipt": bool(projection.get("stage11_closed_by_receipt")),
        "items": page,
        "citations": page,
        "total": len(candidates),
        "limit": safe_limit,
        "truncated": len(candidates) > len(page),
        "retrieval_mode": "bounded_lexical_local_citation_preview",
        "projection_total": _safe_int(projection.get("total")),
        "uses_embeddings": False,
        "uses_model": False,
        "writes_memory": False,
        "writes_index": False,
        "scans_files": False,
        "replicates_data": False,
        "grants_authority": False,
        "governance": _retrieval_preview_governance(),
        "next_smallest_truthful_gap": "stage12_local_evidence_citation_surface",
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


def knowledge_fabric_artifact_index_projection(
    *,
    limit: int = 50,
    memory_limit: int = 100,
    ledger_limit: int = 100,
) -> dict[str, Any]:
    stage11 = apprenticeship_stage11_operator_stage_closure_decision_readback(limit=5)
    stage11_closed = bool(stage11.get("stage11_closed_by_receipt"))
    safe_limit = _safe_limit(limit, default=50)
    safe_memory_limit = _safe_limit(memory_limit, default=100)
    safe_ledger_limit = _safe_limit(ledger_limit, default=100)
    if not stage11_closed:
        return {
            "ok": True,
            "kind": KNOWLEDGE_FABRIC_ARTIFACT_INDEX_PROJECTION_KIND,
            "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
            "source_id": "knowledge_fabric",
            "status": "blocked",
            "artifact_index_projection_ready": False,
            "stage11_closed_by_receipt": False,
            "stage11_latest_closure_receipt_id": _safe_text(stage11.get("latest_receipt_id")),
            "items": [],
            "citations": [],
            "artifact_class_counts": {},
            "source_counts": {},
            "total": 0,
            "limit": safe_limit,
            "truncated": False,
            "memory_timeline_event_count": 0,
            "continuity_ledger_entry_count": 0,
            "reads_memory_timeline": False,
            "reads_continuity_ledger": False,
            "writes_index": False,
            "writes_memory": False,
            "scans_files": False,
            "replicates_data": False,
            "grants_authority": False,
            "governance": _artifact_projection_governance(),
            "next_smallest_truthful_gap": "stage11_ledger_closure",
        }

    memory_events = _read_memory_timeline_events(limit=safe_memory_limit)
    ledger_entries = _read_continuity_ledger_entries(limit=safe_ledger_limit)
    projected: list[dict[str, Any]] = []
    for item in memory_events:
        citation = _project_memory_event(item)
        if citation:
            projected.append(citation)
    for item in ledger_entries:
        citation = _project_continuity_entry(item)
        if citation:
            projected.append(citation)
    projected.sort(
        key=lambda item: (_safe_int(item.get("observed_ts")), _safe_text(item.get("reference_id"))), reverse=True
    )
    page = projected[:safe_limit]
    return {
        "ok": True,
        "kind": KNOWLEDGE_FABRIC_ARTIFACT_INDEX_PROJECTION_KIND,
        "stage": STAGE12_KNOWLEDGE_FABRIC_STAGE,
        "source_id": "knowledge_fabric",
        "status": "ready" if page else "empty",
        "artifact_index_projection_ready": True,
        "stage11_closed_by_receipt": True,
        "stage11_latest_closure_receipt_id": _safe_text(stage11.get("latest_receipt_id")),
        "items": page,
        "citations": page,
        "artifact_class_counts": _count_by(page, "artifact_class"),
        "source_counts": _count_by(page, "source_route"),
        "total": len(projected),
        "limit": safe_limit,
        "truncated": len(projected) > len(page),
        "memory_timeline_event_count": len(memory_events),
        "continuity_ledger_entry_count": len(ledger_entries),
        "reads_memory_timeline": True,
        "reads_continuity_ledger": True,
        "writes_index": False,
        "writes_memory": False,
        "scans_files": False,
        "replicates_data": False,
        "grants_authority": False,
        "governance": _artifact_projection_governance(),
        "next_smallest_truthful_gap": "stage12_retrieval_layer",
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


def _read_memory_timeline_events(*, limit: int) -> list[dict[str, Any]]:
    path = data_dir() / "memory" / "timeline" / "_events.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    events = payload.get("events") if isinstance(payload, dict) else []
    if not isinstance(events, list):
        return []
    return [item for item in events[-limit:] if isinstance(item, dict)]


def _read_continuity_ledger_entries(*, limit: int) -> list[dict[str, Any]]:
    try:
        return [item for item in continuity_tail(limit=limit) if isinstance(item, dict)]
    except Exception:
        return []


def _project_memory_event(item: dict[str, Any]) -> dict[str, Any]:
    references = _references_from(item, _as_dict(item.get("references")), _as_dict(item.get("meta")))
    artifact_class = _artifact_class_for(item, references=references)
    reference_id = _reference_id_for(artifact_class, item, references)
    if not reference_id:
        return {}
    return _citation(
        artifact_class=artifact_class,
        source_route="/memory/timeline/get",
        source_record_id=_safe_text(item.get("id")),
        source_kind=_safe_text(item.get("kind")),
        reference_id=reference_id,
        local_handle=_first_text(references.get("artifact_dir"), item.get("artifact_dir"), item.get("id")),
        evidence_summary=_first_text(item.get("title"), item.get("message"), item.get("kind"), item.get("id")),
        observed_ts=_safe_int(item.get("ts")),
        trace_lineage=references,
        retention=_retention_from(_as_dict(item.get("meta")), item),
        provenance=_provenance_from(item, _as_dict(item.get("meta"))),
    )


def _project_continuity_entry(item: dict[str, Any]) -> dict[str, Any]:
    meta = _as_dict(item.get("meta"))
    references = _references_from(meta)
    artifact_class = _artifact_class_for({"kind": "ledger_append", **meta}, references=references)
    reference_id = _reference_id_for(artifact_class, item, references)
    if not reference_id:
        return {}
    return _citation(
        artifact_class=artifact_class,
        source_route="/continuity/ledger",
        source_record_id=_first_text(
            meta.get("operation_id"), meta.get("trace_id"), meta.get("mission_id"), item.get("ts")
        ),
        source_kind="ledger_append",
        reference_id=reference_id,
        local_handle=_first_text(references.get("artifact_dir"), references.get("run_id"), reference_id),
        evidence_summary=_first_text(
            item.get("content"), meta.get("result_message"), meta.get("operation_error"), "ledger_append"
        ),
        observed_ts=_safe_int(item.get("ts")),
        trace_lineage=references,
        retention=_retention_from(meta, item),
        provenance=_provenance_from(item, meta),
    )


def _citation(
    *,
    artifact_class: str,
    source_route: str,
    source_record_id: str,
    source_kind: str,
    reference_id: str,
    local_handle: str,
    evidence_summary: str,
    observed_ts: int,
    trace_lineage: dict[str, str],
    retention: dict[str, Any],
    provenance: dict[str, str],
) -> dict[str, Any]:
    return {
        "artifact_class": artifact_class,
        "source_route": source_route,
        "source_record_id": _redact_text(source_record_id),
        "source_kind": _redact_text(source_kind),
        "reference_id": _redact_text(reference_id),
        "local_handle": _redact_text(local_handle),
        "evidence_summary": _redact_text(evidence_summary)[:500],
        "observed_ts": observed_ts,
        "redacted": True,
        "trace_lineage": {key: _redact_text(value) for key, value in trace_lineage.items() if value},
        "retention": retention,
        "provenance": provenance,
        "citation_ready": True,
    }


def _artifact_class_for(item: dict[str, Any], *, references: dict[str, str]) -> str:
    kind = _safe_text(item.get("kind")).lower()
    domain = _safe_text(item.get("domain")).lower()
    scope = _safe_text(item.get("scope")).lower()
    haystack = " ".join((kind, domain, scope, " ".join(_safe_text(tag).lower() for tag in _as_list(item.get("tags")))))
    if any(
        key in item for key in ("teaching_session_receipt_id", "replay_receipt_id", "skillization_artifact_receipt_id")
    ):
        return "teaching_outputs"
    if "apprenticeship" in haystack:
        return "teaching_outputs"
    if "receipt" in haystack:
        return "receipts"
    if references.get("trace_id") or references.get("operation_id") or references.get("artifact_dir"):
        return "execution_traces"
    if references.get("approval_id"):
        return "receipts"
    if references.get("mission_id") or "mission" in haystack:
        return "missions"
    if "incident" in haystack:
        return "incidents"
    if "telemetry" in haystack or "observer" in haystack or item.get("source_id"):
        return "observations"
    return "observations"


def _reference_id_for(artifact_class: str, item: dict[str, Any], references: dict[str, str]) -> str:
    if artifact_class == "execution_traces":
        return _first_text(references.get("trace_id"), references.get("operation_id"), references.get("artifact_dir"))
    if artifact_class == "missions":
        return _first_text(references.get("mission_id"), references.get("operation_id"))
    if artifact_class in {"receipts", "teaching_outputs", "staged_capabilities"}:
        return _first_text(item.get("receipt_id"), references.get("approval_id"), item.get("id"))
    if artifact_class == "incidents":
        return _first_text(item.get("incident_id"), item.get("id"), references.get("trace_id"))
    return _first_text(item.get("source_id"), item.get("id"), references.get("trace_id"))


def _references_from(*items: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    keys = ("mission_id", "operation_id", "trace_id", "approval_id", "run_id", "artifact_dir")
    fallback_keys = {
        "operation_id": ("operation_id", "task_id", "current_task_operation_id", "handoff_operation_id"),
        "trace_id": ("trace_id", "current_task_trace_id", "handoff_trace_id"),
        "approval_id": ("approval_id", "current_task_approval_id", "handoff_approval_id"),
        "run_id": ("run_id", "current_task_run_id", "handoff_run_id"),
        "artifact_dir": ("artifact_dir", "artifact_path", "current_task_artifact_dir", "handoff_artifact_dir"),
        "mission_id": ("mission_id", "current_task_mission_id", "handoff_mission_id"),
    }
    for key in keys:
        for item in items:
            for candidate in fallback_keys[key]:
                value = _safe_text(item.get(candidate)).strip()
                if value:
                    out[key] = value
                    break
            if key in out:
                break
    return out


def _retention_from(meta: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    retention: dict[str, Any] = {}
    for out_key, keys in {
        "policy": ("retention_policy", "policy"),
        "class": ("retention_class", "class"),
        "until": ("retention_until", "until", "expires_at"),
        "ttl_seconds": ("ttl_seconds",),
    }.items():
        for key in keys:
            value = meta.get(key) if key in meta else item.get(key)
            if _safe_text(value).strip():
                retention[out_key] = _safe_int(value) if out_key == "ttl_seconds" else _redact_text(value)
                break
    return retention


def _provenance_from(item: dict[str, Any], meta: dict[str, Any]) -> dict[str, str]:
    provenance: dict[str, str] = {}
    for key in ("source", "domain", "actor", "scope", "correlation_id"):
        value = _first_text(meta.get(key), item.get(key))
        if value:
            provenance[key] = _redact_text(value)
    return provenance


def _artifact_projection_governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "requires_stage11_ledger_closure": True,
        "bounded_local_readback": True,
        "reads_known_receipt_surfaces_only": True,
        "does_not_write_index": True,
        "does_not_write_memory": True,
        "does_not_scan_files": True,
        "does_not_replicate_data": True,
        "grants_authority": False,
    }


def _retrieval_preview_governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "requires_artifact_index_projection": True,
        "local_evidence_only": True,
        "bounded_lexical_retrieval_only": True,
        "does_not_use_embeddings": True,
        "does_not_call_model": True,
        "does_not_write_index": True,
        "does_not_write_memory": True,
        "does_not_scan_files": True,
        "does_not_replicate_data": True,
        "grants_authority": False,
    }


def _local_evidence_citation_governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "requires_retrieval_layer": True,
        "citation_surface_only": True,
        "local_evidence_only": True,
        "does_not_generate_answer": True,
        "does_not_call_model": True,
        "does_not_write_index": True,
        "does_not_write_memory": True,
        "does_not_scan_files": True,
        "does_not_replicate_data": True,
        "grants_authority": False,
    }


def _retention_model_governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "requires_local_evidence_citations": True,
        "retention_model_only": True,
        "local_evidence_only": True,
        "does_not_delete_data": True,
        "does_not_mutate_retention": True,
        "does_not_generate_answer": True,
        "does_not_call_model": True,
        "does_not_write_index": True,
        "does_not_write_memory": True,
        "does_not_scan_files": True,
        "does_not_replicate_data": True,
        "grants_authority": False,
    }


def _completion_review_governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "completion_review_only": True,
        "requires_stage11_ledger_closure": True,
        "requires_artifact_index_contract": True,
        "requires_artifact_index_projection": True,
        "requires_retrieval_layer": True,
        "requires_local_evidence_citations": True,
        "requires_retention_model": True,
        "requires_projected_local_evidence": True,
        "requires_cross_artifact_continuity": True,
        "requires_declared_retention_for_review": True,
        "does_not_mark_stage_closed": True,
        "does_not_write_receipts": True,
        "does_not_write_memory": True,
        "does_not_write_index": True,
        "does_not_delete_data": True,
        "does_not_mutate_retention": True,
        "does_not_generate_answer": True,
        "does_not_call_model": True,
        "does_not_scan_files": True,
        "does_not_replicate_data": True,
        "does_not_run_tools": True,
        "does_not_run_shell": True,
        "does_not_run_git": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }


def _completion_review_checks(
    *,
    status: dict[str, Any],
    projection: dict[str, Any],
    retrieval: dict[str, Any],
    citations: dict[str, Any],
    retention: dict[str, Any],
    citation_items: list[dict[str, Any]],
    projection_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    retention_missing_count = _safe_int(retention.get("retention_missing_count"))
    retention_total = _safe_int(retention.get("total"))
    return [
        _review_check(
            "stage11_ledger_closure_backstop",
            bool(status.get("stage11_closed_by_receipt")),
            "stage11_ledger_closure",
            "Stage 11 closure receipt readback is present",
        ),
        _review_check(
            "artifact_index_contract_ready",
            bool(status.get("artifact_index_contract_ready")),
            "stage12_artifact_index_contract",
            "Artifact classes, citation fields, and retention contract are explicit",
        ),
        _review_check(
            "artifact_index_projection_ready",
            bool(projection.get("artifact_index_projection_ready")),
            "stage12_artifact_index_projection",
            "Known local evidence surfaces can be projected into citations",
        ),
        _review_check(
            "projected_local_evidence_present",
            len(projection_items) > 0,
            "stage12_local_evidence_required",
            "At least one local evidence artifact is projected before completion review can pass",
        ),
        _review_check(
            "retrieval_layer_ready",
            bool(retrieval.get("retrieval_layer_ready")),
            "stage12_retrieval_layer",
            "Retrieval can return bounded local evidence references",
        ),
        _review_check(
            "local_evidence_citations_ready",
            bool(citations.get("local_evidence_citations_ready")) and len(citation_items) > 0,
            "stage12_local_evidence_citation_surface",
            "The citation surface returns displayable local evidence citations",
        ),
        _review_check(
            "retention_model_ready",
            bool(retention.get("retention_model_ready")),
            "stage12_retention_model",
            "Citation retention metadata is inspectable",
        ),
        _review_check(
            "retention_declared_for_reviewed_citations",
            retention_total > 0 and retention_missing_count == 0,
            "stage12_retention_metadata_required",
            "Reviewed citations declare retention posture",
        ),
        _review_check(
            "cross_artifact_continuity_ready",
            _cross_artifact_continuity_ready(projection_items),
            "stage12_cross_artifact_continuity_review",
            "Projected evidence preserves enough source and trace lineage to connect artifacts",
        ),
        _review_check(
            "completion_review_does_not_mark_stage_closed",
            True,
            "stage12_completion_review",
            "Completion review is read-only and leaves operator closure as a separate decision",
        ),
    ]


def _review_check(check_id: str, passed: bool, next_gap: str, evidence: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "status": "passed" if passed else "blocked",
        "evidence": evidence,
        "next_smallest_truthful_gap": next_gap,
    }


def _completion_review_next_gap(*, checks: list[dict[str, Any]], status: dict[str, Any]) -> str:
    for check in checks:
        if not bool(check.get("passed")):
            return _safe_text(check.get("next_smallest_truthful_gap")) or "stage12_completion_review"
    return _safe_text(status.get("next_smallest_truthful_gap")) or "stage12_completion_review"


def _cross_artifact_continuity_ready(items: list[dict[str, Any]]) -> bool:
    if len(items) < 2:
        return False
    source_routes = {_safe_text(item.get("source_route")) for item in items if _safe_text(item.get("source_route"))}
    trace_keys = {"mission_id", "operation_id", "trace_id", "run_id", "artifact_dir"}
    lineage_hits = 0
    for item in items:
        trace_lineage = _as_dict(item.get("trace_lineage"))
        if sum(1 for key in trace_keys if _safe_text(trace_lineage.get(key))) >= 2:
            lineage_hits += 1
    return len(source_routes) >= 2 and lineage_hits >= 1


def _retention_model_item(item: dict[str, Any]) -> dict[str, Any]:
    retention = _as_dict(item.get("retention"))
    retention_policy = _redact_text(_first_text(retention.get("policy"), retention.get("retention_policy")))
    retention_class = _redact_text(_first_text(retention.get("class"), retention.get("retention_class")))
    retention_until = _redact_text(
        _first_text(retention.get("until"), retention.get("retention_until"), retention.get("expires_at"))
    )
    ttl_seconds = _safe_int(retention.get("ttl_seconds"))
    retention_declared = bool(retention_policy or retention_class or retention_until or ttl_seconds > 0)
    return {
        "citation_id": _redact_text(item.get("citation_id")),
        "artifact_class": _redact_text(item.get("artifact_class")),
        "source_route": _redact_text(item.get("source_route")),
        "reference_id": _redact_text(item.get("reference_id")),
        "local_handle": _redact_text(item.get("local_handle")),
        "retention_policy": retention_policy,
        "retention_class": retention_class,
        "retention_until": retention_until,
        "ttl_seconds": ttl_seconds,
        "retention_declared": retention_declared,
        "retention_status": "declared" if retention_declared else "missing",
        "retention": {
            "policy": retention_policy,
            "class": retention_class,
            "until": retention_until,
            "ttl_seconds": ttl_seconds,
        },
        "observed_ts": _safe_int(item.get("observed_ts")),
        "redacted": True,
        "deletion_candidate": False,
        "citation_ready": bool(item.get("citation_ready")),
    }


def _citation_surface_item(item: dict[str, Any]) -> dict[str, Any]:
    artifact_class = _redact_text(item.get("artifact_class"))
    reference_id = _redact_text(item.get("reference_id"))
    source_route = _redact_text(item.get("source_route"))
    summary = _redact_text(item.get("evidence_summary"))[:280]
    citation_id = _citation_id(artifact_class, reference_id, source_route)
    return {
        "citation_id": citation_id,
        "artifact_class": artifact_class,
        "source_route": source_route,
        "reference_id": reference_id,
        "local_handle": _redact_text(item.get("local_handle")),
        "evidence_summary": summary,
        "display_label": f"{artifact_class}:{reference_id}" if reference_id else artifact_class,
        "display_text": f"{summary} [{artifact_class}; {reference_id}]".strip(),
        "observed_ts": _safe_int(item.get("observed_ts")),
        "redacted": True,
        "trace_lineage": _as_dict(item.get("trace_lineage")),
        "retention": _as_dict(item.get("retention")),
        "provenance": _as_dict(item.get("provenance")),
        "match_score": _safe_int(item.get("match_score")),
        "matched_terms": [term for term in _as_list(item.get("matched_terms")) if isinstance(term, str)],
        "answer_claim": "",
        "citation_ready": True,
    }


def _citation_id(artifact_class: str, reference_id: str, source_route: str) -> str:
    seed = f"{artifact_class}:{reference_id}:{source_route}".lower()
    out: list[str] = []
    for char in seed:
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "_":
            out.append("_")
    suffix = "".join(out).strip("_")[:96] or "local_evidence"
    return f"kfcite_{suffix}"


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    current: list[str] = []
    for char in query.lower():
        if char.isalnum() or char in {"_", "-"}:
            current.append(char)
            continue
        if current:
            term = "".join(current).strip("-_")
            if len(term) >= 2 and term not in terms:
                terms.append(term)
            current = []
    if current:
        term = "".join(current).strip("-_")
        if len(term) >= 2 and term not in terms:
            terms.append(term)
    return terms[:12]


def _scored_retrieval_item(item: Any, *, terms: list[str]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    haystack = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).lower()
    matched_terms = [term for term in terms if term in haystack]
    score = len(matched_terms)
    out = dict(item)
    out["match_score"] = score
    out["matched_terms"] = matched_terms
    out["retrieval_mode"] = "bounded_lexical_local_citation_preview"
    return out


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = _safe_text(item.get(key)).strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


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


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_text(value).strip()
        if text:
            return text
    return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any) -> int:
    try:
        return int(float(_safe_text(value).strip()))
    except Exception:
        return 0


def _safe_limit(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(parsed, 200))


def _safe_stage12_closure_decision(value: Any) -> str:
    text = _safe_text(value)
    if text in {"close_stage12", "do_not_close_stage12", "needs_more_evidence"}:
        return text
    return "needs_more_evidence"


def _stage12_operator_stage_closure_decision_path() -> Path:
    return data_dir() / "logs" / "knowledge_fabric" / "stage12_operator_stage_closure_decisions.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items[-limit:]


def _now_s() -> int:
    return int(time.time())


def _redact_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value).strip())


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""
