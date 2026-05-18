from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterator

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_plan(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-stage6-prerequisite-bringup-plan.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )


def _run_lens_runtime_script(script_name: str, *args: str) -> None:
    subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / script_name),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _service_config_args(service_config_path: Path | None) -> tuple[str, ...]:
    if service_config_path is None:
        return ()
    return ("-ServiceConfigPath", str(service_config_path))


def _set_stage6_env(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    *,
    service_config_path: Path | None = None,
) -> None:
    monkeypatch.setenv("FRANCIS_ROOT", str(_repo_root()))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")
    if service_config_path is None:
        monkeypatch.delenv("FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH", raising=False)
    else:
        monkeypatch.setenv("FRANCIS_LENS_HOST_SERVICE_CONFIG_PATH", str(service_config_path.resolve()))


def _status_payload(
    data_dir: Path,
    *,
    service_config_path: Path | None = None,
) -> dict[str, Any]:
    proc = _run_plan("-Mode", "Status", "-DataDir", str(data_dir), *_service_config_args(service_config_path))
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def _assert_actor_scope_policy_contract(
    readiness: dict[str, Any],
    *,
    scope_required: bool,
) -> None:
    contract = readiness["actor_scope_policy_contract"]
    assert contract["env_var"] == "FRANCIS_API_ACTOR_SCOPES"
    assert contract["json_shape"] == {"<actor>": ["system.write"]}
    assert contract["required_scope"] == ("system.write" if scope_required else "")
    assert contract["actor_placeholder"] == "<actor>"
    assert contract["scope_required"] is scope_required
    assert contract["powershell_example"] == ('$env:FRANCIS_API_ACTOR_SCOPES = \'{"<actor>":["system.write"]}\'')


def _expected_approval_request_powershell(route: str) -> str:
    return (
        "$body = @{ actor = '<actor>'; reason = '<reason>' } | ConvertTo-Json -Compress; "
        + "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000"
        + route
        + "' -ContentType 'application/json' -Body $body"
    )


def _assert_approval_request_contract(
    action: dict[str, Any],
    *,
    action_id: str,
    route: str,
    approval_action: str,
) -> None:
    assert action["approval_request_contract"] == {
        "route": route,
        "method": "POST",
        "action_id": action_id,
        "approval_action": approval_action,
        "payload_shape": {
            "actor": "<actor>",
            "reason": "<reason>",
        },
        "required_scope": "system.write",
        "actor_scope_policy_contract": {
            "env_var": "FRANCIS_API_ACTOR_SCOPES",
            "json_shape": {"<actor>": ["system.write"]},
            "required_scope": "system.write",
            "actor_placeholder": "<actor>",
            "scope_required": True,
            "powershell_example": '$env:FRANCIS_API_ACTOR_SCOPES = \'{"<actor>":["system.write"]}\'',
        },
        "creates": "approval_request",
        "would_request_approval": False,
        "would_grant_authority": False,
        "would_execute": False,
        "would_mutate_runtime": False,
    }


def _assert_approval_request_command(
    command: dict[str, Any],
    *,
    route: str,
) -> None:
    assert command == {
        "command": _expected_approval_request_powershell(route),
        "route": route,
        "method": "POST",
        "api_base_url": "http://127.0.0.1:8000",
        "payload_shape": {
            "actor": "<actor>",
            "reason": "<reason>",
        },
        "required_scope": "system.write",
        "requires_running_api": True,
        "requires_operator_actor": True,
        "would_request_approval_if_run": True,
        "status_readback_would_request_approval": False,
    }


def _assert_approval_decision_contract(
    action: dict[str, Any],
    *,
    approval_id: str,
) -> None:
    contract = action["approval_decision_contract"]
    assert contract["route"] == "/approvals/decision"
    assert contract["method"] == "POST"
    assert contract["payload_shape"] == {
        "id": approval_id,
        "action": "approve",
        "comment": "<comment>",
        "actor": "<actor>",
    }
    assert contract["allowed_actions"] == ["approve", "reject", "emergency"]
    assert contract["required_scope"] == "approvals.decide"
    assert contract["actor_scope_policy_contract"] == {
        "env_var": "FRANCIS_API_ACTOR_SCOPES",
        "json_shape": {"<actor>": ["approvals.decide"]},
        "required_scope": "approvals.decide",
        "actor_placeholder": "<actor>",
        "scope_required": True,
        "powershell_example": '$env:FRANCIS_API_ACTOR_SCOPES = \'{"<actor>":["approvals.decide"]}\'',
    }
    assert contract["local_caller_required_unless_remote_enabled"] is True
    assert contract["remote_enable_env_var"] == "FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS"
    assert contract["would_decide_approval"] is False


def _expected_approval_decision_powershell(approval_id: str) -> str:
    return (
        "$body = @{ id = '"
        + approval_id
        + "'; action = 'approve'; comment = '<comment>'; actor = '<actor>' } | ConvertTo-Json -Compress; "
        + "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/approvals/decision' "
        + "-ContentType 'application/json' -Body $body"
    )


def _assert_approval_decision_command(
    command: dict[str, Any],
    *,
    approval_id: str,
) -> None:
    assert command == {
        "command": _expected_approval_decision_powershell(approval_id),
        "route": "/approvals/decision",
        "method": "POST",
        "api_base_url": "http://127.0.0.1:8000",
        "payload_shape": {
            "id": approval_id,
            "action": "approve",
            "comment": "<comment>",
            "actor": "<actor>",
        },
        "required_scope": "approvals.decide",
        "requires_running_api": True,
        "requires_local_caller_unless_remote_enabled": True,
        "remote_enable_env_var": "FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS",
        "requires_operator_actor": True,
        "would_decide_approval_if_run": True,
        "status_readback_would_decide_approval": False,
    }


