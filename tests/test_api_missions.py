from __future__ import annotations

from pathlib import Path


def test_missions_create_list_get_update(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Carry Stage 3 continuity work",
            "summary": "Mission declared for the first real Stage 3 slice.",
            "next_step": "Link an operation and advance the mission state.",
            "requester_id": "test.missions",
            "risk_tier": "high",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])

    listed = client.get("/missions/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert any(str(item.get("id")) == mission_id for item in listed_body["items"])

    operation = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "mission linkage test",
            "input": {"goal": "Create a linked run-ledger entry"},
        },
    )
    assert operation.status_code == 200
    operation_body = operation.json()
    assert operation_body["ok"] is True
    operation_id = str(operation_body["operation_id"])

    patched = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "active",
            "next_step": "Review the linked operation and capture follow-up work.",
            "add_task_ids": [operation_id],
            "actor": "test.missions",
            "note": "Mission picked up for execution.",
            "meta": {"source": "integration_test"},
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is True
    assert patched_body["mission"]["status"] == "active"
    assert patched_body["mission"]["linked_task_ids"] == [operation_id]
    assert patched_body["mission"]["linked_task_count"] == 1
    assert patched_body["mission"]["meta"]["source"] == "integration_test"
    history_events = [str(item.get("event")) for item in patched_body["history"]]
    assert "status_changed" in history_events
    assert "task_links_updated" in history_events
    assert "continuity_updated" in history_events

    deadlettered = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "deadlettered",
            "deadletter_reason": "approval_timeout",
            "actor": "test.missions",
            "note": "Operator did not clear the required gate in time.",
        },
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is True
    assert deadlettered_body["mission"]["status"] == "deadlettered"
    assert deadlettered_body["mission"]["deadletter_reason"] == "approval_timeout"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["id"] == mission_id
    assert fetched_body["mission"]["linked_task_ids"] == [operation_id]
    assert fetched_body["mission"]["deadletter_reason"] == "approval_timeout"
    fetched_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert fetched_events.count("status_changed") >= 2


