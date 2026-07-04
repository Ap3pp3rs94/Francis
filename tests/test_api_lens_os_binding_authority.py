from __future__ import annotations

import json
import os
import subprocess
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


def _write_lens_hotkey_runtime_state(data_root: Path, *, pid: int, launch_on_hotkey: bool = False) -> None:
    runtime_root = data_root / "runtime" / "lens-hotkey"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-hotkey.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": launch_on_hotkey,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
                "updated_at": "2026-05-13T00:30:00Z",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_hotkey_owned_runtime_state(data_root: Path) -> None:
    runtime_root = data_root / "runtime" / "lens-hotkey"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_already_owned",
                "pid": 999999,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "hotkey_bound": False,
                "error": "hotkey_already_owned",
                "blocker": "hotkey_already_owned",
                "win32_error": 1409,
                "registration_failure": {
                    "error": "hotkey_already_owned",
                    "blocker": "hotkey_already_owned",
                    "global_hotkey": "Ctrl+Alt+F",
                    "win32_error": 1409,
                },
                "updated_at": "2026-07-03T18:50:00Z",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_overlay_runtime_state(data_root: Path, *, pid: int) -> None:
    runtime_root = data_root / "runtime" / "lens-overlay"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "lens-overlay.pid").write_text(str(pid), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": pid,
                "overlay_name": "Francis Lens Overlay",
                "overlay_scope": "user_session",
                "overlay_window_visible": True,
                "always_on_top": True,
                "updated_at": "2026-05-13T02:30:00Z",
            }
        ),
        encoding="utf-8",
    )


def _write_lens_summon_config(repo_root: Path) -> None:
    config_root = repo_root / "config" / "runtime" / "lens"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "summon.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.config",
                "version": 1,
                "enabled": False,
                "global_hotkey": "Ctrl+Alt+F",
                "binding_scope": "global",
                "binding_enabled": False,
                "register_hotkey": False,
                "startup_register": False,
                "palette_route": "/lens/status",
                "summon_runner": "scripts/lens-summon.ps1",
                "local_palette_launcher": "scripts/lens-command-palette.ps1 -Mode LocalOpen",
                "summon_authority": False,
                "hotkey_registration_authority": False,
                "local_process_launch_authority": False,
                "blocked_reason": "lens_summon_binding_disabled_pending_authority",
                "required_before_enable": [
                    "resident_host_process",
                    "tray_presence",
                    "overlay_window",
                    "global_hotkey_binding",
                    "summon_binding",
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_lens_overlay_config(repo_root: Path) -> None:
    config_root = repo_root / "config" / "runtime" / "lens"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "overlay.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.config",
                "version": 1,
                "enabled": False,
                "overlay_name": "Francis Lens Overlay",
                "overlay_scope": "user_session",
                "window_enabled": False,
                "always_on_top": False,
                "dock_supported": False,
                "focus_supported": False,
                "click_through_supported": False,
                "capture_supported": False,
                "status_route": "/lens/status",
                "host_route": "/lens/host",
                "overlay_runner": "scripts/lens-overlay-window.ps1",
                "requires_explicit_enable": True,
                "overlay_control_authority": False,
                "window_management_authority": False,
                "local_process_launch_authority": False,
                "capture_authority": False,
                "summon_authority": False,
                "tray_registration_authority": False,
                "blocked_reason": "lens_overlay_window_not_implemented",
                "required_before_enable": [
                    "resident_host_process",
                    "tray_presence",
                    "overlay_window",
                    "always_on_top_policy",
                    "global_hotkey_binding",
                    "summon_binding",
                ],
            }
        ),
        encoding="utf-8",
    )


