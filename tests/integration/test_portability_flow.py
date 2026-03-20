from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(_read_text(path) or "{}")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    raw = _read_text(path)
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _restore_text(path: Path, content: str, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def _get_mode() -> dict:
    response = client.get("/control/mode")
    assert response.status_code == 200
    return response.json()


def _set_mode(mode: str, kill_switch: bool | None = None) -> None:
    payload: dict[str, object] = {"mode": mode}
    if kill_switch is not None:
        payload["kill_switch"] = kill_switch
    response = client.put("/control/mode", json=payload)
    assert response.status_code == 200


def _get_scope() -> dict:
    response = client.get("/control/scope")
    assert response.status_code == 200
    return response.json()["scope"]


def _set_scope(scope: dict) -> None:
    response = client.put("/control/scope", json=scope)
    assert response.status_code == 200


def _enable_apps(scope: dict, required_apps: list[str]) -> dict:
    apps = [str(item) for item in scope.get("apps", []) if isinstance(item, str)]
    lowered = [item.lower() for item in apps]
    for app_name in required_apps:
        if app_name.lower() not in lowered:
            apps.append(app_name)
            lowered.append(app_name.lower())
    repo_root = str(Path(__file__).resolve().parents[2])
    workspace_root = str((Path(__file__).resolve().parents[2] / "workspace").resolve())
    return {
        "repos": [repo_root],
        "workspaces": [workspace_root],
        "apps": apps,
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def test_portability_export_preview_apply_flow() -> None:
    workspace_root = Path(__file__).resolve().parents[2] / "workspace"
    repo_root = workspace_root.parent.resolve()
    portability_dir = workspace_root / "portability"
    portability_backup = workspace_root / ".portability-backup-test"
    tracked_paths = [
        workspace_root / "missions" / "missions.json",
        workspace_root / "missions" / "history.jsonl",
        workspace_root / "forge" / "catalog.json",
        workspace_root / "telemetry" / "config.json",
        workspace_root / "federation" / "topology.json",
        workspace_root / "managed_copies" / "registry.json",
        workspace_root / "managed_copies" / "deltas.jsonl",
        workspace_root / "swarm" / "units.json",
        workspace_root / "swarm" / "delegations.jsonl",
        workspace_root / "approvals" / "requests.jsonl",
        workspace_root / "journals" / "decisions.jsonl",
        workspace_root / "logs" / "francis.log.jsonl",
        workspace_root / "runs" / "run_ledger.jsonl",
    ]
    backups = {path: (_read_text(path), path.exists()) for path in tracked_paths}
    mode_before = _get_mode()
    scope_before = _get_scope()

    if portability_backup.exists():
        shutil.rmtree(portability_backup)
    if portability_dir.exists():
        shutil.copytree(portability_dir, portability_backup)

    try:
        _set_mode("pilot", kill_switch=False)
        _set_scope(
            _enable_apps(
                scope_before,
                ["portability", "federation", "managed_copies", "swarm", "telemetry", "approvals"],
            )
        )

        _write_json(
            workspace_root / "missions" / "missions.json",
            {
                "missions": [
                    {
                        "id": "mission-portability",
                        "title": "Portability slice",
                        "objective": "Preserve governed continuity.",
                        "status": "active",
                        "priority": "high",
                        "updated_at": "2026-03-12T10:00:00+00:00",
                    }
                ]
            },
        )
        _write_jsonl(
            workspace_root / "missions" / "history.jsonl",
            [{"kind": "mission.created", "mission_id": "mission-portability", "ts": "2026-03-12T10:00:00+00:00"}],
        )
        _write_json(
            workspace_root / "forge" / "catalog.json",
            {
                "version": 1,
                "entries": [
                    {
                        "id": "cap-portability",
                        "name": "portability.export",
                        "status": "staged",
                    }
                ],
            },
        )
        _write_json(
            workspace_root / "telemetry" / "config.json",
            {"enabled": True, "sources": ["git", "terminal"], "updated_at": "2026-03-12T10:00:00+00:00"},
        )
        _write_json(
            workspace_root / "federation" / "topology.json",
            {
                "version": 1,
                "updated_at": "2026-03-12T10:00:00+00:00",
                "local_node": {
                    "node_id": "node-local",
                    "label": "Primary Node",
                    "role": "primary",
                    "trust_level": "high",
                    "status": "active",
                    "local": True,
                    "paired_by": "system",
                    "paired_at": "2026-03-12T10:00:00+00:00",
                    "last_seen_at": "2026-03-12T10:00:00+00:00",
                    "last_sync_at": "2026-03-12T10:00:00+00:00",
                    "last_sync_summary": "Local node ready.",
                    "scopes": {
                        "repos": [str(repo_root)],
                        "workspaces": [str(workspace_root)],
                        "apps": ["control", "approvals", "lens"],
                    },
                    "capabilities": {"remote_approvals": True, "away_continuity": True, "receipt_summary": True},
                    "notes": "",
                    "revoked_at": None,
                    "revocation_reason": "",
                },
                "paired_nodes": [
                    {
                        "node_id": "node-remote-1",
                        "label": "Remote Node",
                        "role": "always_on",
                        "trust_level": "scoped",
                        "status": "active",
                        "local": False,
                        "paired_by": "architect",
                        "paired_at": "2026-03-12T10:00:00+00:00",
                        "last_seen_at": "2026-03-12T10:00:00+00:00",
                        "last_sync_at": "2026-03-12T10:00:00+00:00",
                        "last_sync_summary": "Remote continuity available.",
                        "scopes": {
                            "repos": [str(repo_root)],
                            "workspaces": [str(workspace_root)],
                            "apps": ["control", "approvals", "lens"],
                        },
                        "capabilities": {"remote_approvals": True, "away_continuity": False, "receipt_summary": True},
                        "notes": "Portable remote node",
                        "revoked_at": None,
                        "revocation_reason": "",
                    }
                ],
            },
        )
        _write_json(
            workspace_root / "managed_copies" / "registry.json",
            {
                "version": 1,
                "updated_at": "2026-03-12T10:00:00+00:00",
                "copies": [
                    {
                        "copy_id": "copy-portability",
                        "customer_label": "Portable Copy",
                        "status": "active",
                        "baseline_version": "francis-core",
                        "sla_tier": "premium",
                        "workspace_namespace": "managed_copies/copy-portability",
                        "capability_packs": ["pack.portability"],
                        "created_by": "architect",
                        "created_at": "2026-03-12T10:00:00+00:00",
                        "last_delta_at": "2026-03-12T10:05:00+00:00",
                        "last_delta_summary": "Portable delta",
                        "delta_count": 1,
                    }
                ],
            },
        )
        _write_jsonl(
            workspace_root / "managed_copies" / "deltas.jsonl",
            [
                {
                    "id": "delta-portability",
                    "ts": "2026-03-12T10:05:00+00:00",
                    "copy_id": "copy-portability",
                    "signal_kind": "capability_signal",
                    "summary": "Portable delta",
                    "delta_model": "safe_signals_only",
                }
            ],
        )
        _write_json(
            workspace_root / "swarm" / "units.json",
            {
                "version": 1,
                "updated_at": "2026-03-12T10:00:00+00:00",
                "units": [
                    {
                        "unit_id": "planner",
                        "label": "Planner",
                        "role": "planner",
                        "summary": "Portable planner",
                        "capabilities": ["mission.plan"],
                        "scope_defaults": {
                            "repos": [str(repo_root)],
                            "workspaces": [str(workspace_root)],
                            "apps": ["control", "approvals", "lens"],
                        },
                        "delegatable": True,
                        "local": True,
                    }
                ],
            },
        )
        _write_jsonl(
            workspace_root / "swarm" / "delegations.jsonl",
            [
                {
                    "id": "delegation-portability",
                    "ts": "2026-03-12T10:06:00+00:00",
                    "status": "queued",
                    "summary": "Queued swarm continuity",
                    "target_unit_id": "planner",
                }
            ],
        )
        _write_jsonl(
            workspace_root / "approvals" / "requests.jsonl",
            [
                {
                    "id": "approval-portability",
                    "ts": "2026-03-12T10:07:00+00:00",
                    "action": "repo.tests",
                    "reason": "Fast checks required",
                    "requested_by": "architect",
                }
            ],
        )
        _write_jsonl(workspace_root / "journals" / "decisions.jsonl", [])

        export_response = client.post(
            "/portability/export",
            json={"label": "Repo continuity", "note": "portable checkpoint"},
            headers={"x-francis-role": "architect"},
        )
        assert export_response.status_code == 200
        export_body = export_response.json()
        bundle_id = str(export_body["bundle_id"]).strip()
        export_path = workspace_root / str(export_body["path"]).strip()
        assert bundle_id
        assert export_path.exists()

        bundle_doc = _read_json(export_path)
        sections = bundle_doc.get("sections", {}) if isinstance(bundle_doc.get("sections"), dict) else {}
        control_section = sections.get("control", {}) if isinstance(sections.get("control"), dict) else {}
        control_state = control_section.get("state", {}) if isinstance(control_section.get("state"), dict) else {}
        control_state["mode"] = "away"
        control_state["kill_switch"] = True
        _write_json(export_path, bundle_doc)

        preview_response = client.post(
            "/portability/import/preview",
            json={"bundle_id": bundle_id},
            headers={"x-francis-role": "architect"},
        )
        assert preview_response.status_code == 200
        preview_body = preview_response.json()
        assert preview_body["preview"]["effects"]["applied_mode"] == "assist"
        assert any("downgraded" in str(item).lower() for item in preview_body["preview"]["warnings"])
        preview_id = str(preview_body["preview"]["preview_id"]).strip()
        assert preview_id

        apply_response = client.post(
            "/portability/import/apply",
            json={"preview_id": preview_id},
            headers={"x-francis-role": "architect"},
        )
        assert apply_response.status_code == 200
        apply_body = apply_response.json()
        assert apply_body["import_id"]
        assert apply_body["state"]["preview_state"] == "applied"

        mode = _get_mode()
        assert mode["mode"] == "assist"
        assert mode["kill_switch"] is False
        scope = _get_scope()
        assert "portability" in [str(item).lower() for item in scope.get("apps", [])]

        telemetry_doc = _read_json(workspace_root / "telemetry" / "config.json")
        assert telemetry_doc["imported_from_bundle_id"] == bundle_id

        missions_doc = _read_json(workspace_root / "missions" / "missions.json")
        assert missions_doc["imported_from_bundle_id"] == bundle_id
        assert missions_doc["missions"][0]["id"] == "mission-portability"

        catalog_doc = _read_json(workspace_root / "forge" / "catalog.json")
        assert any(str(row.get("id", "")).strip() == "cap-portability" for row in catalog_doc.get("entries", []))

        topology_doc = _read_json(workspace_root / "federation" / "topology.json")
        paired_nodes = topology_doc.get("paired_nodes", []) if isinstance(topology_doc.get("paired_nodes"), list) else []
        assert paired_nodes
        imported_node = next(row for row in paired_nodes if str(row.get("node_id", "")).strip() == "node-remote-1")
        assert imported_node["status"] == "stale"
        assert bundle_id in str(imported_node.get("notes", ""))

        archive_dir = workspace_root / "portability" / "imports" / "archive" / bundle_id
        assert (archive_dir / "approvals_requests.jsonl").exists()
        assert (archive_dir / "takeover_state.json").exists()

        ledger_rows = _read_jsonl(workspace_root / "runs" / "run_ledger.jsonl")
        kinds = [str(row.get("kind", "")).strip() for row in ledger_rows]
        assert "portability.bundle.exported" in kinds
        assert "portability.bundle.previewed" in kinds
        assert "portability.bundle.imported" in kinds
    finally:
        _set_scope(scope_before)
        _set_mode(str(mode_before.get("mode", "pilot")), bool(mode_before.get("kill_switch", False)))
        for path, (content, existed) in backups.items():
            _restore_text(path, content, existed)
        if portability_dir.exists():
            shutil.rmtree(portability_dir)
        if portability_backup.exists():
            shutil.copytree(portability_backup, portability_dir)
            shutil.rmtree(portability_backup)

