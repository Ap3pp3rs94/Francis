from pathlib import Path

from francis_brain.apprenticeship import (
    add_session_step,
    create_session,
    generalize_session,
    summarize_apprenticeship,
    write_skill_artifact,
)
from francis_core.workspace_fs import WorkspaceFS


def test_apprenticeship_generalization_and_skill_artifact(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[workspace], journal_path=workspace / "journals" / "fs.jsonl")

    session = create_session(
        fs,
        title="Repository Triage",
        objective="Teach Francis how to inspect a repo before editing",
        tags=["git", "review"],
    )
    session, _step_one = add_session_step(
        fs,
        session_id=session["id"],
        kind="command",
        action="git status --short",
        intent="inspect repo state",
        notes="Start with a cleanliness check.",
    )
    session, _step_two = add_session_step(
        fs,
        session_id=session["id"],
        kind="command",
        action="git diff -- README.md",
        intent="inspect changed file",
        artifact_path="README.md",
    )

    session, generalization = generalize_session(fs, session["id"])
    session, artifact = write_skill_artifact(fs, session["id"])
    summary = summarize_apprenticeship(fs)

    assert session["status"] == "review"
    assert len(generalization["workflow"]) == 2
    assert generalization["parameter_candidates"][0]["example"] == "README.md"
    assert artifact["path"].endswith(f"{session['id']}.json")
    assert artifact["forge_payload"]["name"] == "Repository Triage"
    assert summary["review_count"] == 1
