from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.completion_model import COMPLETION_MODEL_STATUS_KIND, completion_model_status_snapshot


def test_completion_model_snapshot_is_read_only_and_loop_guarded() -> None:
    payload = completion_model_status_snapshot()

    assert payload["ok"] is True
    assert payload["kind"] == COMPLETION_MODEL_STATUS_KIND
    assert payload["status"] == "ready"
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False
    assert payload["grants_execution_authority"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["current_phase"] == "Phase 2"
    assert payload["latest_ledger_entry"]["found"] is True
    assert payload["latest_ledger_entry"]["has_remaining_truthful_gap"] is True
    assert payload["stage17_status"]["found"] is True
    assert payload["stage17_status"]["status"] == "open"
    assert payload["stage17_status"]["read_only_contract"] is True
    assert payload["stage17_status"]["writes_repo"] is False
    assert payload["stage17_status"]["writes_data"] is False
    assert payload["stage17_status"]["grants_execution_authority"] is False
    assert payload["stage17_status"]["grants_mutation_authority"] is False
    assert payload["continue_loop_guard"]["status"] == "ready"
    assert payload["completion_percentage_model"]["movement_allowed_by_this_readback"] is False
    assert payload["routes"]["status"] == "/completion-model/status"
    assert payload["next_continue_decision"]["status"] == "bounded_slice_required"
    assert payload["next_continue_decision"]["selected_gap_source"] == "stage17_latest_ledger_entry"
    assert payload["next_continue_decision"]["stage17_gap_preferred"] is True


def test_completion_model_snapshot_blocks_when_sources_are_missing(tmp_path: Path) -> None:
    payload = completion_model_status_snapshot(
        ledger_path=tmp_path / "missing-ledger.md",
        build_manifest_path=tmp_path / "missing-build-manifest.md",
    )

    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["continue_loop_guard"]["status"] == "blocked"
    assert payload["continue_loop_guard"]["blocked_count"] == 3
    assert payload["next_continue_decision"]["selected_gap_source"] == "completion_model_sources"
    assert payload["next_continue_decision"]["next_smallest_truthful_gap"] == "restore_completion_model_sources"
    checklist = {item["id"]: item["status"] for item in payload["continue_loop_guard"]["checklist"]}
    assert checklist["ledger_read"] == "blocked"
    assert checklist["build_manifest_read"] == "blocked"
    assert checklist["latest_validated_slice_identified"] == "blocked"
    assert checklist["percentage_movement_guard"] == "enforced"


def test_completion_model_snapshot_reads_wrapped_roadmap_area(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "\n".join(
            [
                "# Ledger",
                "",
                "### 2026-06-19 - Wrapped ledger slice",
                "",
                "Roadmap area: Stage 6 / Lens MVP, Orb embodiment,",
                "voice-to-substrate routing, overlay command receipts,",
                "and P9 observability.",
                "",
                "Remaining truthful gap:",
                "",
                "- Keep going.",
                "",
                "## 6. Update rule",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        build_manifest_path=manifest,
    )

    assert payload["latest_ledger_entry"]["roadmap_area"] == (
        "Stage 6 / Lens MVP, Orb embodiment, voice-to-substrate routing, "
        "overlay command receipts, and P9 observability."
    )


def test_completion_model_snapshot_keeps_stage17_gap_when_latest_entry_is_other_lane(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "\n".join(
            [
                "# Ledger",
                "",
                "Francis is in `Phase 2` per `docs/canonical/BUILD_MANIFEST.md`.",
                "",
                "### 2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52",
                "",
                "Roadmap area: Stage 17 / Capability Economy, operator-supplied proposal",
                "evidence and proposal-review queue reduction.",
                "",
                "Remaining truthful gap:",
                "",
                "- Stage 17 remains open. Continue the selected-scope queue.",
                "",
                "### 2026-06-19 - Manual acoustic Orb proof becomes an enforceable monitor gate",
                "",
                "Roadmap area: Stage 6 / Lens MVP, Orb embodiment, voice-to-substrate",
                "routing, overlay command receipts, and P9 observability.",
                "",
                "Remaining truthful gap:",
                "",
                "- A real operator-spoken proof is still needed.",
                "- Stage 17 remains open, but this entry is not the Stage 17 lane.",
                "",
                "### 2026-06-19 - Completion model preserves Stage 17 readback across lane drift",
                "",
                "Roadmap area: Stage 17-adjacent Capability Economy, completion-model",
                "truth, and P9 observability readback.",
                "",
                "Remaining truthful gap:",
                "",
                "- Stage 17 remains open, but this is readback support work.",
                "",
                "## 6. Update rule",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        build_manifest_path=manifest,
    )

    assert payload["latest_ledger_entry"]["title"] == (
        "2026-06-19 - Completion model preserves Stage 17 readback across lane drift"
    )
    assert payload["stage17_status"]["status"] == "open"
    assert payload["stage17_status"]["readback_scope"] == "latest_stage17_ledger_entry"
    assert payload["stage17_status"]["latest_ledger_entry"]["title"] == (
        "2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52"
    )
    assert payload["stage17_status"]["latest_ledger_entry"]["roadmap_area"] == (
        "Stage 17 / Capability Economy, operator-supplied proposal evidence and proposal-review queue reduction."
    )
    assert payload["stage17_status"]["next_smallest_truthful_gap"] == (
        "select_from_latest_stage17_remaining_truthful_gap"
    )
    assert payload["next_continue_decision"]["selected_gap_source"] == "stage17_latest_ledger_entry"
    assert payload["next_continue_decision"]["selected_ledger_title"] == (
        "2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52"
    )
    assert payload["next_continue_decision"]["selected_roadmap_area"] == (
        "Stage 17 / Capability Economy, operator-supplied proposal evidence and proposal-review queue reduction."
    )
    assert payload["next_continue_decision"]["stage17_gap_preferred"] is True
    assert payload["next_continue_decision"]["next_smallest_truthful_gap"] == (
        "- Stage 17 remains open. Continue the selected-scope queue."
    )


def test_completion_model_status_route_is_mounted_and_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/completion-model/status")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == COMPLETION_MODEL_STATUS_KIND
    assert body["status"] == "ready"
    assert body["read_only_contract"] is True
    assert body["writes_repo"] is False
    assert body["writes_data"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["stage17_status"]["read_only_contract"] is True
    assert body["stage17_status"]["writes_repo"] is False
    assert body["stage17_status"]["writes_data"] is False
    assert body["stage17_status"]["grants_execution_authority"] is False
    assert body["stage17_status"]["grants_mutation_authority"] is False
    assert body["completion_percentage_model"]["movement_allowed_by_this_readback"] is False