def test_missions_create_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    set_control_mode("observe", reason="test_missions_create_block", actor="tests")

    created = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission declaration",
            "summary": "Observe mode should reject mission writes.",
            "requester_id": "test.missions.observe",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is False
    assert created_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in created_body["error"]

    listed = client.get("/missions/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["items"] == []


def test_mission_mutation_routes_are_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Observe-mode mutation guard",
            "summary": "Mission should remain unchanged while posture is read-only.",
            "next_step": "Wait for operator posture change.",
            "requester_id": "test.missions.observe",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])

    set_control_mode("observe", reason="test_mission_mutation_block", actor="tests")

    patched = client.patch(
        f"/missions/{mission_id}",
        json={"status": "active", "summary": "should not apply", "actor": "tests"},
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is False
    assert patched_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in patched_body["error"]

    ticked = client.post(f"/missions/{mission_id}/tick", json={"actor": "tests"})
    assert ticked.status_code == 200
    ticked_body = ticked.json()
    assert ticked_body["ok"] is False
    assert ticked_body["applied"] is False
    assert ticked_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in ticked_body["error"]

    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={"reason": "should_not_apply", "actor": "tests"},
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is False
    assert deadlettered_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in deadlettered_body["error"]

    advanced = client.post(f"/missions/{mission_id}/advance", json={"actor": "tests"})
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is False
    assert advanced_body["applied"] is False
    assert advanced_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in advanced_body["error"]

    tick_all = client.post("/missions/tick", json={"actor": "tests", "limit": 10})
    assert tick_all.status_code == 200
    tick_all_body = tick_all.json()
    assert tick_all_body["ok"] is False
    assert tick_all_body["status"] == "blocked"
    assert tick_all_body["items"] == []
    assert tick_all_body["applied"] == 0
    assert "Observe mode keeps Francis read-only." in tick_all_body["errors"][0]["error"]

    run_once = client.post("/missions/run_once", json={"actor": "tests", "limit": 10})
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is False
    assert run_once_body["status"] == "blocked"
    assert run_once_body["items"] == []
    assert run_once_body["advanced"] == 0
    assert run_once_body["processed"] == 0
    assert "Observe mode keeps Francis read-only." in run_once_body["errors"][0]["error"]

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "queued"
    assert fetched_body["mission"]["summary"] == "Mission should remain unchanged while posture is read-only."
    assert fetched_body["mission"]["next_step"] == "Wait for operator posture change."
    assert fetched_body["mission"]["deadletter_reason"] is None
    history_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert history_events == ["created"]


def test_mission_linked_operation_run_updates_history_and_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry a linked operation to completion",
            "summary": "Mission should reflect the linked run lifecycle.",
            "next_step": "Queue the first linked operation.",
            "requester_id": "test.missions.linked",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "mission linked operation",
            "mission_id": mission_id,
            "input": {"goal": "Create a linked plan"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    assert created_body["mission_id"] == mission_id
    assert created_body["mission_linked"] is True
    assert created_body["operation"]["meta"]["mission_id"] == mission_id
    operation_id = str(created_body["operation_id"])

    queued_mission = client.get(f"/missions/{mission_id}")
    assert queued_mission.status_code == 200
    queued_body = queued_mission.json()
    assert queued_body["mission"]["linked_task_ids"] == [operation_id]
    assert queued_body["mission"]["status"] == "queued"

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.linked"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_task_status"] == "completed"
    linked_operations = fetched_body["linked_operations"]
    assert len(linked_operations) == 1
    assert linked_operations[0]["ok"] is True
    assert linked_operations[0]["operation"]["id"] == operation_id
    linked_logs = linked_operations[0]["logs"]
    assert any(item["status"] == "running" for item in linked_logs)
    assert any(item["status"] == "succeeded" for item in linked_logs)
    run_ledger = fetched_body["run_ledger"]
    assert any(item["operation_id"] == operation_id and item["status"] == "running" for item in run_ledger)
    assert any(item["operation_id"] == operation_id and item["status"] == "succeeded" for item in run_ledger)
    loop_state = fetched_body["loop_state"]
    assert loop_state["active_stage"] == "memory"
    assert loop_state["handoff"]["stage"] == "memory"
    assert loop_state["handoff"]["action"] == "review_continuity"
    assert loop_state["handoff"]["operation_id"] == operation_id
    assert loop_state["handoff"]["latest_event"] == fetched_body["history"][-1]["event"]
    assert loop_state["handoff"]["latest_ts"] == fetched_body["history"][-1]["ts"]
    history_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert "linked_task_transition" in history_events
    transition_events = [item for item in fetched_body["history"] if item.get("event") == "linked_task_transition"]
    assert any(item.get("details", {}).get("task_status") == "running" for item in transition_events)
    assert any(item.get("details", {}).get("task_status") == "completed" for item in transition_events)


def test_mission_linked_governance_hold_updates_blocked_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry governed deploy continuity",
            "summary": "Mission should surface governance holds from linked operations.",
            "requester_id": "test.missions.governance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.governance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_task_status"] == "accepted"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "trust_gate"
    assert fetched_body["mission"]["meta"]["last_task_next_step"] == "raise_trust_or_reduce_risk"
    linked_operations = fetched_body["linked_operations"]
    assert len(linked_operations) == 1
    assert linked_operations[0]["operation"]["id"] == operation_id
    assert any(item["name"] == "governance_hold" for item in linked_operations[0]["logs"])
    run_ledger = fetched_body["run_ledger"]
    assert any(item["operation_id"] == operation_id and item["name"] == "governance_hold" for item in run_ledger)
    assert any(item["operation_id"] == operation_id and item["status"] == "blocked" for item in run_ledger)
    loop_state = fetched_body["loop_state"]
    assert loop_state["active_stage"] == "gate"
    assert loop_state["handoff"]["stage"] == "gate"
    assert loop_state["handoff"]["action"] == "raise_trust_or_reduce_risk"
    assert loop_state["handoff"]["operation_id"] == operation_id
    assert loop_state["handoff"]["gate"] == "trust_gate"
    assert loop_state["gate"]["gate"] == "trust_gate"
    assert loop_state["gate"]["next_step"] == "raise_trust_or_reduce_risk"
    assert loop_state["execute"]["next_step"] == "raise_trust_or_reduce_risk"
    assert loop_state["trace"]["latest_event"] == run_ledger[0]["name"]
    assert loop_state["trace"]["latest_ts"]
    assert loop_state["memory"]["latest_event"] == fetched_body["history"][-1]["event"]
    assert loop_state["memory"]["latest_ts"] == fetched_body["history"][-1]["ts"]
    transition_events = [item for item in fetched_body["history"] if item.get("event") == "linked_task_transition"]
    assert transition_events
    assert transition_events[-1]["details"]["gate"] == "trust_gate"
    assert transition_events[-1]["details"]["mission_status_after"] == "blocked"


