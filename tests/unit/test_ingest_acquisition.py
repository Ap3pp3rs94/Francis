"""Offline regression tests for the ingest acquisition orchestrator.

No live Docker: a fake command runner stands in for the daemon so the wrapper
path is exercised CI-safely. Live verification is separate (manual integration).
Covers: run-record creation, no-auto-approval, pause-at-gate, resume-only-after-
consumed-approval, wrapper invocation (not direct SandboxExecutor), promotion
persistence, blocked-path artifact, readback, and runtime-requirement
classification for ScreenEnv-like repos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from francis.governance import approvals
from francis.ingest import IngestService
from francis.ingest.ingest.runtime_requirements import classify_runtime_requirements
from francis.ingest.shared.models import RepoMap

pytestmark = pytest.mark.unit


def _git(path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _green_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "green"
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# green fixture\n", encoding="utf-8")
    (repo / "src" / "hello.txt").write_text("hi\n", encoding="utf-8")
    _git(repo)
    return repo


def _heavy_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "heavy"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "README.md").write_text("# heavy fixture\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname="heavy"\ndependencies=["docker>=7","playwright>=1.5","fastapi","requests","openai"]\n',
        encoding="utf-8",
    )
    (repo / "src" / "pkg" / "test_thing.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    _git(repo)
    return repo


def _docker_up_runner(argv, timeout):
    from francis.ingest.lab.lab_runtime import CommandResult

    key = argv[1] if len(argv) > 1 else ""
    if key == "version":
        return CommandResult(argv=list(argv), exit_code=0, stdout="27.0.0")
    if key == "image":
        return CommandResult(argv=list(argv), exit_code=0)
    if key == "run":
        return CommandResult(argv=list(argv), exit_code=0, stdout="ok")
    return CommandResult(argv=list(argv), exit_code=0)


def _drive_to_completion(svc, run):
    """Approve each gate as the operator and resume until terminal."""
    guard = 0
    while run["status"] == "paused_for_approval" and guard < 6:
        guard += 1
        approvals.decide(run["pending_approval_id"], "approve", actor="op")
        run = svc.continue_acquisition_after_approval(run["id"], actor="op")
    return run


# --- runtime requirement classification --------------------------------------
def test_classify_flags_screenenv_like_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _heavy_repo(tmp_path)
    rm = RepoMap(
        source_id="s",
        repo_root=str(repo),
        is_git_repo=True,
        manifest_files=["pyproject.toml"],
        dependency_manifests=["pyproject.toml"],
        test_files=["src/pkg/test_thing.py"],
    )
    req = classify_runtime_requirements(rm)
    assert req.requires_docker and req.requires_browser and req.requires_network
    assert req.requires_service_runtime and req.requires_external_credentials
    assert req.default_lab_compatible is False
    assert req.recommended_lab_profile.startswith("specialized")


def test_classify_clean_repo_is_default_compatible(tmp_path):
    repo = _green_repo(tmp_path)
    rm = RepoMap(source_id="s", repo_root=str(repo), is_git_repo=True)
    req = classify_runtime_requirements(rm)
    assert req.default_lab_compatible is True
    assert req.recommended_lab_profile == "default"


# --- orchestrator: no auto-grant, pause, resume ------------------------------
def test_acquire_creates_record_pauses_without_granting(tmp_path, monkeypatch):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    svc = IngestService(command_runner=_docker_up_runner)
    run = svc.acquire_source_candidate(_green_repo(tmp_path), opt_in=True, actor="op")
    assert run["status"] == "paused_for_approval"
    assert run["pending_approval_id"]
    assert run["id"].startswith("acq_")
    assert len(run["steps"]) >= 1
    # The orchestrator must NOT have granted the approval itself.
    approved = approvals.approved_dir() / f"{run['pending_approval_id']}.json"
    assert not approved.exists()


def test_continue_requires_granted_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    svc = IngestService(command_runner=_docker_up_runner)
    run = svc.acquire_source_candidate(_green_repo(tmp_path), opt_in=True, actor="op")
    # Resume WITHOUT approving -> still paused, explicitly says not yet granted.
    again = svc.continue_acquisition_after_approval(run["id"], actor="op")
    assert again["status"] == "paused_for_approval"
    assert again["error"] == "approval_not_yet_granted"


def test_full_acquisition_promotes_via_wrapper(tmp_path, monkeypatch):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_LAB_IMAGE", "francis-lab-base:pinned")
    svc = IngestService(command_runner=_docker_up_runner)
    run = svc.acquire_source_candidate(_green_repo(tmp_path), opt_in=True, actor="op")
    run = _drive_to_completion(svc, run)
    assert run["status"] == "promoted"
    assert len(run["approvals"]) == 3  # three genuine gates A,B,C
    res = run["result"]
    assert res["execution_mode"] == "real"
    assert res["exit_code"] == 0
    assert res["validation_status"] == "VALID"
    assert res["promotion_from"] == "drafted" and res["promotion_to"] == "runnable"
    assert res["promoted"] is True
    assert Path(res["receipt_path"]).exists()
    # Promotion persisted + acquisition surfaced in readback.
    rb = svc.readback(source_id=run["source_id"])
    assert rb["counts"]["acquisitions"] == 1
    assert rb["counts"]["lab_execution_runs"] == 1
    fresh = IngestService()
    cand = next(c for c in fresh.capabilities.list_for_source(run["source_id"]) if c.id == run["candidate_id"])
    assert cand.status == "runnable"


def test_incompatible_repo_blocks_execution_before_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    svc = IngestService(command_runner=_docker_up_runner)
    run = svc.acquire_source_candidate(_heavy_repo(tmp_path), candidate_id="run_project_tests", opt_in=True, actor="op")
    assert run["status"] == "blocked"
    assert run["classification"]["default_lab_compatible"] is False
    assert run["result"]["executed"] is False
    assert run["result"]["network_accessed"] is False
    assert run["result"]["recommended_lab_profile"].startswith("specialized")
    assert len(run["steps"]) == 0  # blocked before the governed chain ran
    assert Path(run["artifact_path"]).exists()
    assert svc.readback(source_id=run["source_id"])["counts"]["acquisitions"] == 1