def _grant_lens_authority(
    client,
    *,
    request_route: str,
    grant_route: str,
    reason: str,
) -> tuple[str, str]:
    request_response = client.post(
        request_route,
        json={
            "actor": "test.system.write",
            "reason": reason,
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
            "comment": f"approve {reason}",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    grant = client.post(
        grant_route,
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": f"grant {reason}",
            "lease_seconds": 120,
        },
    )
    assert grant.status_code == 200
    grant_body = grant.json()
    assert grant_body["authority_granted"] is True
    return approval_id, grant_body["receipt"]["receipt_id"]


def test_lens_os_binding_hotkey_runner_uses_ci_tolerant_startup_budget(monkeypatch, tmp_path: Path) -> None:
    from francis.lens import os_binding_authority as module

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    script_root = repo_root / "scripts"
    script_root.mkdir(parents=True)
    (script_root / "lens-hotkey-binding.ps1").write_text("# test hotkey runner\n", encoding="utf-8")
    _write_lens_summon_config(repo_root)
    monkeypatch.setattr(module, "repo_root", lambda: repo_root)
    monkeypatch.setattr(module, "data_dir", lambda: data_root)
    monkeypatch.setattr(module.shutil, "which", lambda name: "powershell.exe")
    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "status": "started", "blockers": []}),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module._run_lens_os_binding_hotkey_action(mode="bind", run_seconds=180)

    assert result["ok"] is True
    command = captured["command"]
    assert isinstance(command, list)
    timeout_index = command.index("-StartupTimeoutSeconds")
    assert command[timeout_index + 1] == "30"
    assert "-ConfigOverridePath" in command
    assert "-NoLaunch" in command