def _wait_for_next_action(
    data_dir: Path,
    *,
    requirement: str,
    action_id: str,
    service_config_path: Path | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for _ in range(20):
        payload = _status_payload(data_dir, service_config_path=service_config_path)
        if (
            payload["next_operator_action_requirement"] == requirement
            and payload["next_operator_action"]["id"] == action_id
        ):
            return payload
        time.sleep(0.5)
    assert payload["next_operator_action_requirement"] == requirement
    assert payload["next_operator_action"]["id"] == action_id
    return payload


@pytest.fixture(autouse=True)
def _cleanup_stage6_temp_runtimes(tmp_path: Path) -> Iterator[None]:
    yield

    data_dir = tmp_path / "data"
    if not data_dir.exists():
        return
    for script_name, mode in (
        ("lens-hotkey-binding.ps1", "Stop"),
        ("lens-tray-presence.ps1", "Stop"),
        ("lens-overlay-window.ps1", "Stop"),
        ("lens-host-supervisor.ps1", "StopResident"),
    ):
        _run_lens_runtime_script(script_name, "-Mode", mode, "-DataDir", str(data_dir))


def test_lens_stage6_prerequisite_bringup_plan_has_confirmed_request_and_grant_boundaries() -> None:
    script = (_repo_root() / "scripts" / "lens-stage6-prerequisite-bringup-plan.ps1").read_text(encoding="utf-8")

    assert "[ValidateSet('Status', 'RequestNext', 'GrantNext', 'ExecuteNext')]" in script
    assert "[switch]$ConfirmRequest" in script
    assert "[switch]$ConfirmGrant" in script
    assert "[switch]$ConfirmExecute" in script
    assert "[string]$ApprovalId" in script
    assert "[int]$RunSeconds" in script
    assert "refused_confirmation_required" in script
    assert "request_lens_resident_runtime_execution_authority" in script
    assert "grant_lens_resident_runtime_execution_authority" in script
    assert "execute_lens_resident_runtime_activation" in script
    assert "request_lens_host_supervision_authority" in script
    assert "grant_lens_host_supervision_authority" in script
    assert "request_lens_tray_authority" in script
    assert "grant_lens_tray_authority" in script
    assert "execute_lens_tray_presence" in script
    assert "request_lens_os_binding_authority" in script
    assert "grant_lens_os_binding_authority" in script
    assert "execute_lens_os_binding" in script
    assert "request_lens_overlay_authority" in script
    assert "grant_lens_overlay_authority" in script
    assert "execute_lens_overlay_window" in script
    assert "request_lens_summon_authority" in script
    assert "grant_lens_summon_authority" in script
    assert "execute_lens_summon_action" in script
    assert 'run_mode_available": False' in script
    assert 'request_next_mode_available": True' in script
    assert 'grant_next_mode_available": True' in script
    assert 'execute_next_mode_available": True' in script
    assert 'would_execute": False' in script
    assert 'would_mutate": False' in script
    assert "execute_supervised_resident_host_start" in script
    assert "apply_persistent_supervision_enablement" in script


def test_lens_stage6_prerequisite_bringup_plan_projects_ordered_governed_sequence(
    tmp_path: Path,
) -> None:
    proc = _run_plan("-Mode", "Status", "-DataDir", str(tmp_path / "data"))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)

    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["status"] == "blocked"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "system_resident_presence"
    assert payload["persistent_supervision_next_smallest_truthful_gap"] in {
        "persistent_supervision_authority_not_granted",
        "persistent_supervision_required_prerequisites_missing",
    }
    assert payload["current_truthful_gap"] == "persistent_supervision_required_prerequisites_missing"
    assert payload["current_truthful_gap_basis"] == "missing_required_before_enable"
    assert payload["current_first_missing_requirement"] == "resident_host_process"
    assert payload["current_first_missing_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["raw_persistent_supervision_next_smallest_truthful_gap"] in {
        "persistent_supervision_authority_not_granted",
        "persistent_supervision_required_prerequisites_missing",
    }

    expected = [
        "resident_host_process",
        "tray_presence",
        "global_hotkey_binding",
        "overlay_window",
        "summon_binding",
    ]
    assert payload["required_before_enable"] == expected
    assert payload["missing_required_before_enable"] == expected
    assert payload["required_before_enable_ready"] is False
    assert payload["first_missing_required_before_enable"] == "resident_host_process"

    handoff = payload["first_missing_requirement_handoff"]
    assert handoff["id"] == "resident_host_process"
    assert handoff["route"] == "/lens/host"
    assert handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert handoff["read_only_contract"] is True
    assert handoff["diagnostic_only"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_mutate"] is False

    steps = {step["id"]: step for step in payload["ordered_prerequisite_steps"]}
    assert list(steps) == expected
    assert steps["resident_host_process"]["actions"][0]["id"] == ("request_resident_runtime_execution_authority")
    assert steps["resident_host_process"]["actions"][0]["route"] == ("/lens/resident-runtime/authority-grant/request")
    _assert_approval_request_contract(
        steps["resident_host_process"]["actions"][0],
        action_id="request_resident_runtime_execution_authority",
        route="/lens/resident-runtime/authority-grant/request",
        approval_action="lens.resident_runtime.execution_authority",
    )
    _assert_approval_request_command(
        steps["resident_host_process"]["actions"][0]["approval_request_command"],
        route="/lens/resident-runtime/authority-grant/request",
    )
    assert steps["resident_host_process"]["actions"][2]["route"] == ("/lens/host/supervision/authority/request")
    assert steps["resident_host_process"]["actions"][-1]["route"] == "/lens/resident-runtime/execute"
    assert steps["resident_host_process"]["actions"][-1]["mode"] == "resident_start"

    assert steps["tray_presence"]["actions"][0]["route"] == "/lens/tray/authority/request"
    assert steps["tray_presence"]["actions"][-1]["route"] == "/lens/tray/execute"
    assert steps["global_hotkey_binding"]["actions"][0]["route"] == "/lens/os-binding/authority/request"
    assert steps["global_hotkey_binding"]["actions"][-1]["route"] == "/lens/os-binding/execute"
    assert steps["global_hotkey_binding"]["actions"][-1]["mode"] == "bind"
    assert steps["overlay_window"]["actions"][0]["route"] == "/lens/overlay/authority/request"
    assert steps["overlay_window"]["actions"][-1]["route"] == "/lens/overlay/execute"
    assert steps["summon_binding"]["actions"][0]["route"] == "/lens/summon/authority/request"
    assert steps["summon_binding"]["actions"][0]["approval_action"] == "lens.summon.action_authority"
    assert steps["summon_binding"]["actions"][-1]["route"] == "/lens/summon/execute"

    enablement_steps = payload["persistent_supervision_enablement_steps"]
    assert [step["id"] for step in enablement_steps] == [
        "request_persistent_supervision_enablement_authority",
        "grant_persistent_supervision_enablement_authority",
        "request_persistent_supervision_execution_authority",
        "grant_persistent_supervision_execution_authority",
        "apply_persistent_supervision_enablement",
    ]
    assert enablement_steps[-1]["route"] == "/lens/host/persistent-supervision/enablement/execution/apply"
    assert payload["next_operator_action_requirement"] == "resident_host_process"
    assert payload["next_operator_action"]["route"] == "/lens/resident-runtime/authority-grant/request"
    _assert_approval_request_contract(
        payload["next_operator_action"],
        action_id="request_resident_runtime_execution_authority",
        route="/lens/resident-runtime/authority-grant/request",
        approval_action="lens.resident_runtime.execution_authority",
    )
    _assert_approval_request_command(
        payload["next_operator_action"]["approval_request_command"],
        route="/lens/resident-runtime/authority-grant/request",
    )
    assert payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest"
        ),
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": payload["next_operator_action"]["approval_request_command"],
    }
    first_operator_command = payload["operator_sequence"][0]["operator_command"]
    for key, value in payload["next_operator_command"].items():
        assert first_operator_command[key] == value
    assert first_operator_command["available_now"] is True
    assert first_operator_command["preview_only"] is False
    assert first_operator_command["availability_reason"] == "current_next_operator_action"
    assert all("operator_command" in item for item in payload["operator_sequence"])
    assert all(item["operator_command"]["requires_confirmation"] is True for item in payload["operator_sequence"])
    assert all(item["operator_command"]["available_now"] is False for item in payload["operator_sequence"][1:])
    assert all(item["operator_command"]["preview_only"] is True for item in payload["operator_sequence"][1:])
    assert payload["operator_sequence_command_availability"] == {
        "available_now_count": 1,
        "preview_only_count": len(payload["operator_sequence"]) - 1,
        "sequence_length": len(payload["operator_sequence"]),
        "truthful": True,
    }
    actor_readiness = payload["next_operator_actor_scope_readiness"]
    assert actor_readiness["ready"] is False
    assert actor_readiness["allowed"] is False
    assert actor_readiness["reason"] == "actor_not_supplied"
    assert actor_readiness["actor_present"] is False
    assert actor_readiness["configured_actor_scope_policy"] is True
    assert actor_readiness["scope_required"] is True
    assert actor_readiness["required_scope"] == "system.write"
    assert actor_readiness["route"] == "/lens/resident-runtime/authority-grant/request"
    assert actor_readiness["method"] == "POST"
    assert actor_readiness["action_id"] == "request_resident_runtime_execution_authority"
    assert actor_readiness["operator_must_supply_actor"] is True
    _assert_actor_scope_policy_contract(actor_readiness, scope_required=True)
    assert all(item["script_would_execute"] is False for item in payload["operator_sequence"])
    assert all(item["script_would_mutate"] is False for item in payload["operator_sequence"])

    checks = {item["id"]: item for item in payload["checks"]}
    assert all(item["passed"] for item in checks.values())
    assert checks["operator_sequence_complete"]["status"] == "complete"
    assert checks["operator_sequence_command_availability"]["status"] == "truthful"
    assert checks["next_operator_actor_scope_readiness"]["status"] == "actor_not_supplied"
    assert checks["script_side_effects_denied"]["status"] == "readback_only"

    governance = payload["governance"]
    assert governance["read_only_contract"] is True
    assert governance["plan_only"] is True
    assert governance["requires_explicit_operator_execution"] is True
    assert governance["request_next_mode_available"] is True
    assert governance["grant_next_mode_available"] is True
    assert governance["execute_next_mode_available"] is True
    assert governance["run_mode_available"] is False
    assert governance["actor_scope_readback"] is True
    assert governance["next_operator_actor_ready"] is False
    assert governance["operator_actor_required"] is True
    assert governance["would_request_authority"] is False
    assert governance["would_grant_authority"] is False
    assert governance["authority_granted"] is False
    assert governance["would_execute"] is False
    assert governance["would_mutate"] is False
    assert governance["execution_authority"] is False
    assert governance["approval_decision_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["process_supervision_authority"] is False
    assert governance["service_control_authority"] is False
    assert governance["tray_registration_authority"] is False
    assert governance["hotkey_registration_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["memory_write"] is False
    assert governance["resident_claim_authority"] is False


def test_lens_stage6_prerequisite_bringup_plan_reports_actor_scope_readiness(
    tmp_path: Path,
) -> None:
    proc = _run_plan(
        "-Mode",
        "Status",
        "-DataDir",
        str(tmp_path / "data"),
        "-Actor",
        "test.system.write",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    readiness = payload["next_operator_actor_scope_readiness"]
    assert readiness["ready"] is True
    assert readiness["allowed"] is True
    assert readiness["reason"] == "ok"
    assert readiness["actor_present"] is True
    assert readiness["actor"] == "test.system.write"
    assert readiness["configured_actor_scope_policy"] is True
    assert readiness["scope_required"] is True
    assert readiness["required_scope"] == "system.write"
    assert readiness["route"] == "/lens/resident-runtime/authority-grant/request"
    assert readiness["method"] == "POST"
    assert readiness["action_id"] == "request_resident_runtime_execution_authority"
    assert readiness["operator_must_supply_actor"] is False
    _assert_actor_scope_policy_contract(readiness, scope_required=True)
    assert readiness["evidence"]["actor_scope_count"] >= 1
    assert readiness["evidence"]["scope_decision"]["missing_scope_count"] == 0

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["next_operator_actor_scope_readiness"]["status"] == "ready"
    assert checks["next_operator_actor_scope_readiness"]["passed"] is True
    assert payload["governance"]["actor_scope_readback"] is True
    assert payload["governance"]["next_operator_actor_ready"] is True
    assert payload["governance"]["operator_actor_required"] is False


def test_lens_stage6_prerequisite_bringup_request_next_requires_confirmation(
    tmp_path: Path,
) -> None:
    proc = _run_plan("-Mode", "RequestNext", "-DataDir", str(tmp_path / "data"), "-Actor", "test.system.write")

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["mode"] == "requestnext"
    assert payload["status"] == "refused_confirmation_required"
    assert payload["ok"] is False
    assert payload["request_result"] == {
        "ok": False,
        "status": "refused_confirmation_required",
        "approval_requested": False,
        "reason": "confirm_request_required",
    }
    assert payload["governance"]["would_request_authority"] is False
    assert payload["governance"]["would_grant_authority"] is False
    assert payload["governance"]["would_execute"] is False
    assert payload["governance"]["would_mutate"] is False


def test_lens_stage6_prerequisite_bringup_grant_next_requires_confirmation(
    tmp_path: Path,
) -> None:
    proc = _run_plan(
        "-Mode",
        "GrantNext",
        "-DataDir",
        str(tmp_path / "data"),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        "approval-does-not-matter-without-confirmation",
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["mode"] == "grantnext"
    assert payload["status"] == "refused_confirmation_required"
    assert payload["ok"] is False
    assert payload["grant_result"] == {
        "ok": False,
        "status": "refused_confirmation_required",
        "authority_granted": False,
        "receipt_written": False,
        "reason": "confirm_grant_required",
    }
    assert payload["governance"]["would_request_authority"] is False
    assert payload["governance"]["would_grant_authority"] is False
    assert payload["governance"]["authority_granted"] is False
    assert payload["governance"]["authority_grant_receipt_write"] is False
    assert payload["governance"]["would_execute"] is False
    assert payload["governance"]["would_mutate"] is False


def test_lens_stage6_prerequisite_bringup_execute_next_requires_confirmation(
    tmp_path: Path,
) -> None:
    proc = _run_plan(
        "-Mode",
        "ExecuteNext",
        "-DataDir",
        str(tmp_path / "data"),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        "approval-does-not-matter-without-confirmation",
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["mode"] == "executenext"
    assert payload["status"] == "refused_confirmation_required"
    assert payload["ok"] is False
    assert payload["execute_result"] == {
        "ok": False,
        "status": "refused_confirmation_required",
        "executed": False,
        "receipt_written": False,
        "reason": "confirm_execute_required",
    }
    assert payload["governance"]["would_request_authority"] is False
    assert payload["governance"]["would_grant_authority"] is False
    assert payload["governance"]["authority_granted"] is False
    assert payload["governance"]["execution_receipt_write"] is False
    assert payload["governance"]["would_execute"] is False
    assert payload["governance"]["would_mutate"] is False


def test_lens_stage6_prerequisite_bringup_request_next_creates_only_next_approval_request(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_plan(
        "-Mode",
        "RequestNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-Reason",
        "test request next prerequisite",
        "-ConfirmRequest",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["mode"] == "requestnext"
    assert payload["status"] == "approval_requested"
    assert payload["ok"] is True
    assert payload["next_operator_action_requirement"] == "resident_host_process"
    request_result = payload["request_result"]
    assert request_result["ok"] is True
    assert request_result["approval_requested"] is True
    assert request_result["action_id"] == "request_resident_runtime_execution_authority"
    assert request_result["route"] == "/lens/resident-runtime/authority-grant/request"
    assert request_result["approval_action"] == "lens.resident_runtime.execution_authority"
    assert request_result["approval_id"]
    assert request_result["result"]["applied"] is False
    assert request_result["result"]["executed"] is False
    assert request_result["governance"]["approval_request_write"] is True
    assert request_result["governance"]["approval_decision_authority"] is False
    assert request_result["governance"]["authority_grant"] is False
    assert request_result["governance"]["execution_authority"] is False
    assert request_result["governance"]["local_process_launch_authority"] is False
    assert request_result["governance"]["memory_write"] is False
    assert request_result["governance"]["resident_claim_authority"] is False
    governance = payload["governance"]
    assert governance["plan_only"] is False
    assert governance["read_only_contract"] is False
    assert governance["diagnostic_only"] is False
    assert governance["approval_request_write"] is True
    assert governance["would_request_authority"] is True
    assert governance["would_grant_authority"] is False
    assert governance["would_execute"] is False
    assert governance["would_mutate"] is False
    assert governance["mutation_authority_granted"] is True

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["next_operator_action_requirement"] == "resident_host_process"
    assert followup_payload["next_operator_action"]["id"] == ("await_resident_runtime_execution_authority_approval")
    assert followup_payload["next_operator_action"]["route"] == ("/lens/resident-runtime/authority-grant/requests")
    assert followup_payload["next_operator_action"]["approval_decision_required"] is True
    assert followup_payload["next_operator_action"]["pending_approval_count"] == 1
    assert followup_payload["next_operator_action"]["pending_approval_id"] == request_result["approval_id"]
    assert followup_payload["next_operator_action"]["decision_route"] == "/approvals/decision"
    assert followup_payload["next_operator_action"]["request_status"] == "pending_review"
    _assert_approval_decision_contract(
        followup_payload["next_operator_action"],
        approval_id=request_result["approval_id"],
    )
    _assert_approval_decision_command(
        followup_payload["next_operator_action"]["approval_decision_command"],
        approval_id=request_result["approval_id"],
    )
    followup_actor_readiness = followup_payload["next_operator_actor_scope_readiness"]
    assert followup_actor_readiness["ready"] is True
    assert followup_actor_readiness["allowed"] is True
    assert followup_actor_readiness["reason"] == "not_required"
    assert followup_actor_readiness["scope_required"] is False
    assert followup_actor_readiness["required_scope"] == ""
    assert followup_actor_readiness["operator_must_supply_actor"] is False
    assert followup_actor_readiness["method"] == "GET"
    assert followup_actor_readiness["action_id"] == "await_resident_runtime_execution_authority_approval"
    _assert_actor_scope_policy_contract(followup_actor_readiness, scope_required=False)
    assert followup_payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
        "mode": "Status",
        "requires_confirmation": False,
        "requires_approval_id": False,
        "requires_operator_approval_decision": True,
        "approval_decision_command": followup_payload["next_operator_action"]["approval_decision_command"],
    }
    assert followup_payload["next_operator_action"]["script_would_execute"] is False
    assert followup_payload["next_operator_action"]["script_would_mutate"] is False


def _approve_request(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    approval_id: str,
    comment: str,
) -> None:
    _set_stage6_env(monkeypatch, data_dir)
    from francis.governance.approvals import decide

    decision = decide(
        approval_id,
        "approve",
        comment,
        actor="test.approvals.decision",
    )
    assert decision["status"] == "approved"


def _request_next(
    data_dir: Path,
    reason: str,
    *,
    service_config_path: Path | None = None,
) -> dict[str, Any]:
    proc = _run_plan(
        "-Mode",
        "RequestNext",
        "-DataDir",
        str(data_dir),
        *_service_config_args(service_config_path),
        "-Actor",
        "test.system.write",
        "-Reason",
        reason,
        "-ConfirmRequest",
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def _grant_next(
    data_dir: Path,
    approval_id: str,
    reason: str,
    *,
    service_config_path: Path | None = None,
) -> dict[str, Any]:
    proc = _run_plan(
        "-Mode",
        "GrantNext",
        "-DataDir",
        str(data_dir),
        *_service_config_args(service_config_path),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        approval_id,
        "-Reason",
        reason,
        "-ConfirmGrant",
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def _execute_next(
    data_dir: Path,
    approval_id: str,
    reason: str,
    *,
    service_config_path: Path | None = None,
    run_seconds: str = "60",
) -> dict[str, Any]:
    proc = _run_plan(
        "-Mode",
        "ExecuteNext",
        "-DataDir",
        str(data_dir),
        *_service_config_args(service_config_path),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        approval_id,
        "-Reason",
        reason,
        "-RunSeconds",
        run_seconds,
        "-ConfirmExecute",
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def _request_approve_grant_next(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    request_reason: str,
    approval_comment: str,
    grant_reason: str,
    service_config_path: Path | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    request = _request_next(data_dir, request_reason, service_config_path=service_config_path)
    approval_id = request["request_result"]["approval_id"]
    _approve_request(monkeypatch, data_dir, approval_id, approval_comment)
    grant = _grant_next(data_dir, approval_id, grant_reason, service_config_path=service_config_path)
    return approval_id, request, grant


def _request_approve_grant_surface_in_process(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    surface: str,
    request_reason: str,
    approval_comment: str,
    grant_reason: str,
    service_config_path: Path | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    _set_stage6_env(monkeypatch, data_dir, service_config_path=service_config_path)
    if surface == "tray_presence":
        from francis.lens.tray_authority import (
            LENS_TRAY_AUTHORITY_REQUEST_ACTION as approval_action,
            LENS_TRAY_AUTHORITY_REQUEST_ROUTE as request_route,
            LENS_TRAY_AUTHORITY_ROUTE as authority_route,
            grant_lens_tray_authority as grant_authority,
            request_lens_tray_authority as request_authority,
        )
    elif surface == "global_hotkey_binding":
        from francis.lens.os_binding_authority import (
            LENS_OS_BINDING_AUTHORITY_REQUEST_ACTION as approval_action,
            LENS_OS_BINDING_AUTHORITY_REQUEST_ROUTE as request_route,
            LENS_OS_BINDING_AUTHORITY_ROUTE as authority_route,
            grant_lens_os_binding_authority as grant_authority,
            request_lens_os_binding_authority as request_authority,
        )
    elif surface == "overlay_window":
        from francis.lens.overlay_authority import (
            LENS_OVERLAY_AUTHORITY_REQUEST_ACTION as approval_action,
            LENS_OVERLAY_AUTHORITY_REQUEST_ROUTE as request_route,
            LENS_OVERLAY_AUTHORITY_ROUTE as authority_route,
            grant_lens_overlay_authority as grant_authority,
            request_lens_overlay_authority as request_authority,
        )
    elif surface == "summon_binding":
        from francis.lens.summon_authority import (
            LENS_SUMMON_AUTHORITY_REQUEST_ACTION as approval_action,
            LENS_SUMMON_AUTHORITY_REQUEST_ROUTE as request_route,
            LENS_SUMMON_AUTHORITY_ROUTE as authority_route,
            grant_lens_summon_authority as grant_authority,
            request_lens_summon_authority as request_authority,
        )
    else:
        raise AssertionError(f"unknown surface fixture: {surface}")

    request = request_authority(
        actor="test.system.write",
        reason=request_reason,
        route=request_route,
        method="POST",
    )
    assert request["ok"] is True
    assert request["approval_requested"] is True
    assert request["action"] == approval_action
    approval_id = request["approval_id"]
    _approve_request(monkeypatch, data_dir, approval_id, approval_comment)
    _set_stage6_env(monkeypatch, data_dir, service_config_path=service_config_path)
    grant = grant_authority(
        approval_id=approval_id,
        actor="test.system.write",
        reason=grant_reason,
        route=authority_route,
        method="POST",
        record_receipt=True,
    )
    assert grant["authority_granted"] is True
    return approval_id, request, grant


def _request_approve_grant_persistent_supervision_enablement_in_process(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    service_config_path: Path,
) -> dict[str, Any]:
    # Keep the temp-config mutation proof inside the 60s live prerequisite lease.
    _set_stage6_env(monkeypatch, data_dir, service_config_path=service_config_path)
    from francis.lens.activation import (
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION,
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        grant_lens_host_persistent_supervision_enablement_authority,
        grant_lens_host_persistent_supervision_enablement_execution_authority,
        request_lens_host_persistent_supervision_enablement_authority,
        request_lens_host_persistent_supervision_enablement_execution_authority,
    )

    enablement_request = request_lens_host_persistent_supervision_enablement_authority(
        actor="test.system.write",
        reason="test request persistent supervision enablement authority after prerequisites",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        method="POST",
    )
    assert enablement_request["ok"] is True
    assert enablement_request["approval_requested"] is True
    assert enablement_request["action"] == LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION
    enablement_approval_id = enablement_request["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        enablement_approval_id,
        "approved only as a persistent supervision enablement authority review decision",
    )
    _set_stage6_env(monkeypatch, data_dir, service_config_path=service_config_path)
    enablement_grant = grant_lens_host_persistent_supervision_enablement_authority(
        approval_id=enablement_approval_id,
        actor="test.system.write",
        reason="test grant persistent supervision enablement authority after prerequisites",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        method="POST",
        record_receipt=True,
    )
    assert enablement_grant["authority_granted"] is True

    execution_request = request_lens_host_persistent_supervision_enablement_execution_authority(
        actor="test.system.write",
        reason="test request persistent supervision execution authority after enablement authority",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        method="POST",
    )
    assert execution_request["ok"] is True
    assert execution_request["approval_requested"] is True
    assert execution_request["action"] == LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION
    execution_approval_id = execution_request["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        execution_approval_id,
        "approved only as a persistent supervision execution authority review decision",
    )
    _set_stage6_env(monkeypatch, data_dir, service_config_path=service_config_path)
    execution_grant = grant_lens_host_persistent_supervision_enablement_execution_authority(
        approval_id=execution_approval_id,
        actor="test.system.write",
        reason="test grant persistent supervision execution authority after review",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        method="POST",
        record_receipt=True,
    )
    assert execution_grant["authority_granted"] is True
    assert execution_grant["service_config_write_authority"] is True

    return {
        "enablement_approval_id": enablement_approval_id,
        "enablement_request": enablement_request,
        "enablement_grant": enablement_grant,
        "execution_approval_id": execution_approval_id,
        "execution_request": execution_request,
        "execution_grant": execution_grant,
    }


def _execute_prerequisites_through_overlay_window(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    service_config_path: Path | None = None,
) -> dict[str, Any]:
    resident_approval_id, _, _ = _request_approve_grant_next(
        data_dir,
        monkeypatch,
        request_reason="test request resident runtime before summon handoff",
        approval_comment="approved only as a resident runtime execution authority review decision",
        grant_reason="test grant resident runtime before summon handoff",
        service_config_path=service_config_path,
    )
    _request_approve_grant_next(
        data_dir,
        monkeypatch,
        request_reason="test request host supervision before summon handoff",
        approval_comment="approved only as a host supervision authority review decision",
        grant_reason="test grant host supervision before summon handoff",
        service_config_path=service_config_path,
    )
    resident_execution = _execute_next(
        data_dir,
        resident_approval_id,
        "test execute resident host before summon handoff",
        service_config_path=service_config_path,
        run_seconds="60",
    )
    assert resident_execution["status"] == "resident_supervision_started"
    _wait_for_next_action(
        data_dir,
        requirement="tray_presence",
        action_id="request_tray_presence_authority",
        service_config_path=service_config_path,
    )

    tray_approval_id, _, _ = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="tray_presence",
        request_reason="test request tray presence before summon handoff",
        approval_comment="approved only as a tray presence authority review decision",
        grant_reason="test grant tray presence before summon handoff",
        service_config_path=service_config_path,
    )
    tray_execution = _execute_next(
        data_dir,
        tray_approval_id,
        "test execute tray presence before summon handoff",
        service_config_path=service_config_path,
        run_seconds="60",
    )
    assert tray_execution["status"] == "tray_presence_started"
    _wait_for_next_action(
        data_dir,
        requirement="global_hotkey_binding",
        action_id="request_global_hotkey_binding_authority",
        service_config_path=service_config_path,
    )

    hotkey_approval_id, _, _ = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="global_hotkey_binding",
        request_reason="test request hotkey binding before summon handoff",
        approval_comment="approved only as a global hotkey binding authority review decision",
        grant_reason="test grant hotkey binding before summon handoff",
        service_config_path=service_config_path,
    )
    hotkey_execution = _execute_next(
        data_dir,
        hotkey_approval_id,
        "test execute hotkey binding before summon handoff",
        service_config_path=service_config_path,
        run_seconds="60",
    )
    assert hotkey_execution["status"] == "global_hotkey_bound"
    _wait_for_next_action(
        data_dir,
        requirement="overlay_window",
        action_id="request_overlay_window_authority",
        service_config_path=service_config_path,
    )

    overlay_approval_id, _, _ = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="overlay_window",
        request_reason="test request overlay window before summon handoff",
        approval_comment="approved only as an overlay window authority review decision",
        grant_reason="test grant overlay window before summon handoff",
        service_config_path=service_config_path,
    )
    overlay_execution = _execute_next(
        data_dir,
        overlay_approval_id,
        "test execute overlay window before summon handoff",
        service_config_path=service_config_path,
        run_seconds="60",
    )
    assert overlay_execution["status"] == "overlay_window_started"
    _wait_for_next_action(
        data_dir,
        requirement="summon_binding",
        action_id="request_summon_binding_authority",
        service_config_path=service_config_path,
    )
    return {
        "resident_approval_id": resident_approval_id,
        "tray_approval_id": tray_approval_id,
        "hotkey_approval_id": hotkey_approval_id,
        "overlay_approval_id": overlay_approval_id,
        "resident_execution": resident_execution,
        "tray_execution": tray_execution,
        "hotkey_execution": hotkey_execution,
        "overlay_execution": overlay_execution,
    }


def test_lens_stage6_prerequisite_bringup_grant_next_creates_only_next_grant_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    requested = _run_plan(
        "-Mode",
        "RequestNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-Reason",
        "test request next prerequisite before grant",
        "-ConfirmRequest",
    )
    assert requested.returncode == 0, requested.stderr or requested.stdout
    requested_payload = json.loads(requested.stdout)
    approval_id = requested_payload["request_result"]["approval_id"]
    assert approval_id

    _approve_request(
        monkeypatch,
        data_dir,
        approval_id,
        "approved only as a resident runtime authority review decision",
    )

    approved_status = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert approved_status.returncode == 0, approved_status.stderr or approved_status.stdout
    approved_payload = json.loads(approved_status.stdout)
    assert approved_payload["next_operator_action"]["id"] == ("grant_resident_runtime_execution_authority")
    assert approved_payload["next_operator_action"]["approved_approval_id"] == approval_id
    assert approved_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode GrantNext -Actor <actor> -ApprovalId {approval_id} -ConfirmGrant"
        ),
        "mode": "GrantNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": True,
    }
    assert approved_payload["next_operator_action"]["script_would_execute"] is False
    assert approved_payload["next_operator_action"]["script_would_mutate"] is False

    granted = _run_plan(
        "-Mode",
        "GrantNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        approval_id,
        "-Reason",
        "test grant next prerequisite authority receipt",
        "-ConfirmGrant",
    )
    assert granted.returncode == 0, granted.stderr or granted.stdout
    payload = json.loads(granted.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["mode"] == "grantnext"
    assert payload["status"] == "authority_granted"
    assert payload["ok"] is True
    grant_result = payload["grant_result"]
    assert grant_result["ok"] is True
    assert grant_result["authority_granted"] is True
    assert grant_result["receipt_written"] is True
    assert grant_result["action_id"] == "grant_resident_runtime_execution_authority"
    assert grant_result["route"] == "/lens/resident-runtime/authority-grant"
    assert grant_result["approval_id"] == approval_id
    assert grant_result["result"]["applied"] is True
    assert grant_result["result"]["executed"] is False
    assert grant_result["result"]["receipt_written"] is True
    assert grant_result["result"]["resident_claim_allowed"] is False
    assert grant_result["governance"]["authority_grant"] is True
    assert grant_result["governance"]["authority_grant_receipt_write"] is True
    assert grant_result["governance"]["approval_decision_authority"] is False
    assert grant_result["governance"]["execution_authority"] is False
    assert grant_result["governance"]["local_process_launch_authority"] is False
    assert grant_result["governance"]["memory_write"] is False
    assert grant_result["governance"]["resident_claim_authority"] is False
    governance = payload["governance"]
    assert governance["plan_only"] is False
    assert governance["read_only_contract"] is False
    assert governance["diagnostic_only"] is False
    assert governance["approval_request_write"] is False
    assert governance["authority_grant_receipt_write"] is True
    assert governance["would_request_authority"] is False
    assert governance["would_grant_authority"] is True
    assert governance["authority_granted"] is True
    assert governance["would_execute"] is False
    assert governance["would_mutate"] is False
    assert governance["mutation_authority_granted"] is True

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["next_operator_action_requirement"] == "resident_host_process"
    assert followup_payload["next_operator_action"]["id"] == "request_host_supervision_authority"
    assert followup_payload["next_operator_action"]["route"] == ("/lens/host/supervision/authority/request")
    assert followup_payload["next_operator_action"]["script_would_execute"] is False
    assert followup_payload["next_operator_action"]["script_would_mutate"] is False


def test_lens_stage6_prerequisite_bringup_execute_next_runs_only_current_bounded_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    resident_request = _run_plan(
        "-Mode",
        "RequestNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-Reason",
        "test request resident runtime authority before execute",
        "-ConfirmRequest",
    )
    assert resident_request.returncode == 0, resident_request.stderr or resident_request.stdout
    resident_approval_id = json.loads(resident_request.stdout)["request_result"]["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        resident_approval_id,
        "approved only as a resident runtime execution authority review decision",
    )
    resident_grant = _run_plan(
        "-Mode",
        "GrantNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        resident_approval_id,
        "-Reason",
        "grant resident runtime authority before execute",
        "-ConfirmGrant",
    )
    assert resident_grant.returncode == 0, resident_grant.stderr or resident_grant.stdout

    host_request = _run_plan(
        "-Mode",
        "RequestNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-Reason",
        "test request host supervision authority before execute",
        "-ConfirmRequest",
    )
    assert host_request.returncode == 0, host_request.stderr or host_request.stdout
    host_approval_id = json.loads(host_request.stdout)["request_result"]["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        host_approval_id,
        "approved only as a host supervision authority review decision",
    )
    host_grant = _run_plan(
        "-Mode",
        "GrantNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        host_approval_id,
        "-Reason",
        "grant host supervision authority before execute",
        "-ConfirmGrant",
    )
    assert host_grant.returncode == 0, host_grant.stderr or host_grant.stdout

    ready = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert ready.returncode == 0, ready.stderr or ready.stdout
    ready_payload = json.loads(ready.stdout)
    assert ready_payload["next_operator_action"]["id"] == "execute_supervised_resident_host_start"
    assert ready_payload["next_operator_action"]["route"] == "/lens/resident-runtime/execute"
    assert ready_payload["next_operator_action"]["active_approval_id"] == resident_approval_id
    assert ready_payload["next_operator_action"]["host_supervision_active_approval_id"] == host_approval_id
    assert ready_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {resident_approval_id} -RunSeconds 2 -ConfirmExecute"
        ),
        "mode": "ExecuteNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": False,
    }
    assert ready_payload["next_operator_action"]["script_would_execute"] is False
    assert ready_payload["next_operator_action"]["script_would_mutate"] is False

    executed = _run_plan(
        "-Mode",
        "ExecuteNext",
        "-DataDir",
        str(data_dir),
        "-Actor",
        "test.system.write",
        "-ApprovalId",
        resident_approval_id,
        "-Reason",
        "test execute bounded resident runtime next action",
        "-RunSeconds",
        "2",
        "-ConfirmExecute",
    )
    assert executed.returncode == 0, executed.stderr or executed.stdout
    payload = json.loads(executed.stdout)
    assert payload["kind"] == "lens.stage6.prerequisite_bringup.plan"
    assert payload["mode"] == "executenext"
    assert payload["status"] == "resident_supervision_started"
    assert payload["ok"] is True
    execute_result = payload["execute_result"]
    assert execute_result["ok"] is True
    assert execute_result["executed"] is True
    assert execute_result["receipt_written"] is True
    assert execute_result["action_id"] == "execute_supervised_resident_host_start"
    assert execute_result["route"] == "/lens/resident-runtime/execute"
    assert execute_result["approval_id"] == resident_approval_id
    assert execute_result["run_seconds"] == 2
    assert execute_result["result"]["executed"] is True
    assert execute_result["result"]["resident_supervision_lease_started"] is True
    assert execute_result["result"]["resident_claim_allowed"] is False
    assert execute_result["governance"]["uses_existing_execution_route"] is True
    assert execute_result["governance"]["approval_decision_authority"] is False
    assert execute_result["governance"]["authority_grant"] is False
    assert execute_result["governance"]["execution_receipt_write"] is True
    assert execute_result["governance"]["memory_write"] is False
    assert execute_result["governance"]["resident_claim_authority"] is False
    governance = payload["governance"]
    assert governance["plan_only"] is False
    assert governance["read_only_contract"] is False
    assert governance["diagnostic_only"] is False
    assert governance["approval_request_write"] is False
    assert governance["authority_grant_receipt_write"] is False
    assert governance["execution_receipt_write"] is True
    assert governance["would_request_authority"] is False
    assert governance["would_grant_authority"] is False
    assert governance["would_execute"] is True
    assert governance["would_mutate"] is True
    assert governance["approval_decision_authority"] is False
    assert governance["memory_write"] is False
    assert governance["resident_claim_authority"] is False

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["next_operator_action_requirement"] == "tray_presence"
    assert followup_payload["current_first_missing_requirement"] == "tray_presence"
    assert followup_payload["current_first_missing_truthful_gap"] == "summon_tray_presence_blocker_boundary"
    assert followup_payload["next_operator_action"]["id"] == "request_tray_presence_authority"
    assert followup_payload["next_operator_action"]["route"] == "/lens/tray/authority/request"
    assert followup_payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": followup_payload["next_operator_action"]["approval_request_command"],
    }
    assert followup_payload["operator_sequence"][0]["id"] == "request_tray_presence_authority"
    assert followup_payload["operator_sequence"][0]["operator_command"]["available_now"] is True
    assert followup_payload["operator_sequence"][0]["operator_command"]["preview_only"] is False


def test_lens_stage6_prerequisite_bringup_tray_execution_advances_to_hotkey(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"

    resident_request = _request_next(data_dir, "test request resident runtime before tray handoff")
    resident_approval_id = resident_request["request_result"]["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        resident_approval_id,
        "approved only as a resident runtime execution authority review decision",
    )
    _grant_next(data_dir, resident_approval_id, "test grant resident runtime before tray handoff")

    host_request = _request_next(data_dir, "test request host supervision before tray handoff")
    host_approval_id = host_request["request_result"]["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        host_approval_id,
        "approved only as a host supervision authority review decision",
    )
    _grant_next(data_dir, host_approval_id, "test grant host supervision before tray handoff")

    resident_execution = _execute_next(data_dir, resident_approval_id, "test execute resident host before tray handoff")
    assert resident_execution["status"] == "resident_supervision_started"
    assert resident_execution["execute_result"]["action_id"] == "execute_supervised_resident_host_start"

    tray_status = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert tray_status.returncode == 0, tray_status.stderr or tray_status.stdout
    tray_status_payload = json.loads(tray_status.stdout)
    assert tray_status_payload["next_operator_action_requirement"] == "tray_presence"
    assert tray_status_payload["next_operator_action"]["id"] == "request_tray_presence_authority"

    tray_request = _request_next(data_dir, "test request tray presence before hotkey handoff")
    tray_approval_id = tray_request["request_result"]["approval_id"]
    assert tray_request["request_result"]["action_id"] == "request_tray_presence_authority"
    assert tray_request["request_result"]["approval_action"] == "lens.tray.presence_authority"
    _approve_request(
        monkeypatch,
        data_dir,
        tray_approval_id,
        "approved only as a tray presence authority review decision",
    )

    tray_grant = _grant_next(data_dir, tray_approval_id, "test grant tray presence before hotkey handoff")
    assert tray_grant["grant_result"]["action_id"] == "grant_tray_presence_authority"
    assert tray_grant["grant_result"]["authority_granted"] is True

    tray_ready = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert tray_ready.returncode == 0, tray_ready.stderr or tray_ready.stdout
    tray_ready_payload = json.loads(tray_ready.stdout)
    assert tray_ready_payload["next_operator_action_requirement"] == "tray_presence"
    assert tray_ready_payload["next_operator_action"]["id"] == "execute_tray_presence"
    assert tray_ready_payload["next_operator_action"]["route"] == "/lens/tray/execute"
    assert tray_ready_payload["next_operator_action"]["active_approval_id"] == tray_approval_id
    assert tray_ready_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {tray_approval_id} -RunSeconds 2 -ConfirmExecute"
        ),
        "mode": "ExecuteNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": False,
    }

    tray_execution = _execute_next(
        data_dir,
        tray_approval_id,
        "test execute tray presence before hotkey handoff",
        run_seconds="60",
    )
    assert tray_execution["status"] == "tray_presence_started", json.dumps(tray_execution, indent=2)
    assert tray_execution["execute_result"]["action_id"] == "execute_tray_presence"
    assert tray_execution["execute_result"]["executed"] is True
    assert tray_execution["execute_result"]["receipt_written"] is True
    assert tray_execution["execute_result"]["result"]["tray_presence"] is True
    assert tray_execution["execute_result"]["result"]["governance"]["tray_registration_authority"] is True
    assert tray_execution["execute_result"]["result"]["governance"]["resident_claim_authority"] is False
    assert tray_execution["governance"]["execution_receipt_write"] is True
    assert tray_execution["governance"]["would_execute"] is True
    assert tray_execution["governance"]["would_mutate"] is True

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["next_operator_action_requirement"] == "global_hotkey_binding"
    assert followup_payload["current_first_missing_requirement"] == "global_hotkey_binding"
    assert followup_payload["current_first_missing_truthful_gap"] == "os_level_command_palette_binding"
    assert followup_payload["next_operator_action"]["id"] == "request_global_hotkey_binding_authority"
    assert followup_payload["next_operator_action"]["route"] == "/lens/os-binding/authority/request"
    assert followup_payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": followup_payload["next_operator_action"]["approval_request_command"],
    }
    assert followup_payload["operator_sequence"][0]["id"] == "request_global_hotkey_binding_authority"
    assert followup_payload["operator_sequence"][0]["operator_command"]["available_now"] is True
    assert followup_payload["operator_sequence"][0]["operator_command"]["preview_only"] is False


def test_lens_stage6_prerequisite_bringup_hotkey_execution_advances_to_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"

    resident_request = _request_next(data_dir, "test request resident runtime before hotkey handoff")
    resident_approval_id = resident_request["request_result"]["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        resident_approval_id,
        "approved only as a resident runtime execution authority review decision",
    )
    _grant_next(data_dir, resident_approval_id, "test grant resident runtime before hotkey handoff")

    host_request = _request_next(data_dir, "test request host supervision before hotkey handoff")
    host_approval_id = host_request["request_result"]["approval_id"]
    _approve_request(
        monkeypatch,
        data_dir,
        host_approval_id,
        "approved only as a host supervision authority review decision",
    )
    _grant_next(data_dir, host_approval_id, "test grant host supervision before hotkey handoff")
    resident_execution = _execute_next(
        data_dir,
        resident_approval_id,
        "test execute resident host before hotkey handoff",
        run_seconds="60",
    )
    assert resident_execution["status"] == "resident_supervision_started"

    tray_approval_id, _, _ = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="tray_presence",
        request_reason="test request tray presence before hotkey execution",
        approval_comment="approved only as a tray presence authority review decision",
        grant_reason="test grant tray presence before hotkey execution",
    )
    tray_execution = _execute_next(
        data_dir,
        tray_approval_id,
        "test execute tray presence before hotkey execution",
        run_seconds="60",
    )
    assert tray_execution["status"] == "tray_presence_started"

    hotkey_status = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert hotkey_status.returncode == 0, hotkey_status.stderr or hotkey_status.stdout
    hotkey_status_payload = json.loads(hotkey_status.stdout)
    assert hotkey_status_payload["next_operator_action_requirement"] == "global_hotkey_binding"
    assert hotkey_status_payload["next_operator_action"]["id"] == "request_global_hotkey_binding_authority"

    hotkey_request = _request_next(data_dir, "test request hotkey binding before overlay handoff")
    hotkey_approval_id = hotkey_request["request_result"]["approval_id"]
    assert hotkey_request["request_result"]["action_id"] == "request_global_hotkey_binding_authority"
    assert hotkey_request["request_result"]["approval_action"] == ("lens.os_binding.command_palette_binding_authority")
    _approve_request(
        monkeypatch,
        data_dir,
        hotkey_approval_id,
        "approved only as a global hotkey binding authority review decision",
    )

    hotkey_grant = _grant_next(data_dir, hotkey_approval_id, "test grant hotkey binding before overlay handoff")
    assert hotkey_grant["grant_result"]["action_id"] == "grant_global_hotkey_binding_authority"
    assert hotkey_grant["grant_result"]["authority_granted"] is True

    hotkey_ready = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert hotkey_ready.returncode == 0, hotkey_ready.stderr or hotkey_ready.stdout
    hotkey_ready_payload = json.loads(hotkey_ready.stdout)
    assert hotkey_ready_payload["next_operator_action_requirement"] == "global_hotkey_binding"
    assert hotkey_ready_payload["next_operator_action"]["id"] == "execute_global_hotkey_binding"
    assert hotkey_ready_payload["next_operator_action"]["route"] == "/lens/os-binding/execute"
    assert hotkey_ready_payload["next_operator_action"]["active_approval_id"] == hotkey_approval_id
    assert hotkey_ready_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {hotkey_approval_id} -RunSeconds 2 -ConfirmExecute"
        ),
        "mode": "ExecuteNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": False,
    }

    hotkey_execution = _execute_next(
        data_dir,
        hotkey_approval_id,
        "test execute hotkey binding before overlay handoff",
        run_seconds="60",
    )
    assert hotkey_execution["status"] == "global_hotkey_bound", json.dumps(hotkey_execution, indent=2)
    assert hotkey_execution["execute_result"]["action_id"] == "execute_global_hotkey_binding"
    assert hotkey_execution["execute_result"]["executed"] is True
    assert hotkey_execution["execute_result"]["receipt_written"] is True
    assert hotkey_execution["execute_result"]["result"]["global_hotkey_binding"] is True
    assert hotkey_execution["execute_result"]["result"]["hotkey_runtime_ready"] is True
    assert hotkey_execution["execute_result"]["result"]["launch_on_hotkey"] is False
    assert hotkey_execution["execute_result"]["result"]["governance"]["hotkey_registration_authority"] is True
    assert hotkey_execution["execute_result"]["result"]["governance"]["summon_authority"] is False
    assert hotkey_execution["governance"]["execution_receipt_write"] is True
    assert hotkey_execution["governance"]["would_execute"] is True
    assert hotkey_execution["governance"]["would_mutate"] is True

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["next_operator_action_requirement"] == "overlay_window"
    assert followup_payload["current_first_missing_requirement"] == "overlay_window"
    assert followup_payload["current_first_missing_truthful_gap"] == "summon_overlay_window_blocker_boundary"
    assert followup_payload["next_operator_action"]["id"] == "request_overlay_window_authority"
    assert followup_payload["next_operator_action"]["route"] == "/lens/overlay/authority/request"
    assert followup_payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": followup_payload["next_operator_action"]["approval_request_command"],
    }
    assert followup_payload["operator_sequence"][0]["id"] == "request_overlay_window_authority"
    assert followup_payload["operator_sequence"][0]["operator_command"]["available_now"] is True
    assert followup_payload["operator_sequence"][0]["operator_command"]["preview_only"] is False


