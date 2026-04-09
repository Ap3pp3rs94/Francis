from __future__ import annotations

import json
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.approvals_store import (
    find_latest_request_by_metadata,
    get_request,
    list_requests,
    load_approval_snapshot,
    pending_count,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ""
    if rows:
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def test_approval_snapshot_reuses_materialized_rows_for_queries(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[workspace], journal_path=workspace / "journals" / "fs.jsonl")
    _write_jsonl(
        workspace / "approvals" / "requests.jsonl",
        [
            {
                "id": "req-approved",
                "ts": "2026-04-09T10:00:00+00:00",
                "run_id": "run-approved",
                "action": "forge.promote",
                "reason": "promote capability",
                "requested_by": "architect",
                "metadata": {"stage_id": "cap-1"},
            },
            {
                "id": "req-pending",
                "ts": "2026-04-09T11:00:00+00:00",
                "run_id": "run-pending",
                "action": "tools.repo.tests",
                "reason": "run fast checks",
                "requested_by": "architect",
                "metadata": {"signature": "sig-fast"},
            },
        ],
    )
    _write_jsonl(
        workspace / "journals" / "decisions.jsonl",
        [
            {
                "id": "decision-1",
                "ts": "2026-04-09T10:05:00+00:00",
                "run_id": "run-approved",
                "kind": "approval.decision",
                "request_id": "req-approved",
                "action": "forge.promote",
                "decision": "approved",
                "decided_by": "architect",
                "note": "approved",
            }
        ],
    )

    snapshot = load_approval_snapshot(fs)
    monkeypatch.setattr(
        fs,
        "read_text",
        lambda rel_path: (_ for _ in ()).throw(AssertionError(f"unexpected workspace read: {rel_path}")),
    )

    approved = get_request(fs, "req-approved", snapshot=snapshot)
    assert approved is not None
    assert approved["status"] == "approved"

    pending = list_requests(fs, status="pending", limit=10, snapshot=snapshot)
    assert [row["id"] for row in pending] == ["req-pending"]
    assert pending_count(fs, snapshot=snapshot) == 1

    by_stage = find_latest_request_by_metadata(
        fs,
        action="forge.promote",
        metadata_keys=("stage_id", "entry_id"),
        metadata_value="cap-1",
        snapshot=snapshot,
    )
    assert by_stage is not None
    assert by_stage["id"] == "req-approved"

    by_signature = find_latest_request_by_metadata(
        fs,
        action="tools.repo.tests",
        metadata_keys=("signature",),
        metadata_value="sig-fast",
        snapshot=snapshot,
    )
    assert by_signature is not None
    assert by_signature["id"] == "req-pending"


def test_approval_snapshot_cache_reuses_clean_workspace_reads(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[workspace], journal_path=workspace / "journals" / "fs.jsonl")
    _write_jsonl(
        workspace / "approvals" / "requests.jsonl",
        [
            {
                "id": "req-pending",
                "ts": "2026-04-09T11:00:00+00:00",
                "run_id": "run-pending",
                "action": "tools.repo.tests",
                "reason": "run fast checks",
                "requested_by": "architect",
                "metadata": {"signature": "sig-fast"},
            }
        ],
    )

    first = load_approval_snapshot(fs)
    monkeypatch.setattr(
        fs,
        "read_text",
        lambda rel_path: (_ for _ in ()).throw(AssertionError(f"unexpected workspace read: {rel_path}")),
    )

    second = load_approval_snapshot(fs)
    assert second.pending_count == first.pending_count
    assert list(second.approvals_by_id) == list(first.approvals_by_id)


def test_approval_snapshot_cache_invalidates_when_requests_change(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[workspace], journal_path=workspace / "journals" / "fs.jsonl")
    requests_path = workspace / "approvals" / "requests.jsonl"
    _write_jsonl(
        requests_path,
        [
            {
                "id": "req-1",
                "ts": "2026-04-09T11:00:00+00:00",
                "run_id": "run-1",
                "action": "tools.repo.tests",
                "reason": "run fast checks",
                "requested_by": "architect",
                "metadata": {"signature": "sig-fast"},
            }
        ],
    )

    first = load_approval_snapshot(fs)
    assert first.pending_count == 1

    _write_jsonl(
        requests_path,
        [
            {
                "id": "req-1",
                "ts": "2026-04-09T11:00:00+00:00",
                "run_id": "run-1",
                "action": "tools.repo.tests",
                "reason": "run fast checks",
                "requested_by": "architect",
                "metadata": {"signature": "sig-fast"},
            },
            {
                "id": "req-2",
                "ts": "2026-04-09T11:05:00+00:00",
                "run_id": "run-2",
                "action": "tools.repo.tests",
                "reason": "run slow checks",
                "requested_by": "architect",
                "metadata": {"signature": "sig-slow"},
            },
        ],
    )

    second = load_approval_snapshot(fs)
    assert second.pending_count == 2
    assert [row["id"] for row in second.approvals] == ["req-1", "req-2"]
