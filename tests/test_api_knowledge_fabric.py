from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app


def _write_stage11_closure_receipt(data_root: Path, *, receipt_id: str = "apprenticeship_stage11_closure_test") -> None:
    path = data_root / "logs" / "apprenticeship" / "stage11_operator_stage_closure_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "francis.stage11.apprenticeship.stage11_closure_decision_receipt",
                "receipt_id": receipt_id,
                "stage": "Stage 11 / Apprenticeship",
                "source_id": "apprenticeship",
                "target": "stage11_apprenticeship",
                "actor": "test.operator",
                "decision": "close_stage11",
                "completion_review_ready": True,
                "stage11_closed_by_receipt": True,
                "marks_runtime_stage_state": False,
                "recorded_ts": 1_800_000_100,
                "governance": {
                    "explicit_operator_decision": True,
                    "stage_closure_decision": True,
                    "completion_review_ready": True,
                    "does_not_mutate_runtime_stage_state": True,
                    "grants_execution_authority": False,
                    "grants_mutation_authority": False,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_knowledge_fabric_status_blocks_until_stage11_closure(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/knowledge-fabric/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage12.knowledge_fabric.status"
    assert body["stage"] == "Stage 12 / Knowledge Fabric"
    assert body["status"] == "awaiting_stage11_ledger_closure"
    assert body["stage11_closed_by_receipt"] is False
    assert body["stage11_latest_closure_receipt_id"] == ""
    assert body["artifact_index_contract_ready"] is False
    assert body["artifact_index_projection_ready"] is False
    assert body["artifact_index_projection_count"] == 0
    assert body["artifact_indexing_active"] is False
    assert body["retrieval_layer_ready"] is False
    assert body["local_evidence_citations_ready"] is False
    assert body["retention_model_ready"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 6
    assert body["routes"]["artifact_index_contract"] == "/knowledge-fabric/artifact-index-contract"
    assert body["routes"]["artifact_index_projection"] == "/knowledge-fabric/artifact-index-projection"
    assert body["routes"]["local_evidence_citations"] == "/knowledge-fabric/local-evidence-citations"
    assert body["routes"]["retention_model"] == "/knowledge-fabric/retention-model"
    assert body["routes"]["memory_timeline"] == "/memory/timeline/list"
    assert body["routes"]["artifact_inspection"] == "/artifacts/inspect"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["requires_stage11_ledger_closure"] is True
    assert body["governance"]["does_not_index_files"] is True
    assert body["governance"]["does_not_write_memory"] is True
    assert body["governance"]["does_not_delete_data"] is True
    assert body["governance"]["does_not_mutate_retention"] is True
    assert body["governance"]["does_not_replicate_data"] is True
    assert body["next_smallest_truthful_gap"] == "stage11_ledger_closure"
    assert not data_root.exists()


def test_knowledge_fabric_artifact_index_contract_is_read_only_after_stage11_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage11_closure_receipt(data_root, receipt_id="apprenticeship_stage11_closure_kf_test")

    client = TestClient(create_app())
    response = client.get("/knowledge-fabric/artifact-index-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage12.knowledge_fabric.artifact_index_contract"
    assert body["status"] == "ready"
    assert body["artifact_index_contract_ready"] is True
    assert body["stage11_closed_by_receipt"] is True
    assert body["stage11_latest_closure_receipt_id"] == "apprenticeship_stage11_closure_kf_test"
    assert body["artifact_class_count"] == 7
    assert body["required_citation_fields"] == [
        "artifact_class",
        "source_route",
        "reference_id",
        "local_handle",
        "evidence_summary",
        "observed_ts",
        "redacted",
    ]
    assert body["citation_rules"]["local_evidence_only"] is True
    assert body["citation_rules"]["must_include_reference_id"] is True
    assert body["citation_rules"]["must_redact_secret_text"] is True
    assert body["citation_rules"]["may_not_claim_unindexed_evidence"] is True
    assert body["retention_contract"]["required"] is True
    assert body["existing_read_surfaces"]["memory_timeline"] == "/memory/timeline/list"
    assert body["writes_index"] is False
    assert body["writes_memory"] is False
    assert body["scans_files"] is False
    assert body["replicates_data"] is False
    assert body["grants_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["artifact_classes_explicit"] is True
    assert body["governance"]["citation_contract_explicit"] is True
    assert body["governance"]["retention_contract_explicit"] is True
    assert body["next_smallest_truthful_gap"] == "stage12_artifact_index_projection"

    classes = {item["id"]: item for item in body["artifact_classes"]}
    assert set(classes) == {
        "receipts",
        "missions",
        "incidents",
        "staged_capabilities",
        "observations",
        "teaching_outputs",
        "execution_traces",
    }
    assert classes["receipts"]["primary_reference_field"] == "receipt_id"
    assert "receipt_id" in classes["receipts"]["citation_fields"]
    assert classes["execution_traces"]["primary_reference_field"] == "trace_id"
    assert "artifact_dir" in classes["execution_traces"]["citation_fields"]
    assert all(item["index_status"] == "contract_only" for item in classes.values())

    status = client.get("/knowledge-fabric/status").json()
    assert status["status"] == "stage12_retention_model_ready"
    assert status["artifact_index_contract_ready"] is True
    assert status["artifact_index_projection_ready"] is True
    assert status["artifact_index_projection_count"] == 0
    assert status["retrieval_layer_ready"] is True
    assert status["local_evidence_citations_ready"] is True
    assert status["retention_model_ready"] is True
    assert status["ready_count"] == 6
    assert status["required_count"] == 6
    assert status["next_smallest_truthful_gap"] == "stage12_completion_review"


def test_knowledge_fabric_artifact_index_projection_projects_local_citations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    _write_stage11_closure_receipt(data_root, receipt_id="apprenticeship_stage11_closure_projection_test")
    memory_path = data_root / "memory" / "timeline" / "_events.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": 1_800_000_200,
                "events": [
                    {
                        "id": "evt-kf-trace",
                        "ts": 1_800_000_201,
                        "kind": "memory_write",
                        "title": "Operation evidence token=kfprojectionsecret123",
                        "message": "Execution trace summary",
                        "trace_id": "trace-kf",
                        "mission_id": "mission-kf",
                        "operation_id": "op-kf",
                        "approval_id": "approval-kf",
                        "run_id": "run-kf",
                        "artifact_dir": "data/artifacts/kf-trace",
                        "domain": "operations",
                        "actor": "francis",
                        "scope": "mission.loop",
                        "meta": {
                            "source": "unit_test",
                            "retention_policy": "mission_trace",
                            "ttl_seconds": 86400,
                        },
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    from francis.chat.continuity.ledger import append

    append(
        "assistant",
        "Mission ledger evidence token=ledgerprojectionsecret123",
        {
            "source": "unit_test",
            "mission_id": "mission-ledger-kf",
            "operation_id": "op-ledger-kf",
            "trace_id": "trace-ledger-kf",
            "run_id": "run-ledger-kf",
            "artifact_dir": "data/artifacts/ledger-kf",
            "scope": "mission.loop",
            "operation_status": "succeeded",
            "retention_policy": "mission_trace",
        },
    )

    client = TestClient(create_app())
    response = client.get("/knowledge-fabric/artifact-index-projection?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.stage12.knowledge_fabric.artifact_index_projection"
    assert body["status"] == "ready"
    assert body["artifact_index_projection_ready"] is True
    assert body["stage11_closed_by_receipt"] is True
    assert body["memory_timeline_event_count"] == 1
    assert body["continuity_ledger_entry_count"] == 1
    assert body["total"] == 2
    assert body["truncated"] is False
    assert body["reads_memory_timeline"] is True
    assert body["reads_continuity_ledger"] is True
    assert body["writes_index"] is False
    assert body["writes_memory"] is False
    assert body["scans_files"] is False
    assert body["replicates_data"] is False
    assert body["grants_authority"] is False
    assert body["governance"]["read_only"] is True
    assert body["governance"]["bounded_local_readback"] is True
    assert body["governance"]["does_not_scan_files"] is True
    assert body["next_smallest_truthful_gap"] == "stage12_retrieval_layer"

    citations = body["citations"]
    assert len(citations) == 2
    by_source = {item["source_route"]: item for item in citations}
    memory = by_source["/memory/timeline/get"]
    assert memory["artifact_class"] == "execution_traces"
    assert memory["reference_id"] == "trace-kf"
    assert memory["local_handle"] == "data/artifacts/kf-trace"
    assert memory["redacted"] is True
    assert memory["citation_ready"] is True
    assert memory["trace_lineage"]["mission_id"] == "mission-kf"
    assert memory["trace_lineage"]["operation_id"] == "op-kf"
    assert memory["retention"]["policy"] == "mission_trace"
    assert memory["retention"]["ttl_seconds"] == 86400
    assert "kfprojectionsecret123" not in json.dumps(memory, sort_keys=True)

    ledger = by_source["/continuity/ledger"]
    assert ledger["artifact_class"] == "execution_traces"
    assert ledger["reference_id"] == "trace-ledger-kf"
    assert ledger["local_handle"] == "data/artifacts/ledger-kf"
    assert ledger["redacted"] is True
    assert ledger["trace_lineage"]["mission_id"] == "mission-ledger-kf"
    assert ledger["provenance"]["source"] == "unit_test"
    assert "ledgerprojectionsecret123" not in json.dumps(ledger, sort_keys=True)

    assert body["artifact_class_counts"] == {"execution_traces": 2}
    assert body["source_counts"] == {"/continuity/ledger": 1, "/memory/timeline/get": 1}

    retrieval = client.get("/knowledge-fabric/retrieval-preview?query=ledger&limit=5").json()
    assert retrieval["ok"] is True
    assert retrieval["kind"] == "francis.stage12.knowledge_fabric.retrieval_preview"
    assert retrieval["status"] == "ready"
    assert retrieval["query"] == "ledger"
    assert retrieval["terms"] == ["ledger"]
    assert retrieval["retrieval_layer_ready"] is True
    assert retrieval["retrieval_mode"] == "bounded_lexical_local_citation_preview"
    assert retrieval["uses_embeddings"] is False
    assert retrieval["uses_model"] is False
    assert retrieval["writes_memory"] is False
    assert retrieval["writes_index"] is False
    assert retrieval["scans_files"] is False
    assert retrieval["replicates_data"] is False
    assert retrieval["grants_authority"] is False
    assert retrieval["governance"]["local_evidence_only"] is True
    assert retrieval["governance"]["bounded_lexical_retrieval_only"] is True
    assert retrieval["total"] == 1
    assert retrieval["items"][0]["source_route"] == "/continuity/ledger"
    assert retrieval["items"][0]["reference_id"] == "trace-ledger-kf"
    assert retrieval["items"][0]["match_score"] >= 1
    assert retrieval["items"][0]["matched_terms"] == ["ledger"]
    assert "ledgerprojectionsecret123" not in json.dumps(retrieval, sort_keys=True)
    assert retrieval["next_smallest_truthful_gap"] == "stage12_local_evidence_citation_surface"

    citation_surface = client.get("/knowledge-fabric/local-evidence-citations?query=ledger&limit=5").json()
    assert citation_surface["ok"] is True
    assert citation_surface["kind"] == "francis.stage12.knowledge_fabric.local_evidence_citations"
    assert citation_surface["status"] == "ready"
    assert citation_surface["query"] == "ledger"
    assert citation_surface["local_evidence_citations_ready"] is True
    assert citation_surface["writes_memory"] is False
    assert citation_surface["writes_index"] is False
    assert citation_surface["generates_answer"] is False
    assert citation_surface["uses_model"] is False
    assert citation_surface["scans_files"] is False
    assert citation_surface["replicates_data"] is False
    assert citation_surface["grants_authority"] is False
    assert citation_surface["governance"]["citation_surface_only"] is True
    assert citation_surface["total"] == 1
    citation = citation_surface["citations"][0]
    assert citation["citation_id"].startswith("kfcite_execution_traces_trace_ledger_kf")
    assert citation["artifact_class"] == "execution_traces"
    assert citation["source_route"] == "/continuity/ledger"
    assert citation["reference_id"] == "trace-ledger-kf"
    assert citation["display_label"] == "execution_traces:trace-ledger-kf"
    assert citation["answer_claim"] == ""
    assert citation["citation_ready"] is True
    assert "ledgerprojectionsecret123" not in json.dumps(citation_surface, sort_keys=True)
    assert citation_surface["next_smallest_truthful_gap"] == "stage12_retention_model"

    retention_model = client.get("/knowledge-fabric/retention-model?query=ledger&limit=5").json()
    assert retention_model["ok"] is True
    assert retention_model["kind"] == "francis.stage12.knowledge_fabric.retention_model"
    assert retention_model["status"] == "ready"
    assert retention_model["query"] == "ledger"
    assert retention_model["retention_model_ready"] is True
    assert retention_model["local_evidence_citations_ready"] is True
    assert retention_model["stage11_closed_by_receipt"] is True
    assert retention_model["total"] == 1
    assert retention_model["citation_total"] == 1
    assert retention_model["retention_declared_count"] == 1
    assert retention_model["retention_missing_count"] == 0
    assert retention_model["retention_policy_counts"] == {"mission_trace": 1}
    assert retention_model["writes_memory"] is False
    assert retention_model["writes_index"] is False
    assert retention_model["generates_answer"] is False
    assert retention_model["uses_model"] is False
    assert retention_model["scans_files"] is False
    assert retention_model["replicates_data"] is False
    assert retention_model["deletes_data"] is False
    assert retention_model["mutates_retention"] is False
    assert retention_model["grants_authority"] is False
    assert retention_model["governance"]["retention_model_only"] is True
    assert retention_model["governance"]["does_not_delete_data"] is True
    assert retention_model["governance"]["does_not_mutate_retention"] is True
    retention = retention_model["items"][0]
    assert retention["citation_id"] == citation["citation_id"]
    assert retention["artifact_class"] == "execution_traces"
    assert retention["source_route"] == "/continuity/ledger"
    assert retention["reference_id"] == "trace-ledger-kf"
    assert retention["retention_policy"] == "mission_trace"
    assert retention["retention_class"] == ""
    assert retention["retention_until"] == ""
    assert retention["ttl_seconds"] == 0
    assert retention["retention_declared"] is True
    assert retention["retention_status"] == "declared"
    assert retention["deletion_candidate"] is False
    assert "ledgerprojectionsecret123" not in json.dumps(retention_model, sort_keys=True)
    assert retention_model["next_smallest_truthful_gap"] == "stage12_completion_review"

    status = client.get("/knowledge-fabric/status").json()
    assert status["status"] == "stage12_retention_model_ready"
    assert status["retrieval_layer_ready"] is True
    assert status["local_evidence_citations_ready"] is True
    assert status["retention_model_ready"] is True
    assert status["next_smallest_truthful_gap"] == "stage12_completion_review"


def test_knowledge_fabric_artifact_index_projection_blocks_without_stage11_closure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    response = TestClient(create_app()).get("/knowledge-fabric/artifact-index-projection")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "blocked"
    assert body["artifact_index_projection_ready"] is False
    assert body["stage11_closed_by_receipt"] is False
    assert body["items"] == []
    assert body["total"] == 0
    assert body["reads_memory_timeline"] is False
    assert body["reads_continuity_ledger"] is False
    assert body["writes_index"] is False
    assert body["writes_memory"] is False
    assert body["scans_files"] is False
    assert body["next_smallest_truthful_gap"] == "stage11_ledger_closure"

    retrieval = TestClient(create_app()).get("/knowledge-fabric/retrieval-preview?query=anything").json()
    assert retrieval["status"] == "blocked"
    assert retrieval["retrieval_layer_ready"] is False
    assert retrieval["items"] == []
    assert retrieval["uses_embeddings"] is False
    assert retrieval["uses_model"] is False
    assert retrieval["writes_memory"] is False
    assert retrieval["writes_index"] is False
    assert retrieval["scans_files"] is False
    assert retrieval["next_smallest_truthful_gap"] == "stage11_ledger_closure"

    citations = TestClient(create_app()).get("/knowledge-fabric/local-evidence-citations?query=anything").json()
    assert citations["status"] == "blocked"
    assert citations["local_evidence_citations_ready"] is False
    assert citations["items"] == []
    assert citations["writes_memory"] is False
    assert citations["writes_index"] is False
    assert citations["generates_answer"] is False
    assert citations["uses_model"] is False
    assert citations["scans_files"] is False
    assert citations["next_smallest_truthful_gap"] == "stage11_ledger_closure"

    retention = TestClient(create_app()).get("/knowledge-fabric/retention-model?query=anything").json()
    assert retention["status"] == "blocked"
    assert retention["retention_model_ready"] is False
    assert retention["local_evidence_citations_ready"] is False
    assert retention["items"] == []
    assert retention["retention_declared_count"] == 0
    assert retention["retention_missing_count"] == 0
    assert retention["retention_policy_counts"] == {}
    assert retention["writes_memory"] is False
    assert retention["writes_index"] is False
    assert retention["generates_answer"] is False
    assert retention["uses_model"] is False
    assert retention["scans_files"] is False
    assert retention["deletes_data"] is False
    assert retention["mutates_retention"] is False
    assert retention["governance"]["requires_local_evidence_citations"] is True
    assert retention["next_smallest_truthful_gap"] == "stage11_ledger_closure"