def test_mission_tick_reconciles_pending_link_and_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Reconcile mission from linked queued work",
            "summary": "Tick should project the latest linked task into mission continuity.",
            "requester_id": "test.missions.tick",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "queued mission tick",
            "mission_id": mission_id,
            "input": {"goal": "Create a queued linked operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    first_tick = client.post(
        f"/missions/{mission_id}/tick",
        json={"actor": "test.missions.tick", "note": "reconcile queued task"},
    )
    assert first_tick.status_code == 200
    first_tick_body = first_tick.json()
    assert first_tick_body["ok"] is True
    assert first_tick_body["applied"] is True
    assert first_tick_body["mission"]["status"] == "queued"
    assert first_tick_body["mission"]["meta"]["last_task_id"] == operation_id
    assert first_tick_body["mission"]["meta"]["last_task_status"] == "pending"
    tick_events = [item for item in first_tick_body["history"] if item.get("event") == "mission_ticked"]
    assert tick_events
    assert tick_events[-1]["details"]["latest_task_status"] == "pending"

    second_tick = client.post(
        f"/missions/{mission_id}/tick",
        json={"actor": "test.missions.tick", "note": "repeat reconcile"},
    )
    assert second_tick.status_code == 200
    second_tick_body = second_tick.json()
    assert second_tick_body["ok"] is True
    assert second_tick_body["applied"] is False
    second_tick_events = [item for item in second_tick_body["history"] if item.get("event") == "mission_ticked"]
    assert len(second_tick_events) == len(tick_events)


def test_mission_deadletter_endpoint_moves_blocked_mission_cleanly(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Deadletter a blocked mission",
            "summary": "Governed mission should move cleanly into deadletter.",
            "requester_id": "test.missions.deadletter",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "blocked for deadletter",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.deadletter"})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={
            "reason": "operator_abandoned_after_governance_hold",
            "actor": "test.missions.deadletter",
            "note": "Mission will not be retried.",
        },
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is True
    assert deadlettered_body["mission"]["status"] == "deadlettered"
    assert deadlettered_body["mission"]["deadletter_reason"] == "operator_abandoned_after_governance_hold"

    history_events = [str(item.get("event")) for item in deadlettered_body["history"]]
    assert "status_changed" in history_events
    assert "continuity_updated" in history_events

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "deadlettered"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] == "blocked"

    ticked = client.post(f"/missions/{mission_id}/tick", json={"actor": "test.missions.deadletter"})
    assert ticked.status_code == 200
    ticked_body = ticked.json()
    assert ticked_body["ok"] is True
    assert ticked_body["applied"] is False
    assert ticked_body["mission"]["status"] == "deadlettered"