def test_lens_stage6_prerequisite_bringup_overlay_execution_advances_to_summon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"

    resident_approval_id, _, _ = _request_approve_grant_next(
        data_dir,
        monkeypatch,
        request_reason="test request resident runtime before overlay handoff",
        approval_comment="approved only as a resident runtime execution authority review decision",
        grant_reason="test grant resident runtime before overlay handoff",
    )
    _request_approve_grant_next(
        data_dir,
        monkeypatch,
        request_reason="test request host supervision before overlay handoff",
        approval_comment="approved only as a host supervision authority review decision",
        grant_reason="test grant host supervision before overlay handoff",
    )
    resident_execution = _execute_next(
        data_dir,
        resident_approval_id,
        "test execute resident host before overlay handoff",
        run_seconds="60",
    )
    assert resident_execution["status"] == "resident_supervision_started"

    tray_approval_id, _, _ = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="tray_presence",
        request_reason="test request tray presence before overlay handoff",
        approval_comment="approved only as a tray presence authority review decision",
        grant_reason="test grant tray presence before overlay handoff",
    )
    tray_execution = _execute_next(
        data_dir,
        tray_approval_id,
        "test execute tray presence before overlay handoff",
        run_seconds="60",
    )
    assert tray_execution["status"] == "tray_presence_started"

    hotkey_approval_id, _, _ = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="global_hotkey_binding",
        request_reason="test request hotkey binding before overlay execution",
        approval_comment="approved only as a global hotkey binding authority review decision",
        grant_reason="test grant hotkey binding before overlay execution",
    )
    hotkey_execution = _execute_next(
        data_dir,
        hotkey_approval_id,
        "test execute hotkey binding before overlay execution",
        run_seconds="60",
    )
    assert hotkey_execution["status"] == "global_hotkey_bound"

    overlay_status = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert overlay_status.returncode == 0, overlay_status.stderr or overlay_status.stdout
    overlay_status_payload = json.loads(overlay_status.stdout)
    assert overlay_status_payload["next_operator_action_requirement"] == "overlay_window"
    assert overlay_status_payload["next_operator_action"]["id"] == "request_overlay_window_authority"

    overlay_approval_id, overlay_request, overlay_grant = _request_approve_grant_next(
        data_dir,
        monkeypatch,
        request_reason="test request overlay window before summon handoff",
        approval_comment="approved only as an overlay window authority review decision",
        grant_reason="test grant overlay window before summon handoff",
    )
    assert overlay_request["request_result"]["action_id"] == "request_overlay_window_authority"
    assert overlay_request["request_result"]["approval_action"] == "lens.overlay.window_authority"
    assert overlay_grant["grant_result"]["action_id"] == "grant_overlay_window_authority"
    assert overlay_grant["grant_result"]["authority_granted"] is True

    overlay_ready = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert overlay_ready.returncode == 0, overlay_ready.stderr or overlay_ready.stdout
    overlay_ready_payload = json.loads(overlay_ready.stdout)
    assert overlay_ready_payload["next_operator_action_requirement"] == "overlay_window"
    assert overlay_ready_payload["next_operator_action"]["id"] == "execute_overlay_window"
    assert overlay_ready_payload["next_operator_action"]["route"] == "/lens/overlay/execute"
    assert overlay_ready_payload["next_operator_action"]["active_approval_id"] == overlay_approval_id
    assert overlay_ready_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {overlay_approval_id} -RunSeconds 2 -ConfirmExecute"
        ),
        "mode": "ExecuteNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": False,
    }

    overlay_execution = _execute_next(
        data_dir,
        overlay_approval_id,
        "test execute overlay window before summon handoff",
        run_seconds="60",
    )
    assert overlay_execution["status"] == "overlay_window_started", json.dumps(overlay_execution, indent=2)
    assert overlay_execution["execute_result"]["action_id"] == "execute_overlay_window"
    assert overlay_execution["execute_result"]["executed"] is True
    assert overlay_execution["execute_result"]["receipt_written"] is True
    assert overlay_execution["execute_result"]["result"]["overlay_window"] is True
    assert overlay_execution["execute_result"]["result"]["overlay_runtime_ready"] is True
    assert overlay_execution["execute_result"]["result"]["resident_claim_allowed"] is False
    assert overlay_execution["execute_result"]["result"]["governance"]["overlay_control_authority"] is True
    assert overlay_execution["execute_result"]["result"]["governance"]["summon_authority"] is False
    assert overlay_execution["governance"]["execution_receipt_write"] is True
    assert overlay_execution["governance"]["would_execute"] is True
    assert overlay_execution["governance"]["would_mutate"] is True

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["next_operator_action_requirement"] == "summon_binding"
    assert followup_payload["current_first_missing_requirement"] == "summon_binding"
    assert followup_payload["current_first_missing_truthful_gap"] == "summon_anywhere_blockers"
    assert followup_payload["next_operator_action"]["id"] == "request_summon_binding_authority"
    assert followup_payload["next_operator_action"]["route"] == "/lens/summon/authority/request"
    assert followup_payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": followup_payload["next_operator_action"]["approval_request_command"],
    }
    assert followup_payload["operator_sequence"][0]["id"] == "request_summon_binding_authority"
    assert followup_payload["operator_sequence"][0]["operator_command"]["available_now"] is True
    assert followup_payload["operator_sequence"][0]["operator_command"]["preview_only"] is False


