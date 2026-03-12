import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from apps.api.main import app as orchestrator_app
import services.hud.app.main as hud_main
import services.hud.app.views.approval_queue as approval_queue_view
import services.hud.app.views.action_deck as action_deck_view
import services.hud.app.views.apprenticeship as apprenticeship_view
import services.hud.app.views.blocked_actions as blocked_actions_view
import services.hud.app.state as hud_state
import services.hud.app.views.current_work as current_work_view
import services.hud.app.views.dashboard as dashboard_view
import services.hud.app.views.execution_feed as execution_feed_view
import services.hud.app.views.execution_journal as execution_journal_view
import services.hud.app.views.inbox as inbox_view
import services.hud.app.views.incidents as incidents_view
import services.hud.app.views.missions as missions_view
import services.hud.app.views.repo_drilldown as repo_drilldown_view
import services.hud.app.views.runs as runs_view
import services.hud.app.views.shift_report as shift_report_view
from services.hud.app.main import app


client = TestClient(app)
orchestrator = TestClient(orchestrator_app)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def _get_mode() -> dict:
    response = orchestrator.get("/control/mode")
    assert response.status_code == 200
    return response.json()


def _set_mode(mode: str, kill_switch: bool | None = None) -> None:
    payload: dict[str, object] = {"mode": mode}
    if kill_switch is not None:
        payload["kill_switch"] = kill_switch
    response = orchestrator.put("/control/mode", json=payload)
    assert response.status_code == 200


def _get_scope() -> dict:
    response = orchestrator.get("/control/scope")
    assert response.status_code == 200
    return response.json()["scope"]


def _set_scope(scope: dict) -> None:
    response = orchestrator.put("/control/scope", json=scope)
    assert response.status_code == 200


def _enable_apps(scope: dict, required_apps: list[str]) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    lowered = [item.lower() for item in apps]
    for app_name in required_apps:
        if app_name.lower() not in lowered:
            apps.append(app_name)
            lowered.append(app_name.lower())
    return {
        "repos": scope.get("repos", []),
        "workspaces": scope.get("workspaces", []),
        "apps": apps,
    }


def test_hud_root_serves_operator_surface() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Francis Lens" in response.text
    assert "Operator overlay for live work." in response.text
    assert "Desktop Shell" in response.text
    assert "Display Target" in response.text
    assert "Restart HUD" in response.text
    assert "Ctrl+Shift+Alt+C" in response.text
    assert "The Orb rides directly over the cursor." in response.text
    assert "Hold the moving Orb itself to panic stop" in response.text
    assert "Shift Report" in response.text
    assert "Shift report will render from away continuity, handback, and mission state." in response.text
    assert "Return briefing cards will render from the backend contract." in response.text
    assert "Mission-centered return evidence will render here." in response.text
    assert "Away-safe task posture will render from the backend contract." in response.text
    assert "Shift report actions will render from the backend contract." in response.text
    assert "Shift report detail will render from away continuity and handback state." in response.text
    assert "Teaching Sessions" in response.text
    assert "Teaching sessions will render from bounded demonstrations, replay, and review state." in response.text
    assert "Start Session" in response.text
    assert "Record Step" in response.text
    assert "Replay lines will render from the backend contract." in response.text
    assert "Generalized workflow detail will render from the backend contract." in response.text
    assert "Current Work Focus" in response.text
    assert "Terminal and Next Move" in response.text
    assert "Approval Queue" in response.text
    assert "Approval Detail" in response.text
    assert "Approval summary will render from the current workspace queue." in response.text
    assert "Approval state will reflect whether this detail is current or historical." in response.text
    assert "Detail cards will render from the backend contract." in response.text
    assert "Execution Journal" in response.text
    assert "Receipt Detail" in response.text
    assert "Receipt summary will render from the run ledger." in response.text
    assert "Receipt state will reflect whether this detail is current or historical." in response.text
    assert "Repo Drilldown" in response.text
    assert "Repo Status" in response.text
    assert "Local Diff" in response.text
    assert "Ruff Check" in response.text
    assert "Operator link will resolve from the current Lens action chain." in response.text
    assert "Link state will resolve from live workspace continuity." in response.text
    assert "Repo drilldown summary will render here." in response.text
    assert "Repo severity will resolve from drilldown results." in response.text
    assert "Drilldown cards will render from the backend contract." in response.text
    assert "Structured drilldown evidence will render here." in response.text
    assert "Evidence for the next move will render here." in response.text
    assert "Terminal summary will explain the first failure or clean completion." in response.text
    assert "Terminal breakdown will render from the backend contract." in response.text
    assert "Execution feed will explain the current operator chain." in response.text
    assert "Execution evidence will render here." in response.text
    assert "Mission Stack" in response.text
    assert "Incident Posture" in response.text
    assert "Blocked Actions" in response.text
    assert "Mission detail will render from active or backlog work." in response.text
    assert "Incident detail will render from live workspace posture." in response.text
    assert "Blocked action detail will render from Lens policy state." in response.text
    assert "Inbox Surface" in response.text
    assert "Inbox summary will render from the backend contract." in response.text
    assert "Inbox detail will render from the current workspace queue." in response.text
    assert "Run Surface" in response.text
    assert "Run summary will render from the backend contract." in response.text
    assert "Run detail will render from the current workspace run surface." in response.text
    assert "Detail cards will render from the backend contract." in response.text
    assert "/static/orb/francis-orb.js" in response.text


def test_hud_serves_orb_bundle() -> None:
    response = client.get("/static/orb/francis-orb.js")

    assert response.status_code == 200
    assert "Francis Orb bundle" in response.text
    assert "createFrancisOrb" in response.text


def test_hud_dashboard_exposes_mode_and_cards() -> None:
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"]["current"] in {"observe", "assist", "pilot", "away"}
    assert "pilot" in body["mode"]["available"]
    assert len(body["cards"]) == 5
    card_ids = {card["id"] for card in body["cards"]}
    assert "current-work" in card_ids
    assert "next-best-action" in card_ids
    assert all("summary" in card for card in body["cards"])
    assert all("signal" in card for card in body["cards"])
    assert all("evidence" in card for card in body["cards"])
    assert all("detail" in card for card in body["cards"])


def test_hud_bootstrap_aggregates_core_surfaces() -> None:
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "hud"
    assert body["dashboard"]["surface"] == "dashboard"
    assert body["actions"]["status"] == "ok"
    assert body["current_work"]["surface"] == "current_work"
    assert body["shift_report"]["surface"] == "shift_report"
    assert body["repo_drilldown"]["surface"] == "repo_drilldown"
    assert body["apprenticeship_surface"]["surface"] == "apprenticeship_surface"
    assert body["approval_queue"]["surface"] == "approval_queue"
    assert body["blocked_actions"]["surface"] == "blocked_actions"
    assert body["action_deck"]["surface"] == "action_deck"
    assert body["execution_journal"]["surface"] == "execution_journal"
    assert body["execution_feed"]["surface"] == "execution_feed"
    assert body["missions"]["surface"] == "missions"
    assert body["inbox"]["surface"] == "inbox"
    assert body["runs"]["surface"] == "runs"
    assert body["fabric"]["surface"] == "fabric"
    assert body["voice"]["surface"] == "voice"
    assert body["orb"]["surface"] == "orb"
    assert set(body["surface_digests"].keys()) >= {
        "snapshot",
        "actions",
        "current_work",
        "shift_report",
        "repo_drilldown",
        "apprenticeship_surface",
        "approval_queue",
        "execution_journal",
        "execution_feed",
        "action_deck",
        "dashboard",
        "missions",
        "incidents",
        "inbox",
        "runs",
        "fabric",
        "voice",
        "orb",
    }


