from __future__ import annotations

from pathlib import Path


def _client(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    return TestClient(create_app()), data_root


def test_lens_os_binding_authority_grant_requires_approved_request(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    request_response = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request governed OS-binding authority",
        },
    )
    assert request_response.status_code == 200
    request_body = request_response.json()
    approval_id = request_body["approval_id"]

    blocked_grant = client.post(
        "/lens/os-binding/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "try before approval",
        },
    )
    assert blocked_grant.status_code == 200
    blocked_body = blocked_grant.json()
    assert blocked_body["kind"] == "lens.os_binding.command_palette_binding_authority.grant_denial"
    assert blocked_body["status"] == "blocked"
    assert blocked_body["authority_granted"] is False
    assert blocked_body["os_level_command_palette_binding_authority"] is False
    assert blocked_body["applied"] is False
    assert blocked_body["executed"] is False
    assert blocked_body["receipt_written"] is False
    assert "os_binding_authority_approval_not_approved" in blocked_body["blockers"]
    assert blocked_body["governance"]["execution_authority"] is False
    assert blocked_body["governance"]["approval_decision_authority"] is False
    assert blocked_body["governance"]["memory_write"] is False
    assert blocked_body["governance"]["hotkey_registration_authority"] is False
    assert blocked_body["governance"]["summon_authority"] is False

    grants_before = client.get("/lens/os-binding/authority/grants?limit=10").json()
    assert grants_before["kind"] == "lens.os_binding.command_palette_binding_authority.grant_receipts"
    assert grants_before["status"] == "empty"
    assert grants_before["authority_granted"] is False
    assert grants_before["items"] == []
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_authority_grant_writes_receipt_without_binding(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    request_response = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request governed OS-binding authority",
        },
    )
    assert request_response.status_code == 200
    approval_id = request_response.json()["approval_id"]

    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "allow bounded authority grant receipt",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    grant = client.post(
        "/lens/os-binding/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "grant OS-binding authority receipt only",
            "lease_seconds": 120,
        },
    )
    assert grant.status_code == 200
    body = grant.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding_authority.grant"
    assert body["status"] == "authority_granted"
    assert body["approval_id"] == approval_id
    assert body["authority_granted"] is True
    assert body["os_level_command_palette_binding_authority"] is True
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["opens_palette"] is False
    assert body["registers_hotkey"] is False
    assert body["launches_process"] is False
    assert body["controls_overlay"] is False
    assert body["applied"] is True
    assert body["executed"] is False
    assert body["receipt_written"] is True
    assert body["grant"]["grant_receipt_written"] is True
    receipt = body["receipt"]
    assert receipt["kind"] == "lens.os_binding.command_palette_binding_authority.grant_receipt"
    assert receipt["approval_id"] == approval_id
    assert receipt["authority_granted"] is True
    assert receipt["os_level_command_palette_binding_authority"] is True
    assert receipt["os_level_command_palette"] is False
    assert receipt["summon_anywhere"] is False
    assert receipt["opens_palette"] is False
    assert receipt["registers_hotkey"] is False
    assert receipt["launches_process"] is False
    assert receipt["controls_overlay"] is False
    assert receipt["lease_seconds"] == 120
    governance = body["governance"]
    assert governance["authority_grant_boundary"] is True
    assert governance["authority_granted"] is True
    assert governance["os_level_command_palette_binding_authority"] is True
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["resident_claim_authority"] is False
    assert governance["mutation_authority_granted"] is False

    grants = client.get("/lens/os-binding/authority/grants?limit=10").json()
    assert grants["status"] == "readback_ready"
    assert grants["authority_granted"] is True
    assert grants["os_level_command_palette_binding_authority"] is True
    assert grants["active_latest"]["receipt_id"] == receipt["receipt_id"]
    assert grants["items"][0]["receipt_id"] == receipt["receipt_id"]
    assert grants["opens_palette"] is False
    assert grants["registers_hotkey"] is False
    assert grants["launches_process"] is False
    assert grants["controls_overlay"] is False

    readback = client.get("/lens/os-binding/authority/requests?limit=10").json()
    assert readback["status"] == "authority_granted"
    assert readback["active_grant_receipt_id"] == receipt["receipt_id"]
    assert readback["authority_granted"] is True
    assert readback["os_level_command_palette_binding_authority"] is True
    assert readback["os_level_command_palette"] is False
    assert readback["summon_anywhere"] is False
    assert readback["opens_palette"] is False
    assert readback["registers_hotkey"] is False
    assert readback["launches_process"] is False
    assert readback["controls_overlay"] is False

    plan = client.get("/lens/os-binding/plan").json()
    assert plan["kind"] == "lens.os_binding.implementation_plan"
    assert plan["status"] == "blocked"
    assert plan["authority_granted"] is True
    assert plan["os_level_command_palette_binding_authority"] is True
    assert plan["active_grant_receipt_id"] == receipt["receipt_id"]
    assert plan["authority_grant_consumed"] is True
    assert plan["os_level_command_palette"] is False
    assert plan["summon_anywhere"] is False
    assert plan["plan"]["would_open_palette"] is False
    assert plan["plan"]["would_register_hotkey"] is False
    assert plan["plan"]["would_summon"] is False
    assert plan["plan"]["would_launch_process"] is False
    assert plan["plan"]["would_write_memory"] is False
    assert plan["authority_request_readback"]["active_grant_receipt_id"] == receipt["receipt_id"]
    assert plan["command_palette_contract"]["readback_ready"] is True
    assert plan["command_palette_contract"]["authority_granted"] is True
    assert plan["command_palette_contract"]["active_grant_receipt_id"] == receipt["receipt_id"]
    assert plan["command_palette_contract"]["os_level_command_palette"] is False
    steps = {item["id"]: item for item in plan["plan"]["steps"]}
    palette_step = steps["os_level_command_palette_contract"]
    assert palette_step["ready"] is False
    assert palette_step["readback_ready"] is True
    assert palette_step["authority_required"] == "os_level_command_palette_binding_authority"
    assert palette_step["authority_granted"] is True
    assert palette_step["active_grant_receipt_id"] == receipt["receipt_id"]
    assert palette_step["bridge_script"] == "scripts/lens-command-palette.ps1"
    assert "os_level_command_palette_missing" in palette_step["blockers"]

    readiness = client.get("/lens/os-binding/readiness").json()
    authority_readback = readiness["authority_request_readback"]
    assert authority_readback["status"] == "authority_granted"
    assert authority_readback["active_grant_receipt_id"] == receipt["receipt_id"]
    assert authority_readback["authority_granted"] is True
    assert authority_readback["os_level_command_palette_binding_authority"] is True
    assert readiness["authority_granted"] is True
    assert readiness["os_level_command_palette_binding_authority"] is True
    assert readiness["active_grant_receipt_id"] == receipt["receipt_id"]
    assert readiness["authority_grant_consumed"] is True
    assert readiness["status"] == "blocked"
    assert readiness["ready"] is False
    assert readiness["os_level_command_palette"] is False
    assert readiness["summon_anywhere"] is False
    assert readiness["command_palette_contract"]["readback_ready"] is True
    assert readiness["command_palette_contract"]["authority_granted"] is True
    assert readiness["command_palette_contract"]["active_grant_receipt_id"] == receipt["receipt_id"]
    requirements = {item["id"]: item for item in readiness["requirements"]}
    assert requirements["authority_request_readback"]["authority_granted"] is True
    assert requirements["authority_request_readback"]["active_grant_receipt_id"] == receipt["receipt_id"]
    assert requirements["os_level_command_palette"]["authority_granted"] is True
    assert requirements["os_level_command_palette"]["active_grant_receipt_id"] == receipt["receipt_id"]
    assert requirements["os_level_command_palette"]["ready"] is False
    assert requirements["os_level_command_palette"]["readback_ready"] is True
    assert readiness["implementation_plan"]["authority_granted"] is True
    assert readiness["implementation_plan"]["active_grant_receipt_id"] == receipt["receipt_id"]
    assert readiness["implementation_plan"]["authority_grant_consumed"] is True
    assert readiness["implementation_plan"]["command_palette_contract"]["readback_ready"] is True

    status = client.get("/lens/status?limit=10").json()
    os_binding_criterion = next(
        item for item in status["stage6_readiness"]["criteria"] if item["id"] == "os_binding_readiness"
    )
    assert os_binding_criterion["authority_granted"] is True
    assert os_binding_criterion["os_level_command_palette_binding_authority"] is True
    assert os_binding_criterion["authority_grants_route"] == "/lens/os-binding/authority/grants"
    assert os_binding_criterion["active_grant_receipt_id"] == receipt["receipt_id"]
    assert os_binding_criterion["authority_grant_consumed"] is True
    assert os_binding_criterion["os_level_command_palette"] is False
    assert os_binding_criterion["summon_anywhere"] is False

    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_execution_denial_writes_receipt_after_authority_grant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    request_response = client.post(
        "/lens/os-binding/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request governed OS-binding authority",
        },
    )
    assert request_response.status_code == 200
    approval_id = request_response.json()["approval_id"]

    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "allow bounded authority grant receipt",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    grant = client.post(
        "/lens/os-binding/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "grant OS-binding authority receipt only",
            "lease_seconds": 120,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    grant_receipt_id = grant_body["receipt"]["receipt_id"]

    execute = client.post(
        "/lens/os-binding/execute",
        json={
            "actor": "test.system.write",
            "reason": "attempt OS palette binding after grant",
        },
    )

    assert execute.status_code == 200
    body = execute.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding.execution_denial"
    assert body["status"] == "denied_no_os_binding_execution_boundary"
    assert body["route"] == "/lens/os-binding/execute"
    assert body["receipt_route"] == "/lens/os-binding/denials"
    assert body["execution_readiness_route"] == "/lens/os-binding/execution/readiness"
    assert body["plan"]["execute_route"] == "/lens/os-binding/execute"
    assert body["plan"]["denials_route"] == "/lens/os-binding/denials"
    assert body["readiness"]["execute_route"] == "/lens/os-binding/execute"
    assert body["readiness"]["denials_route"] == "/lens/os-binding/denials"
    assert body["approval_id"] == approval_id
    assert body["active_grant_receipt_id"] == grant_receipt_id
    assert body["authority_granted"] is True
    assert body["os_level_command_palette_binding_authority"] is True
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["opens_palette"] is False
    assert body["registers_hotkey"] is False
    assert body["launches_process"] is False
    assert body["controls_overlay"] is False
    assert body["applied"] is False
    assert body["executed"] is False
    assert body["receipt_written"] is True
    assert body["denial"]["denial_receipt_written"] is True
    assert body["denial"]["would_open_palette"] is False
    assert body["denial"]["would_register_hotkey"] is False
    assert body["denial"]["would_summon"] is False
    assert body["denial"]["would_launch_process"] is False
    assert body["denial"]["would_control_overlay"] is False
    assert body["denial"]["would_write_memory"] is False
    assert body["denial"]["would_decide_approval"] is False
    assert body["denial"]["would_claim_resident"] is False
    assert "os_binding_execution_boundary_not_implemented" in body["blockers"]
    assert "hotkey_registration_authority_not_granted" in body["blockers"]
    assert "summon_authority_not_granted" in body["blockers"]
    assert body["governance"]["gate"] == "lens_os_binding_command_palette_execution_denial"
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_decision_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["hotkey_registration_authority"] is False
    assert body["governance"]["summon_authority"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert body["governance"]["denial_receipt_write_authority"] is True

    receipt = body["receipt"]
    assert receipt["kind"] == "lens.os_binding.command_palette_binding.denial.receipt"
    assert receipt["status"] == "denied_no_os_binding_execution_boundary"
    assert receipt["approval_id"] == approval_id
    assert receipt["active_grant_receipt_id"] == grant_receipt_id
    assert receipt["execution"]["would_register_hotkey"] is False
    assert receipt["execution"]["would_summon"] is False
    assert receipt["governance"]["denial_receipt_write_authority"] is True
    assert receipt["governance"]["execution_authority"] is False
    assert receipt["governance"]["memory_write"] is False

    denials = client.get(f"/lens/os-binding/denials?limit=10&approval_id={approval_id}")
    assert denials.status_code == 200
    denials_body = denials.json()
    assert denials_body["kind"] == "lens.os_binding.command_palette_binding.denial_receipts"
    assert denials_body["status"] == "readback_ready"
    assert denials_body["route"] == "/lens/os-binding/denials"
    assert denials_body["execute_route"] == "/lens/os-binding/execute"
    assert denials_body["plan_route"] == "/lens/os-binding/plan"
    assert denials_body["readiness_route"] == "/lens/os-binding/readiness"
    assert denials_body["authority_route"] == "/lens/os-binding/authority"
    assert denials_body["grants_route"] == "/lens/os-binding/authority/grants"
    assert denials_body["execution_readiness_route"] == "/lens/os-binding/execution/readiness"
    assert denials_body["approval_id"] == approval_id
    assert denials_body["total"] == 1
    assert denials_body["latest"]["receipt_id"] == receipt["receipt_id"]
    assert denials_body["items"][0]["active_grant_receipt_id"] == grant_receipt_id
    assert denials_body["governance"]["read_only_contract"] is True
    assert denials_body["governance"]["denial_receipt_write_authority"] is False
    assert denials_body["governance"]["execution_authority"] is False
    assert denials_body["governance"]["approval_decision_authority"] is False
    assert denials_body["governance"]["memory_write"] is False

    readiness_response = client.get(
        "/lens/os-binding/execution/readiness?limit=10&actor=test.system.write",
    )
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()
    assert readiness["kind"] == "lens.os_binding.command_palette_binding.execution_readiness"
    assert readiness["status"] == "blocked"
    assert readiness["route"] == "/lens/os-binding/execution/readiness"
    assert readiness["execute_route"] == "/lens/os-binding/execute"
    assert readiness["denials_route"] == "/lens/os-binding/denials"
    assert readiness["plan_route"] == "/lens/os-binding/plan"
    assert readiness["readiness_route"] == "/lens/os-binding/readiness"
    assert readiness["authority_route"] == "/lens/os-binding/authority"
    assert readiness["authority_grants_route"] == "/lens/os-binding/authority/grants"
    assert readiness["ready"] is False
    assert readiness["execution_ready"] is False
    assert readiness["permission_allowed"] is True
    assert readiness["authority_granted"] is True
    assert readiness["os_level_command_palette_binding_authority"] is True
    assert readiness["active_grant_receipt_id"] == grant_receipt_id
    assert readiness["denial_boundary_observed"] is True
    assert readiness["denial_status"] == "denied_no_os_binding_execution_boundary"
    assert readiness["denial_receipt_readback_ready"] is True
    assert readiness["denial_receipt_total"] == 1
    assert readiness["latest_denial_receipt_id"] == receipt["receipt_id"]
    requirements = {item["id"]: item for item in readiness["requirements"]}
    assert requirements["system_write_permission"]["ready"] is True
    assert requirements["os_binding_authority_grant"]["ready"] is True
    assert requirements["os_binding_execution_denial_boundary"]["ready"] is True
    assert requirements["os_binding_denial_receipts"]["ready"] is True
    assert requirements["global_hotkey_binding"]["ready"] is False
    assert requirements["summon_binding"]["ready"] is False
    assert requirements["resident_host"]["ready"] is False
    assert requirements["tray_presence"]["ready"] is False
    assert requirements["overlay_window"]["ready"] is False
    assert "global_hotkey_binding" in readiness["blocked_requirements"]
    assert "summon_binding" in readiness["blocked_requirements"]
    assert "os_binding_execution_boundary_not_implemented" in readiness["blockers"]
    assert readiness["execution_denial"]["receipt_written"] is False
    assert readiness["denial_receipts"]["total"] == 1
    assert readiness["governance"]["gate"] == "lens_os_binding_command_palette_execution_readiness_audit"
    assert readiness["governance"]["read_only_contract"] is True
    assert readiness["governance"]["execution_authority"] is False
    assert readiness["governance"]["approval_decision_authority"] is False
    assert readiness["governance"]["memory_write"] is False
    assert readiness["governance"]["hotkey_registration_authority"] is False
    assert readiness["governance"]["summon_authority"] is False
    assert readiness["governance"]["denial_receipt_write_authority"] is False
    assert readiness["governance"]["mutation_authority_granted"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()
