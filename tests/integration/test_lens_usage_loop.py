from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
import services.orchestrator.app.routes.lens as lens_routes


def _get_mode(client: TestClient) -> dict:
    response = client.get("/control/mode")
    assert response.status_code == 200
    return response.json()


def _set_mode(client: TestClient, mode: str, kill_switch: bool | None = None) -> None:
    payload: dict[str, object] = {"mode": mode}
    if kill_switch is not None:
        payload["kill_switch"] = kill_switch
    response = client.put("/control/mode", json=payload)
    assert response.status_code == 200


def _get_scope(client: TestClient) -> dict:
    response = client.get("/control/scope")
    assert response.status_code == 200
    return response.json()["scope"]


def _set_scope(client: TestClient, scope: dict) -> None:
    response = client.put("/control/scope", json=scope)
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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    raw = _read_text(path)
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _restore_text(path: Path, content: str, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def test_lens_execute_routes_orb_authority_commands(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        lens_routes,
        "check_action_allowed",
        lambda *args, **kwargs: (True, "allowed", {}),
    )
    monkeypatch.setattr(
        lens_routes,
        "resolve_orb_focus_target",
        lambda max_age_ms=2500: {
            "x": 320,
            "y": 240,
            "surface": {"kind": "francis", "label": "Francis surface"},
            "zone": {"kind": "francis_action_row", "label": "Francis action row"},
            "affordances": [
                {"kind": "focus_click", "label": "Focus Click"},
            ],
            "target": {
                "label": "Francis focus point",
                "confidence": "likely",
                "stability": {"state": "settled"},
                "window": {"in_bounds": True},
            },
        },
    )
    monkeypatch.setattr(
        lens_routes,
        "queue_orb_authority_command",
        lambda **kwargs: captured.update(kwargs) or {
            "status": "ok",
            "receipt_id": "receipt-orb-1",
            "command": {
                "id": "cmd-orb-1",
                "kind": kwargs.get("kind"),
                "reason": kwargs.get("reason"),
                "status": "queued",
                "grounding": kwargs.get("grounding", {}),
            },
            "authority": {
                "surface": "orb_authority",
                "summary": "1 queued Orb authority command(s) are waiting for lawful Away control.",
                "state": {
                    "state": "human_active",
                    "eligible": False,
                    "live": False,
                    "idle_seconds": 0.0,
                    "idle_threshold_seconds": 30.0,
                },
            },
        },
    )
    monkeypatch.setattr(
        lens_routes,
        "cancel_orb_authority_queue",
        lambda **kwargs: {
            "status": "ok",
            "receipt_id": "receipt-orb-2",
            "canceled_count": 1,
            "authority": {
                "surface": "orb_authority",
                "summary": "No Orb authority commands are waiting. Human control remains primary.",
                "state": {
                    "state": "human_active",
                    "eligible": False,
                    "live": False,
                    "idle_seconds": 0.0,
                    "idle_threshold_seconds": 30.0,
                },
            },
        },
    )

    with TestClient(app) as client:
        move_response = client.post(
            "/lens/actions/execute",
            json={
                "kind": "orb.authority.queue_move",
                "args": {"x": 320, "y": 240, "coordinate_space": "display"},
                "dry_run": False,
            },
        )
        assert move_response.status_code == 200
        move_payload = move_response.json()
        assert move_payload["status"] == "ok"
        assert move_payload["result"]["command"]["kind"] == "mouse.move"
        assert move_payload["result"]["command"]["grounding"]["state"] == "concrete"
        assert move_payload["result"]["tool"]["skill"] == "orb.authority"
        assert move_payload["result"]["presentation"]["cards"][0]["label"] == "Authority"
        assert move_payload["result"]["receipt_id"] == "receipt-orb-1"
        assert isinstance(captured.get("grounding"), dict)
        assert captured["grounding"]["state"] == "concrete"

        clear_response = client.post(
            "/lens/actions/execute",
            json={
                "kind": "orb.authority.clear_queue",
                "args": {"reason": "Operator cleared the queue."},
                "dry_run": False,
            },
        )
        assert clear_response.status_code == 200
        clear_payload = clear_response.json()
        assert clear_payload["status"] == "ok"
        assert clear_payload["result"]["canceled_count"] == 1
        assert clear_payload["result"]["presentation"]["cards"][-1]["label"] == "Cleared"


def test_lens_execute_rejects_invalid_orb_authority_coordinates(monkeypatch) -> None:
    monkeypatch.setattr(
        lens_routes,
        "check_action_allowed",
        lambda *args, **kwargs: (True, "allowed", {}),
    )
    with TestClient(app) as client:
        response = client.post(
            "/lens/actions/execute",
            json={
                "kind": "orb.authority.queue_move",
                "args": {"x": "left-edge", "y": 240, "coordinate_space": "display"},
                "dry_run": False,
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "x must be numeric for orb.authority.queue_move"


def test_lens_execute_routes_takeover_desktop_enqueue(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        lens_routes,
        "check_action_allowed",
        lambda *args, **kwargs: (True, "allowed", {}),
    )
    monkeypatch.setattr(
        lens_routes,
        "control_takeover_desktop_enqueue",
        lambda request, payload: captured.update(
            {
                "summary": payload.summary,
                "command_grounding": payload.commands[0].grounding if payload.commands else {},
            }
        ) or {
            "status": "ok",
            "session_id": "takeover-session-1",
            "summary": "Queued 1 desktop command into the takeover session.",
            "receipt_id": "receipt-desktop-1",
            "commands": [
                {
                    "id": "cmd-desktop-1",
                    "kind": "mouse.move",
                    "reason": "Move into place.",
                    "status": "queued",
                    "grounding": payload.commands[0].grounding if payload.commands else {},
                }
            ],
            "authority": {
                "surface": "orb_authority",
                "summary": "1 queued Orb authority command(s) are waiting for lawful Away control.",
                "state": {
                    "state": "human_active",
                    "eligible": False,
                    "live": False,
                    "idle_seconds": 0.0,
                    "idle_threshold_seconds": 30.0,
                },
            },
        },
    )

    with TestClient(app) as client:
        response = client.post(
            "/lens/actions/execute",
            json={
                "kind": "control.takeover.desktop.enqueue",
                "args": {
                    "summary": "Queue desktop move",
                    "commands": [
                        {
                            "kind": "mouse.move",
                            "args": {"x": 320, "y": 240, "coordinate_space": "display"},
                            "grounding": {
                                "state": "concrete",
                                "control_ready": True,
                                "zone_label": "Francis action row",
                                "summary": "Concrete Francis action row target. Focus Click is grounded from the Orb.",
                            },
                        }
                    ],
                },
                "dry_run": False,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["result"]["session_id"] == "takeover-session-1"
    assert payload["result"]["commands"][0]["kind"] == "mouse.move"
    assert payload["result"]["tool"]["skill"] == "control.takeover.desktop"
    assert payload["result"]["presentation"]["cards"][0]["label"] == "Authority"
    assert payload["result"]["receipt_id"] == "receipt-desktop-1"
    assert isinstance(captured.get("command_grounding"), dict)
    assert captured["command_grounding"]["state"] == "concrete"


def test_lens_state_surfaces_current_work_and_next_best_action() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    apprenticeship_path = workspace / "apprenticeship" / "sessions.json"
    catalog_path = workspace / "forge" / "catalog.json"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    apprenticeship_before_exists = apprenticeship_path.exists()
    apprenticeship_before = _read_text(apprenticeship_path)
    catalog_before_exists = catalog_path.exists()
    catalog_before = _read_text(catalog_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_json(apprenticeship_path, {"sessions": []})
        _write_json(catalog_path, {"entries": []})
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-1",
                    "ts": "2026-03-11T01:00:00+00:00",
                    "ingested_at": "2026-03-11T01:00:01+00:00",
                    "run_id": "usage-loop-run",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                state = client.get("/lens/state")
            finally:
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert state.status_code == 200
        payload = state.json()
        assert payload["current_work"]["repo"]["available"] is True
        assert payload["current_work"]["repo"]["dirty"] is True
        assert payload["current_work"]["attention"]["kind"] == "terminal_failure"
        assert payload["next_best_action"]["kind"] == "repo.tests"
        assert payload["next_best_action"]["enabled"] is False
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(apprenticeship_path, apprenticeship_before, apprenticeship_before_exists)
        _restore_text(catalog_path, catalog_before, catalog_before_exists)
        if signal_before_exists:
            signal_path.write_text(signal_before, encoding="utf-8")
        elif signal_path.exists():
            signal_path.unlink()


def test_lens_state_prioritizes_review_ready_apprenticeship_over_terminal_failure() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    apprenticeship_path = workspace / "apprenticeship" / "sessions.json"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    apprenticeship_before_exists = apprenticeship_path.exists()
    apprenticeship_before = _read_text(apprenticeship_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_json(
            apprenticeship_path,
            {
                "sessions": [
                    {
                        "id": "teach-review",
                        "title": "Teach repo verification",
                        "objective": "Turn the verify lane into a reusable skill",
                        "status": "review",
                        "step_count": 2,
                        "updated_at": "2026-03-11T01:12:00+00:00",
                    }
                ]
            },
        )
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-1b",
                    "ts": "2026-03-11T01:12:00+00:00",
                    "ingested_at": "2026-03-11T01:12:01+00:00",
                    "run_id": "usage-loop-run-review",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                state = client.get("/lens/state")
            finally:
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert state.status_code == 200
        payload = state.json()
        assert payload["current_work"]["attention"]["kind"] == "teaching_review"
        assert payload["current_work"]["apprenticeship"]["focus_session"]["id"] == "teach-review"
        assert payload["next_best_action"]["kind"] == "apprenticeship.skillize"
        assert payload["next_best_action"]["args"]["session_id"] == "teach-review"
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(apprenticeship_path, apprenticeship_before, apprenticeship_before_exists)
        _restore_text(signal_path, signal_before, signal_before_exists)


def test_lens_state_prioritizes_staged_capability_over_terminal_failure() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    apprenticeship_path = workspace / "apprenticeship" / "sessions.json"
    catalog_path = workspace / "forge" / "catalog.json"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    apprenticeship_before_exists = apprenticeship_path.exists()
    apprenticeship_before = _read_text(apprenticeship_path)
    catalog_before_exists = catalog_path.exists()
    catalog_before = _read_text(catalog_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_json(apprenticeship_path, {"sessions": []})
        _write_json(
            catalog_path,
            {
                "entries": [
                    {
                        "id": "cap-stage",
                        "name": "Capability Stage",
                        "slug": "capability-stage",
                        "description": "A staged capability ready for governed promotion.",
                        "risk_tier": "medium",
                        "status": "staged",
                        "version": "0.3.0",
                        "path": "forge/staging/cap-stage",
                        "imported_from_bundle_id": "bundle-usage-capability",
                        "imported_at": "2026-03-11T01:10:00+00:00",
                        "validation": {"ok": True},
                        "diff_summary": {"file_count": 4},
                        "tool_pack": {"skill_name": "forge.pack.capability-stage"},
                    }
                ]
            },
        )
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-capability-telemetry-1",
                    "ts": "2026-03-11T01:15:00+00:00",
                    "ingested_at": "2026-03-11T01:15:01+00:00",
                    "run_id": "usage-loop-capability-run",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                state = client.get("/lens/state")
            finally:
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert state.status_code == 200
        payload = state.json()
        assert payload["current_work"]["attention"]["kind"] == "capability_review"
        assert payload["current_work"]["capabilities"]["focus_entry"]["id"] == "cap-stage"
        assert payload["current_work"]["capabilities"]["focus_entry"]["recommended_action"] == "forge.promote"
        assert payload["current_work"]["capabilities"]["focus_entry"]["provenance"]["kind"] == "local_import"
        assert payload["current_work"]["capabilities"]["focus_entry"]["provenance"]["review_required"] is True
        assert any("provenance" in blocker.lower() or "local review" in blocker.lower() for blocker in payload["current_work"]["blockers"])
        assert payload["next_best_action"]["kind"] == "forge.promote"
        assert payload["next_best_action"]["enabled"] is False
        assert payload["next_best_action"]["args"]["stage_id"] == "cap-stage"
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(apprenticeship_path, apprenticeship_before, apprenticeship_before_exists)
        _restore_text(catalog_path, catalog_before, catalog_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
        _restore_text(signal_path, signal_before, signal_before_exists)


def test_lens_promote_blocks_external_capability_without_traceable_provenance() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    catalog_path = workspace / "forge" / "catalog.json"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    catalog_before_exists = catalog_path.exists()
    catalog_before = _read_text(catalog_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        _write_json(
            catalog_path,
            {
                "entries": [
                    {
                        "id": "cap-promote-blocked",
                        "name": "Capability External",
                        "slug": "capability-imported",
                        "status": "staged",
                        "version": "0.5.0",
                        "path": "forge/staging/cap-promote-blocked",
                        "validation": {"ok": True},
                        "diff_summary": {
                            "file_count": 2,
                            "files": [
                                {"path": "forge/staging/cap-promote-blocked/README.md"},
                                {"path": "forge/staging/cap-promote-blocked/tests/test_capability_imported.py"},
                            ],
                        },
                        "tool_pack": {"skill_name": "forge.pack.capability-imported"},
                        "provenance": {"source_kind": "third_party"},
                    }
                ]
            },
        )
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["forge", "lens", "approvals"]))
                request_response = client.post(
                    "/approvals/request",
                    json={
                        "action": "forge.promote",
                        "reason": "Promote external capability",
                        "metadata": {"stage_id": "cap-promote-blocked", "action_kind": "forge.promote"},
                    },
                )
                assert request_response.status_code == 200
                approval_id = str(request_response.json()["approval"]["id"]).strip()
                assert approval_id
                decide_response = client.post(
                    f"/approvals/{approval_id}/decision",
                    json={"decision": "approved", "note": "approval is present but provenance anchors are not"},
                )
                assert decide_response.status_code == 200
                response = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "forge.promote",
                        "args": {
                            "stage_id": "cap-promote-blocked",
                            "approval_id": approval_id,
                        },
                    },
                )
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["message"] == "Capability is not promotion-ready"
        assert detail["rule"] == "provenance"
        assert "provenance" in detail["reason"].lower()
    finally:
        _restore_text(catalog_path, catalog_before, catalog_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)


def test_lens_state_surfaces_untrusted_capability_quarantine() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    apprenticeship_path = workspace / "apprenticeship" / "sessions.json"
    catalog_path = workspace / "forge" / "catalog.json"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    apprenticeship_before_exists = apprenticeship_path.exists()
    apprenticeship_before = _read_text(apprenticeship_path)
    catalog_before_exists = catalog_path.exists()
    catalog_before = _read_text(catalog_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_json(apprenticeship_path, {"sessions": []})
        _write_json(
            catalog_path,
            {
                "entries": [
                    {
                        "id": "cap-quarantine",
                        "name": "Capability Quarantine",
                        "slug": "capability-quarantine",
                        "description": "An imported capability that cannot be traced safely.",
                        "risk_tier": "high",
                        "status": "staged",
                        "version": "0.6.0",
                        "path": "forge/staging/cap-quarantine",
                        "validation": {"ok": True},
                        "diff_summary": {
                            "file_count": 2,
                            "files": [
                                {"path": "forge/staging/cap-quarantine/README.md"},
                                {"path": "forge/staging/cap-quarantine/tests/test_capability_quarantine.py"},
                            ],
                        },
                        "tool_pack": {"skill_name": "forge.pack.capability-quarantine"},
                        "provenance": {"source_kind": "third_party"},
                    }
                ]
            },
        )
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-capability-telemetry-2",
                    "ts": "2026-03-13T03:15:00+00:00",
                    "ingested_at": "2026-03-13T03:15:01+00:00",
                    "run_id": "usage-loop-capability-run-2",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                state = client.get("/lens/state")
            finally:
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert state.status_code == 200
        payload = state.json()
        assert payload["current_work"]["attention"]["kind"] == "capability_review"
        assert payload["current_work"]["capabilities"]["focus_entry"]["id"] == "cap-quarantine"
        assert payload["current_work"]["capabilities"]["focus_entry"]["recommended_action"] == "forge.quarantine"
        assert payload["next_best_action"]["kind"] == "forge.quarantine"
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(apprenticeship_path, apprenticeship_before, apprenticeship_before_exists)
        _restore_text(catalog_path, catalog_before, catalog_before_exists)
        _restore_text(signal_path, signal_before, signal_before_exists)


def test_lens_actions_include_repo_usage_chips_and_repo_status_executes() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    apprenticeship_path = workspace / "apprenticeship" / "sessions.json"
    repo_drilldown_path = workspace / "lens" / "repo_drilldown.json"
    signal_path = repo_root / "usage-loop-signal.txt"
    telemetry_before = _read_text(telemetry_path)
    apprenticeship_before_exists = apprenticeship_path.exists()
    apprenticeship_before = _read_text(apprenticeship_path)
    repo_drilldown_before_exists = repo_drilldown_path.exists()
    repo_drilldown_before = _read_text(repo_drilldown_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_json(apprenticeship_path, {"sessions": []})
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-2",
                    "ts": "2026-03-11T01:05:00+00:00",
                    "ingested_at": "2026-03-11T01:05:01+00:00",
                    "run_id": "usage-loop-run-2",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["tools", "lens", "telemetry"]))
                actions = client.get("/lens/actions")
                assert actions.status_code == 200
                actions_payload = actions.json()
                chip_kinds = [chip.get("kind") for chip in actions_payload.get("action_chips", [])]
                assert "repo.status" in chip_kinds
                assert "repo.diff" in chip_kinds
                assert "repo.lint" in chip_kinds
                assert "repo.tests" in chip_kinds
                assert "repo.tests.request_approval" in chip_kinds

                repo_status = client.post("/lens/actions/execute", json={"kind": "repo.status"})
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert repo_status.status_code == 200
        result_payload = repo_status.json()
        assert result_payload["result"]["kind"] == "repo.status"
        assert result_payload["result"]["tool"]["skill"] == "repo.status"
        assert result_payload["result"]["summary"]
        assert result_payload["result"]["presentation"]["kind"] == "repo.status"
        assert result_payload["result"]["presentation"]["severity"] in {"low", "medium"}
        assert result_payload["result"]["presentation"]["cards"]
        assert result_payload["result"]["presentation"]["evidence"]
        persisted = json.loads(_read_text(repo_drilldown_path))
        assert persisted["surface"] == "repo_drilldown"
        assert persisted["kind"] == "repo.status"
        assert persisted["presentation"]["kind"] == "repo.status"
        assert persisted["presentation"]["cards"]
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(apprenticeship_path, apprenticeship_before, apprenticeship_before_exists)
        _restore_text(repo_drilldown_path, repo_drilldown_before, repo_drilldown_before_exists)
        _restore_text(signal_path, signal_before, signal_before_exists)


def test_lens_actions_carry_repo_tests_approval_into_action_chip() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace.parent
    telemetry_path = workspace / "telemetry" / "events.jsonl"
    apprenticeship_path = workspace / "apprenticeship" / "sessions.json"
    signal_path = repo_root / "usage-loop-signal.txt"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    telemetry_before = _read_text(telemetry_path)
    apprenticeship_before_exists = apprenticeship_path.exists()
    apprenticeship_before = _read_text(apprenticeship_path)
    signal_before_exists = signal_path.exists()
    signal_before = _read_text(signal_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        signal_path.write_text("usage signal\n", encoding="utf-8")
        _write_json(apprenticeship_path, {"sessions": []})
        _write_jsonl(
            telemetry_path,
            [
                {
                    "id": "usage-loop-telemetry-3",
                    "ts": "2026-03-11T01:10:00+00:00",
                    "ingested_at": "2026-03-11T01:10:01+00:00",
                    "run_id": "usage-loop-run-3",
                    "kind": "telemetry.event",
                    "stream": "terminal",
                    "source": "terminal",
                    "severity": "error",
                    "text": "terminal: pytest -q tests/integration/test_lens_usage_loop.py (exit=1)",
                    "fields": {
                        "command": "pytest -q tests/integration/test_lens_usage_loop.py",
                        "cwd": str(repo_root),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "1 failed",
                    },
                }
            ],
        )
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["tools", "lens", "telemetry", "approvals", "control"]))

                request_approval = client.post("/lens/actions/execute", json={"kind": "repo.tests.request_approval"})
                assert request_approval.status_code == 200
                approval_id = str(request_approval.json()["result"]["approval"]["id"]).strip()
                assert approval_id

                pending_actions = client.get("/lens/actions")
                assert pending_actions.status_code == 200
                pending_chips = pending_actions.json()["action_chips"]
                pending_repo_tests = next(
                    chip for chip in pending_chips if str(chip.get("kind", "")).strip() == "repo.tests"
                )
                assert pending_repo_tests["enabled"] is False
                assert "pending" in str(pending_repo_tests.get("policy_reason", "")).lower()

                approve = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "control.remote.approval.approve",
                        "args": {"approval_id": approval_id, "note": "lens usage approval"},
                    },
                )
                assert approve.status_code == 200

                approved_actions = client.get("/lens/actions")
                assert approved_actions.status_code == 200
                approved_chips = approved_actions.json()["action_chips"]
                approved_repo_tests = next(
                    chip for chip in approved_chips if str(chip.get("kind", "")).strip() == "repo.tests"
                )
                assert approved_repo_tests["enabled"] is True
                execute_args = approved_repo_tests.get("execute_via", {}).get("payload", {}).get("args", {})
                assert execute_args.get("approval_id") == approval_id
                assert execute_args.get("lane") == "fast"
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )
    finally:
        telemetry_path.write_text(telemetry_before, encoding="utf-8")
        _restore_text(apprenticeship_path, apprenticeship_before, apprenticeship_before_exists)
        _restore_text(signal_path, signal_before, signal_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)


def test_lens_actions_request_and_execute_capability_promotion() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    catalog_path = workspace / "forge" / "catalog.json"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    catalog_before_exists = catalog_path.exists()
    catalog_before = _read_text(catalog_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)

    try:
        _write_json(
            catalog_path,
            {
                "entries": [
                    {
                        "id": "cap-promote",
                        "name": "Capability Promote",
                        "slug": "capability-promote",
                        "description": "A staged capability ready for promotion.",
                        "risk_tier": "medium",
                        "status": "staged",
                        "version": "0.4.0",
                        "path": "forge/staging/cap-promote",
                        "validation": {"ok": True},
                        "diff_summary": {"file_count": 5},
                        "tool_pack": {"skill_name": "forge.pack.capability-promote"},
                    }
                ]
            },
        )
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["forge", "approvals", "control", "lens"]))

                actions = client.get("/lens/actions")
                assert actions.status_code == 200
                action_chips = actions.json()["action_chips"]
                promote_chip = next(
                    chip for chip in action_chips if str(chip.get("kind", "")).strip() == "forge.promote"
                )
                request_chip = next(
                    chip
                    for chip in action_chips
                    if str(chip.get("kind", "")).strip() == "forge.promote.request_approval"
                )
                assert promote_chip["enabled"] is False
                assert request_chip["enabled"] is True
                assert request_chip["execute_via"]["payload"]["args"]["stage_id"] == "cap-promote"

                request_approval = client.post(
                    "/lens/actions/execute",
                    json={"kind": "forge.promote.request_approval", "args": {"stage_id": "cap-promote"}},
                )
                assert request_approval.status_code == 200
                approval_id = str(request_approval.json()["result"]["approval"]["id"]).strip()
                assert approval_id

                pending_actions = client.get("/lens/actions")
                assert pending_actions.status_code == 200
                pending_promote = next(
                    chip
                    for chip in pending_actions.json()["action_chips"]
                    if str(chip.get("kind", "")).strip() == "forge.promote"
                )
                assert pending_promote["enabled"] is False
                assert "pending" in str(pending_promote.get("policy_reason", "")).lower()
                assert not any(
                    str(chip.get("kind", "")).strip() == "forge.promote.request_approval"
                    for chip in pending_actions.json()["action_chips"]
                )

                approve = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "control.remote.approval.approve",
                        "args": {"approval_id": approval_id, "note": "approve capability promotion"},
                    },
                )
                assert approve.status_code == 200

                approved_actions = client.get("/lens/actions")
                assert approved_actions.status_code == 200
                approved_promote = next(
                    chip
                    for chip in approved_actions.json()["action_chips"]
                    if str(chip.get("kind", "")).strip() == "forge.promote"
                )
                assert approved_promote["enabled"] is False
                assert "assist mode" in str(approved_promote.get("policy_reason", "")).lower()

                _set_mode(client, "pilot", kill_switch=False)
                pilot_actions = client.get("/lens/actions")
                assert pilot_actions.status_code == 200
                approved_promote = next(
                    chip
                    for chip in pilot_actions.json()["action_chips"]
                    if str(chip.get("kind", "")).strip() == "forge.promote"
                )
                assert approved_promote["enabled"] is True
                promote_args = approved_promote.get("execute_via", {}).get("payload", {}).get("args", {})
                assert promote_args.get("stage_id") == "cap-promote"
                assert promote_args.get("approval_id") == approval_id

                promote = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "forge.promote",
                        "args": {"stage_id": "cap-promote", "approval_id": approval_id},
                    },
                )
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert promote.status_code == 200
        result_payload = promote.json()
        assert result_payload["result"]["kind"] == "forge.promote"
        assert result_payload["result"]["tool"]["skill"] == "forge.promote"
        assert result_payload["result"]["tool"]["approval_id"] == approval_id
        assert result_payload["result"]["presentation"]["kind"] == "forge.promote"
        assert result_payload["result"]["entry"]["status"] == "active"
        assert result_payload["result"]["tool_pack_registered"] is True
        catalog = json.loads(_read_text(catalog_path))
        promoted_entry = next(entry for entry in catalog["entries"] if entry["id"] == "cap-promote")
        assert promoted_entry["status"] == "active"
        assert promoted_entry["promoted_at"]
        ledger_rows = _read_jsonl(run_ledger_path)
        forge_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "forge.promote"
        )
        summary = forge_receipt.get("summary", {}) if isinstance(forge_receipt.get("summary"), dict) else {}
        assert summary["stage_id"] == "cap-promote"
        assert summary["status"] == "active"
        assert summary["approval_id"] == approval_id
    finally:
        _restore_text(catalog_path, catalog_before, catalog_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)