def _execute_prerequisites_through_summon_binding(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    service_config_path: Path | None = None,
) -> dict[str, Any]:
    chain = _execute_prerequisites_through_overlay_window(
        data_dir,
        monkeypatch,
        service_config_path=service_config_path,
    )
    summon_approval_id, summon_request, summon_grant = _request_approve_grant_surface_in_process(
        data_dir,
        monkeypatch,
        surface="summon_binding",
        request_reason="test request summon binding before persistent supervision enablement",
        approval_comment="approved only as a summon action authority review decision",
        grant_reason="test grant summon binding before persistent supervision enablement",
        service_config_path=service_config_path,
    )
    summon_execution = _execute_next(
        data_dir,
        summon_approval_id,
        "test execute summon binding before persistent supervision enablement",
        service_config_path=service_config_path,
        run_seconds="60",
    )
    return {
        **chain,
        "summon_approval_id": summon_approval_id,
        "summon_request": summon_request,
        "summon_grant": summon_grant,
        "summon_execution": summon_execution,
    }


def _write_disabled_temp_service_config(tmp_path: Path) -> Path:
    source = _repo_root() / "config" / "runtime" / "services" / "lens-host.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload.update(
        {
            "process_supervision_enabled": True,
            "persistent_supervision_enabled": False,
            "supervision_ready": False,
            "supervision_blocked_reason": "resident_supervision_prerequisites_pending",
            "blocked_reason": "lens_host_persistent_supervision_prerequisites_pending",
        }
    )
    target = tmp_path / "service-config" / "lens-host.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def test_lens_stage6_prerequisite_bringup_summon_execution_advances_to_enablement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    chain = _execute_prerequisites_through_overlay_window(data_dir, monkeypatch)
    assert chain["overlay_execution"]["execute_result"]["result"]["overlay_window"] is True

    summon_status = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert summon_status.returncode == 0, summon_status.stderr or summon_status.stdout
    summon_status_payload = json.loads(summon_status.stdout)
    assert summon_status_payload["next_operator_action_requirement"] == "summon_binding"
    assert summon_status_payload["next_operator_action"]["id"] == "request_summon_binding_authority"

    summon_approval_id, summon_request, summon_grant = _request_approve_grant_next(
        data_dir,
        monkeypatch,
        request_reason="test request summon binding before persistent supervision enablement",
        approval_comment="approved only as a summon action authority review decision",
        grant_reason="test grant summon binding before persistent supervision enablement",
    )
    assert summon_request["request_result"]["action_id"] == "request_summon_binding_authority"
    assert summon_request["request_result"]["approval_action"] == "lens.summon.action_authority"
    assert summon_grant["grant_result"]["action_id"] == "grant_summon_binding_authority"
    assert summon_grant["grant_result"]["authority_granted"] is True

    summon_ready = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert summon_ready.returncode == 0, summon_ready.stderr or summon_ready.stdout
    summon_ready_payload = json.loads(summon_ready.stdout)
    assert summon_ready_payload["next_operator_action_requirement"] == "summon_binding"
    assert summon_ready_payload["next_operator_action"]["id"] == "execute_summon_binding"
    assert summon_ready_payload["next_operator_action"]["route"] == "/lens/summon/execute"
    assert summon_ready_payload["next_operator_action"]["active_approval_id"] == summon_approval_id
    assert summon_ready_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {summon_approval_id} -RunSeconds 2 -ConfirmExecute"
        ),
        "mode": "ExecuteNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": False,
    }

    summon_execution = _execute_next(
        data_dir,
        summon_approval_id,
        "test execute summon binding before persistent supervision enablement",
        run_seconds="60",
    )
    assert summon_execution["status"] == "summon_binding_observed", json.dumps(summon_execution, indent=2)
    assert summon_execution["execute_result"]["action_id"] == "execute_summon_binding"
    assert summon_execution["execute_result"]["executed"] is True
    assert summon_execution["execute_result"]["receipt_written"] is True
    assert summon_execution["execute_result"]["result"]["summon_binding"] is True
    assert summon_execution["execute_result"]["result"]["summon_runtime_ready"] is True
    assert summon_execution["execute_result"]["result"]["bounded_handoff_ready"] is True
    assert summon_execution["execute_result"]["result"]["allow_launch"] is False
    assert summon_execution["execute_result"]["result"]["summon_anywhere"] is False
    assert summon_execution["execute_result"]["result"]["governance"]["summon_authority"] is True
    assert summon_execution["execute_result"]["result"]["governance"]["summon_anywhere_authority"] is False
    assert summon_execution["execute_result"]["result"]["governance"]["os_level_summon_authority"] is False
    assert summon_execution["execute_result"]["result"]["governance"]["mutation_authority_granted"] is False
    assert summon_execution["governance"]["execution_receipt_write"] is True
    assert summon_execution["governance"]["would_execute"] is True
    assert summon_execution["governance"]["would_mutate"] is True

    followup = _run_plan("-Mode", "Status", "-DataDir", str(data_dir))
    assert followup.returncode == 0, followup.stderr or followup.stdout
    followup_payload = json.loads(followup.stdout)
    assert followup_payload["status"] == "ready_for_persistent_supervision_enablement_sequence"
    assert followup_payload["required_before_enable_ready"] is True
    assert followup_payload["missing_required_before_enable"] == []
    assert followup_payload["current_first_missing_requirement"] == ""
    assert followup_payload["current_first_missing_truthful_gap"] == ""
    assert followup_payload["current_truthful_gap"] == "persistent_supervision_execution_boundary"
    assert followup_payload["current_truthful_gap_basis"] == ("persistent_supervision_plan.next_smallest_truthful_gap")
    assert followup_payload["next_operator_action_requirement"] == "persistent_supervision_enablement"
    assert followup_payload["next_operator_action"]["id"] == "request_persistent_supervision_enablement_authority"
    assert followup_payload["next_operator_action"]["route"] == (
        "/lens/host/persistent-supervision/enablement/authority/request"
    )
    assert followup_payload["next_operator_command"] == {
        "command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode RequestNext -Actor <actor> -ConfirmRequest",
        "mode": "RequestNext",
        "requires_confirmation": True,
        "requires_approval_id": False,
        "requires_operator_approval_decision": False,
        "approval_request_command": followup_payload["next_operator_action"]["approval_request_command"],
    }
    assert followup_payload["operator_sequence"][0]["id"] == "request_persistent_supervision_enablement_authority"
    assert followup_payload["operator_sequence"][0]["operator_command"]["available_now"] is True
    assert followup_payload["operator_sequence"][0]["operator_command"]["preview_only"] is False


