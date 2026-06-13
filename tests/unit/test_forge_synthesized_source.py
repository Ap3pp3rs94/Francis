"""CI-safe tests for binding a synthesized (dry-run) tree back as an ingest source."""

from __future__ import annotations

from pathlib import Path

import pytest

from francis.governance import approvals
from francis.ingest import IngestService

pytestmark = pytest.mark.unit

_NEW_FILE_PROPOSAL = (
    "diff --git a/src/francis/ingest/synth_loop.py b/src/francis/ingest/synth_loop.py\n"
    "--- /dev/null\n"
    "+++ b/src/francis/ingest/synth_loop.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def francis_loop(a, b):\n"
    "+    return a + b\n"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "francis" / "ingest").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    return repo


def _drive_to_dryrun(service: IngestService, repo: Path) -> str:
    started = service.synthesize_capability(
        repo, "inspect_project_structure", actor="op", builder_client=lambda *_a: _NEW_FILE_PROPOSAL
    )
    run_id = started["builder_run_id"]
    approval_id = started["pending_approval_id"]
    approvals.decide(approval_id, "approve", actor="operator")
    service.consume_forge_apply_approval(repo, run_id, approval_id, actor="op")
    out = service.dryrun_forge_apply(repo, run_id, approval_id, _NEW_FILE_PROPOSAL, actor="op")
    assert out["status"] == "dryrun_applied"
    return run_id


def test_bind_registers_synthesized_tree_as_new_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _drive_to_dryrun(service, repo)
    origin_id = service.sources.list()[-1].id  # origin registered during synthesize

    out = service.bind_synthesized_source(repo, run_id, actor="op")
    rec = out["forge_synthesized_source"]

    assert out["status"] == "bound"
    synth_id = rec["synthesized_source_id"]
    assert synth_id and synth_id != origin_id
    # The synthesized tree is now a real, inspectable ingest source...
    assert rec["candidate_count"] >= 1
    assert service.sources.get(synth_id) is not None
    # ...containing the synthesized file, and the real repo is still untouched.
    assert Path(rec["synthesized_source_path"], "src/francis/ingest/synth_loop.py").exists()
    assert not (repo / "src/francis/ingest/synth_loop.py").exists()
    assert rec["validation_path"] == "standard_acquisition_then_lab_v0_corridor"


def test_bind_blocked_without_dryrun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    service.add_source(repo, actor="op")

    out = service.bind_synthesized_source(repo, "nonexistent_builder_run", actor="op")
    assert out["status"] == "blocked"
    assert "forge_apply_dryrun_missing" in out["blockers"]


def test_bound_source_surfaces_in_origin_readback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _drive_to_dryrun(service, repo)
    origin_id = service.sources.list()[-1].id
    service.bind_synthesized_source(repo, run_id, actor="op")

    counts = service.readback(source_id=origin_id)["counts"]
    assert counts["forge_synthesized_sources"] == 1