def test_lens_actions_quarantine_and_revoke_capability() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    catalog_path = workspace / "forge" / "catalog.json"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    catalog_before_exists = catalog_path.exists()
    catalog_before = _read_text(catalog_path)
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)

    try:
        _write_json(
            catalog_path,
            {
                "entries": [
                    {
                        "id": "cap-lifecycle",
                        "name": "Capability Lifecycle",
                        "slug": "capability-lifecycle",
                        "description": "An active capability that needs governed shutdown.",
                        "risk_tier": "high",
                        "status": "active",
                        "version": "1.2.0",
                        "path": "forge/library/cap-lifecycle",
                        "validation": {"ok": True},
                        "diff_summary": {"file_count": 3},
                        "tool_pack": {"skill_name": "forge.pack.capability-lifecycle"},
                        "provenance": {
                            "source_kind": "vendor",
                            "vendor": "Lifecycle Vendor",
                            "review_state": "approved",
                        },
                    }
                ]
            },
        )
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["forge", "approvals", "lens"]))

                quarantine = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "forge.quarantine",
                        "args": {"entry_id": "cap-lifecycle", "reason": "Capability failed provenance review."},
                    },
                )
                assert quarantine.status_code == 200
                assert quarantine.json()["result"]["entry"]["status"] == "quarantined"

                request_revoke = client.post(
                    "/lens/actions/execute",
                    json={"kind": "forge.revoke.request_approval", "args": {"entry_id": "cap-lifecycle"}},
                )
                assert request_revoke.status_code == 200
                approval_id = str(request_revoke.json()["result"]["approval"]["id"]).strip()
                assert approval_id

                decide_response = client.post(
                    f"/approvals/{approval_id}/decision",
                    json={"decision": "approved", "note": "Capability should be revoked after quarantine."},
                )
                assert decide_response.status_code == 200

                revoke = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "forge.revoke",
                        "args": {
                            "entry_id": "cap-lifecycle",
                            "approval_id": approval_id,
                            "reason": "Capability is no longer trusted for governed use.",
                        },
                    },
                )
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert revoke.status_code == 200
        result_payload = revoke.json()
        assert result_payload["result"]["kind"] == "forge.revoke"
        assert result_payload["result"]["tool"]["approval_id"] == approval_id
        assert result_payload["result"]["entry"]["status"] == "revoked"
        assert result_payload["result"]["presentation"]["kind"] == "forge.revoke"
        catalog = json.loads(_read_text(catalog_path))
        lifecycle_entry = next(entry for entry in catalog["entries"] if entry["id"] == "cap-lifecycle")
        assert lifecycle_entry["status"] == "revoked"
        assert lifecycle_entry["quarantined_at"]
        assert lifecycle_entry["revoked_at"]
        ledger_rows = _read_jsonl(run_ledger_path)
        revoke_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "forge.revoke"
        )
        revoke_summary = revoke_receipt.get("summary", {}) if isinstance(revoke_receipt.get("summary"), dict) else {}
        assert revoke_summary["entry_id"] == "cap-lifecycle"
        assert revoke_summary["approval_id"] == approval_id
        quarantine_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "forge.quarantine"
        )
        quarantine_summary = quarantine_receipt.get("summary", {}) if isinstance(quarantine_receipt.get("summary"), dict) else {}
        assert quarantine_summary["entry_id"] == "cap-lifecycle"
        assert quarantine_summary["status"] == "quarantined"
    finally:
        _restore_text(catalog_path, catalog_before, catalog_before_exists)
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)


