from __future__ import annotations

from pathlib import Path

import pytest

from francis.ingest import IngestService
from francis.ingest.core.local_builder import (
    COPY_POLICY_DO_NOT_COPY,
    LocalOllamaBuilder,
    OllamaBuildRequest,
    build_ollama_prompt,
    compile_capability_spec_from_candidate,
    forbidden_scope_violations,
)
from francis.ingest.ingest.runtime_requirements import classify_runtime_requirements
from francis.ingest.shared.models import (
    CapabilityCandidate,
    RepoMap,
    SourcePermissionProfile,
    SourceRecord,
)

pytestmark = pytest.mark.unit


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    (repo / "src" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "tests" / "test_main.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    return repo


def _screenenv_like_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "screenenv_like"
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# screenenv-like fixture\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname="screenenv-like"\ndependencies=["docker","playwright","fastapi","requests","openai"]\n',
        encoding="utf-8",
    )
    (repo / "src" / "test_gui.py").write_text("import selenium\n", encoding="utf-8")
    return repo


def _source(repo: Path) -> SourceRecord:
    return SourceRecord(
        id="src_test",
        type="repo",
        original_path=str(repo),
        canonical_path=str(repo),
        created_at="2026-06-11T00:00:00+00:00",
        updated_at="2026-06-11T00:00:00+00:00",
        fingerprint="sha256:test",
        status="indexed",
    )


def _candidate(name: str = "inspect_project_structure") -> CapabilityCandidate:
    execute = name == "run_project_tests"
    return CapabilityCandidate(
        id=f"cap_{name}",
        name=name,
        source_id="src_test",
        source_type="repo",
        status="drafted" if not execute else "discovered",
        description="Inspect or validate a source candidate.",
        permissions_required=SourcePermissionProfile(read=True, execute=execute),
        risk_level="low" if not execute else "medium",
        suggested_validation=["pytest -q"] if execute else [],
    )


def _repo_map(repo: Path) -> RepoMap:
    return RepoMap(
        source_id="src_test",
        repo_root=str(repo),
        is_git_repo=False,
        manifest_files=["pyproject.toml"],
        dependency_manifests=["pyproject.toml"],
        test_files=["tests/test_main.py"],
        docs_readmes=["README.md"],
        source_directories=["src"],
        license_file="",
        suggested_validation_commands=[{"command": "pytest -q"}],
    )


