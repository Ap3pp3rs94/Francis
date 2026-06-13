"""CI-safe tests for the governed dry-run applier (scratch-only, repo untouched)."""

from __future__ import annotations

from pathlib import Path

import pytest

from francis.governance import approvals
from francis.ingest import IngestService
from francis.ingest.core import proposal_review as pr

pytestmark = pytest.mark.unit

_NEW_FILE_PROPOSAL = (
    "diff --git a/src/francis/ingest/dryrun_cap.py b/src/francis/ingest/dryrun_cap.py\n"
    "--- /dev/null\n"
    "+++ b/src/francis/ingest/dryrun_cap.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def francis_dryrun(a, b):\n"
    "+    return a * b\n"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "francis" / "ingest").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    return repo


def _drive_to_consumed(service: IngestService, repo: Path, proposal: str) -> tuple[str, str]:
    """Run builder->review->preflight->request->approve->consume; return ids."""
    started = service.synthesize_capability(
        repo, "inspect_project_structure", actor="op", builder_client=lambda *_a: proposal
    )
    assert started["state"] == "paused_for_approval", started
    run_id = started["builder_run_id"]
    approval_id = started["pending_approval_id"]
    approvals.decide(approval_id, "approve", actor="operator")
    consumed = service.consume_forge_apply_approval(repo, run_id, approval_id, actor="op")
    assert consumed["status"] == "consumed"
    return run_id, approval_id


# --------------------------------------------------------------------------- #
# Applier function (pure)
# --------------------------------------------------------------------------- #
def test_applier_creates_new_file_in_scratch_only(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    results = pr.apply_unified_diff_to_tree(_NEW_FILE_PROPOSAL, str(scratch))
    assert len(results) == 1
    r = results[0]
    assert r.status == "applied"
    assert r.is_new_file is True
    written = scratch / "src/francis/ingest/dryrun_cap.py"
    assert written.exists()
    assert "francis_dryrun" in written.read_text(encoding="utf-8")


def test_applier_modifies_existing_with_context(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    (scratch / "pkg").mkdir(parents=True)
    (scratch / "pkg" / "mod.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    diff = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n--- a/pkg/mod.py\n+++ b/pkg/mod.py\n"
        "@@ -1,3 +1,3 @@\n a = 1\n-b = 2\n+b = 20\n c = 3\n"
    )
    results = pr.apply_unified_diff_to_tree(diff, str(scratch))
    assert results[0].status == "applied"
    assert (scratch / "pkg" / "mod.py").read_text(encoding="utf-8") == "a = 1\nb = 20\nc = 3\n"


def test_applier_rejects_context_mismatch(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    (scratch / "pkg").mkdir(parents=True)
    (scratch / "pkg" / "mod.py").write_text("totally = different\n", encoding="utf-8")
    diff = "diff --git a/pkg/mod.py b/pkg/mod.py\n--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n"
    results = pr.apply_unified_diff_to_tree(diff, str(scratch))
    assert results[0].status == "rejected"
    assert results[0].reject_reason == "removed_line_mismatch"
    # File left untouched.
    assert (scratch / "pkg" / "mod.py").read_text(encoding="utf-8") == "totally = different\n"


def test_applier_forbidden_path_guard(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    diff = (
        "diff --git a/src/francis/governance/x.py b/src/francis/governance/x.py\n"
        "--- /dev/null\n+++ b/src/francis/governance/x.py\n@@ -0,0 +1,1 @@\n+EVIL = 1\n"
    )
    results = pr.apply_unified_diff_to_tree(diff, str(scratch), forbidden_files=["src/francis/governance/**"])
    assert results[0].status == "rejected"
    assert results[0].reject_reason == "forbidden_path_write_guard"
    assert not (scratch / "src/francis/governance/x.py").exists()


# --------------------------------------------------------------------------- #
# Service brick (end-to-end via the orchestrator)
# --------------------------------------------------------------------------- #
def test_dryrun_applies_to_scratch_and_leaves_repo_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id, approval_id = _drive_to_consumed(service, repo, _NEW_FILE_PROPOSAL)

    out = service.dryrun_forge_apply(repo, run_id, approval_id, _NEW_FILE_PROPOSAL, actor="op")
    dr = out["forge_apply_dryrun"]

    assert out["status"] == "dryrun_applied"
    assert dr["files_applied"] == 1
    assert dr["wrote_to_repo"] is False
    assert dr["patch_applied_to_repo"] is False
    # The proposed file exists somewhere in the scratch tree...
    scratch_hits = list(Path(dr["scratch_root"]).rglob("dryrun_cap.py"))
    assert scratch_hits, "proposed file not found in scratch tree"
    assert "francis_dryrun" in scratch_hits[0].read_text(encoding="utf-8")
    # ...and NEVER in the real repo.
    assert not (repo / "src/francis/ingest/dryrun_cap.py").exists()


def test_dryrun_blocked_without_consumed_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    started = service.synthesize_capability(repo, actor="op", builder_client=lambda *_a: _NEW_FILE_PROPOSAL)
    run_id = started["builder_run_id"]
    approval_id = started["pending_approval_id"]
    # Not approved, not consumed.
    out = service.dryrun_forge_apply(repo, run_id, approval_id, _NEW_FILE_PROPOSAL, actor="op")
    assert out["status"] == "blocked"
    assert "forge_apply_approval_consumption_missing" in out["blockers"]


def test_dryrun_indeterminate_on_digest_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id, approval_id = _drive_to_consumed(service, repo, _NEW_FILE_PROPOSAL)

    out = service.dryrun_forge_apply(repo, run_id, approval_id, "different text", actor="op")
    assert out["status"] == "indeterminate"
    assert not (repo / "src/francis/ingest/dryrun_cap.py").exists()


def test_dryrun_surfaces_in_readback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id, approval_id = _drive_to_consumed(service, repo, _NEW_FILE_PROPOSAL)
    service.dryrun_forge_apply(repo, run_id, approval_id, _NEW_FILE_PROPOSAL, actor="op")
    source_id = service.sources.list()[0].id
    assert service.readback(source_id=source_id)["counts"]["forge_apply_dryruns"] == 1
