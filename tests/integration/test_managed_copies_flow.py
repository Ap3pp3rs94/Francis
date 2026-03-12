from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


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


def test_managed_copy_create_delta_quarantine_and_replace_flow() -> None:
    workspace = Path(__file__).resolve().parents[2] / "workspace"
    registry_path = workspace / "managed_copies" / "registry.json"
    deltas_path = workspace / "managed_copies" / "deltas.jsonl"
    run_ledger_path = workspace / "runs" / "run_ledger.jsonl"
    log_path = workspace / "logs" / "francis.log.jsonl"
    decisions_path = workspace / "journals" / "decisions.jsonl"
    registry_before_exists = registry_path.exists()
    registry_before = _read_text(registry_path)
    deltas_before_exists = deltas_path.exists()
    deltas_before = _read_text(deltas_path)
    run_ledger_before_exists = run_ledger_path.exists()
    run_ledger_before = _read_text(run_ledger_path)
    log_before_exists = log_path.exists()
    log_before = _read_text(log_path)
    decisions_before_exists = decisions_path.exists()
    decisions_before = _read_text(decisions_path)

    try:
        with TestClient(app) as client:
            original_mode = _get_mode(client)
            original_scope = _get_scope(client)
            try:
                _set_mode(client, "pilot", kill_switch=False)
                _set_scope(client, _enable_apps(original_scope, ["managed_copies", "federation", "receipts"]))

                created = client.post(
                    "/managed-copies/create",
                    json={
                        "customer_label": "Acme Copy",
                        "baseline_version": "francis-core",
                        "sla_tier": "premium",
                        "capability_packs": ["pack.alpha"],
                        "notes": "Premium managed deployment.",
                    },
                )
                assert created.status_code == 200
                created_payload = created.json()
                copy_id = str(created_payload["copy"]["copy_id"]).strip()
                assert copy_id

                delta = client.post(
                    f"/managed-copies/copies/{copy_id}/delta",
                    json={
                        "signal_kind": "capability_signal",
                        "summary": "Promote lint-safe review flow.",
                        "evidence_refs": ["run:123", "approval:abc"],
                        "capability_packs": ["pack.beta"],
                    },
                )
                assert delta.status_code == 200
                delta_payload = delta.json()
                assert delta_payload["delta"]["delta_model"] == "safe_signals_only"
                assert delta_payload["state"]["delta_count"] >= 1

                quarantined = client.post(
                    f"/managed-copies/copies/{copy_id}/quarantine",
                    json={"reason": "Rogue behavior detected in customer delta."},
                )
                assert quarantined.status_code == 200
                assert quarantined.json()["copy"]["status"] == "quarantined"

                replaced = client.post(
                    f"/managed-copies/copies/{copy_id}/replace",
                    json={"reason": "Replace from clean baseline after rogue quarantine.", "baseline_version": "francis-core-1.1"},
                )
                assert replaced.status_code == 200
                replaced_payload = replaced.json()
                assert replaced_payload["replaced"]["status"] == "replaced"
                assert replaced_payload["replacement"]["status"] == "active"
                assert replaced_payload["replacement"]["replaces_copy_id"] == copy_id
            finally:
                _set_scope(client, original_scope)
                _set_mode(
                    client,
                    str(original_mode.get("mode", "pilot")),
                    bool(original_mode.get("kill_switch", False)),
                )

        registry = json.loads(_read_text(registry_path))
        copies = registry["copies"]
        replaced_copy = next(row for row in copies if row["copy_id"] == copy_id)
        replacement_copy = next(row for row in copies if row.get("replaces_copy_id") == copy_id)
        assert replaced_copy["status"] == "replaced"
        assert replacement_copy["status"] == "active"
        assert replacement_copy["baseline_version"] == "francis-core-1.1"

        deltas = _read_jsonl(deltas_path)
        assert any(str(row.get("copy_id", "")).strip() == copy_id for row in deltas)
        assert deltas[-1]["delta_model"] == "safe_signals_only"

        ledger_rows = _read_jsonl(run_ledger_path)
        kinds = [str(row.get("kind", "")).strip() for row in ledger_rows]
        assert "managed.copy.created" in kinds
        assert "managed.copy.delta.recorded" in kinds
        assert "managed.copy.quarantined" in kinds
        assert "managed.copy.replaced" in kinds
    finally:
        _restore_text(registry_path, registry_before, registry_before_exists)
        _restore_text(deltas_path, deltas_before, deltas_before_exists)
        _restore_text(run_ledger_path, run_ledger_before, run_ledger_before_exists)
        _restore_text(log_path, log_before, log_before_exists)
        _restore_text(decisions_path, decisions_before, decisions_before_exists)
