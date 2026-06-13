"""CLI + API exposure tests for the Forge synthesis / acquisition corridor."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from francis.__main__ import main
from francis.api.app import create_app
from francis.ingest import IngestService
from francis.ingest.core.local_builder import (
    LocalOllamaBuilder,
    OllamaBuilderConfig,
    OllamaBuildRequest,
    compile_capability_spec_from_candidate,
)

_FORGE_ACTOR = "test.ingest.forge"
_CLEAN_PROPOSAL = (
    "diff --git a/src/francis/ingest/exposure_cap.py b/src/francis/ingest/exposure_cap.py\n"
    "--- /dev/null\n"
    "+++ b/src/francis/ingest/exposure_cap.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def exposure_cap(a, b):\n"
    "+    return a + b\n"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "francis" / "ingest").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    return repo


def _make_builder_run(service: IngestService, repo: Path, proposal: str) -> str:
    source = service.sources.get(service.add_source(repo, actor="op")["source"]["id"])
    service.inspect_repo(repo, actor="op")
    source = service.sources.get(source.id)
    candidate = service._candidate_from_ref(source, "inspect_project_structure", actor="op")
    repo_map = service._load_repo_map(source)
    spec = compile_capability_spec_from_candidate(source=source, candidate=candidate, repo_map=repo_map)
    result = LocalOllamaBuilder(
        config=OllamaBuilderConfig(host="http://127.0.0.1:11434", model="fake"),
        client=lambda *_a: proposal,
        receipt_writer=service.receipts,
    ).run(OllamaBuildRequest.from_spec(spec), actor="op")
    return result.record.builder_run_id


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_forge_review_api_clean(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _repo(tmp_path)
    run_id = _make_builder_run(IngestService(), repo, _CLEAN_PROPOSAL)

    response = TestClient(create_app()).post(
        "/ingest/forge/review",
        json={
            "source_or_path": str(repo),
            "builder_run_id": run_id,
            "proposal_text": _CLEAN_PROPOSAL,
            "actor": _FORGE_ACTOR,
        },
    )
    body = response.json()
    assert body["kind"] == "francis.ingest.forge.review"
    assert body["verdict"] == "clean"
    assert body["builder_proposal_review"]["patch_applied"] is False


def test_forge_review_api_permission_denied(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _repo(tmp_path)
    response = TestClient(create_app()).post(
        "/ingest/forge/review",
        json={"source_or_path": str(repo), "builder_run_id": "x", "actor": "intruder.no.scope"},
    )
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "api_permission_denied"


def test_acquire_start_api(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _repo(tmp_path)
    IngestService().add_source(repo, actor="op")
    response = TestClient(create_app()).post(
        "/ingest/acquire/start",
        json={"source_or_path": str(repo), "actor": _FORGE_ACTOR},
    )
    body = response.json()
    assert body["kind"] == "francis.ingest.acquire.start"
    # A real governed acquisition run record was produced (paused/blocked/etc.).
    assert body.get("id", "").startswith("acq_")
    assert body["status"] in (
        "paused_for_approval",
        "blocked",
        "refused",
        "completed",
        "promoted",
        "invalid",
        "failed",
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_forge_review(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _repo(tmp_path)
    run_id = _make_builder_run(IngestService(), repo, _CLEAN_PROPOSAL)
    proposal_file = tmp_path / "proposal.diff"
    proposal_file.write_text(_CLEAN_PROPOSAL, encoding="utf-8")

    rc = main(["forge", "review", str(repo), run_id, "--proposal-file", str(proposal_file), "--actor", "op"])
    assert rc == 0
    # The review record was persisted.
    assert IngestService().readback()["counts"]["builder_proposal_reviews"] == 1


def test_cli_acquire_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    repo = _repo(tmp_path)
    rc = main(["acquire", "start", str(repo), "--actor", "op"])
    # Returns an int exit code; a governed acquisition run was recorded.
    assert rc in (0, 1)
    assert IngestService().readback()["counts"]["acquisitions"] >= 1
