from __future__ import annotations

import json
from pathlib import Path


def test_stage3_readiness_proof_exercises_public_mission_loop(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"operator.stage3.readiness": ["missions.write"]}),
    )

    from francis.missions.readiness_proof import run_stage3_readiness_proof

    result = run_stage3_readiness_proof(confirm=True)

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["proof_missions"]["completed"].startswith("msn_")
    assert result["proof_missions"]["deadlettered"].startswith("msn_")
    readiness = result["readiness"]
    assert readiness["stage"] == "Stage 3 - Missions"
    assert readiness["satisfied"] == readiness["total"] == 5
    assert readiness["blocked_criteria_ids"] == []
    criteria = {item["id"]: item for item in readiness["criteria"]}
    assert criteria["idempotent_ticks"]["evidence"]["mission_ticked_count"] >= 1
    assert (
        result["proof_missions"]["completed"]
        in criteria["session_continuity"]["evidence"]["missions_with_memory_receipts"]
    )
    assert (
        result["proof_missions"]["deadlettered"] in criteria["deadletter_cleanly"]["evidence"]["sampled_deadletter_ids"]
    )


def test_stage3_readiness_proof_requires_confirmation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))

    from francis.missions.readiness_proof import run_stage3_readiness_proof

    result = run_stage3_readiness_proof()

    assert result["ok"] is False
    assert result["error"] == "confirmation_required"


def test_stage3_readiness_proof_respects_mission_permission_gate(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from francis.missions.readiness_proof import run_stage3_readiness_proof

    result = run_stage3_readiness_proof(confirm=True, actor="operator.stage3.readiness")

    assert result["ok"] is False
    assert result["stage"] == "create_completed_mission"
    assert result["error"] == "api_permission_denied"
    assert result["body"]["status"] == "denied"
    assert result["body"]["governance"]["gate"] == "permission_gate"
    assert not (data_root / "missions").exists()