def test_mission_run_once_advances_safe_queue_actions(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    ready = client.post(
        "/missions/create",
        json={
            "objective": "Create the first linked operation",
            "summary": "Mission has no linked task yet.",
            "priority": 8,
            "requester_id": "test.missions.queue",
        },
    )
    assert ready.status_code == 200
    ready_id = str(ready.json()["mission_id"])

    blocked = client.post(
        "/missions/create",
        json={
            "objective": "Resolve governed blocker",
            "summary": "Mission should surface a trust blocker.",
            "priority": 9,
            "requester_id": "test.missions.queue",
        },
    )
    assert blocked.status_code == 200
    blocked_id = str(blocked.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    blocked_operation = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "queue blocker",
            "mission_id": blocked_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert blocked_operation.status_code == 200
    blocked_operation_id = str(blocked_operation.json()["operation_id"])

    blocked_run = client.post(f"/operations/{blocked_operation_id}/run", json={"worker_id": "test.missions.queue"})
    assert blocked_run.status_code == 200
    assert blocked_run.json()["status"] == "blocked"

    run_once = client.post(
        "/missions/run_once", json={"actor": "test.missions.queue", "note": "queue reconcile", "limit": 10}
    )
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is True
    assert run_once_body["processed"] >= 2
    assert run_once_body["advanced"] == 1
    assert run_once_body["counts"]["blocked"] >= 1
    assert run_once_body["counts"]["queued"] >= 1
    results = run_once_body["results"]
    blocked_result = next(item for item in results if item["mission_id"] == blocked_id)
    assert blocked_result["applied"] is False
    assert blocked_result["action"] == "raise_trust_or_reduce_risk"
    ready_result = next(item for item in results if item["mission_id"] == ready_id)
    assert ready_result["applied"] is True
    assert ready_result["action"] == "create_first_operation"
    assert ready_result["operation_id"]
    queue_items = run_once_body["items"]
    assert queue_items[0]["id"] == blocked_id
    assert queue_items[0]["recommended_action"] == "raise_trust_or_reduce_risk"
    assert queue_items[0]["action_target_id"] == blocked_operation_id
    ready_item = next(item for item in queue_items if item["id"] == ready_id)
    assert ready_item["recommended_action"] == "run_linked_operation"
    assert ready_item["linked_task_count"] == 1
    assert ready_item["last_advance_action"] == "create_first_operation"


def test_mission_run_once_executes_linked_queued_operation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Run the linked queued operation",
            "summary": "Queue runner should execute the linked task in one bounded pass.",
            "requester_id": "test.missions.queue",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "run_once linked operation",
            "mission_id": mission_id,
            "input": {"goal": "Create a queued plan for the queue runner"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is True
    assert run_once_body["advanced"] == 1
    results = run_once_body["results"]
    mission_result = next(item for item in results if item["mission_id"] == mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "run_linked_operation"
    assert mission_result["operation_id"] == operation_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "run_linked_operation"
    assert fetched_body["mission"]["meta"]["last_advance_outcome"] == "succeeded"


def test_mission_store_run_once_uses_bounded_runtime_path(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions import run_queue_once as mission_run_queue_once

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Store queue runner should create bounded progress",
            "summary": "Top-level mission runner should use the same safe queue behavior as the API route.",
            "requester_id": "test.missions.store",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    result = mission_run_queue_once(limit=10, actor="test.missions.store", note="store queue run")
    assert result["ok"] is True
    assert result["advanced"] == 1
    mission_result = next(item for item in result["results"] if item["mission_id"] == mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "create_first_operation"
    assert mission_result["operation_id"]

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "create_first_operation"


def test_mission_advance_creates_first_operation_with_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Build the first mission plan",
            "summary": "Mission needs its first linked operation.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "note": "spawn first linked run"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "create_first_operation"
    operation_id = str(advanced_body["operation_id"])
    assert operation_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["linked_task_ids"] == [operation_id]
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "create_first_operation"
    assert fetched_body["mission"]["meta"]["last_advance_operation_id"] == operation_id
    history_events = [item for item in fetched_body["history"] if item.get("event") == "advance_receipt"]
    assert history_events
    assert history_events[-1]["details"]["applied"] is True


def test_mission_advance_runs_linked_queued_operation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Advance a queued linked operation",
            "summary": "Mission runner should execute the queued linked task.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "advance linked run",
            "mission_id": mission_id,
            "input": {"goal": "Create a linked queued plan"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "run_linked_operation"
    assert advanced_body["operation_id"] == operation_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "run_linked_operation"
    advance_events = [item for item in fetched_body["history"] if item.get("event") == "advance_receipt"]
    assert advance_events
    assert advance_events[-1]["details"]["operation_id"] == operation_id


def test_mission_advance_respects_governance_blockers(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission should not auto-advance",
            "summary": "Mission runner must not bypass governance.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "blocked advance",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.advance"})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is False
    assert advanced_body["action"] == "raise_trust_or_reduce_risk"
    assert advanced_body["operation_id"] == operation_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_advance_outcome"] == "requires_operator"


def test_mission_advance_surfaces_approval_handoff_for_governed_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Approval-bound mission should surface exact handoff",
            "summary": "Mission advance should return the approval needed for the next step.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post("/trust/set", json={"level": 6, "reason": "mission-advance-approval-handoff"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "approval-bound advance",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "run_linked_operation"
    assert advanced_body["operation_id"] == operation_id
    assert advanced_body["status"] == "queued"
    assert advanced_body["approval_id"]
    assert advanced_body["gate"] == "approvals_gate"
    assert advanced_body["next_step"] == "review_pending_approval"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "approvals_gate"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] in {"pending", "needs_approval"}


def test_mission_run_once_surfaces_approval_handoff_for_governed_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Queue runner should surface approval handoff",
            "summary": "Bounded queue run should return approval ids for governed next steps.",
            "requester_id": "test.missions.queue",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post("/trust/set", json={"level": 6, "reason": "mission-run-once-approval-handoff"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "approval-bound queue runner",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is True
    mission_result = next(item for item in run_once_body["results"] if item["mission_id"] == mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "run_linked_operation"
    assert mission_result["operation_id"] == operation_id
    assert mission_result["status"] == "queued"
    assert mission_result["approval_id"]
    assert mission_result["gate"] == "approvals_gate"
    assert mission_result["next_step"] == "review_pending_approval"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "approvals_gate"
