"""CI-safe tests for the Forge synthesis orchestrator (ingest pushes synthesis).

Drives spec -> builder proposal -> digest-gated review -> apply preflight ->
[pause at the real francis.forge.apply gate] -> consume -> apply boundary
(refusal) -> validation plan, all with an injected deterministic builder client
(no live Ollama, no Docker).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from francis.governance import approvals
from francis.ingest import IngestService

pytestmark = pytest.mark.unit

_IN_SCOPE_PROPOSAL = (
    "diff --git a/src/francis/ingest/synth_cap.py b/src/francis/ingest/synth_cap.py\n"
    "--- a/src/francis/ingest/synth_cap.py\n"
    "+++ b/src/francis/ingest/synth_cap.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def francis_synth(a, b):\n"
    "+    return a - b\n"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    (repo / "src" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "tests" / "test_main.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    return repo


def _client(text: str):
    return lambda _host, _model, _prompt, _timeout: text


def test_synthesis_pushes_to_apply_gate_and_pauses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)

    out = service.synthesize_capability(
        repo, "inspect_project_structure", actor="op", builder_client=_client(_IN_SCOPE_PROPOSAL)
    )

    assert out["state"] == "paused_for_approval"
    assert out["review_verdict"] == "clean"
    assert out["builder_run_id"]
    assert out["pending_approval_id"]
    labels = [s["label"] for s in out["steps"]]
    assert labels == ["compile_spec", "builder_proposal", "review", "apply_preflight", "request_apply_approval"]
    # No approval was granted by the orchestrator.
    assert not (approvals.approved_dir() / f"{out['pending_approval_id']}.json").exists()


def test_synthesis_blocks_on_forbidden_proposal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    forbidden = (
        "diff --git a/src/francis/governance/redaction.py b/src/francis/governance/redaction.py\n"
        "--- a/src/francis/governance/redaction.py\n+++ b/src/francis/governance/redaction.py\n"
        "@@ -0,0 +1,1 @@\n+BACKDOOR = True\n"
    )

    out = service.synthesize_capability(repo, actor="op", builder_client=_client(forbidden))

    assert out["state"] == "blocked"
    assert out["review_verdict"] == "blocked"
    # Never reached the apply gate.
    assert not out["pending_approval_id"]
    assert "request_apply_approval" not in [s["label"] for s in out["steps"]]


def test_synthesis_resume_requires_granted_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    started = service.synthesize_capability(repo, actor="op", builder_client=_client(_IN_SCOPE_PROPOSAL))
    run_id = started["id"]

    # Resume before approval -> still paused, not auto-granted.
    early = service.continue_synthesis_after_approval(run_id, actor="op")
    assert early["status"] == "paused_for_approval"
    assert early["error"] == "approval_not_yet_granted"

    approvals.decide(started["pending_approval_id"], "approve", actor="operator")
    resumed = service.continue_synthesis_after_approval(run_id, actor="op")

    # Approved + consumed, but apply is refused: honest terminal state.
    assert resumed["state"] == "refused"
    assert resumed["result"]["apply_refused"] is True
    assert resumed["result"]["patch_applied"] is False
    assert resumed["result"]["capability_promoted"] is False
    labels = [s["label"] for s in resumed["steps"]]
    assert "consume_apply_approval" in labels
    assert "apply_boundary" in labels
    assert "validation_plan" in labels


def test_synthesis_blocks_when_builder_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)

    def _unavailable(_host, _model, _prompt, _timeout):
        raise ConnectionError("ollama unreachable")

    out = service.synthesize_capability(repo, actor="op", builder_client=_unavailable)

    assert out["state"] == "blocked"
    assert any(w.startswith("builder_unavailable") for w in out["warnings"])
    assert out["result"]["patch_applied"] is False


def test_synthesis_run_surfaces_in_readback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    service.synthesize_capability(repo, actor="op", builder_client=_client(_IN_SCOPE_PROPOSAL))
    source_id = service.sources.list()[0].id

    rb = service.readback(source_id=source_id)
    assert rb["counts"]["forge_synthesis_runs"] == 1
