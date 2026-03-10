import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app as orchestrator_app
import services.hud.app.main as hud_main
import services.hud.app.state as hud_state
import services.hud.app.views.dashboard as dashboard_view
import services.hud.app.views.inbox as inbox_view
import services.hud.app.views.incidents as incidents_view
import services.hud.app.views.missions as missions_view
import services.hud.app.views.runs as runs_view
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
    assert "The Orb rides directly over the cursor." in response.text
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
    assert len(body["cards"]) == 3


def test_hud_bootstrap_aggregates_core_surfaces() -> None:
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "hud"
    assert body["dashboard"]["surface"] == "dashboard"
    assert body["actions"]["status"] == "ok"
    assert body["missions"]["surface"] == "missions"
    assert body["inbox"]["surface"] == "inbox"
    assert body["runs"]["surface"] == "runs"
    assert body["fabric"]["surface"] == "fabric"
    assert body["voice"]["surface"] == "voice"
    assert body["orb"]["surface"] == "orb"


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
    monkeypatch.setattr(missions_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(incidents_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(inbox_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(runs_view, "build_lens_snapshot", _unexpected_snapshot_build)
    monkeypatch.setattr(
        hud_main,
        "get_lens_actions",
        lambda max_actions=8: {"status": "ok", "action_chips": [], "blocked_actions": []},
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

    assert payload["dashboard"]["objective"]["label"] == "Shared snapshot"
    assert payload["missions"]["active_count"] == 1
    assert payload["incidents"]["items"][0]["summary"] == "clear"
    assert payload["inbox"]["messages"][0]["title"] == "Inbox clear"
    assert payload["runs"]["active_run"]["run_id"] == "run-1"


def test_hud_bootstrap_reads_live_workspace_state(monkeypatch, tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    monkeypatch.setattr(hud_state, "DEFAULT_WORKSPACE_ROOT", workspace_root)

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
    assert body["dashboard"]["mode"]["current"] == "away"
    assert body["missions"]["active_count"] == 1
    assert body["missions"]["backlog_count"] == 1
    assert body["incidents"]["open_count"] == 1
    assert body["incidents"]["security"]["quarantine_count"] == 1
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
    assert body["movement"]["profile"] == "humanized_follow"
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
    assert response.text.count("event: bootstrap") >= 2
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