def test_lens_os_binding_hotkey_runner_can_enable_launch_on_hotkey_when_explicitly_allowed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.lens import os_binding_authority as module

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    script_root = repo_root / "scripts"
    script_root.mkdir(parents=True)
    (script_root / "lens-hotkey-binding.ps1").write_text("# test hotkey runner\n", encoding="utf-8")
    _write_lens_summon_config(repo_root)
    monkeypatch.setattr(module, "repo_root", lambda: repo_root)
    monkeypatch.setattr(module, "data_dir", lambda: data_root)
    monkeypatch.setattr(module.shutil, "which", lambda name: "powershell.exe")
    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "status": "started", "blockers": []}),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module._run_lens_os_binding_hotkey_action(mode="bind", run_seconds=180, allow_launch=True)

    assert result["ok"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert "-NoLaunch" not in command
    override_index = command.index("-ConfigOverridePath")
    override_path = Path(command[override_index + 1])
    override = json.loads(override_path.read_text(encoding="utf-8"))
    assert override["summon_authority"] is True
    assert override["overlay_control_authority"] is True
    assert override["hotkey_registration_authority"] is True
    assert override["local_process_launch_authority"] is True


def test_lens_os_binding_hotkey_runner_writes_requested_global_hotkey_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.lens import os_binding_authority as module

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    script_root = repo_root / "scripts"
    script_root.mkdir(parents=True)
    (script_root / "lens-hotkey-binding.ps1").write_text("# test hotkey runner\n", encoding="utf-8")
    _write_lens_summon_config(repo_root)
    monkeypatch.setattr(module, "repo_root", lambda: repo_root)
    monkeypatch.setattr(module, "data_dir", lambda: data_root)
    monkeypatch.setattr(module.shutil, "which", lambda name: "powershell.exe")
    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "status": "started", "blockers": []}),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module._run_lens_os_binding_hotkey_action(
        mode="bind",
        run_seconds=180,
        global_hotkey="Ctrl+Alt+Shift+F12",
    )

    assert result["ok"] is True
    command = captured["command"]
    assert isinstance(command, list)
    override_index = command.index("-ConfigOverridePath")
    override_path = Path(command[override_index + 1])
    override = json.loads(override_path.read_text(encoding="utf-8"))
    assert override["global_hotkey"] == "Ctrl+Alt+Shift+F12"


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
    assert governance["hotkey_registration_authority"] is True
    assert governance["summon_authority"] is False
    assert governance["overlay_control_authority"] is False
    assert governance["local_process_launch_authority"] is True
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
    assert readback["active_grant_approval_id"] == approval_id
    assert readback["active_approval_id"] == approval_id
    assert readback["active_authority_grant"]["receipt_id"] == receipt["receipt_id"]
    assert readback["active_authority_grant"]["approval_id"] == approval_id
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
    assert plan["command_palette_contract"]["url_entrypoint_ready"] is True
    assert plan["command_palette_contract"]["url_entrypoint_route"] == "/?francis_lens=command_palette"
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
    assert authority_readback["authority_required"] == "os_level_command_palette_binding_authority"
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
    assert readiness["command_palette_contract"]["url_entrypoint_ready"] is True
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
    assert os_binding_criterion["execution_readiness_status"] == "blocked"
    assert os_binding_criterion["execution_readiness_ready"] is False
    assert os_binding_criterion["execution_boundary_observed"] is True
    assert os_binding_criterion["execution_denial_receipt_readback_ready"] is True
    assert os_binding_criterion["execution_denial_receipt_total"] == 0
    assert os_binding_criterion["execution_next_smallest_truthful_gap"] == "os_binding_execution_prerequisites"
    status_execution_readiness = status["os_binding_execution_readiness"]
    assert status_execution_readiness["route"] == "/lens/os-binding/execution/readiness"
    assert status_execution_readiness["authority_granted"] is True
    assert status_execution_readiness["os_level_command_palette_binding_authority"] is True
    assert status_execution_readiness["active_grant_receipt_id"] == receipt["receipt_id"]
    assert status_execution_readiness["denial_boundary_observed"] is True
    assert status_execution_readiness["denial_receipt_readback_ready"] is True
    assert status_execution_readiness["execution_prerequisites_ready"] is False
    assert status_execution_readiness["blocked_execution_prerequisites"] == [
        "system_write_permission",
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
        "tray_presence",
        "overlay_window",
    ]

    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_execution_readiness_carries_live_hotkey_runtime_without_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _write_lens_summon_config(data_root.parent)
    _write_lens_hotkey_runtime_state(data_root, pid=os.getpid())

    response = client.get("/lens/os-binding/execution/readiness?actor=test.system.write")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding.execution_readiness"
    assert body["status"] == "blocked"
    assert body["ready"] is False
    assert body["execution_ready"] is False
    requirements = {item["id"]: item for item in body["requirements"]}
    hotkey_requirement = requirements["global_hotkey_binding"]
    assert hotkey_requirement["ready"] is True
    assert hotkey_requirement["runtime_ready"] is True
    assert hotkey_requirement["runtime_requirement_state"] == "bound"
    assert hotkey_requirement["runtime_blocker"] == ""
    assert hotkey_requirement["hotkey_runtime_readback"]["process_alive"] is True
    assert hotkey_requirement["hotkey_runtime_readback"]["hotkey_bound"] is True
    assert hotkey_requirement["blockers"] == []
    assert "global_hotkey_binding" not in body["blocked_execution_prerequisites"]
    assert body["execution_prerequisites_ready"] is False
    assert body["os_level_command_palette"] is True
    assert body["summon_anywhere"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["hotkey_registration_authority"] is False
    assert body["governance"]["summon_authority"] is False


def test_lens_os_binding_execution_readiness_accepts_runtime_hotkey_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _write_lens_summon_config(data_root.parent)
    runtime_root = data_root / "runtime" / "lens-hotkey"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "os-binding-summon-override.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.config",
                "global_hotkey": "Ctrl+Alt+Shift+F12",
                "binding_scope": "global",
            }
        ),
        encoding="utf-8",
    )
    (runtime_root / "lens-hotkey.pid").write_text(str(os.getpid()), encoding="ascii")
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": os.getpid(),
                "global_hotkey": "Ctrl+Alt+Shift+F12",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": True,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
                "updated_at": "2026-05-24T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/lens/os-binding/execution/readiness?actor=test.system.write")

    assert response.status_code == 200
    body = response.json()
    requirements = {item["id"]: item for item in body["requirements"]}
    hotkey_requirement = requirements["global_hotkey_binding"]
    readback = hotkey_requirement["hotkey_runtime_readback"]
    assert hotkey_requirement["runtime_ready"] is True
    assert readback["config_source"] == "runtime_override"
    assert readback["global_hotkey"] == "Ctrl+Alt+Shift+F12"
    assert readback["expected_global_hotkey"] == "Ctrl+Alt+Shift+F12"
    assert readback["blocker"] == ""
    assert "global_hotkey_binding" not in body["blocked_execution_prerequisites"]


def test_lens_host_launch_manifest_accepts_summon_runtime_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _write_lens_summon_config(data_root.parent)
    runtime_root = data_root / "runtime" / "lens-summon"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "summon-action-override.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.config",
                "global_hotkey": "Ctrl+Alt+Shift+F12",
                "binding_scope": "global",
            }
        ),
        encoding="utf-8",
    )
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.runtime_state",
                "status": "summon_binding_observed",
                "global_hotkey": "Ctrl+Alt+Shift+F12",
                "binding_scope": "global",
                "bounded_handoff_ready": True,
                "local_open_ready": True,
                "opened": True,
                "no_launch": False,
                "summon_anywhere": True,
                "os_level_summon": True,
                "updated_at": "2026-05-24T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/lens/status?limit=10")

    assert response.status_code == 200
    body = response.json()
    readback = body["resident_host"]["launch_manifest"]["summon_runtime_readback"]
    assert readback["ready"] is True
    assert readback["config_source"] == "runtime_override"
    assert readback["global_hotkey"] == "Ctrl+Alt+Shift+F12"
    assert readback["expected_global_hotkey"] == "Ctrl+Alt+Shift+F12"
    assert readback["blocker"] == ""


