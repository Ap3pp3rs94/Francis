"""CI-safe tests for the Forge synthesis corridor (no live Ollama, no Docker).

Covers the governed forward arc after a builder proposal:
review (digest-gated) -> apply preflight -> approval request -> single-use
consumption -> honest apply boundary (refusal) -> Lab validation plan, plus the
deterministic evaluators (scope, copy-overlap, secret/destructive tokens).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from francis.governance import approvals
from francis.ingest import IngestService
from francis.ingest.core import proposal_review as pr
from francis.ingest.core.local_builder import (
    LocalOllamaBuilder,
    OllamaBuildRequest,
    OllamaBuilderConfig,
    compile_capability_spec_from_candidate,
)

pytestmark = pytest.mark.unit

# A clean, in-scope unified diff (touches an allowed ingest path only).
_CLEAN_PROPOSAL = (
    "diff --git a/src/francis/ingest/demo_cap.py b/src/francis/ingest/demo_cap.py\n"
    "--- a/src/francis/ingest/demo_cap.py\n"
    "+++ b/src/francis/ingest/demo_cap.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def francis_native_capability(a, b):\n"
    "+    return a + b\n"
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


def _proposal_builder_run(service: IngestService, repo: Path, proposal_text: str, *, client=None) -> str:
    """Drive a real builder run with a fake client returning ``proposal_text``."""

    source = service.sources.get(service.add_source(repo, actor="op")["source"]["id"])
    service.inspect_repo(repo, actor="op")
    source = service.sources.get(source.id)
    candidate = service._candidate_from_ref(source, "inspect_project_structure", actor="op")
    repo_map = service._load_repo_map(source)
    spec = compile_capability_spec_from_candidate(source=source, candidate=candidate, repo_map=repo_map)
    fake = client or (lambda _h, _m, _p, _t: proposal_text)
    result = LocalOllamaBuilder(
        config=OllamaBuilderConfig(host="http://127.0.0.1:11434", model="fake"),
        client=fake,
        receipt_writer=service.receipts,
    ).run(OllamaBuildRequest.from_spec(spec), actor="op")
    return result.record.builder_run_id


# --------------------------------------------------------------------------- #
# Deterministic evaluators
# --------------------------------------------------------------------------- #
def test_diff_parser_extracts_files_and_counts() -> None:
    parsed = pr.parse_unified_diff(_CLEAN_PROPOSAL)
    assert parsed.is_diff is True
    assert parsed.well_formed is True
    assert parsed.files == ["src/francis/ingest/demo_cap.py"]
    assert parsed.hunk_count == 1
    assert len(parsed.added_lines) == 2


def test_scope_blocks_forbidden_and_out_of_scope() -> None:
    parsed = pr.parse_unified_diff(
        "diff --git a/src/francis/governance/redaction.py b/src/francis/governance/redaction.py\n"
        "--- a/src/francis/governance/redaction.py\n+++ b/src/francis/governance/redaction.py\n"
        "@@ -0,0 +1,1 @@\n+EVIL = 1\n"
    )
    blockers, outside = pr.scope_findings(
        parsed,
        allowed_files=["src/francis/ingest/**"],
        forbidden_files=["src/francis/governance/**"],
        max_files_changed=3,
    )
    assert any(b.startswith("touches_forbidden_file:") for b in blockers)
    assert outside == ["src/francis/governance/redaction.py"]


def test_token_scan_flags_secret_and_destructive() -> None:
    findings = pr.token_scan_findings(["API_KEY = 'abc'", "shutil.rmtree('/')"])
    assert "proposal_contains_secret_like_token" in findings
    assert "proposal_contains_destructive_token" in findings


def test_copy_overlap_flags_verbatim_source(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    body = "\n".join(f"def function_number_{i}(value_{i}):\n    return value_{i} * {i} + 7" for i in range(20))
    (src / "original.py").write_text(body, encoding="utf-8")
    findings, metrics = pr.copy_overlap_findings(body.splitlines(), source_root=str(tmp_path))
    assert any(f.startswith("possible_third_party_copy:") for f in findings)
    assert metrics["max_overlap_ratio"] >= pr._COPY_OVERLAP_FLAG_RATIO


# --------------------------------------------------------------------------- #
# Review gate (digest-gated)
# --------------------------------------------------------------------------- #
def test_review_indeterminate_without_full_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)

    out = service.review_builder_proposal(repo, run_id, actor="op")

    assert out["verdict"] == "indeterminate"
    assert "no_full_proposal_text_supplied" in out["builder_proposal_review"]["blockers"]
    assert out["builder_proposal_review"]["digest_verified"] is False


def test_review_indeterminate_on_digest_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)

    out = service.review_builder_proposal(repo, run_id, "a different proposal entirely", actor="op")

    assert out["verdict"] == "indeterminate"
    assert "supplied_text_digest_mismatch" in out["builder_proposal_review"]["blockers"]


def test_review_clean_on_matching_in_scope_proposal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)

    out = service.review_builder_proposal(repo, run_id, _CLEAN_PROPOSAL, actor="op")
    review = out["builder_proposal_review"]

    assert out["verdict"] == "clean"
    assert review["digest_verified"] is True
    assert review["proposal_kind"] == "patch"
    assert review["touched_files"] == ["src/francis/ingest/demo_cap.py"]
    assert review["patch_applied"] is False


def test_review_blocks_forbidden_path_proposal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    forbidden = (
        "diff --git a/src/francis/governance/redaction.py b/src/francis/governance/redaction.py\n"
        "--- a/src/francis/governance/redaction.py\n+++ b/src/francis/governance/redaction.py\n"
        "@@ -0,0 +1,1 @@\n+BACKDOOR = True\n"
    )
    run_id = _proposal_builder_run(service, repo, forbidden)

    out = service.review_builder_proposal(repo, run_id, forbidden, actor="op")

    assert out["verdict"] == "blocked"
    assert out["ok"] is False
    assert any(b.startswith("touches_forbidden_file:") for b in out["builder_proposal_review"]["blockers"])


def test_review_digest_matches_builder_digest_function() -> None:
    """The review gate's digest must equal the builder's recorded digest for the
    same text, incl. non-ASCII -- otherwise every review silently goes indeterminate."""
    from francis.ingest.core import local_builder

    sample = "diff café — ünïcode +Δ\n+line\n"
    assert pr.text_digest(sample) == local_builder._text_digest(sample)


# --------------------------------------------------------------------------- #
# Apply corridor: preflight -> request -> consume (single-use) -> boundary
# --------------------------------------------------------------------------- #
def test_apply_preflight_blocks_until_review_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)

    # No review yet -> preflight blocked.
    pf_missing = service.preflight_forge_apply(repo, run_id, actor="op")
    assert pf_missing["status"] == "blocked"
    assert "proposal_review_missing" in pf_missing["forge_apply_preflight"]["blockers"]

    service.review_builder_proposal(repo, run_id, _CLEAN_PROPOSAL, actor="op")
    pf = service.preflight_forge_apply(repo, run_id, actor="op")
    assert pf["status"] == "needs_approval"
    assert pf["forge_apply_preflight"]["patch_applied"] is False


def test_full_apply_corridor_is_single_use_and_never_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)
    service.review_builder_proposal(repo, run_id, _CLEAN_PROPOSAL, actor="op")
    service.preflight_forge_apply(repo, run_id, actor="op")

    request = service.request_forge_apply_approval(repo, run_id, actor="op")
    approval_id = request["forge_apply_approval_request"]["approval_id"]
    assert request["status"] == "needs_approval"

    # Consuming before the operator approves is blocked (no auto-grant).
    before = service.consume_forge_apply_approval(repo, run_id, approval_id, actor="op")
    assert before["status"] == "blocked"
    assert any(b.startswith("approval_not_approved") for b in before["blockers"])

    approvals.decide(approval_id, "approve", actor="operator")
    consumed = service.consume_forge_apply_approval(repo, run_id, approval_id, actor="op")
    assert consumed["status"] == "consumed"
    assert consumed["forge_apply_approval_consumption"]["single_use_enforced"] is True
    assert consumed["forge_apply_approval_consumption"]["patch_applied"] is False

    # Reuse is blocked.
    reuse = service.consume_forge_apply_approval(repo, run_id, approval_id, actor="op")
    assert reuse["status"] == "blocked"
    assert "forge_apply_approval_already_consumed" in reuse["blockers"]

    # Even with a consumed approval, applying is refused.
    boundary = service.boundary_forge_apply(repo, run_id, approval_id, actor="op")
    assert boundary["status"] == "blocked"
    assert boundary["forge_apply_boundary"]["apply_refused"] is True
    assert boundary["forge_apply_boundary"]["patch_applied"] is False
    assert boundary["forge_apply_boundary"]["wrote_to_repo"] is False
    assert boundary["execution"]["execution_authority"] is False


def test_validation_plan_projects_lab_path_without_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)
    # Compile a spec artifact so the validation plan can read its commands.
    service.compile_capability_spec(repo, "inspect_project_structure", actor="op")
    service.review_builder_proposal(repo, run_id, _CLEAN_PROPOSAL, actor="op")

    plan = service.plan_forge_validation(repo, run_id, actor="op")

    assert plan["status"] == "planned"
    vp = plan["forge_validation_plan"]
    assert vp["validation_path"] == "francis_lab_v0_sandboxed_rebuild_run_test"
    assert vp["requires_separate_lab_execution_approval"] is True
    assert vp["executed"] is False
    assert vp["capability_promoted"] is False


def test_readback_surfaces_forge_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    service = IngestService()
    repo = _repo(tmp_path)
    run_id = _proposal_builder_run(service, repo, _CLEAN_PROPOSAL)
    source_id = service.sources.list()[0].id
    service.review_builder_proposal(repo, run_id, _CLEAN_PROPOSAL, actor="op")
    service.preflight_forge_apply(repo, run_id, actor="op")

    counts = service.readback(source_id=source_id)["counts"]
    assert counts["builder_proposal_reviews"] == 1
    assert counts["forge_apply_preflights"] == 1