def test_lens_execute_repo_tests_with_approved_request() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    approvals_path = workspace / "approvals" / "requests.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    approvals_before_exists = approvals_path.exists()
    approvals_before = _read_text(approvals_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)

    try:
        approvals_path.parent.mkdir(parents=True, exist_ok=True)
        approvals_path.write_text("", encoding="utf-8")
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.write_text("", encoding="utf-8")

        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "assist", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["tools", "lens", "approvals", "control"]))

                request_approval = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "repo.tests.request_approval",
                        "args": {"target": "tests/unit/test_usage_loop.py"},
                    },
                )
                assert request_approval.status_code == 200
                approval_id = str(request_approval.json()["result"]["approval"]["id"]).strip()
                assert approval_id

                approve = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "control.remote.approval.approve",
                        "args": {"approval_id": approval_id, "note": "approve direct repo tests"},
                    },
                )
                assert approve.status_code == 200

                repo_tests = client.post(
                    "/lens/actions/execute",
                    json={
                        "kind": "repo.tests",
                        "args": {"target": "tests/unit/test_usage_loop.py", "approval_id": approval_id},
                    },
                )
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        assert repo_tests.status_code == 200
        result_payload = repo_tests.json()
        assert result_payload["result"]["kind"] == "repo.tests"
        assert result_payload["result"]["tool"]["skill"] == "repo.tests"
        assert result_payload["result"]["tool"]["approval_id"] == approval_id
        assert result_payload["result"]["presentation"]["kind"] == "repo.tests"
        assert result_payload["result"]["presentation"]["severity"] in {"low", "medium", "high"}
        assert result_payload["result"]["presentation"]["cards"]
        assert result_payload["result"]["presentation"]["detail"]["stats"]["lane"] == "fast"
        ledger_rows = _read_jsonl(run_ledger_path)
        lens_receipt = next(
            row for row in reversed(ledger_rows) if str(row.get("kind", "")).strip() == "lens.action.execute"
        )
        summary = lens_receipt.get("summary", {}) if isinstance(lens_receipt.get("summary"), dict) else {}
        assert summary["action_kind"] == "repo.tests"
        assert summary["summary_text"]
        assert summary["signal"] in {"low", "medium", "high"}
        assert summary["skill"] == "repo.tests"
        assert summary["approval_id"] == approval_id
        assert summary["presentation_cards"]
    finally:
        _restore_text(approvals_path, approvals_before, approvals_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