def test_lens_stage6_prerequisite_bringup_applies_enablement_to_temp_service_config_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    service_config_path = _write_disabled_temp_service_config(tmp_path)
    live_service_config_path = _repo_root() / "config" / "runtime" / "services" / "lens-host.json"
    live_service_config_before = live_service_config_path.read_text(encoding="utf-8")

    chain = _execute_prerequisites_through_summon_binding(
        data_dir,
        monkeypatch,
    )
    assert chain["summon_execution"]["execute_result"]["result"]["bounded_handoff_ready"] is True

    ready = _run_plan(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        *_service_config_args(service_config_path),
    )
    assert ready.returncode == 0, ready.stderr or ready.stdout
    ready_payload = json.loads(ready.stdout)
    assert ready_payload["status"] == "ready_for_persistent_supervision_enablement_sequence"
    assert ready_payload["next_operator_action"]["id"] == "request_persistent_supervision_enablement_authority"

    enablement_chain = _request_approve_grant_persistent_supervision_enablement_in_process(
        data_dir,
        monkeypatch,
        service_config_path=service_config_path,
    )
    enablement_approval_id = enablement_chain["enablement_approval_id"]
    execution_approval_id = enablement_chain["execution_approval_id"]

    apply_ready = _run_plan(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_dir),
        *_service_config_args(service_config_path),
    )
    assert apply_ready.returncode == 0, apply_ready.stderr or apply_ready.stdout
    apply_ready_payload = json.loads(apply_ready.stdout)
    assert apply_ready_payload["next_operator_action_requirement"] == "persistent_supervision_enablement"
    assert apply_ready_payload["next_operator_action"]["id"] == "apply_persistent_supervision_enablement"
    assert apply_ready_payload["next_operator_action"]["active_approval_id"] == execution_approval_id
    assert apply_ready_payload["next_operator_action"]["enablement_active_approval_id"] == enablement_approval_id
    assert apply_ready_payload["next_operator_command"] == {
        "command": (
            ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
            f"-Mode ExecuteNext -Actor <actor> -ApprovalId {execution_approval_id} -RunSeconds 2 -ConfirmExecute"
        ),
        "mode": "ExecuteNext",
        "requires_confirmation": True,
        "requires_approval_id": True,
        "requires_operator_approval_decision": False,
    }

    apply_result = _execute_next(
        data_dir,
        execution_approval_id,
        "test apply persistent supervision enablement against temp service config",
        service_config_path=service_config_path,
        run_seconds="2",
    )
    assert apply_result["status"] == "service_config_updated", json.dumps(apply_result, indent=2)
    assert apply_result["execute_result"]["action_id"] == "apply_persistent_supervision_enablement"
    assert apply_result["execute_result"]["executed"] is True
    assert apply_result["execute_result"]["receipt_written"] is True
    execution = apply_result["execute_result"]["result"]
    assert execution["service_config"]["path"] == str(service_config_path.resolve())
    assert execution["service_config"]["updated"] is True
    assert "persistent_supervision_enabled" in execution["service_config"]["changed_fields"]
    assert execution["persistent_supervision_enablement_allowed"] is True
    assert execution["persistent_supervision_ready"] is True
    assert execution["resident_claim_allowed"] is False
    assert execution["governance"]["service_config_write_authority"] is True
    assert execution["governance"]["persistent_supervision_execution_authority"] is True
    assert execution["governance"]["service_config_mutation_authority"] is True
    assert execution["governance"]["service_install_authority"] is False
    assert execution["governance"]["service_control_authority"] is False
    assert execution["governance"]["local_process_launch_authority"] is False
    assert execution["governance"]["memory_write"] is False
    assert execution["governance"]["resident_claim_authority"] is False
    assert apply_result["governance"]["would_mutate"] is True
    assert apply_result["execute_result"]["governance"]["service_config_write_authority"] is True

    temp_service_config = json.loads(service_config_path.read_text(encoding="utf-8"))
    assert temp_service_config["process_supervision_enabled"] is True
    assert temp_service_config["persistent_supervision_enabled"] is True
    assert temp_service_config["installable"] is False
    assert temp_service_config["service_control_authority"] is False
    assert temp_service_config["resident_claim_authority"] is False
    assert live_service_config_path.read_text(encoding="utf-8") == live_service_config_before