def test_capability_spec_compiler_creates_francis_spec(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    spec = compile_capability_spec_from_candidate(
        source=_source(repo),
        candidate=_candidate("inspect_project_structure"),
        repo_map=_repo_map(repo),
    )

    assert spec.source_id == "src_test"
    assert spec.candidate_id == "cap_inspect_project_structure"
    assert spec.capability_name == "inspect_project_structure"
    assert "without executing source code" in spec.francis_native_purpose
    assert spec.copy_policy == COPY_POLICY_DO_NOT_COPY
    assert spec.conceptual_rebuild_only is True


def test_spec_includes_allowed_forbidden_and_do_not_copy_policy(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    spec = compile_capability_spec_from_candidate(
        source=_source(repo),
        candidate=_candidate("run_project_tests"),
        repo_map=_repo_map(repo),
        allowed_files=["src/francis/ingest/**"],
        forbidden_files=["ROADMAP.md", "AGENTS.md"],
    )

    assert spec.build_task.allowed_files == ["src/francis/ingest/**"]
    assert "ROADMAP.md" in spec.build_task.forbidden_files
    assert any("copy_third_party" in item for item in spec.risk.forbidden_behaviors)
    assert "lab_validation" == spec.capability_class


def test_screenenv_like_requirements_are_not_default_lab_compatible(tmp_path: Path) -> None:
    repo = _screenenv_like_repo(tmp_path)
    repo_map = RepoMap(
        source_id="src_test",
        repo_root=str(repo),
        is_git_repo=False,
        manifest_files=["pyproject.toml"],
        dependency_manifests=["pyproject.toml"],
        test_files=["src/test_gui.py"],
    )
    req = classify_runtime_requirements(repo_map)
    spec = compile_capability_spec_from_candidate(
        source=_source(repo),
        candidate=_candidate("run_project_tests"),
        repo_map=repo_map,
        runtime_requirements=req,
    )

    assert spec.risk.default_lab_compatible is False
    assert spec.risk.recommended_next_action == "capability study / specialized Lab profile design"
    assert spec.capability_class == "isolated desktop / GUI automation / sandbox environment"
    assert "specialized_lab_profile_required_before_execution" in spec.validation.promotion_requirements


def test_ollama_unavailable_returns_clean_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    spec = compile_capability_spec_from_candidate(
        source=_source(_repo(tmp_path)),
        candidate=_candidate(),
        repo_map=_repo_map(_repo(tmp_path)),
    )

    def unavailable(_host: str, _model: str, _prompt: str, _timeout: int) -> str:
        raise OSError("connection refused")

    result = LocalOllamaBuilder(client=unavailable).run(OllamaBuildRequest.from_spec(spec), actor="test")

    assert result.ok is False
    assert result.status == "unavailable"
    assert result.record.ollama_available is False
    assert result.record.patch_applied is False
    assert Path(result.artifact_path).exists()
    assert Path(result.receipt_path).exists()


def test_prompt_omits_forbidden_paths(tmp_path: Path) -> None:
    spec = compile_capability_spec_from_candidate(
        source=_source(_repo(tmp_path)),
        candidate=_candidate(),
        repo_map=_repo_map(_repo(tmp_path)),
        forbidden_files=["ROADMAP.md", "src/francis/governance/**"],
    )
    prompt = build_ollama_prompt(OllamaBuildRequest.from_spec(spec))

    assert "ROADMAP.md" not in prompt
    assert "src/francis/governance" not in prompt
    assert "forbidden_paths_enforced_but_omitted" in prompt


def test_builder_persists_record_and_readback_lists_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _repo(tmp_path)
    service = IngestService()
    add = service.add_source(repo, actor="test")
    source_id = add["source"]["id"]

    def fake_client(_host: str, _model: str, _prompt: str, _timeout: int) -> str:
        return "Plan only: add a focused unit test. No patch applied."

    source = service.sources.get(source_id)
    candidate = service._candidate_from_ref(source, "inspect_project_structure", actor="test")
    repo_map = service._load_repo_map(source)
    spec = compile_capability_spec_from_candidate(source=source, candidate=candidate, repo_map=repo_map)
    result = LocalOllamaBuilder(client=fake_client, receipt_writer=service.receipts).run(
        OllamaBuildRequest.from_spec(spec), actor="test"
    )
    readback = service.list_builder_runs(source_id=source_id)

    assert result.status == "proposed"
    assert result.record.patch_proposed is False
    assert result.record.patch_applied is False
    assert readback["count"] == 1
    assert readback["builder_runs"][0]["builder_run"]["builder_run_id"] == result.record.builder_run_id


def test_adapter_does_not_apply_patch_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    spec = compile_capability_spec_from_candidate(
        source=_source(_repo(tmp_path)),
        candidate=_candidate(),
        repo_map=_repo_map(_repo(tmp_path)),
    )

    def fake_patch(_host: str, _model: str, _prompt: str, _timeout: int) -> str:
        return "diff --git a/tests/tmp_test.py b/tests/tmp_test.py\n+++ b/tests/tmp_test.py\n@@\n+def test_x(): pass\n"

    result = LocalOllamaBuilder(client=fake_patch).run(OllamaBuildRequest.from_spec(spec), actor="test")

    assert result.status == "proposed"
    assert result.record.patch_proposed is True
    assert result.record.patch_applied is False
    assert result.proposed_patch_text.startswith("diff --git")


def test_model_refusal_is_recorded_without_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    spec = compile_capability_spec_from_candidate(
        source=_source(_repo(tmp_path)),
        candidate=_candidate(),
        repo_map=_repo_map(_repo(tmp_path)),
    )

    def fake_refusal(_host: str, _model: str, _prompt: str, _timeout: int) -> str:
        return "Refused. The requested edit crosses a forbidden path."

    result = LocalOllamaBuilder(client=fake_refusal).run(OllamaBuildRequest.from_spec(spec), actor="test")

    assert result.status == "refused"
    assert result.record.refusal_reason == "model_refused"
    assert result.record.patch_applied is False


def test_forbidden_files_cannot_be_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    spec = compile_capability_spec_from_candidate(
        source=_source(_repo(tmp_path)),
        candidate=_candidate(),
        repo_map=_repo_map(_repo(tmp_path)),
    )
    request = OllamaBuildRequest.from_spec(spec)
    request = OllamaBuildRequest(
        task_id=request.task_id,
        spec=request.spec,
        model=request.model,
        allowed_files=["ROADMAP.md"],
        forbidden_files=["ROADMAP.md"],
        validation_commands=request.validation_commands,
        risk_level=request.risk_level,
        stop_conditions=request.stop_conditions,
    )

    def should_not_call(_host: str, _model: str, _prompt: str, _timeout: int) -> str:
        raise AssertionError("builder called despite forbidden scope")

    result = LocalOllamaBuilder(client=should_not_call).run(request, actor="test")

    assert result.status == "blocked"
    assert result.record.ollama_available is False
    assert result.record.patch_applied is False
    assert forbidden_scope_violations(["ROADMAP.md"], ["ROADMAP.md"])
