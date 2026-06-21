from __future__ import annotations

import json
from pathlib import Path

from francis.workers.local_drone import run_local_drone


def test_local_drone_no_model_call_writes_advisory_packet_and_receipt(tmp_path: Path) -> None:
    context = tmp_path / "context.md"
    context.write_text("Stage 17 context with SECRET_DO_NOT_PERSIST", encoding="utf-8")

    result = run_local_drone(
        task="Find one narrow Stage 17 risk.",
        context_path=context,
        worker_id="worker-1-orb-voice-proof",
        drone_id="risk-scan",
        state_root=tmp_path / "local-drones",
        call_model=False,
    )

    assert result.status == "skipped"
    assert result.model == "llama3.2:3b"
    assert result.authority == "advisory_only"
    assert result.can_commit is False
    assert result.can_push is False
    assert result.can_claim_completion is False

    packet = Path(result.packet_path).read_text(encoding="utf-8")
    assert "No local-model output was produced" in packet
    assert "SECRET_DO_NOT_PERSIST" not in packet

    receipt_lines = Path(result.receipt_path).read_text(encoding="utf-8").splitlines()
    assert len(receipt_lines) == 1
    receipt = json.loads(receipt_lines[0])
    assert receipt["kind"] == "francis.local_drone.receipt"
    assert receipt["status"] == "skipped"
    assert receipt["provider"] == "ollama"
    assert receipt["model"] == "llama3.2:3b"
    assert receipt["can_commit"] is False
    assert receipt["can_push"] is False
    assert receipt["can_claim_completion"] is False
    assert "SECRET_DO_NOT_PERSIST" not in receipt_lines[0]
