from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app
from services.worker.app import main as worker_main


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


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _remove_jobs(job_ids: list[str]) -> None:
    path = _workspace_root() / "queue" / "jobs.jsonl"
    rows = _read_jsonl(path)
    keep = [row for row in rows if str(row.get("id", "")) not in set(job_ids)]
    _write_jsonl(path, keep)


def test_worker_cycle_processes_mission_queue() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["missions", "worker", "receipts"]))

        create = c.post(
            "/missions",
            json={
                "title": f"Worker-{uuid4()}",
                "objective": "worker cycle integration",
                "steps": ["only-step"],
            },
        )
        assert create.status_code == 200
        mission_id = create.json()["mission"]["id"]

        cycle = c.post(
            "/worker/cycle",
            json={"max_jobs": 200, "max_runtime_seconds": 60, "action_allowlist": ["mission.tick"]},
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["status"] == "ok"
        assert payload["processed_count"] >= 1
        assert payload["success_count"] >= 1
        assert any(
            row.get("action") == "mission.tick" and row.get("mission_id") == mission_id for row in payload.get("jobs", [])
        )

        mission = c.get(f"/missions/{mission_id}")
        assert mission.status_code == 200
        status = mission.json()["mission"]["status"]
        assert status in {"completed", "active"}

        receipts = c.get("/receipts/latest", params={"limit": 200})
        assert receipts.status_code == 200
        ledger_rows = receipts.json()["receipts"]["ledger"]
        assert any(row.get("kind") == "worker.cycle" for row in ledger_rows)
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_blocked_in_observe_mode() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_scope(c, _enable_apps(original_scope, ["worker"]))
        _set_mode(c, "observe", kill_switch=False)
        blocked = c.post("/worker/cycle", json={"max_jobs": 10, "max_runtime_seconds": 30})
        assert blocked.status_code == 403
        assert "Control denied" in blocked.json().get("detail", "")
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_rbac_denies_observer_role() -> None:
    c = TestClient(app)
    denied = c.post(
        "/worker/cycle",
        headers={"x-francis-role": "observer"},
        json={"max_jobs": 10, "max_runtime_seconds": 30},
    )
    assert denied.status_code == 403
    assert "RBAC denied" in denied.json().get("detail", "")


def test_worker_cycle_executes_forge_propose_job() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)

    job_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker", "forge"]))

        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.propose",
                "status": "queued",
                "attempts": 0,
                "context": {"deadletter_count": 1, "open_incident_count": 0, "active_mission_count": 1},
            }
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={"max_jobs": 20, "max_runtime_seconds": 60, "action_allowlist": ["forge.propose"]},
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["success_count"] >= 1
        matched = [row for row in payload.get("jobs", []) if row.get("job_id") == job_id]
        assert matched
        assert matched[0]["ok"] is True
        report_path = matched[0]["result"].get("report_path", "")
        assert isinstance(report_path, str) and report_path.startswith("forge/reports/")

        jobs_after = _read_jsonl(jobs_path)
        updated = [row for row in jobs_after if row.get("id") == job_id]
        assert updated
        assert updated[0].get("status") == "done"
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_retry_backoff_and_deadletter_escalation() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)

    job_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker"]))

        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        deadletter_path = _workspace_root() / "queue" / "deadletter.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.unknown",
                "status": "queued",
                "attempts": 0,
                "max_attempts": 2,
                "base_backoff_seconds": 60,
            }
        )
        _write_jsonl(jobs_path, jobs)
        dead_before = len(_read_jsonl(deadletter_path))

        first = c.post(
            "/worker/cycle",
            json={"max_jobs": 20, "max_runtime_seconds": 60, "action_allowlist": ["forge.unknown"]},
        )
        assert first.status_code == 200
        assert first.json()["error_count"] >= 1
        assert first.json()["requeued_count"] >= 1

        jobs_after_first = _read_jsonl(jobs_path)
        first_job = [row for row in jobs_after_first if row.get("id") == job_id][0]
        assert first_job.get("status") == "queued"
        assert int(first_job.get("attempts", 0)) == 1
        assert first_job.get("next_run_after")

        second = c.post(
            "/worker/cycle",
            json={"max_jobs": 20, "max_runtime_seconds": 60, "action_allowlist": ["forge.unknown"]},
        )
        assert second.status_code == 200
        assert second.json()["processed_count"] == 0

        jobs_after_second = _read_jsonl(jobs_path)
        for row in jobs_after_second:
            if row.get("id") == job_id:
                row["next_run_after"] = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        _write_jsonl(jobs_path, jobs_after_second)

        third = c.post(
            "/worker/cycle",
            json={"max_jobs": 20, "max_runtime_seconds": 60, "action_allowlist": ["forge.unknown"]},
        )
        assert third.status_code == 200
        assert third.json()["deadlettered_count"] >= 1

        jobs_final = _read_jsonl(jobs_path)
        final_job = [row for row in jobs_final if row.get("id") == job_id][0]
        assert final_job.get("status") == "failed"
        assert int(final_job.get("attempts", 0)) == 2

        dead_after = _read_jsonl(deadletter_path)
        assert len(dead_after) >= dead_before + 1
        assert any(
            isinstance(item.get("job"), dict) and item["job"].get("id") == job_id and item.get("kind") == "worker.deadletter"
            for item in dead_after
        )
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_renews_lease_for_long_running_job(monkeypatch) -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    job_id = str(uuid4())

    def _slow_forge_execute(job: dict, *, run_id: str, fs) -> dict:
        time.sleep(1.2)
        return {
            "ok": True,
            "run_id": run_id,
            "job_id": str(job.get("id", "")),
            "action": str(job.get("action", "")),
            "report_path": "forge/reports/mock.json",
            "proposal_count": 1,
        }

    monkeypatch.setattr(worker_main, "execute_forge_job", _slow_forge_execute)

    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker", "forge"]))

        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.propose",
                "status": "queued",
                "attempts": 0,
                "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
            }
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={
                "max_jobs": 10,
                "max_runtime_seconds": 60,
                "action_allowlist": ["forge.propose"],
                "lease_ttl_seconds": 5,
                "lease_heartbeat_seconds": 1,
            },
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["success_count"] >= 1
        assert payload["lease_renewed_count"] >= 1
        assert payload["lease_lost_count"] == 0

        jobs_after = _read_jsonl(jobs_path)
        updated = [row for row in jobs_after if row.get("id") == job_id]
        assert updated
        assert updated[0].get("status") == "done"
        assert updated[0].get("lease_owner") is None
        assert updated[0].get("lease_key") is None
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_reclaims_expired_lease_and_processes_job() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    job_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker", "forge"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.propose",
                "status": "leased",
                "lease_owner": "stale-worker",
                "lease_key": str(uuid4()),
                "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat(),
                "attempts": 0,
                "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 1},
            }
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={"max_jobs": 10, "max_runtime_seconds": 60, "action_allowlist": ["forge.propose"]},
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["reclaimed_leases_count"] >= 1
        assert payload["processed_count"] >= 1
        matched = [row for row in payload.get("jobs", []) if row.get("job_id") == job_id]
        assert matched
        assert matched[0]["ok"] is True

        jobs_after = _read_jsonl(jobs_path)
        updated = [row for row in jobs_after if row.get("id") == job_id]
        assert updated
        assert updated[0].get("status") == "done"
        assert updated[0].get("lease_owner") is None
        assert updated[0].get("lease_key") is None
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_concurrent_runs_claim_job_once(monkeypatch) -> None:
    job_id = str(uuid4())
    jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
    jobs = _read_jsonl(jobs_path)
    jobs.append(
        {
            "id": job_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": str(uuid4()),
            "action": "forge.concurrent",
            "status": "queued",
            "attempts": 0,
            "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
        }
    )
    _write_jsonl(jobs_path, jobs)

    def _slow_forge_execute(job: dict, *, run_id: str, fs) -> dict:
        time.sleep(1.0)
        return {
            "ok": True,
            "run_id": run_id,
            "job_id": str(job.get("id", "")),
            "action": str(job.get("action", "")),
            "report_path": "forge/reports/mock-concurrent.json",
            "proposal_count": 1,
        }

    monkeypatch.setattr(worker_main, "execute_forge_job", _slow_forge_execute)

    def _run(label: str) -> dict:
        return worker_main.run_worker_cycle(
            run_id=f"concurrent-{label}-{uuid4()}",
            max_jobs=10,
            max_runtime_seconds=60,
            action_allowlist={"forge.concurrent"},
            lease_ttl_seconds=5,
            lease_heartbeat_seconds=1,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(_run, "a")
            future_b = pool.submit(_run, "b")
            summaries = [future_a.result(), future_b.result()]

        processed_rows = [
            row
            for summary in summaries
            for row in summary.get("jobs", [])
            if str(row.get("job_id", "")) == job_id
        ]
        assert len(processed_rows) == 1
        assert processed_rows[0].get("ok") is True

        jobs_after = _read_jsonl(jobs_path)
        updated = [row for row in jobs_after if row.get("id") == job_id]
        assert updated
        assert updated[0].get("status") == "done"
        assert int(updated[0].get("attempts", 0)) == 1
    finally:
        _remove_jobs([job_id])


def test_worker_cycle_recovery_breakdown_by_action_class() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    forge_id = str(uuid4())
    skill_id = str(uuid4())
    active_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.extend(
            [
                {
                    "id": forge_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "status": "leased",
                    "lease_owner": "stale-worker",
                    "lease_key": str(uuid4()),
                    "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat(),
                    "attempts": 0,
                },
                {
                    "id": skill_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "skill.run",
                    "status": "leased",
                    "lease_owner": "stale-worker",
                    "lease_key": str(uuid4()),
                    "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat(),
                    "attempts": 0,
                },
                {
                    "id": active_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "status": "leased",
                    "lease_owner": "active-worker",
                    "lease_key": str(uuid4()),
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
                    "attempts": 0,
                },
            ]
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={"max_jobs": 10, "max_runtime_seconds": 60, "action_allowlist": ["mission.tick"]},
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["reclaimed_leases_count"] >= 2
        recovered = payload.get("recovered_leases_by_action_class", {})
        assert int(recovered.get("forge", 0)) >= 1
        assert int(recovered.get("skill", 0)) >= 1

        jobs_after = _read_jsonl(jobs_path)
        forge_row = [row for row in jobs_after if row.get("id") == forge_id][0]
        skill_row = [row for row in jobs_after if row.get("id") == skill_id][0]
        active_row = [row for row in jobs_after if row.get("id") == active_id][0]
        assert forge_row.get("status") == "queued"
        assert skill_row.get("status") == "queued"
        assert active_row.get("status") == "leased"
    finally:
        _remove_jobs([forge_id, skill_id, active_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_concurrency_gate_blocks_second_run(monkeypatch) -> None:
    job_id = str(uuid4())
    jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
    jobs = _read_jsonl(jobs_path)
    jobs.append(
        {
            "id": job_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": str(uuid4()),
            "action": "forge.gate",
            "status": "queued",
            "attempts": 0,
            "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
        }
    )
    _write_jsonl(jobs_path, jobs)

    started = threading.Event()
    release = threading.Event()

    def _gated_execute(job: dict, *, run_id: str, fs) -> dict:
        started.set()
        release.wait(timeout=5)
        return {
            "ok": True,
            "run_id": run_id,
            "job_id": str(job.get("id", "")),
            "action": str(job.get("action", "")),
            "report_path": "forge/reports/mock-gate.json",
            "proposal_count": 1,
        }

    monkeypatch.setattr(worker_main, "execute_forge_job", _gated_execute)

    def _run(label: str) -> dict:
        return worker_main.run_worker_cycle(
            run_id=f"gate-{label}-{uuid4()}",
            max_jobs=10,
            max_runtime_seconds=60,
            action_allowlist={"forge.gate"},
            lease_ttl_seconds=5,
            lease_heartbeat_seconds=1,
            max_concurrent_cycles=1,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(_run, "one")
            assert started.wait(timeout=2.0)
            second_summary = pool.submit(_run, "two").result()
            assert second_summary.get("status") == "blocked"
            assert "max concurrent worker cycles reached" in str(second_summary.get("reason", ""))
            release.set()
            first_summary = first_future.result()

        assert first_summary.get("status") == "ok"
        assert first_summary.get("processed_count", 0) >= 1
    finally:
        release.set()
        _remove_jobs([job_id])


def test_worker_recover_endpoint_can_filter_action_classes() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    forge_id = str(uuid4())
    skill_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.extend(
            [
                {
                    "id": forge_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "status": "leased",
                    "lease_owner": "stale-worker",
                    "lease_key": str(uuid4()),
                    "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                    "attempts": 0,
                },
                {
                    "id": skill_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "skill.run",
                    "status": "leased",
                    "lease_owner": "stale-worker",
                    "lease_key": str(uuid4()),
                    "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                    "attempts": 0,
                },
            ]
        )
        _write_jsonl(jobs_path, jobs)

        recover = c.post("/worker/recover", json={"action_classes": ["skill"]})
        assert recover.status_code == 200
        payload = recover.json()
        assert payload["status"] == "ok"
        assert payload["recovered_count"] >= 1
        assert int(payload.get("recovered_by_action_class", {}).get("skill", 0)) >= 1
        assert int(payload.get("recovered_by_action_class", {}).get("forge", 0)) == 0

        jobs_after = _read_jsonl(jobs_path)
        forge_row = [row for row in jobs_after if row.get("id") == forge_id][0]
        skill_row = [row for row in jobs_after if row.get("id") == skill_id][0]
        assert forge_row.get("status") == "leased"
        assert skill_row.get("status") == "queued"
    finally:
        _remove_jobs([forge_id, skill_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_status_reports_expired_leased_jobs() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    job_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.propose",
                "status": "leased",
                "lease_owner": "stale-worker",
                "lease_key": str(uuid4()),
                "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat(),
                "attempts": 0,
            }
        )
        _write_jsonl(jobs_path, jobs)

        status = c.get("/worker/status")
        assert status.status_code == 200
        queue = status.json()["queue"]
        assert queue["leased"] >= 1
        assert queue["leased_expired"] >= 1
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_skips_active_non_expired_lease() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    job_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker", "forge"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.propose",
                "status": "leased",
                "lease_owner": "other-worker",
                "lease_key": str(uuid4()),
                "lease_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=240)).isoformat(),
                "attempts": 0,
                "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
            }
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={"max_jobs": 10, "max_runtime_seconds": 60, "action_allowlist": ["forge.propose"]},
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["processed_count"] == 0
        assert payload["lease_busy_count"] >= 1

        jobs_after = _read_jsonl(jobs_path)
        job_rows = [row for row in jobs_after if row.get("id") == job_id]
        assert job_rows
        assert job_rows[0].get("status") == "leased"
        assert job_rows[0].get("lease_owner") == "other-worker"
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_status_endpoint_returns_queue_metrics() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker"]))
        status = c.get("/worker/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["status"] == "ok"
        assert "queue" in payload
        assert "deadletter" in payload
        assert "last_worker_run" in payload
        queue = payload["queue"]
        assert "queued_due" in queue
        assert "queued_backoff" in queue
    finally:
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_priority_order_and_action_limits() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    low_id = str(uuid4())
    urgent_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker", "forge"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.extend(
            [
                {
                    "id": low_id,
                    "ts": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "priority": "low",
                    "status": "queued",
                    "attempts": 0,
                    "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
                },
                {
                    "id": urgent_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "run_id": str(uuid4()),
                    "action": "forge.propose",
                    "priority": "urgent",
                    "status": "queued",
                    "attempts": 0,
                    "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 1},
                },
            ]
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={
                "max_jobs": 10,
                "max_runtime_seconds": 60,
                "action_allowlist": ["forge.propose"],
                "action_limits": {"forge.propose": 1},
            },
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["processed_count"] == 1
        assert payload["deferred_count"] >= 1
        assert payload["jobs"][0]["job_id"] == urgent_id

        jobs_after = _read_jsonl(jobs_path)
        low_job = [row for row in jobs_after if row.get("id") == low_id][0]
        urgent_job = [row for row in jobs_after if row.get("id") == urgent_id][0]
        assert urgent_job.get("status") == "done"
        assert low_job.get("status") == "queued"
    finally:
        _remove_jobs([low_id, urgent_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))


def test_worker_cycle_action_timeout_can_escalate_to_deadletter() -> None:
    c = TestClient(app)
    original_mode = _get_mode(c)
    original_scope = _get_scope(c)
    job_id = str(uuid4())
    try:
        _set_mode(c, "pilot", kill_switch=False)
        _set_scope(c, _enable_apps(original_scope, ["worker", "forge"]))
        jobs_path = _workspace_root() / "queue" / "jobs.jsonl"
        jobs = _read_jsonl(jobs_path)
        jobs.append(
            {
                "id": job_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": str(uuid4()),
                "action": "forge.propose",
                "status": "queued",
                "attempts": 0,
                "max_attempts": 1,
                "context": {"deadletter_count": 0, "open_incident_count": 0, "active_mission_count": 0},
            }
        )
        _write_jsonl(jobs_path, jobs)

        cycle = c.post(
            "/worker/cycle",
            json={
                "max_jobs": 10,
                "max_runtime_seconds": 60,
                "action_allowlist": ["forge.propose"],
                "action_timeouts": {"forge.propose": 0},
            },
        )
        assert cycle.status_code == 200
        payload = cycle.json()
        assert payload["deadlettered_count"] >= 1
        matched = [row for row in payload.get("jobs", []) if row.get("job_id") == job_id]
        assert matched
        assert matched[0]["ok"] is False
        assert "runtime exceeded timeout" in matched[0]["error"]

        jobs_after = _read_jsonl(jobs_path)
        final_job = [row for row in jobs_after if row.get("id") == job_id][0]
        assert final_job.get("status") == "failed"
    finally:
        _remove_jobs([job_id])
        _set_scope(c, original_scope)
        _set_mode(c, str(original_mode.get("mode", "pilot")), bool(original_mode.get("kill_switch", False)))