def test_lens_os_binding_execution_readiness_carries_live_overlay_runtime_without_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _write_lens_summon_config(data_root.parent)
    _write_lens_overlay_config(data_root.parent)
    _write_lens_overlay_runtime_state(data_root, pid=os.getpid())

    response = client.get("/lens/os-binding/execution/readiness?actor=test.system.write")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding.execution_readiness"
    assert body["status"] == "blocked"
    assert body["ready"] is False
    assert body["execution_ready"] is False
    requirements = {item["id"]: item for item in body["requirements"]}
    overlay_requirement = requirements["overlay_window"]
    assert overlay_requirement["ready"] is False
    assert overlay_requirement["runtime_ready"] is True
    assert overlay_requirement["runtime_requirement_state"] == "visible"
    assert overlay_requirement["runtime_blocker"] == ""
    assert overlay_requirement["overlay_runtime_readback"]["process_alive"] is True
    assert overlay_requirement["overlay_runtime_readback"]["overlay_window_visible"] is True
    assert overlay_requirement["overlay_runtime_readback"]["always_on_top"] is True
    assert "lens_overlay_window_not_implemented" not in overlay_requirement["blockers"]
    assert "overlay_window_missing" not in overlay_requirement["blockers"]
    assert "overlay_window_disabled" in overlay_requirement["blockers"]
    assert "overlay_control_authority_not_granted" in overlay_requirement["blockers"]
    assert "overlay_window" in body["blocked_execution_prerequisites"]
    assert body["execution_prerequisites_ready"] is False
    assert body["os_level_command_palette"] is False
    assert body["summon_anywhere"] is False
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["window_management_authority"] is False


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
    assert "summon_authority_not_granted" in body["blockers"]
    assert body["governance"]["gate"] == "lens_os_binding_command_palette_execution_denial"
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_decision_authority"] is False
    assert body["governance"]["memory_write"] is False
    assert body["governance"]["hotkey_registration_authority"] is True
    assert body["governance"]["summon_authority"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["local_process_launch_authority"] is True
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
    assert readiness["execution_prerequisites_ready"] is False
    assert readiness["required_before_execution_boundary"] == [
        "system_write_permission",
        "os_binding_readiness_readback",
        "os_binding_implementation_plan",
        "os_binding_authority_grant",
        "os_binding_execution_denial_boundary",
        "os_binding_denial_receipts",
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
        "tray_presence",
        "overlay_window",
    ]
    assert readiness["blocked_execution_prerequisites"] == [
        "global_hotkey_binding",
        "summon_binding",
        "resident_host",
        "tray_presence",
        "overlay_window",
    ]
    assert readiness["blocked_surface_prerequisites"] == readiness["blocked_execution_prerequisites"]
    assert readiness["next_smallest_truthful_gap"] == "os_binding_execution_prerequisites"
    handoff = readiness["execution_boundary_handoff"]
    assert handoff["status"] == "blocked_by_prerequisites"
    assert handoff["route"] == "/lens/os-binding/execute"
    assert handoff["readiness_route"] == "/lens/os-binding/execution/readiness"
    assert handoff["next_step"] == "resolve_os_binding_execution_prerequisites_before_execution_boundary"
    assert handoff["next_smallest_truthful_gap"] == "os_binding_execution_prerequisites"
    assert handoff["blocked_requirements"] == readiness["blocked_execution_prerequisites"]
    assert handoff["blocked_surface_prerequisites"] == readiness["blocked_surface_prerequisites"]
    assert handoff["read_only_contract"] is True
    assert handoff["would_execute"] is False
    assert handoff["would_open_palette"] is False
    assert handoff["would_register_hotkey"] is False
    assert handoff["would_summon"] is False
    assert handoff["would_control_overlay"] is False
    assert handoff["would_launch_process"] is False
    assert handoff["would_write_memory"] is False
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
    assert readiness["governance"]["hotkey_registration_authority"] is True
    assert readiness["governance"]["local_process_launch_authority"] is True
    assert readiness["governance"]["summon_authority"] is False
    assert readiness["governance"]["denial_receipt_write_authority"] is False
    assert readiness["governance"]["mutation_authority_granted"] is False
    assert not (data_root / "runtime" / "lens-host" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-host" / "lens-host.pid").exists()


def test_lens_os_binding_launch_on_hotkey_requires_exact_cross_authority_grants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, _data_root = _client(monkeypatch, tmp_path)
    approval_id, _grant_receipt_id = _grant_lens_authority(
        client,
        request_route="/lens/os-binding/authority/request",
        grant_route="/lens/os-binding/authority",
        reason="request governed OS-binding authority",
    )

    execute = client.post(
        "/lens/os-binding/execute",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "attempt launch-on-hotkey binding without cross grants",
            "run_seconds": 1,
            "allow_launch": True,
        },
    )

    assert execute.status_code == 200
    body = execute.json()
    assert body["kind"] == "lens.os_binding.command_palette_binding.execution_denial"
    assert body["status"] == "blocked"
    assert body["approval_id"] == approval_id
    assert body["allow_launch"] is True
    assert body["launch_on_hotkey"] is False
    assert body["executed"] is False
    assert "summon_approval_id_required_for_launch_on_hotkey" in body["blockers"]
    assert "overlay_approval_id_required_for_launch_on_hotkey" in body["blockers"]
    assert "summon_authority_not_granted_for_launch_on_hotkey" in body["blockers"]
    assert "overlay_control_authority_not_granted_for_launch_on_hotkey" in body["blockers"]
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["hotkey_registration_authority"] is True
    assert body["governance"]["hotkey_launch_on_press_authority"] is False
    assert body["governance"]["summon_authority"] is False
    assert body["governance"]["overlay_control_authority"] is False
    assert body["governance"]["local_process_launch_authority"] is True


def test_lens_os_binding_launch_on_hotkey_records_authorized_runtime_readback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.lens import os_binding_authority as module

    client, data_root = _client(monkeypatch, tmp_path)
    repo_root = data_root.parent
    _write_lens_summon_config(repo_root)

    os_approval_id, os_grant_receipt_id = _grant_lens_authority(
        client,
        request_route="/lens/os-binding/authority/request",
        grant_route="/lens/os-binding/authority",
        reason="request governed OS-binding authority",
    )
    summon_approval_id, summon_grant_receipt_id = _grant_lens_authority(
        client,
        request_route="/lens/summon/authority/request",
        grant_route="/lens/summon/authority",
        reason="request governed summon action authority",
    )
    overlay_approval_id, overlay_grant_receipt_id = _grant_lens_authority(
        client,
        request_route="/lens/overlay/authority/request",
        grant_route="/lens/overlay/authority",
        reason="request governed overlay window authority",
    )

    def fake_hotkey_runner(*, mode: str, run_seconds: int, allow_launch: bool = False) -> dict[str, object]:
        assert mode == "bind"
        assert run_seconds == 1
        assert allow_launch is True
        _write_lens_hotkey_runtime_state(data_root, pid=os.getpid(), launch_on_hotkey=True)
        return {
            "ok": True,
            "status": "started",
            "script_mode": "Start",
            "blockers": [],
            "runner": {
                "ok": True,
                "status": "started",
                "launch_on_hotkey": True,
            },
        }

    monkeypatch.setattr(module, "_run_lens_os_binding_hotkey_action", fake_hotkey_runner)

    result = module.execute_lens_os_binding(
        approval_id=os_approval_id,
        summon_approval_id=summon_approval_id,
        overlay_approval_id=overlay_approval_id,
        actor="test.system.write",
        reason="bind hotkey with governed launch handoff authority",
        route="/lens/os-binding/execute",
        method="POST",
        record_receipt=True,
        mode="bind",
        run_seconds=1,
        allow_launch=True,
    )

    assert result["kind"] == "lens.os_binding.command_palette_binding.execution"
    assert result["status"] == "global_hotkey_bound"
    assert result["approval_id"] == os_approval_id
    assert result["active_grant_receipt_id"] == os_grant_receipt_id
    assert result["summon_approval_id"] == summon_approval_id
    assert result["summon_authority_grant_receipt_id"] == summon_grant_receipt_id
    assert result["overlay_approval_id"] == overlay_approval_id
    assert result["overlay_authority_grant_receipt_id"] == overlay_grant_receipt_id
    assert result["allow_launch"] is True
    assert result["global_hotkey_binding"] is True
    assert result["hotkey_runtime_ready"] is True
    assert result["launch_on_hotkey"] is True
    assert result["summon_anywhere"] is False
    assert result["next_smallest_truthful_gap"] == "summon_binding"
    assert result["governance"]["execution_authority"] is True
    assert result["governance"]["hotkey_registration_authority"] is True
    assert result["governance"]["hotkey_launch_on_press_authority"] is True
    assert result["governance"]["summon_authority"] is True
    assert result["governance"]["overlay_control_authority"] is True
    assert result["governance"]["window_management_authority"] is True
    assert result["governance"]["local_process_launch_authority"] is True
    assert result["governance"]["next_step"] == (
        "continue_with_summon_anywhere_runtime_readback_after_launch_hotkey_binding"
    )
    assert result["receipt_written"] is True
    receipt = result["receipt"]
    assert receipt["kind"] == "lens.os_binding.command_palette_binding.execution_receipt"
    assert receipt["active_grant_receipt_id"] == os_grant_receipt_id
    assert receipt["summon_authority_grant_receipt_id"] == summon_grant_receipt_id
    assert receipt["overlay_authority_grant_receipt_id"] == overlay_grant_receipt_id
    assert receipt["execution"]["allow_launch"] is True
    assert receipt["execution"]["launch_on_hotkey"] is True


def test_lens_os_binding_execute_surfaces_owned_global_hotkey_blocker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from francis.lens import os_binding_authority as module

    client, data_root = _client(monkeypatch, tmp_path)
    repo_root = data_root.parent
    _write_lens_summon_config(repo_root)

    os_approval_id, _os_grant_receipt_id = _grant_lens_authority(
        client,
        request_route="/lens/os-binding/authority/request",
        grant_route="/lens/os-binding/authority",
        reason="request governed OS-binding authority",
    )

    def fake_hotkey_runner(*, mode: str, run_seconds: int, allow_launch: bool = False) -> dict[str, object]:
        assert mode == "bind"
        assert run_seconds == 1
        assert allow_launch is False
        _write_lens_hotkey_owned_runtime_state(data_root)
        return {
            "ok": False,
            "status": "hotkey_already_owned",
            "script_mode": "Start",
            "blockers": ["hotkey_already_owned"],
            "runner": {
                "ok": False,
                "status": "hotkey_already_owned",
                "blocker": "hotkey_already_owned",
                "win32_error": 1409,
            },
        }

    monkeypatch.setattr(module, "_run_lens_os_binding_hotkey_action", fake_hotkey_runner)

    result = module.execute_lens_os_binding(
        approval_id=os_approval_id,
        actor="test.system.write",
        reason="bind hotkey with an already-owned global chord",
        route="/lens/os-binding/execute",
        method="POST",
        record_receipt=False,
        mode="bind",
        run_seconds=1,
        allow_launch=False,
    )

    assert result["kind"] == "lens.os_binding.command_palette_binding.execution"
    assert result["status"] == "hotkey_already_owned"
    assert result["applied"] is False
    assert result["executed"] is False
    assert result["global_hotkey"] == "Ctrl+Alt+F"
    assert result["global_hotkey_binding"] is False
    assert result["hotkey_runtime_ready"] is False
    assert result["hotkey_runtime_readback"]["requirement_state"] == "blocked"
    assert result["hotkey_runtime_readback"]["blocker"] == "hotkey_already_owned"
    assert result["hotkey_runtime_readback"]["runtime_status"] == "hotkey_already_owned"
    assert result["hotkey_runtime_readback"]["runtime_status_error"] == "hotkey_already_owned"
    assert result["hotkey_runtime_readback"]["win32_error"] == 1409
    assert result["hotkey_runtime_readback"]["registration_failure"]["global_hotkey"] == "Ctrl+Alt+F"
    assert result["next_smallest_truthful_gap"] == "choose_unclaimed_global_hotkey"
    assert result["blockers"] == ["hotkey_already_owned"]
    assert result["authority_granted"] is True
    assert result["os_level_command_palette_binding_authority"] is True
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["hotkey_registration_authority"] is False
