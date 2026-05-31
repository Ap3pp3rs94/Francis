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
    assert body["artifact_indexing_active"] is False
    assert body["retrieval_layer_ready"] is False
    assert body["local_evidence_citations_ready"] is False
    assert body["retention_model_ready"] is False
    assert body["ready_count"] == 0
    assert body["required_count"] == 5
    assert body["routes"]["artifact_index_contract"] == "/knowledge-fabric/artifact-index-contract"
    assert body["routes"]["memory_timeline"] == "/memory/timeline/list"
    assert body["routes"]["artifact_inspection"] == "/artifacts/inspect"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["requires_stage11_ledger_closure"] is True
    assert body["governance"]["does_not_index_files"] is True
    assert body["governance"]["does_not_write_memory"] is True
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
    assert status["status"] == "stage12_artifact_index_contract_ready"
    assert status["artifact_index_contract_ready"] is True
    assert status["ready_count"] == 2
    assert status["required_count"] == 5
    assert status["next_smallest_truthful_gap"] == "stage12_artifact_index_projection"
