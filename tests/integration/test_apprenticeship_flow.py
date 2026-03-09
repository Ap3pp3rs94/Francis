from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app
from francis_brain.ledger import RunLedger
from francis_core.workspace_fs import WorkspaceFS
import services.orchestrator.app.lens_snapshot as lens_snapshot
import services.orchestrator.app.routes.apprenticeship as apprenticeship_routes
import services.orchestrator.app.routes.forge as forge_routes
import services.orchestrator.app.routes.lens as lens_routes


client = TestClient(app)


def _wire_workspace(monkeypatch, tmp_path: Path) -> Path:
    workspace = (tmp_path / "workspace").resolve()
    repo_root = workspace.parent.resolve()

    def _bind(module) -> None:
        fs = WorkspaceFS(
            roots=[workspace],
            journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
        )
        monkeypatch.setattr(module, "_workspace_root", workspace)
        if hasattr(module, "_repo_root"):
            monkeypatch.setattr(module, "_repo_root", repo_root)
        monkeypatch.setattr(module, "_fs", fs)
        if hasattr(module, "_ledger"):
            monkeypatch.setattr(module, "_ledger", RunLedger(fs, rel_path="runs/run_ledger.jsonl"))

    for module in [apprenticeship_routes, forge_routes, lens_routes]:
        _bind(module)
    monkeypatch.setattr(lens_snapshot, "DEFAULT_WORKSPACE_ROOT", workspace)
    return workspace


def test_apprenticeship_route_can_teach_generalize_and_skillize(monkeypatch, tmp_path: Path) -> None:
    _wire_workspace(monkeypatch, tmp_path)
    title = f"Teach-{uuid4()}"

    created = client.post(
        "/apprenticeship/sessions",
        json={"title": title, "objective": "Teach repo triage", "tags": ["git", "review"]},
    )
    assert created.status_code == 200
    session_id = created.json()["session"]["id"]

    step_one = client.post(
        f"/apprenticeship/sessions/{session_id}/steps",
        json={
            "kind": "command",
            "action": "git status --short",
            "intent": "inspect repo state",
            "notes": "Look for dirty files first.",
        },
    )
    assert step_one.status_code == 200

    step_two = client.post(
        f"/apprenticeship/sessions/{session_id}/steps",
        json={
            "kind": "command",
            "action": "git diff -- README.md",
            "intent": "inspect changed file",
            "artifact_path": "README.md",
        },
    )
    assert step_two.status_code == 200

    replay = client.get(f"/apprenticeship/sessions/{session_id}/replay")
    assert replay.status_code == 200
    assert replay.json()["replay"]["step_count"] == 2

    generalized = client.post(f"/apprenticeship/sessions/{session_id}/generalize")
    assert generalized.status_code == 200
    generalization = generalized.json()["generalization"]
    assert generalization["skill_candidate"]["forge_payload"]["name"] == title
    assert generalization["parameter_candidates"][0]["example"] == "README.md"

    skillized = client.post(f"/apprenticeship/sessions/{session_id}/skillize")
    assert skillized.status_code == 200
    payload = skillized.json()
    assert payload["skill_artifact"]["path"].startswith("apprenticeship/skills/")
    assert payload["stage"]["stage_id"]
    assert payload["session"]["status"] == "skillized"

    detail = client.get(f"/apprenticeship/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["session"]["forge_stage_id"] == payload["stage"]["stage_id"]


def test_lens_surfaces_apprenticeship_actions(monkeypatch, tmp_path: Path) -> None:
    _wire_workspace(monkeypatch, tmp_path)
    title = f"LensTeach-{uuid4()}"

    created = client.post(
        "/apprenticeship/sessions",
        json={"title": title, "objective": "Teach lens review", "tags": ["lens"]},
    )
    assert created.status_code == 200
    session_id = created.json()["session"]["id"]

    step = client.post(
        f"/apprenticeship/sessions/{session_id}/steps",
        json={"kind": "command", "action": "pytest -q", "intent": "verify changes"},
    )
    assert step.status_code == 200

    actions = client.get("/lens/actions")
    assert actions.status_code == 200
    action_kinds = [chip.get("kind") for chip in actions.json()["action_chips"]]
    assert "apprenticeship.generalize" in action_kinds

    generalized = client.post(
        "/lens/actions/execute",
        json={"kind": "apprenticeship.generalize", "args": {"session_id": session_id}},
    )
    assert generalized.status_code == 200
    assert generalized.json()["result"]["summary"]["generalization"]["workflow"][0]["intent"] == "verify changes"

    post_generalize_actions = client.get("/lens/actions")
    assert post_generalize_actions.status_code == 200
    action_kinds = [chip.get("kind") for chip in post_generalize_actions.json()["action_chips"]]
    assert "apprenticeship.skillize" in action_kinds
