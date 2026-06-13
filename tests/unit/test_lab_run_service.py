"""Integration tests for IngestService.run_lab_capability (Francis Lab v0).

Offline: a fake command runner stands in for Docker, and the upstream consumed
approval is seeded directly as an artifact (the full approval chain is exercised
elsewhere). These assert the governance contract end-to-end: refusal without a
consumed approval, refusal of unsafe candidates, simulated default when Docker is
down, real-mode promotion only on real+valid evidence, and that every run writes
a receipt visible in readback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from francis.ingest import IngestService
from francis.ingest.lab.lab_runtime import CommandResult, SandboxExecutor
from francis.ingest.core.registry import write_ingest_record_artifact

pytestmark = pytest.mark.unit


def _clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "clean_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "README.md").write_text("# Clean Repo\n\nSafe local fixture.\n", encoding="utf-8")
    (repo / "src" / "index.ts").write_text("export const answer = 42;\n", encoding="utf-8")
    (repo / "tests" / "index.test.ts").write_text("import '../src/index';\n", encoding="utf-8")
    (repo / "package.json").write_text(
        '{\n  "name": "clean",\n  "main": "src/index.ts",\n  "scripts": {"test": "node --test"}\n}\n',
        encoding="utf-8",
    )
    return repo


def _docker_down_runner(argv, timeout):
    if len(argv) > 1 and argv[1] == "version":
        return CommandResult(argv=list(argv), exit_code=1, stderr="daemon down")
    return CommandResult(argv=list(argv), exit_code=0)


def _docker_up_runner(argv, timeout):
    key = argv[1] if len(argv) > 1 else ""
    if key == "version":
        return CommandResult(argv=list(argv), exit_code=0, stdout="27.0.0")
    if key == "image":
        return CommandResult(argv=list(argv), exit_code=0)  # inspect -> present
    if key == "run":
        return CommandResult(argv=list(argv), exit_code=0, stdout="ok", duration_ms=42)
    return CommandResult(argv=list(argv), exit_code=0)


def _setup(tmp_path, monkeypatch, runner):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_LAB_IMAGE", "francis-lab-base:pinned")
    repo = _clean_repo(tmp_path)
    service = IngestService(command_runner=runner)
    add = service.add_source(repo, actor="test.lab")
    source_id = add["source"]["id"]
    cands = service.extract_candidates(source_id, actor="test.lab")["candidates"]
    target = next(c for c in cands if c["name"] == "run_project_tests")
    return service, repo, source_id, target["id"]


def _seed_consumption(source_id: str, candidate_id: str, approval_id: str) -> None:
    write_ingest_record_artifact(
        "lab_sandboxed_rebuild_run_test_approval_consumptions",
        f"consume_{approval_id}",
        {
            "sandboxed_rebuild_run_test_approval_consumption": {
                "id": f"consume_{approval_id}",
                "approval_id": approval_id,
                "approval_request_id": f"req_{approval_id}",
                "sandboxed_boundary_id": f"boundary_{approval_id}",
                "source_id": source_id,
                "candidate_id": candidate_id,
                "candidate_name": "run_project_tests",
                "status": "consumed",
                "approval_consumed": True,
                "action_hash": "deadbeef",
            }
        },
    )


def _assert_refusal_receipt(result, *, expect_source_id=None):
    """Shared assertions: a refusal path still emits an auditable, negative-claims receipt."""
    run = result["lab_execution_run"]
    assert run["operation"] == "lab.execution.run"
    assert run["execution_mode"] == "refused"
    assert run["executed"] is False
    assert run["repo_code_executed"] is False
    assert run["execution_authority"] is False
    assert run["network_accessed"] is False
    assert run["wrote_to_repo"] is False
    assert run["promoted"] is False
    assert run["validation_status"] == "REFUSED"
    assert run["created_at"]
    assert run["commands_run"] == []
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert result["receipt"]["operation"] == "lab.execution.run"
    assert result["receipt"]["result_status"] == "refused"
    if expect_source_id is not None:
        assert run["source_id"] == expect_source_id


def test_refused_without_consumed_approval(monkeypatch, tmp_path):
    service, repo, src, _cap = _setup(tmp_path, monkeypatch, _docker_down_runner)
    result = service.run_lab_capability(repo, "run_project_tests", "appr_missing", opt_in=True, actor="t")
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert "sandboxed_rebuild_run_test_approval_not_consumed" in result["blockers"]
    # Refusal must still be receipted (the gap this fix closes).
    _assert_refusal_receipt(result, expect_source_id=src)
    assert result["lab_execution_run"]["failure_reason"] == "lab_run_refused"
    assert "blocker:sandboxed_rebuild_run_test_approval_not_consumed" in result["lab_execution_run"]["warnings"]
    readback = service.readback(source_id=src)
    assert readback["counts"]["lab_execution_runs"] == 1


def test_refused_candidate_unavailable_writes_receipt(monkeypatch, tmp_path):
    service, repo, src, _cap = _setup(tmp_path, monkeypatch, _docker_down_runner)
    result = service.run_lab_capability(repo, "no_such_candidate", "appr_x", opt_in=True, actor="t")
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["error"] == "capability_candidate_unavailable"
    _assert_refusal_receipt(result, expect_source_id=src)
    assert result["lab_execution_run"]["failure_reason"] == "capability_candidate_unavailable"
    # Candidate ref is preserved even though no candidate record resolved.
    assert result["lab_execution_run"]["candidate_name"] == "no_such_candidate"
    assert service.readback(source_id=src)["counts"]["lab_execution_runs"] == 1


def test_refused_repo_map_unavailable_writes_receipt(monkeypatch, tmp_path):
    service, repo, src, _cap = _setup(tmp_path, monkeypatch, _docker_down_runner)
    # Candidate is already persisted; remove the repo-map artifact so _load_repo_map fails.
    repo_map_path = service.sources.get(src).metadata.get("repo_map_path")
    assert repo_map_path and Path(repo_map_path).exists()
    Path(repo_map_path).unlink()
    result = service.run_lab_capability(repo, "run_project_tests", "appr_y", opt_in=True, actor="t")
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["error"] == "repo_map_unavailable"
    _assert_refusal_receipt(result, expect_source_id=src)
    assert result["lab_execution_run"]["failure_reason"] == "repo_map_unavailable"


def test_refused_unsafe_candidate_writes_receipt(monkeypatch, tmp_path):
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _clean_repo(tmp_path)
    (repo / ".env").write_text("API_TOKEN=super-secret-value\n", encoding="utf-8")
    (repo / "deploy.sh").write_text("#!/bin/sh\nrm -rf /\n", encoding="utf-8")
    service = IngestService(command_runner=_docker_down_runner)
    src = service.add_source(repo, actor="t")["source"]["id"]
    cands = service.extract_candidates(src, actor="t")["candidates"]
    target = next(c for c in cands if c["name"] == "run_project_tests")
    _seed_consumption(src, target["id"], "appr_unsafe2")
    result = service.run_lab_capability(repo, "run_project_tests", "appr_unsafe2", opt_in=True, actor="t")
    assert result["ok"] is False
    _assert_refusal_receipt(result, expect_source_id=src)
    # No execution occurred despite a valid consumed approval — safety blocked it.
    assert any(w.startswith("blocker:") for w in result["lab_execution_run"]["warnings"])


def test_refused_for_unsafe_candidate(monkeypatch, tmp_path):
    # A repo with a destructive/credential signal makes run_project_tests unsafe.
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _clean_repo(tmp_path)
    (repo / ".env").write_text("API_TOKEN=super-secret-value\n", encoding="utf-8")
    (repo / "deploy.sh").write_text("#!/bin/sh\nrm -rf /\n", encoding="utf-8")
    service = IngestService(command_runner=_docker_down_runner)
    add = service.add_source(repo, actor="t")
    src = add["source"]["id"]
    cands = service.extract_candidates(src, actor="t")["candidates"]
    target = next(c for c in cands if c["name"] == "run_project_tests")
    _seed_consumption(src, target["id"], "appr_unsafe")
    result = service.run_lab_capability(repo, "run_project_tests", "appr_unsafe", opt_in=True, actor="t")
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert any("blocked_risk_signal" in b or "destructive" in b for b in result["blockers"])


def test_simulated_default_when_docker_down(monkeypatch, tmp_path):
    service, repo, src, cap = _setup(tmp_path, monkeypatch, _docker_down_runner)
    _seed_consumption(src, cap, "appr_sim")
    result = service.run_lab_capability(repo, "run_project_tests", "appr_sim", opt_in=True, actor="t")
    assert result["ok"] is True
    assert result["execution_mode"] == "simulated"
    assert result["status"] == "PARTIAL"
    run = result["lab_execution_run"]
    assert run["executed"] is False
    assert run["repo_code_executed"] is False
    assert run["execution_authority"] is False
    # No promotion on simulated evidence.
    assert result["candidate"]["status"] != "validated"
    # Receipt + artifact were written and are visible in readback.
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    readback = service.readback(source_id=src)
    assert readback["counts"]["lab_execution_runs"] == 1


def test_simulated_when_opt_in_absent_even_if_docker_up(monkeypatch, tmp_path):
    service, repo, src, cap = _setup(tmp_path, monkeypatch, _docker_up_runner)
    _seed_consumption(src, cap, "appr_noopt")
    result = service.run_lab_capability(repo, "run_project_tests", "appr_noopt", opt_in=False, actor="t")
    assert result["execution_mode"] == "simulated"
    assert "opt_in_not_provided" in result["simulated_reasons"]


def test_real_run_valid_promotes_one_rung(monkeypatch, tmp_path):
    service, repo, src, cap = _setup(tmp_path, monkeypatch, _docker_up_runner)
    _seed_consumption(src, cap, "appr_real")
    # Ensure executor uses the same fake runner.
    service.sandbox = SandboxExecutor(_docker_up_runner)
    result = service.run_lab_capability(repo, "run_project_tests", "appr_real", opt_in=True, actor="t")
    assert result["ok"] is True
    assert result["execution_mode"] == "real"
    assert result["status"] == "VALID"
    run = result["lab_execution_run"]
    assert run["executed"] is True
    assert run["repo_code_executed"] is True
    # discovered -> drafted (one rung), never leaping to validated.
    assert result["promotion"]["from_status"] == "discovered"
    assert result["promotion"]["to_status"] == "drafted"
    assert result["candidate"]["status"] == "drafted"


def test_real_run_fails_closed_when_image_absent(monkeypatch, tmp_path):
    def runner(argv, timeout):
        key = argv[1] if len(argv) > 1 else ""
        if key == "version":
            return CommandResult(argv=list(argv), exit_code=0, stdout="27.0.0")
        if key == "image":
            return CommandResult(argv=list(argv), exit_code=1)  # inspect -> absent
        return CommandResult(argv=list(argv), exit_code=0)

    service, repo, src, cap = _setup(tmp_path, monkeypatch, runner)
    service.sandbox = SandboxExecutor(runner)
    _seed_consumption(src, cap, "appr_noimg")
    result = service.run_lab_capability(repo, "run_project_tests", "appr_noimg", opt_in=True, actor="t")
    # Falls back to simulated; never attempts docker run; no promotion.
    assert result["execution_mode"] == "simulated"
    assert result["lab_execution_run"]["failure_reason"] == "pinned_image_not_present_locally_refused_to_pull"
    assert result["candidate"]["status"] != "validated"