def test_hud_bootstrap_reuses_single_snapshot_for_views(monkeypatch) -> None:
    snapshot = {
        "control": {"mode": "assist", "kill_switch": False},
        "objective": {"label": "Shared snapshot", "definition_of_done": "Reuse lens state once."},
        "missions": {
            "active_count": 1,
            "backlog_count": 0,
            "completed_count": 0,
            "active": [{"id": "mission-1", "title": "Shared snapshot", "status": "active"}],
            "backlog": [],
            "completed": [],
        },
        "approvals": {"pending_count": 0},
        "incidents": {"open_count": 0, "highest_severity": "nominal", "items": [{"summary": "clear"}]},
        "security": {"quarantine_count": 0, "top_categories": {}, "highest_severity": "nominal"},
        "runs": {
            "ledger_count": 1,
            "last_run": {"run_id": "run-1", "phase": "verify", "summary": "ok"},
            "recent": [],
            "ledger_tail": [],
        },
        "apprenticeship": {"review_count": 0},
        "fabric": {
            "citation_ready_count": 1,
            "calibration": {"confidence_counts": {"confirmed": 1, "likely": 0, "uncertain": 0}},
        },
        "inbox": {"count": 0, "alert_count": 0, "items": []},
    }

    def _unexpected_snapshot_build() -> dict[str, object]:
        raise AssertionError("bootstrap should reuse the shared snapshot")

    monkeypatch.setattr(hud_main, "build_lens_snapshot", lambda: snapshot)
    monkeypatch.setattr(dashboard_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(approval_queue_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(action_deck_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(blocked_actions_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(apprenticeship_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(current_work_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(shift_report_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(execution_feed_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(execution_journal_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(missions_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(incidents_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(inbox_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(repo_drilldown_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(runs_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(
        hud_main,
        "get_lens_actions",
        lambda max_actions=8: {
            "status": "ok",
            "action_chips": [{"kind": "control.remote.approvals"}, {"kind": "control.remote.approval.approve"}],
            "blocked_actions": [],
        },
    )
    monkeypatch.setattr(
        hud_main,
        "build_operator_presence",
        lambda **_: {"surface": "voice", "mode": "assist", "headline": "Stable", "lines": [], "actions": []},
    )
    monkeypatch.setattr(
        hud_main,
        "build_orb_state",
        lambda **_: {"surface": "orb", "mode": "assist", "posture": "resting", "visual": {"ring_density": 6}},
    )
    monkeypatch.setattr(
        hud_main,
        "get_fabric_surface",
        lambda refresh=False, defer_if_missing=False: {"surface": "fabric", "summary": {"artifact_count": 1}},
    )

    payload = hud_main._build_bootstrap_payload()

    assert payload["current_work"]["surface"] == "current_work"
    assert payload["shift_report"]["surface"] == "shift_report"
    assert payload["repo_drilldown"]["surface"] == "repo_drilldown"
    assert payload["apprenticeship_surface"]["surface"] == "apprenticeship_surface"
    assert payload["approval_queue"]["surface"] == "approval_queue"
    assert payload["blocked_actions"]["surface"] == "blocked_actions"
    assert payload["action_deck"]["surface"] == "action_deck"
    assert payload["execution_journal"]["surface"] == "execution_journal"
    assert payload["execution_feed"]["surface"] == "execution_feed"
    assert payload["dashboard"]["objective"]["label"] == "Shared snapshot"
    assert payload["missions"]["active_count"] == 1
    assert payload["incidents"]["items"][0]["summary"] == "clear"
    assert payload["inbox"]["messages"][0]["title"] == "Inbox clear"
    assert payload["runs"]["active_run"]["run_id"] == "run-1"
    assert "surface_digests" in payload
    assert payload["surface_digests"]["current_work"]
    assert payload["surface_digests"]["shift_report"]
    assert payload["surface_digests"]["apprenticeship_surface"]


def test_hud_bootstrap_reads_live_workspace_state(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)
    repo_root = workspace_root.parent
    _git(repo_root, "init")
    (repo_root / "usage-signal.txt").write_text("draft\n", encoding="utf-8")

    _write_json(
        workspace_root / "control" / "state.json",
        {
            "mode": "away",
            "kill_switch": False,
            "scopes": {
                "repos": [str(workspace_root.parent)],
                "workspaces": [str(workspace_root)],
                "apps": ["control", "approvals", "receipts", "lens", "missions"],
            },
        },
    )
    _write_json(
        workspace_root / "missions" / "missions.json",
        {
            "missions": [
                {
                    "id": "mission-live-lens",
                    "title": "Live Lens",
                    "objective": "Show real workspace state in the HUD",
                    "status": "active",
                    "priority": "high",
                    "updated_at": "2026-03-08T12:00:00+00:00",
                },
                {
                    "id": "mission-backlog",
                    "title": "Voice backend",
                    "status": "planned",
                    "updated_at": "2026-03-08T11:00:00+00:00",
                },
            ]
        },
    )
    _write_jsonl(
        workspace_root / "approvals" / "requests.jsonl",
        [
            {
                "id": "approval-1",
                "ts": "2026-03-08T12:01:00+00:00",
                "action": "forge.promote",
                "reason": "Promote a staged capability",
                "requested_by": "architect.ap3pp",
            }
        ],
    )
    _write_jsonl(
        workspace_root / "incidents" / "incidents.jsonl",
        [
            {
                "id": "incident-1",
                "ts": "2026-03-08T12:02:00+00:00",
                "severity": "high",
                "state": "open",
                "summary": "Observer detected sustained error pressure.",
                "source": "observer",
            }
        ],
    )
    _write_jsonl(
        workspace_root / "security" / "quarantine.jsonl",
        [
            {
                "id": "quarantine-1",
                "ts": "2026-03-08T12:02:30+00:00",
                "severity": "high",
                "surface": "approvals",
                "action": "approvals.request",
                "categories": ["policy_bypass"],
            }
        ],
    )
    _write_jsonl(
        workspace_root / "inbox" / "messages.jsonl",
        [
            {
                "id": "msg-1",
                "ts": "2026-03-08T12:03:00+00:00",
                "title": "Approval waiting",
                "summary": "A forge promotion is awaiting approval.",
                "severity": "alert",
            }
        ],
    )
    _write_jsonl(
        workspace_root / "telemetry" / "events.jsonl",
        [
            {
                "id": "telemetry-live-1",
                "ts": "2026-03-08T12:03:30+00:00",
                "ingested_at": "2026-03-08T12:03:31+00:00",
                "run_id": "run-live",
                "kind": "telemetry.event",
                "stream": "terminal",
                "source": "terminal",
                "severity": "error",
                "text": "terminal: pytest -q tests/integration/test_hud_foundation.py (exit=1)",
                "fields": {
                    "command": "pytest -q tests/integration/test_hud_foundation.py",
                    "cwd": str(repo_root),
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "1 failed",
                },
            }
        ],
    )
    _write_json(
        workspace_root / "runs" / "last_run.json",
        {
            "run_id": "run-live",
            "phase": "verify",
            "summary": "Lens is now reading live workspace state.",
        },
    )
    _write_jsonl(
        workspace_root / "runs" / "run_ledger.jsonl",
        [
            {
                "run_id": "run-live",
                "ts": "2026-03-08T12:04:00+00:00",
                "kind": "hud.bootstrap",
            }
        ],
    )
    _write_json(
        workspace_root / "apprenticeship" / "sessions.json",
        {
            "sessions": [
                {
                    "id": "teach-1",
                    "title": "Repo triage",
                    "objective": "Teach repo review",
                    "status": "review",
                    "step_count": 2,
                    "tags": ["git"],
                    "created_at": "2026-03-08T12:05:00+00:00",
                    "updated_at": "2026-03-08T12:06:00+00:00",
                    "last_event_at": "2026-03-08T12:06:00+00:00",
                }
            ]
        },
    )

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["control"]["mode"] == "away"
    assert body["snapshot"]["objective"]["label"] == "Live Lens"
    assert body["snapshot"]["current_work"]["repo"]["available"] is True
    assert body["snapshot"]["current_work"]["repo"]["dirty"] is True
    assert body["snapshot"]["current_work"]["attention"]["kind"] == "teaching_review"
    assert body["snapshot"]["next_best_action"]["kind"] == "apprenticeship.skillize"
    assert body["current_work"]["surface"] == "current_work"
    assert body["shift_report"]["surface"] == "shift_report"
    assert body["shift_report"]["state"] == "away_live"
    assert body["shift_report"]["summary"].startswith("Away Mode is active on Live Lens.")
    assert any(item["kind"] == "mission" for item in body["shift_report"]["evidence"])
    assert body["shift_report"]["recommendations"]
    assert body["shift_report"]["controls"]["current_work"]["target_surface"] == "current_work"
    assert "away_safe_tasks" in body["shift_report"]
    assert body["apprenticeship_surface"]["surface"] == "apprenticeship_surface"
    assert body["apprenticeship_surface"]["focus_session_id"] == "teach-1"
    assert body["apprenticeship_surface"]["sessions"][0]["id"] == "teach-1"
    assert body["snapshot"]["autonomy"]["guardrail"]["cooldown_active"] is False
    assert body["current_work"]["attention"]["kind"] == "teaching_review"
    assert body["current_work"]["apprenticeship"]["focus_session"]["id"] == "teach-1"
    assert body["current_work"]["repo"]["top_paths"][0] == "usage-signal.txt"
    assert body["current_work"]["terminal"]["command"] == "pytest -q tests/integration/test_hud_foundation.py"
    assert body["current_work"]["terminal_summary"].startswith("Terminal failure anchor:")
    assert any(item["kind"] == "failure" for item in body["current_work"]["terminal_breakdown"])
    assert body["current_work"]["next_action"]["kind"] == "apprenticeship.skillize"
    assert body["current_work"]["operator_link"]["action_kind"] == "apprenticeship.skillize"
    assert body["current_work"]["operator_link"]["state"] in {"approval_pending", "receipt_grounded", "following"}
    assert body["current_work"]["focus_action"]["state"] in {"approval_ready", "ready", "approval_request", "blocked"}
    assert body["current_work"]["repo"]["severity"] in {"medium", "high"}
    assert body["current_work"]["next_action_signal"]["severity"] == "high"
    assert any(item["kind"] == "terminal" for item in body["current_work"]["next_action_evidence"])
    assert any(item["kind"] == "teaching" for item in body["current_work"]["next_action_evidence"])
    assert any(item["kind"] in {"blocker", "approval"} for item in body["current_work"]["next_action_evidence"])
    assert any("approval" in item.lower() or "terminal" in item.lower() for item in body["current_work"]["blockers"])
    assert body["repo_drilldown"]["surface"] == "repo_drilldown"
    assert body["repo_drilldown"]["state"] in {"idle", "ready"}
    assert body["approval_queue"]["surface"] == "approval_queue"
    assert body["approval_queue"]["pending_count"] == 1
    assert body["approval_queue"]["items"][0]["id"] == "approval-1"
    assert body["blocked_actions"]["surface"] == "blocked_actions"
    assert body["execution_journal"]["surface"] == "execution_journal"
    assert body["execution_journal"]["active_run"]["run_id"] == "run-live"
    assert body["execution_journal"]["items"][0]["kind"] == "hud.bootstrap"
    assert body["execution_feed"]["surface"] == "execution_feed"
    assert body["execution_feed"]["focus_action_kind"] == "apprenticeship.skillize"
    assert body["execution_feed"]["severity"] == "high"
    assert body["dashboard"]["mode"]["current"] == "away"
    assert any(card["id"] == "current-work" for card in body["dashboard"]["cards"])
    assert any(card["id"] == "next-best-action" for card in body["dashboard"]["cards"])
    assert body["missions"]["active_count"] == 1
    assert body["missions"]["backlog_count"] == 1
    assert body["missions"]["summary"].startswith("Live Lens is in active")
    assert body["missions"]["active"][0]["detail_cards"]
    assert body["incidents"]["open_count"] == 1
    assert body["incidents"]["security"]["quarantine_count"] == 1
    assert body["incidents"]["summary"].startswith("Observer detected sustained error pressure.")
    assert body["incidents"]["items"][0]["detail_cards"]
    assert body["inbox"]["alert_count"] == 1
    assert body["runs"]["active_run"]["run_id"] == "run-live"
    assert body["snapshot"]["apprenticeship"]["review_count"] == 1
    assert body["snapshot"]["security"]["quarantine_count"] == 1
    assert body["snapshot"]["security"]["top_categories"]["policy_bypass"] == 1
    assert body["fabric"]["surface"] == "fabric"
    assert body["fabric"]["summary"]["pending"] is True
    assert body["voice"]["grounding"]["trust"] == "Likely"
    assert body["voice"]["mode"] == "away"
    assert "Incident pressure is high." in body["voice"]["headline"]
    assert body["voice"]["notification"]["kind"] == "incident.pressure"
    assert body["orb"]["mode"] == "away"
    assert body["orb"]["interjection_level"] == 3
    assert body["orb"]["state"]["security_quarantines"] == 1
    assert body["orb"]["visual"]["ring_density"] >= 6


def test_hud_current_work_route_returns_structured_focus() -> None:
    response = client.get("/api/current-work")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "current_work"
    assert "summary" in payload
    assert "repo" in payload
    assert payload["repo"]["severity"] in {"low", "medium", "high", "unknown"}
    assert "attention" in payload
    assert "terminal" in payload
    assert "terminal_summary" in payload
    assert "terminal_breakdown" in payload
    assert "next_action" in payload
    assert "operator_link" in payload
    assert "focus_action" in payload
    assert "next_action_signal" in payload
    assert "next_action_resume" in payload
    assert "next_action_evidence" in payload
    assert "fabric_evidence" in payload
    assert "apprenticeship" in payload


def test_hud_shift_report_route_returns_structured_surface() -> None:
    response = client.get("/api/shift-report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "shift_report"
    assert payload["state"] in {"idle", "away_live", "return_briefing"}
    assert "summary" in payload
    assert "severity" in payload
    assert "cards" in payload
    assert "evidence" in payload
    assert "recommendations" in payload
    assert "controls" in payload
    assert "away_safe_tasks" in payload
    assert "detail" in payload


def test_hud_repo_drilldown_route_returns_structured_surface() -> None:
    response = client.get("/api/repo-drilldown")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "repo_drilldown"
    assert payload["state"] in {"idle", "ready"}
    assert "focus_kind" in payload
    assert "summary" in payload
    assert "severity" in payload
    assert "cards" in payload
    assert "controls" in payload
    assert set(payload["controls"].keys()) == {"status", "diff", "lint", "tests"}
    assert "audit" in payload
    assert "detail" in payload


def test_hud_apprenticeship_route_returns_structured_surface() -> None:
    response = client.get("/api/apprenticeship")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "apprenticeship_surface"
    assert "summary" in payload
    assert "severity" in payload
    assert "focus_session_id" in payload
    assert "cards" in payload
    assert "sessions" in payload
    assert "controls" in payload
    assert "detail" in payload


def test_hud_approval_queue_route_returns_pending_requests() -> None:
    response = client.get("/api/approval-queue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "approval_queue"
    assert "focus_approval_id" in payload
    assert "pending_count" in payload
    assert "items" in payload


def test_hud_action_deck_route_returns_structured_surface() -> None:
    response = client.get("/api/action-deck")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "action_deck"
    assert "summary" in payload
    assert "blocked_summary" in payload
    assert "focus_action_kind" in payload
    assert "items" in payload


def test_hud_blocked_actions_route_returns_structured_surface() -> None:
    response = client.get("/api/blocked-actions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "blocked_actions"
    assert "focus_blocked_kind" in payload
    assert "summary" in payload
    assert "items" in payload
    assert "detail" in payload


def test_hud_approval_queue_view_normalizes_requested_action_kind(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "approvals": {
                "pending_count": 1,
                "pending": [
                    {
                        "id": "approval-tests",
                        "ts": "2026-03-11T10:00:00+00:00",
                        "action": "tool.run",
                        "reason": "Fast checks need approval",
                        "requested_by": "francis",
                        "metadata": {
                            "skill": "repo.tests",
                            "args": {"lane": "fast", "target": "tests/integration/test_hud_foundation.py"},
                        },
                    }
                ],
            }
        }

    def _actions(max_actions: int = 8) -> dict[str, object]:
        assert max_actions == 8
        return {
            "action_chips": [
                {"kind": "control.remote.approvals"},
                {"kind": "control.remote.approval.approve"},
                {"kind": "control.remote.approval.reject"},
                {"kind": "repo.tests"},
            ]
        }

    monkeypatch.setattr(approval_queue_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(approval_queue_view, "get_lens_actions", _actions)

    payload = approval_queue_view.get_approval_queue_view()

    assert payload["focus_approval_id"] == "approval-tests"
    assert payload["items"][0]["requested_action_kind"] == "repo.tests"
    assert payload["items"][0]["detail_summary"].startswith("repo.tests is waiting on an operator decision.")
    assert payload["items"][0]["detail_cards"]
    assert payload["items"][0]["audit"]["approval_id"] == "approval-tests"
    assert payload["items"][0]["audit"]["requested_action_kind"] == "repo.tests"
    assert payload["items"][0]["can_execute_after_approval"] is True
    assert payload["items"][0]["execute_after_approval_kind"] == "repo.tests"
    assert payload["items"][0]["detail_state"] == "historical"


def test_hud_current_work_view_surfaces_approval_ready_resume(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "approvals": {
                "pending_count": 1,
                "pending": [
                    {
                        "id": "approval-tests",
                        "action": "tool.run",
                        "reason": "Fast checks need approval",
                        "requested_by": "francis",
                        "metadata": {
                            "skill": "repo.tests",
                            "args": {"lane": "fast", "target": "tests/integration/test_hud_foundation.py"},
                        },
                    }
                ],
            },
            "current_work": {
                "summary": "Mode assist. Repository pressure is visible.",
                "repo": {
                    "available": True,
                    "branch": "main",
                    "dirty": True,
                    "changed_count": 2,
                    "staged_count": 0,
                    "unstaged_count": 2,
                    "untracked_count": 0,
                    "top_paths": ["services/hud/app/static/index.html"],
                    "summary": "Branch main | 2 change(s): 0 staged, 2 unstaged, 0 untracked",
                },
                "telemetry": {
                    "last_terminal": {
                        "command": "pytest -q tests/integration/test_hud_foundation.py",
                        "exit_code": 1,
                        "stderr": "1 failed",
                        "stdout": "",
                        "severity": "error",
                        "text": "terminal failure",
                    }
                },
                "attention": {
                    "kind": "terminal_failure",
                    "label": "Terminal Failure",
                    "reason": "The latest terminal command failed.",
                },
                "blockers": ["1 approval(s) are pending."],
                "mission": None,
                "last_run": {},
            },
            "fabric": {"calibration": {"confidence_counts": {}, "stale_current_state_count": 0}},
            "next_best_action": {
                "kind": "repo.tests",
                "label": "Run Fast Checks",
                "reason": "The latest test command failed.",
            },
        }

    monkeypatch.setattr(current_work_view, "build_lens_snapshot", _snapshot)

    payload = current_work_view.get_current_work_view()

    assert payload["next_action_resume"]["state"] == "approval_ready"
    assert payload["next_action_resume"]["approval_id"] == "approval-tests"
    assert payload["next_action_resume"]["action_kind"] == "repo.tests"
    assert payload["operator_link"]["state"] == "approval_pending"
    assert payload["operator_link"]["approval_id"] == "approval-tests"
    assert payload["operator_link"]["action_kind"] == "repo.tests"
    assert payload["focus_action"]["state"] == "approval_ready"
    assert payload["focus_action"]["kind"] == "repo.tests"
    assert payload["focus_action"]["execute_kind"] == "repo.tests"
    assert payload["focus_action"]["args"]["approval_id"] == "approval-tests"
    assert payload["next_action_signal"]["summary"] == "Approval-backed continuation is ready to resume from the queue."
    assert any(
        str(row.get("kind", "")) == "resume" and "approval-tests" in str(row.get("detail", ""))
        for row in payload["next_action_evidence"]
    )


def test_hud_current_work_view_adds_cited_fabric_evidence(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    _write_json(
        workspace_root / "brain" / "fabric" / "snapshot.json",
        {
            "generated_at": "2026-03-11T11:10:00+00:00",
            "summary": {
                "artifact_count": 1,
                "citation_ready_count": 1,
                "source_counts": {"runs.last": 1},
                "lane_counts": {"hot": 1, "warm": 0, "cold": 0},
            },
            "artifacts": [
                {
                    "id": "runs.last:run-live",
                    "source": "runs.last",
                    "kind": "run",
                    "title": "Latest verify run",
                    "body": "pytest -q tests/integration/test_hud_foundation.py failed with 1 failed while verifying HUD contract",
                    "ts": "2026-03-11T11:09:00+00:00",
                    "status": "failed",
                    "severity": "high",
                    "verification_status": "failed",
                    "retention_lane": "hot",
                    "provenance": {"rel_path": "runs/run_ledger.jsonl", "record_index": 0},
                    "relationships": {"run_id": "run-live", "mission_id": "mission-live"},
                }
            ],
        },
    )

    def _snapshot() -> dict[str, object]:
        return {
            "current_work": {
                "summary": "Tests are failing on the HUD contract.",
                "repo": {
                    "available": True,
                    "branch": "main",
                    "dirty": True,
                    "changed_count": 2,
                    "top_paths": ["tests/integration/test_hud_foundation.py"],
                },
                "telemetry": {
                    "last_terminal": {
                        "command": "pytest -q tests/integration/test_hud_foundation.py",
                        "exit_code": 1,
                        "stderr": "1 failed",
                        "severity": "error",
                    }
                },
                "attention": {"kind": "terminal_failure", "label": "Terminal Failure"},
                "blockers": [],
                "mission": {"id": "mission-live", "title": "HUD contract", "objective": "Verify HUD surface"},
                "last_run": {"run_id": "run-live", "phase": "verify", "summary": "HUD verification failed"},
            },
            "fabric": {"calibration": {"confidence_counts": {"confirmed": 1, "likely": 0, "uncertain": 0}}},
            "next_best_action": {
                "kind": "repo.tests",
                "label": "Run Fast Checks",
                "reason": "The latest test command failed.",
            },
            "approvals": {"pending_count": 0, "pending": []},
        }

    monkeypatch.setattr(current_work_view, "get_workspace_root", lambda: workspace_root)
    monkeypatch.setattr(current_work_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(
        current_work_view,
        "get_lens_actions",
        lambda max_actions=8: {"action_chips": [{"kind": "repo.tests", "label": "Run Fast Checks", "enabled": True}]},
    )

    payload = current_work_view.get_current_work_view()

    assert payload["fabric_evidence"]
    assert payload["fabric_evidence"][0]["citation"]["rel_path"] == "runs/run_ledger.jsonl"
    assert any(str(row.get("kind", "")) == "citation" for row in payload["next_action_evidence"])
    assert payload["next_action_signal"]["summary"] == "Cited local evidence is grounding the next operator move."


def test_hud_current_work_view_prioritizes_teaching_review(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "approvals": {"pending_count": 0, "pending": []},
            "current_work": {
                "summary": "Teach repo verification is ready to become a reusable skill.",
                "repo": {
                    "available": True,
                    "branch": "main",
                    "dirty": True,
                    "changed_count": 2,
                    "staged_count": 0,
                    "unstaged_count": 2,
                    "untracked_count": 0,
                    "top_paths": ["services/hud/app/static/index.html"],
                    "summary": "Branch main | 2 change(s): 0 staged, 2 unstaged, 0 untracked",
                },
                "telemetry": {
                    "last_terminal": {
                        "command": "pytest -q tests/integration/test_hud_foundation.py",
                        "exit_code": 1,
                        "stderr": "1 failed",
                        "stdout": "",
                        "severity": "error",
                        "text": "terminal failure",
                    }
                },
                "attention": {
                    "kind": "teaching_review",
                    "label": "Teaching Review",
                    "reason": "Teach repo verification is generalized and ready to skillize after 2 demonstrated step(s).",
                },
                "blockers": ["1 approval(s) are pending."],
                "mission": None,
                "last_run": {},
                "apprenticeship": {
                    "session_count": 1,
                    "recording_count": 0,
                    "review_count": 1,
                    "skillized_count": 0,
                    "focus_session": {
                        "id": "teach-review",
                        "title": "Teach repo verification",
                        "objective": "Turn verify flow into a reusable skill",
                        "status": "review",
                        "step_count": 2,
                        "summary": "Teach repo verification is generalized and ready to skillize after 2 demonstrated step(s).",
                        "recommended_action": "apprenticeship.skillize",
                    },
                },
            },
            "fabric": {"calibration": {"confidence_counts": {}, "stale_current_state_count": 0}},
            "next_best_action": {
                "kind": "apprenticeship.skillize",
                "label": "Skillize Teaching Session",
                "reason": "Teach repo verification has review-ready structure and can be staged into Forge now.",
                "args": {"session_id": "teach-review"},
            },
        }

    monkeypatch.setattr(current_work_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(
        current_work_view,
        "get_lens_actions",
        lambda max_actions=8: {
            "action_chips": [
                {
                    "kind": "apprenticeship.skillize",
                    "label": "Skillize Teaching Session",
                    "enabled": True,
                    "risk_tier": "medium",
                    "reason": "Teach repo verification is ready to stage into Forge.",
                    "execute_via": {"payload": {"args": {"session_id": "teach-review"}}},
                }
            ]
        },
    )

    payload = current_work_view.get_current_work_view()

    assert payload["attention"]["kind"] == "teaching_review"
    assert payload["apprenticeship"]["focus_session"]["id"] == "teach-review"
    assert payload["next_action"]["kind"] == "apprenticeship.skillize"
    assert payload["focus_action"]["execute_kind"] == "apprenticeship.skillize"
    assert payload["focus_action"]["args"]["session_id"] == "teach-review"
    assert payload["next_action_signal"]["summary"] == "A reviewed teaching session is ready to become a staged skill."
    assert any(str(row.get("kind", "")) == "teaching" for row in payload["next_action_evidence"])


def test_hud_blocked_actions_view_adds_detail_contract(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {"next_best_action": {"kind": "repo.tests"}}

    def _actions(max_actions: int = 8) -> dict[str, object]:
        assert max_actions == 8
        return {
            "blocked_actions": [
                {
                    "kind": "repo.tests",
                    "policy_reason": "Fast checks are waiting on approval.",
                    "risk_tier": "high",
                    "trust_badge": "Blocked",
                }
            ]
        }

    monkeypatch.setattr(blocked_actions_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(blocked_actions_view, "get_lens_actions", _actions)

    payload = blocked_actions_view.get_blocked_actions_view()

    assert payload["focus_blocked_kind"] == "repo.tests"
    assert payload["items"][0]["detail_summary"].startswith("repo.tests is blocked.")
    assert payload["items"][0]["detail_cards"]
    assert payload["items"][0]["detail_state"] == "current"
    assert payload["items"][0]["audit"]["kind"] == "repo.tests"
    assert payload["items"][0]["audit"]["detail_state"] == "current"


def test_hud_action_deck_view_exposes_backend_controls(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "next_best_action": {"kind": "repo.tests"},
            "current_work": {
                "focus_action": {
                    "kind": "repo.tests",
                    "execute_kind": "repo.tests.request_approval",
                }
            },
        }

    def _actions(max_actions: int = 8) -> dict[str, object]:
        assert max_actions == 8
        return {
            "action_chips": [
                {"kind": "repo.status", "label": "Repo Status", "enabled": True, "risk_tier": "low"},
                {
                    "kind": "repo.tests.request_approval",
                    "label": "Request Fast Checks Approval",
                    "enabled": True,
                    "risk_tier": "medium",
                    "execute_via": {"payload": {"args": {"lane": "fast"}}},
                },
            ]
        }

    monkeypatch.setattr(action_deck_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(action_deck_view, "get_lens_actions", _actions)

    payload = action_deck_view.get_action_deck_view(
        blocked_actions={"count": 0, "summary": "No blocked actions surfaced"},
    )

    assert payload["focus_action_kind"] == "repo.tests"
    assert payload["items"][1]["kind"] == "repo.tests"
    assert payload["items"][1]["execute_kind"] == "repo.tests.request_approval"
    assert payload["items"][1]["state"] == "current"
    assert payload["items"][1]["args"]["lane"] == "fast"


def test_hud_repo_drilldown_view_exposes_compact_audit(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(repo_drilldown_view, "get_workspace_root", lambda: workspace_root)

    def _snapshot() -> dict[str, object]:
        return {
            "current_work": {
                "repo": {
                    "branch": "main",
                    "dirty": True,
                    "changed_count": 3,
                    "top_paths": ["services/hud/app/static/index.html"],
                    "summary": "Branch main | 3 change(s) present",
                    "severity": "medium",
                }
            }
        }

    monkeypatch.setattr(repo_drilldown_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(
        repo_drilldown_view,
        "get_lens_actions",
        lambda max_actions=8: {
            "action_chips": [
                {"kind": "repo.status", "label": "Repo Status", "enabled": True, "risk_tier": "low"},
                {"kind": "repo.diff", "label": "Local Diff", "enabled": True, "risk_tier": "low"},
                {"kind": "repo.lint", "label": "Ruff Check", "enabled": True, "risk_tier": "medium"},
                {
                    "kind": "repo.tests",
                    "label": "Fast Checks",
                    "enabled": True,
                    "risk_tier": "medium",
                    "execute_via": {"payload": {"args": {"lane": "fast", "approval_id": "approval-tests"}}},
                },
            ]
        },
    )
    _write_json(
        workspace_root / "lens" / "repo_drilldown.json",
        {
            "kind": "repo.tests",
            "run_id": "run-tests",
            "trace_id": "trace-tests",
            "tool": {"skill": "repo.tests", "approval_id": "approval-tests"},
            "execution_args": {"lane": "fast", "approval_id": "approval-tests"},
            "presentation": {
                "summary": "Lane fast executed. 12 passed | 0 failed",
                "severity": "low",
                "cards": [{"label": "Lane", "value": "fast", "tone": "low"}],
                "evidence": [{"kind": "tests", "severity": "low", "detail": "12 passed | 0 failed"}],
            },
        },
    )

    payload = repo_drilldown_view.get_repo_drilldown_view()

    assert payload["focus_kind"] == "repo.tests"
    assert payload["audit"]["kind"] == "repo.tests"
    assert payload["audit"]["run_id"] == "run-tests"
    assert payload["audit"]["card_count"] == 1
    assert payload["audit"]["evidence_count"] == 1
    assert payload["controls"]["status"]["execute_kind"] == "repo.status"
    assert payload["controls"]["tests"]["execute_kind"] == "repo.tests"
    assert payload["controls"]["tests"]["args"]["approval_id"] == "approval-tests"


def test_hud_shift_report_view_builds_return_briefing(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "control": {"mode": "assist"},
            "missions": {
                "active": [
                    {
                        "id": "mission-night-shift",
                        "title": "Night Shift Build",
                        "objective": "Carry work through the return briefing",
                        "status": "active",
                        "priority": "high",
                    }
                ]
            },
            "approvals": {"pending_count": 1, "pending": [{"id": "approval-tests"}]},
            "incidents": {
                "open_count": 1,
                "highest_severity": "high",
                "items": [{"id": "incident-1", "summary": "Observer error pressure is still open."}],
            },
            "runs": {
                "last_run": {
                    "run_id": "run-night-1",
                    "phase": "verify",
                    "summary": "Away validation completed.",
                }
            },
            "takeover": {
                "handback_available": True,
                "handback": {
                    "summary": "Validation completed and one approval was left queued.",
                    "reason": "Night shift advanced the safe validation lane.",
                    "pending_approvals": 1,
                    "run_id": "run-night-1",
                    "trace_id": "trace-night-1",
                    "handed_back_at": "2026-03-11T09:00:00+00:00",
                    "fabric_posture": {"trust": "Likely"},
                },
            },
            "next_best_action": {
                "kind": "repo.tests",
                "label": "Run Fast Checks",
                "reason": "The validation lane is ready for review.",
            },
            "current_work": {
                "summary": "Validation lane is ready to resume.",
                "repo": {
                    "available": True,
                    "branch": "main",
                    "dirty": True,
                    "changed_count": 2,
                    "staged_count": 0,
                    "unstaged_count": 2,
                    "untracked_count": 0,
                    "top_paths": ["tests/integration/test_hud_foundation.py"],
                    "summary": "Branch main | 2 change(s): 0 staged, 2 unstaged, 0 untracked",
                },
                "telemetry": {"last_terminal": {}},
                "attention": {
                    "kind": "approval_waiting",
                    "label": "Approval Waiting",
                    "reason": "The next move is waiting on operator approval.",
                },
                "blockers": ["1 approval(s) are pending."],
                "mission": {
                    "id": "mission-night-shift",
                    "title": "Night Shift Build",
                },
                "last_run": {
                    "run_id": "run-night-1",
                    "phase": "verify",
                    "summary": "Away validation completed.",
                },
            },
            "autonomy": {
                "budget": {
                    "date": "2026-03-11",
                    "counts": {"worker.cycle": 4},
                    "updated_at": "2026-03-11T09:00:00+00:00",
                    "total_executions": 4,
                    "top_action": {"kind": "worker.cycle", "count": 4},
                },
                "reactor": {
                    "halted_reason": "dispatch_runtime_budget_exceeded",
                    "budget_halted": True,
                    "collect_queued_count": 2,
                    "dispatch_retried_count": 1,
                },
                "guardrail": {
                    "cooldown_active": True,
                    "cooldown_remaining_ticks": 2,
                    "escalations_count": 3,
                    "last_reason": "retry_pressure_cooldown",
                },
            },
            "fabric": {
                "calibration": {
                    "confidence_counts": {"confirmed": 1, "likely": 1, "uncertain": 0},
                    "stale_current_state_count": 0,
                }
            },
        }

    monkeypatch.setattr(shift_report_view, "build_lens_snapshot", _snapshot)
    monkeypatch.setattr(
        shift_report_view,
        "get_lens_actions",
        lambda max_actions=8: {
            "status": "ok",
            "action_chips": [
                {
                    "kind": "repo.tests",
                    "label": "Run Fast Checks",
                    "enabled": True,
                    "risk_tier": "medium",
                    "execute_via": {"payload": {"args": {"lane": "fast", "approval_id": "approval-tests"}}},
                },
                {
                    "kind": "observer.scan",
                    "label": "Run Observer Scan",
                    "enabled": True,
                    "risk_tier": "low",
                    "reason": "Observer scan is due.",
                },
                {
                    "kind": "worker.cycle",
                    "label": "Process Worker Queue",
                    "enabled": False,
                    "risk_tier": "medium",
                    "policy_reason": "daily cap reached for worker.cycle",
                },
                {
                    "kind": "autonomy.reactor.guardrail.reset",
                    "label": "Reset Guardrail",
                    "enabled": True,
                    "risk_tier": "high",
                }
            ],
            "blocked_actions": [],
        },
    )

    payload = shift_report_view.get_shift_report_view()

    assert payload["state"] == "return_briefing"
    assert payload["severity"] == "high"
    assert payload["summary"].startswith("Return briefing for Night Shift Build.")
    assert payload["cards"][0]["label"] == "State"
    assert any(str(item.get("kind", "")) == "handback" for item in payload["evidence"])
    assert payload["detail"]["handback"]["summary"] == "Validation completed and one approval was left queued."
    assert payload["detail"]["handback"]["trust"] == "Likely"
    assert payload["recommendations"][0] == "Review the pending approvals before resuming execution."
    assert any(str(item.get("kind", "")) == "guardrail" for item in payload["evidence"])
    assert payload["detail"]["autonomy"]["guardrail"]["cooldown_active"] is True
    assert payload["controls"]["resume"]["label"] == "Execute Next Move"
    assert payload["controls"]["resume"]["execute_kind"] == "repo.tests"
    assert payload["controls"]["approvals"]["target_surface"] == "approval_queue"
    assert payload["controls"]["incidents"]["target_surface"] == "incidents"
    assert payload["controls"]["guardrail_reset"]["enabled"] is True
    assert payload["controls"]["guardrail_reset"]["execute_kind"] == "autonomy.reactor.guardrail.reset"
    assert payload["away_safe_tasks"]["summary"] == "1 away-safe task(s) ready, 1 gated."
    assert payload["away_safe_tasks"]["allowed"][0]["kind"] == "observer.scan"
    assert payload["away_safe_tasks"]["gated"][0]["kind"] == "worker.cycle"


def test_hud_apprenticeship_view_exposes_teaching_workflow(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    _write_json(
        workspace_root / "apprenticeship" / "sessions.json",
        {
            "sessions": [
                {
                    "id": "teach-current",
                    "title": "Teach Repo Triage",
                    "objective": "Capture repo review flow",
                    "status": "recording",
                    "step_count": 2,
                    "created_at": "2026-03-11T10:00:00+00:00",
                    "updated_at": "2026-03-11T10:05:00+00:00",
                    "last_event_at": "2026-03-11T10:05:00+00:00",
                    "generalization": {
                        "summary": "Reusable repo triage workflow.",
                        "workflow": [
                            {
                                "index": 1,
                                "intent": "inspect repo state",
                                "kind": "command",
                                "action_template": "git status --short",
                            }
                        ],
                        "parameter_candidates": [{"name": "artifact_path_1", "example": "README.md"}],
                    },
                }
            ]
        },
    )
    _write_jsonl(
        workspace_root / "apprenticeship" / "sessions" / "teach-current.jsonl",
        [
            {
                "id": "step-1",
                "index": 1,
                "kind": "command",
                "action": "git status --short",
                "intent": "inspect repo state",
            },
            {
                "id": "step-2",
                "index": 2,
                "kind": "command",
                "action": "git diff -- README.md",
                "intent": "inspect changed file",
                "artifact_path": "README.md",
            },
        ],
    )

    monkeypatch.setattr(apprenticeship_view, "get_workspace_root", lambda: workspace_root)
    monkeypatch.setattr(
        apprenticeship_view,
        "build_lens_snapshot",
        lambda: {"apprenticeship": {"session_count": 1, "recording_count": 1, "review_count": 0, "skillized_count": 0}},
    )
    monkeypatch.setattr(apprenticeship_view, "load_snapshot", lambda fs: {"artifacts": []})
    monkeypatch.setattr(
        apprenticeship_view,
        "query_fabric",
        lambda fs, **kwargs: {
            "results": [
                {
                    "artifact_id": "artifact-1",
                    "title": "run_ledger.jsonl",
                    "summary": "Captured repo triage receipts.",
                    "source": "runs",
                    "trust_badge": "Likely",
                    "citation": {"rel_path": "runs/run_ledger.jsonl", "record_index": 0},
                }
            ]
        },
    )

    payload = apprenticeship_view.get_apprenticeship_view()

    assert payload["surface"] == "apprenticeship_surface"
    assert payload["focus_session_id"] == "teach-current"
    assert payload["sessions"][0]["detail_state"] == "current"
    assert payload["sessions"][0]["detail_cards"]
    assert payload["detail"]["replay"]["step_count"] == 2
    assert payload["detail"]["generalization"]["summary"] == "Reusable repo triage workflow."
    assert payload["detail"]["fabric_evidence"][0]["citation"]["rel_path"] == "runs/run_ledger.jsonl"
    assert payload["detail"]["trust_posture"]["trust"] == "Likely"
    assert payload["detail"]["audit"]["fabric_evidence_count"] == 1
    assert payload["sessions"][0]["detail_summary"].endswith("Grounded by 1 cited artifact(s).")
    assert payload["controls"]["create_session"]["enabled"] is True
    assert payload["controls"]["record_step"]["enabled"] is True
    assert payload["controls"]["generalize"]["execute_kind"] == "apprenticeship.generalize"
    assert payload["controls"]["skillize"]["execute_kind"] == "apprenticeship.skillize"


def test_hud_apprenticeship_create_and_record_routes(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(apprenticeship_view, "get_workspace_root", lambda: workspace_root)

    created = client.post(
        "/api/apprenticeship/sessions",
        json={"title": "Teach Lens Review", "objective": "Capture review flow", "tags": ["lens", "review"]},
    )
    assert created.status_code == 200
    created_body = created.json()
    session_id = created_body["session"]["id"]
    assert created_body["apprenticeship_surface"]["surface"] == "apprenticeship_surface"

    recorded = client.post(
        f"/api/apprenticeship/sessions/{session_id}/steps",
        json={
            "kind": "command",
            "action": "pytest -q tests/integration/test_hud_foundation.py",
            "intent": "verify HUD contract",
            "artifact_path": "tests/integration/test_hud_foundation.py",
        },
    )
    assert recorded.status_code == 200
    recorded_body = recorded.json()
    assert recorded_body["step"]["intent"] == "verify HUD contract"
    assert recorded_body["apprenticeship_surface"]["focus_session_id"] == session_id
    assert recorded_body["apprenticeship_surface"]["detail"]["replay"]["step_count"] == 1
    assert recorded_body["apprenticeship_surface"]["controls"]["generalize"]["enabled"] is True


def test_hud_missions_view_exposes_focus_and_audit(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "missions": {
                "active_count": 1,
                "backlog_count": 1,
                "completed_count": 0,
                "active": [
                    {
                        "id": "mission-active",
                        "title": "Fix HUD contract",
                        "objective": "Replace raw detail dumps",
                        "status": "active",
                        "priority": "high",
                    }
                ],
                "backlog": [
                    {
                        "id": "mission-backlog",
                        "title": "Follow-up cleanup",
                        "objective": "Tighten remaining panes",
                        "status": "planned",
                        "priority": "medium",
                    }
                ],
                "completed": [],
            }
        }

    monkeypatch.setattr(missions_view, "build_lens_snapshot", _snapshot)

    payload = missions_view.get_missions_view()

    assert payload["focus_mission_id"] == "mission-active"
    assert payload["active"][0]["detail_state"] == "current"
    assert payload["active"][0]["audit"]["id"] == "mission-active"
    assert payload["active"][0]["audit"]["detail_state"] == "current"
    assert payload["backlog"][0]["detail_state"] == "historical"


def test_hud_incidents_view_exposes_focus_and_audit(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "incidents": {
                "open_count": 2,
                "highest_severity": "high",
                "items": [
                    {
                        "id": "incident-top",
                        "summary": "Approval queue is blocked",
                        "severity": "high",
                        "state": "open",
                        "source": "approval-queue",
                    },
                    {
                        "id": "incident-old",
                        "summary": "Repo drift detected",
                        "severity": "medium",
                        "state": "open",
                        "source": "repo",
                    },
                ],
            },
            "security": {
                "quarantine_count": 0,
                "highest_severity": "nominal",
            },
        }

    monkeypatch.setattr(incidents_view, "build_lens_snapshot", _snapshot)

    payload = incidents_view.get_incidents_view()

    assert payload["focus_incident_id"] == "incident-top"
    assert payload["items"][0]["detail_state"] == "current"
    assert payload["items"][0]["audit"]["id"] == "incident-top"
    assert payload["items"][0]["audit"]["detail_state"] == "current"
    assert payload["items"][1]["detail_state"] == "historical"


def test_hud_execution_journal_route_returns_receipts() -> None:
    response = client.get("/api/execution-journal")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "execution_journal"
    assert "focus_run_id" in payload
    assert "focus_action_kind" in payload
    assert "active_run" in payload
    assert "items" in payload


def test_hud_execution_feed_route_returns_structured_surface() -> None:
    response = client.get("/api/execution-feed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "execution_feed"
    assert "summary" in payload
    assert "severity" in payload
    assert "evidence" in payload
    assert "detail" in payload
    assert "operator_link" in payload["detail"]


def test_hud_missions_route_returns_structured_surface() -> None:
    response = client.get("/api/missions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "missions"
    assert "focus_mission_id" in payload
    assert "summary" in payload
    assert "severity" in payload
    assert "cards" in payload
    assert "detail" in payload


def test_hud_incidents_route_returns_structured_surface() -> None:
    response = client.get("/api/incidents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "incidents"
    assert "focus_incident_id" in payload
    assert "summary" in payload
    assert "severity" in payload
    assert "cards" in payload
    assert "detail" in payload


def test_hud_inbox_route_returns_structured_surface() -> None:
    response = client.get("/api/inbox")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "inbox"
    assert "focus_message_id" in payload
    assert "summary" in payload
    assert "severity" in payload
    assert "cards" in payload
    assert "detail" in payload


def test_hud_runs_route_returns_structured_surface() -> None:
    response = client.get("/api/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "runs"
    assert "focus_run_id" in payload
    assert "summary" in payload
    assert "severity" in payload
    assert "cards" in payload
    assert "detail" in payload


def test_hud_execution_journal_view_normalizes_action_and_approval_keys(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "runs": {
                "last_run": {
                    "run_id": "run-tests",
                    "phase": "verify",
                    "summary": "Fast checks ran through Lens.",
                },
                "ledger_tail": [
                    {
                        "run_id": "run-tests",
                        "ts": "2026-03-11T10:02:00+00:00",
                        "kind": "lens.action.execute",
                        "summary": {
                            "action_kind": "repo.tests",
                            "ok": True,
                            "summary_text": "Lane fast executed. 12 passed | 0 failed | 4 skipped/deselected",
                            "presentation_cards": [
                                {"label": "Lane", "value": "fast", "tone": "low"},
                                {"label": "Passed", "value": "12", "tone": "low"},
                            ],
                        },
                        "detail": {"action_kind": "repo.tests", "approval_id": "approval-tests"},
                    },
                    {
                        "run_id": "run-tests",
                        "ts": "2026-03-11T10:01:00+00:00",
                        "kind": "approval.decided",
                        "summary": {"decision": "approved", "approval_id": "approval-tests"},
                    },
                ],
                "recent": [],
            }
        }

    monkeypatch.setattr(execution_journal_view, "build_lens_snapshot", _snapshot)

    payload = execution_journal_view.get_execution_journal_view()

    assert payload["focus_run_id"] == "run-tests"
    assert payload["focus_action_kind"] == "repo.tests"
    lens_row = next(item for item in payload["items"] if item["kind"] == "lens.action.execute")
    approval_row = next(item for item in payload["items"] if item["kind"] == "approval.decided")
    assert lens_row["action_kind"] == "repo.tests"
    assert lens_row["approval_id"] == "approval-tests"
    assert lens_row["summary"].startswith("repo.tests | Lane fast executed.")
    assert lens_row["detail_summary"].startswith("Lens Action for repo.tests.")
    assert lens_row["detail_cards"][0]["label"] == "Lane"
    assert lens_row["detail_state"] == "historical"
    assert lens_row["audit"]["action_kind"] == "repo.tests"
    assert lens_row["audit"]["run_id"] == "run-tests"
    assert approval_row["approval_id"] == "approval-tests"
    assert approval_row["decision"] == "approved"
    assert approval_row["detail_summary"].startswith("Approval approved for approval-tests.")
    assert approval_row["detail_cards"]
    assert approval_row["detail_state"] == "historical"
    assert approval_row["audit"]["approval_id"] == "approval-tests"
    assert approval_row["audit"]["decision"] == "approved"


def test_hud_inbox_view_marks_current_and_historical_messages(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "inbox": {
                "count": 2,
                "alert_count": 1,
                "items": [
                    {
                        "id": "msg-1",
                        "ts": "2026-03-11T10:05:00+00:00",
                        "title": "Approval waiting",
                        "summary": "repo.tests needs a decision",
                        "severity": "alert",
                    },
                    {
                        "id": "msg-2",
                        "ts": "2026-03-11T10:01:00+00:00",
                        "title": "Observer note",
                        "summary": "observer scan completed",
                        "severity": "low",
                    },
                ],
            }
        }

    monkeypatch.setattr(inbox_view, "build_lens_snapshot", _snapshot)

    payload = inbox_view.get_inbox_view()

    assert payload["summary"].startswith("Approval waiting | alert | repo.tests needs a decision")
    assert payload["focus_message_id"] == "msg-1"
    assert payload["messages"][0]["detail_state"] == "current"
    assert payload["messages"][0]["detail_cards"][0]["label"] == "Message"
    assert payload["messages"][0]["audit"]["id"] == "msg-1"
    assert payload["messages"][0]["audit"]["detail_state"] == "current"
    assert payload["messages"][1]["detail_state"] == "historical"


def test_hud_runs_view_carries_latest_receipt_summary(monkeypatch) -> None:
    def _snapshot() -> dict[str, object]:
        return {
            "runs": {
                "last_run": {
                    "run_id": "run-tests",
                    "phase": "verify",
                    "summary": "Fast checks ran through Lens.",
                },
                "recent": [
                    {
                        "run_id": "run-tests",
                        "event_count": 3,
                        "last_kind": "lens.action.execute",
                        "last_ts": "2026-03-11T10:02:00+00:00",
                    },
                    {
                        "run_id": "run-older",
                        "event_count": 1,
                        "last_kind": "approval.decided",
                        "last_ts": "2026-03-11T09:58:00+00:00",
                    },
                ],
                "ledger_tail": [
                    {
                        "run_id": "run-tests",
                        "ts": "2026-03-11T10:02:00+00:00",
                        "kind": "lens.action.execute",
                        "summary": {
                            "action_kind": "repo.tests",
                            "summary_text": "Lane fast executed. 12 passed | 0 failed",
                        },
                    },
                    {
                        "run_id": "run-older",
                        "ts": "2026-03-11T09:58:00+00:00",
                        "kind": "approval.decided",
                        "summary": {"decision": "approved", "approval_id": "approval-old"},
                    },
                ],
            }
        }

    monkeypatch.setattr(runs_view, "build_lens_snapshot", _snapshot)

    payload = runs_view.get_runs_view()

    assert "Lane fast executed. 12 passed | 0 failed" in payload["summary"]
    assert payload["focus_run_id"] == "run-tests"
    assert payload["active_run"]["detail_state"] == "current"
    assert payload["active_run"]["audit"]["run_id"] == "run-tests"
    assert any(card["label"] == "Latest Receipt" for card in payload["cards"])
    assert payload["run_groups"][0]["detail_state"] == "current"
    assert payload["run_groups"][0]["detail_cards"][-1]["value"] == "Lane fast executed. 12 passed | 0 failed"
    assert payload["run_groups"][0]["audit"]["latest_receipt"] == "Lane fast executed. 12 passed | 0 failed"
    assert payload["run_groups"][1]["detail_state"] == "historical"


def test_hud_orb_surface_reflects_live_presence(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)

    _write_json(
        workspace_root / "control" / "state.json",
        {
            "mode": "pilot",
            "kill_switch": False,
            "scopes": {
                "repos": [str(workspace_root.parent)],
                "workspaces": [str(workspace_root)],
                "apps": ["control", "approvals", "receipts", "lens", "missions"],
            },
        },
    )
    _write_json(
        workspace_root / "runs" / "last_run.json",
        {
            "run_id": "run-orb",
            "phase": "execute",
            "summary": "Orb should move with the work.",
        },
    )
    _write_json(
        workspace_root / "missions" / "missions.json",
        {
            "missions": [
                {
                    "id": "mission-orb",
                    "title": "Orb cursor",
                    "objective": "Make the orb visibly active",
                    "status": "active",
                    "priority": "high",
                    "updated_at": "2026-03-09T13:00:00+00:00",
                }
            ]
        },
    )

    response = client.get("/api/orb")

    assert response.status_code == 200
    body = response.json()
    assert body["surface"] == "orb"
    assert body["mode"] == "pilot"
    assert body["posture"] == "acting"
    assert body["operator_cursor"] is True
    assert body["movement"]["anchor"] == "cursor"
    assert body["movement"]["profile"] == "cursor_ride"
    assert body["movement"]["cursor_lock"] is True
    assert body["movement"]["lead_style"] == "predictive_commit"
    assert body["handback"]["ritual"] == "return_to_ambient"
    assert body["handback"]["return_profile"] == "release_arc"
    assert body["handback"]["duration_ms"] == 1480
    assert body["handback"]["velocity_carry"] > 0.3
    assert body["visual"]["pulse_kind"] == "execution"


def test_hud_fabric_surface_supports_summary_and_query(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)

    _write_json(
        workspace_root / "runs" / "last_run.json",
        {
            "run_id": "run-fabric",
            "phase": "report",
            "summary": "Fabric HUD query path is live.",
        },
    )
    _write_jsonl(
        workspace_root / "journals" / "decisions.jsonl",
        [
            {
                "id": "decision-fabric-1",
                "ts": "2026-03-09T12:00:00+00:00",
                "kind": "observer.decision",
                "run_id": "run-fabric",
                "headline": "Approval waiting for forge promote.",
                "reason": "Approval waiting",
            }
        ],
    )
    _write_jsonl(
        workspace_root / "telemetry" / "events.jsonl",
        [
            {
                "id": "telemetry-fabric-1",
                "ts": "2026-03-09T12:01:00+00:00",
                "ingested_at": "2026-03-09T12:01:01+00:00",
                "run_id": "run-fabric",
                "kind": "telemetry.event",
                "stream": "dev_server",
                "source": "api",
                "severity": "critical",
                "text": "service crashed under load",
                "fields": {"service": "api"},
            }
        ],
    )

    summary = client.get("/api/fabric")

    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["surface"] == "fabric"
    assert summary_payload["summary"]["artifact_count"] >= 2
    assert summary_payload["summary"]["calibration"]["confidence_counts"]["likely"] >= 1

    query = client.post("/api/fabric/query", json={"query": "approval waiting", "limit": 5, "include_related": True})

    assert query.status_code == 200
    query_payload = query.json()
    assert query_payload["surface"] == "fabric"
    assert query_payload["result_count"] >= 1
    assert query_payload["results"][0]["confidence"] == "likely"
    assert query_payload["results"][0]["citation"]["rel_path"] == "journals/decisions.jsonl"


def test_hud_bootstrap_defers_fabric_when_snapshot_is_missing(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fabric"]["surface"] == "fabric"
    assert payload["fabric"]["summary"]["pending"] is True
    assert payload["fabric"]["summary"]["artifact_count"] == 0


def test_hud_actions_endpoint_proxies_lens_actions() -> None:
    original_mode = _get_mode()
    original_scope = _get_scope()
    try:
        _set_mode("pilot", kill_switch=False)
        _set_scope(_enable_apps(original_scope, ["lens", "control", "receipts", "approvals", "worker"]))

        response = client.get("/api/actions")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert any(chip.get("kind") == "control.panic" for chip in payload.get("action_chips", []))
        assert any(
            chip.get("execute_via", {}).get("endpoint") == "/lens/actions/execute"
            for chip in payload.get("action_chips", [])
        )
    finally:
        _set_scope(original_scope)
        _set_mode(str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_hud_action_execute_can_mutate_and_refresh_snapshot() -> None:
    original_mode = _get_mode()
    original_scope = _get_scope()
    try:
        _set_mode("pilot", kill_switch=False)
        _set_scope(_enable_apps(original_scope, ["lens", "control", "receipts", "approvals"]))

        panic = client.post("/api/actions/execute", json={"kind": "control.panic"})

        assert panic.status_code == 200
        payload = panic.json()
        assert payload["execution"]["status"] == "ok"
        assert payload["execution"]["result"]["after"]["kill_switch"] is True
        assert payload["snapshot"]["control"]["kill_switch"] is True
        assert payload["actions"]["status"] == "ok"
        assert payload["voice"]["surface"] == "voice"
        assert payload["orb"]["surface"] == "orb"
        assert payload["current_work"]["surface"] == "current_work"
        assert payload["shift_report"]["surface"] == "shift_report"
        assert payload["repo_drilldown"]["surface"] == "repo_drilldown"
        assert payload["approval_queue"]["surface"] == "approval_queue"
        assert payload["blocked_actions"]["surface"] == "blocked_actions"
        assert payload["execution_journal"]["surface"] == "execution_journal"
        assert payload["execution_feed"]["surface"] == "execution_feed"
        assert payload["execution_feed"]["detail"]["execution"]["result"]["after"]["kill_switch"] is True
        assert payload["dashboard"]["surface"] == "dashboard"
        assert payload["missions"]["surface"] == "missions"
        assert payload["incidents"]["surface"] == "incidents"
        assert payload["inbox"]["surface"] == "inbox"
        assert payload["runs"]["surface"] == "runs"
        assert payload["fabric"]["surface"] == "fabric"
        assert payload["surface_digests"]["shift_report"]
        assert payload["surface_digests"]["execution_feed"]
    finally:
        _set_scope(original_scope)
        _set_mode(str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_hud_stream_emits_sse_bootstrap_updates(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_bootstrap_payload(*, max_actions: int = 8) -> dict[str, object]:
        calls["count"] += 1
        return {
            "status": "ok",
            "service": "hud",
            "version": "0.2.0",
            "snapshot": {"count": calls["count"], "max_actions": max_actions},
            "actions": {"status": "ok", "action_chips": [], "blocked_actions": []},
            "voice": {"surface": "voice", "mode": "pilot", "headline": "Stable", "lines": [], "actions": []},
            "dashboard": {"surface": "dashboard", "mode": {"current": "pilot", "available": ["pilot"]}, "cards": []},
            "missions": {"surface": "missions", "active": [], "backlog": []},
            "incidents": {"surface": "incidents", "items": [{"summary": "none"}]},
            "inbox": {"surface": "inbox", "messages": []},
            "runs": {"surface": "runs", "active_run": {"run_id": "r1", "phase": "verify"}},
        }

    monkeypatch.setattr(hud_main, "_build_bootstrap_payload", fake_bootstrap_payload)

    response = client.get("/api/stream", params={"max_seconds": 1, "poll_interval_ms": 50})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: bootstrap") == 1
    assert response.text.count("event: surface_update") >= 1
    assert "event: end" in response.text


def test_hud_root_mentions_voice_presence() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Voice Presence" in response.text
    assert "Orb Chamber" in response.text



def test_hud_voice_briefing_surface_uses_voice_operator(monkeypatch) -> None:
    monkeypatch.setattr(
        hud_main,
        "build_live_operator_briefing",
        lambda mode="assist", max_actions=3: {
            "status": "ok",
            "run_id": "voice-run-1",
            "briefing": {
                "mode": mode,
                "headline": "System state is stable.",
                "lines": ["Control mode is assist."],
                "actions": [{"kind": "observer.scan", "label": "Run Observer Scan"}],
            },
        },
    )

    response = client.get("/api/voice/briefing", params={"mode": "assist", "max_actions": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "voice-run-1"
    assert payload["briefing"]["mode"] == "assist"
    assert payload["briefing"]["actions"][0]["kind"] == "observer.scan"



def test_hud_voice_command_preview_surface_uses_voice_operator(monkeypatch) -> None:
    monkeypatch.setattr(
        hud_main,
        "preview_operator_command",
        lambda utterance, locale="en-US", max_actions=5: {
            "status": "ok",
            "run_id": "voice-preview-1",
            "intent": {"kind": "action.suggestion", "trust": "Likely"},
            "matches": [
                {
                    "kind": "control.panic",
                    "label": "Panic Stop (Kill Switch)",
                    "risk_tier": "high",
                    "match_score": 12,
                    "why": ["matched alias 'panic'"],
                }
            ],
            "governance": {
                "execution": "not_performed",
                "requires_explicit_execution": True,
                "reason": "Voice preview cannot execute actions implicitly.",
            },
        },
    )

    response = client.post(
        "/api/voice/command/preview",
        json={"utterance": "panic stop the system", "locale": "en-US", "max_actions": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "voice-preview-1"
    assert payload["intent"]["kind"] == "action.suggestion"
    assert payload["matches"][0]["kind"] == "control.panic"
