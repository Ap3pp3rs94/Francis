from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_connector_script(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env.pop("FRANCIS_CHATGPT_VOICE_CONNECTOR_URL", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "chatgpt-voice-connector.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
        env=run_env,
    )


def test_chatgpt_voice_connector_resolves_cross_platform_powershell_for_status_readback() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "function Resolve-PowerShellHost" in script
    assert "Get-Command powershell -ErrorAction SilentlyContinue" in script
    assert "Get-Command pwsh -ErrorAction SilentlyContinue" in script
    assert "$StartProcessArgs.WindowStyle = 'Hidden'" in script
    assert "$Process = Start-Process @StartProcessArgs" in script
    assert "status = 'status_timeout'" in script
    assert "$Raw = & powershell @Args 2>&1" not in script


def test_chatgpt_voice_connector_restart_mcp_preserves_public_tunnel_contract() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "RestartMcp" in script
    assert "if ($Mode -eq 'RestartMcp')" in script
    assert "ExpectedCommandText 'francis.mcp_gateway.server'" in script
    assert "ExpectedCommandText 'chatgpt-voice-mcp.ps1'" in script
    assert "public_tunnel_restarted = $false" in script
    assert "cloudflared_login = Get-PropertyValue -Payload $State -Name 'cloudflared_login' -Default $null" in script
    assert "OpensPublicTunnel $false -WritesData $true" in script


def test_chatgpt_voice_connector_start_persistent_never_opens_localtunnel() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "StartPersistent" in script
    assert "if ($Mode -eq 'StartPersistent')" in script
    assert "status = 'connector_url_not_persistent'" in script
    assert "public_tunnel_started = $false" in script
    assert "localtunnel_fallback" in script
    assert "$McpProcess = Start-McpLauncher -ConnectorHost $ConnectorHost" in script
    assert "mcp_log_capture = 'not_captured_detached_start'" in script
    assert "$Payload.status = if ($ConnectorReady)" in script
    assert "OpensPublicTunnel $false -WritesData $true" in script


def test_chatgpt_voice_connector_cloudflared_quick_mode_is_truthfully_ephemeral() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "StartCloudflaredQuick" in script
    assert "cloudflared_quick_ephemeral" in script
    assert "known_cloudflared_quick_tunnel" in script
    assert "cloudflared_quick_url_is_not_persistent_ingress" in script
    assert "cloudflared_quick_started_ready" in script
    assert "persistent_candidate = $false" in script
    assert "OpensPublicTunnel $true -WritesData $true" in script


def test_chatgpt_voice_connector_cloudflared_named_mode_is_bounded_persistent_ingress() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "StartCloudflaredLogin" in script
    assert "AuthorizeCloudflaredLogin" in script
    assert "provider_login_writes_origin_cert" in script
    assert "StartCloudflaredNamed" in script
    assert "CloudflaredTunnelName" in script
    assert "CloudflaredHostname" in script
    assert "cloudflared_named_tunnel" in script
    assert "cloudflared_named_started_ready" in script
    assert "cloudflared_named_hostname_mismatch" in script
    assert "$TunnelArgs += @('run', $BoundedTunnelName)" in script
    assert "public_tunnel_started = $TunnelAlive" in script
    assert "connector_url_recorded = $true" in script
    assert "public_connector_verified = $ConnectorReady" in script
    assert "cloudflared_named_connector_unverified" in script
    assert "verify_cloudflared_hostname_route_and_chatgpt_connector_url" in script
    assert "inspect_cloudflared_named_tunnel_logs" in script
    assert "persistent_candidate = $true" in script
    assert "OpensPublicTunnel $false -WritesData $true" in script
    assert "OpensPublicTunnel $true -WritesData $true" in script
    assert "start_cloudflared_named" in script


def test_chatgpt_voice_connector_cloudflared_token_mode_uses_secret_file_contract() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "StartCloudflaredToken" in script
    assert "CloudflaredTokenFile" in script
    assert "Get-CloudflaredTokenTunnelReadiness" in script
    assert "dashboard_managed_https_tunnel_token_file" in script
    assert "token_file_content_read = $false" in script
    assert "cloudflared_token_tunnel" in script
    assert "'--token-file', $BoundedTokenFile" in script
    assert "'--url', \"http://$HostAddress`:$Port\"" in script
    assert "cloudflared_token_started_ready" in script
    assert "start_cloudflared_token" in script
    assert "do not paste token contents into chat" in script


def test_chatgpt_voice_connector_plan_reuses_cloudflared_resolver_for_readiness() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "function Resolve-CloudflaredPath" in script
    assert "function Get-CloudflaredOriginCertReadiness" in script
    assert "function Get-CloudflaredNamedTunnelReadiness" in script
    assert "function Get-CloudflaredTokenTunnelReadiness" in script
    assert "[string]$ResolvedPath = ''" in script
    assert "Get-CommandReadiness -Name 'cloudflared'" in script
    assert "named_tunnel_preflight" in script
    assert "choose_cloudflared_dashboard_token_file" in script
    assert "create_cloudflared_named_tunnel_and_route_hostname" in script
    assert "choose_cloudflared_named_hostname" in script
    assert "origin_cert_content_read" in script
    assert "run_cloudflared_tunnel_login" in script
    assert "standard install location" in script


def test_chatgpt_voice_connector_localtunnel_fallback_detaches_tunnel_process() -> None:
    script = (_repo_root() / "scripts" / "chatgpt-voice-connector.ps1").read_text(encoding="utf-8")

    assert "status = 'localtunnel_subdomain_required'" in script
    assert "$TunnelLogCapture = 'not_captured_detached_start'" in script
    assert "Start-Process -FilePath 'node' -ArgumentList $TunnelArgs -PassThru -WindowStyle Hidden" in script
    assert "Wait-ForTunnelUrl -StdoutPath $TunnelStdout" not in script
    assert "tunnel_log_capture = $TunnelLogCapture" in script


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_status_is_read_only_without_runtime_state(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "not_started"
    assert payload["connector_url"] == ""
    assert payload["endpoint_status"]["status"] == "local_listener_missing"
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_restart_mcp_requires_runtime_state(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "RestartMcp",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "mcp_runtime_state_required"
    assert payload["blockers"] == ["runtime_state_required"]
    assert payload["governance"]["read_only"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_requires_explicit_public_tunnel_authorization(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Start",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "operator_public_tunnel_authorization_required"
    assert payload["blockers"] == ["expose_public_tunnel_flag_required"]
    assert payload["governance"]["read_only"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_status_accepts_manual_connector_url(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis.example.test/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_started"
    assert payload["connector_url"] == "https://francis.example.test/mcp"
    assert payload["connector_url_source"] == "argument"
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_url"]["shape_valid"] is True
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_probe_timeout_seconds"] == 5
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_status_accepts_environment_connector_url(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        env={"FRANCIS_CHATGPT_VOICE_CONNECTOR_URL": "https://francis-env.example.test/mcp"},
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_started"
    assert payload["connector_url"] == "https://francis-env.example.test/mcp"
    assert payload["connector_url_source"] == "environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL"
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_url"]["shape_valid"] is True
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_probe_timeout_seconds"] == 5
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_named_requires_public_tunnel_flag(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredNamed",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTunnelName",
        "francis",
        "-CloudflaredHostname",
        "francis.example.test",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "operator_public_tunnel_authorization_required"
    assert payload["blockers"] == ["expose_public_tunnel_flag_required"]
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_token_requires_public_tunnel_flag(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    token_file = tmp_path / "cloudflared-token.txt"
    token_file.write_text("test-token", encoding="utf-8")
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredToken",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTokenFile",
        str(token_file),
        "-CloudflaredHostname",
        "francis.example.test",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "operator_public_tunnel_authorization_required"
    assert payload["blockers"] == ["expose_public_tunnel_flag_required"]
    assert payload["cloudflared_token_start"]["public_tunnel_started"] is False
    assert payload["cloudflared_token_start"]["connector_url_recorded"] is False
    assert payload["cloudflared_token_start"]["token_file_content_read"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_token_requires_token_file_before_state_writes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    missing_token_file = tmp_path / "missing-cloudflared-token.txt"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredToken",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTokenFile",
        str(missing_token_file),
        "-CloudflaredHostname",
        "francis.example.test",
        "-ExposePublicTunnel",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "cloudflared_token_file_missing"
    assert payload["blockers"] == ["cloudflared_token_file_missing"]
    assert payload["cloudflared_token_start"]["public_tunnel_started"] is False
    assert payload["cloudflared_token_start"]["connector_url_recorded"] is False
    assert payload["cloudflared_token_start"]["token_file_content_read"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_login_requires_authorization(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredLogin",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "operator_cloudflared_login_authorization_required"
    assert payload["blockers"] == ["authorize_cloudflared_login_flag_required"]
    assert payload["next_operator_step"] == "rerun_with_authorize_cloudflared_login"
    assert payload["cloudflared_login"]["provider_login_started"] is False
    assert payload["cloudflared_login"]["public_tunnel_started"] is False
    assert payload["cloudflared_login"]["connector_url_recorded"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_login_persists_provider_login_state(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    fake_profile = tmp_path / "profile"
    fake_bin = tmp_path / "bin"
    fake_profile.mkdir()
    fake_bin.mkdir()
    fake_cloudflared = fake_bin / "cloudflared.cmd"
    fake_cloudflared.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredLogin",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-AuthorizeCloudflaredLogin",
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": "",
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is True
    assert payload["status"] in {"cloudflared_login_started", "cloudflared_login_started_process_not_alive"}
    assert payload["cloudflared_login"]["status"] == payload["status"]
    assert payload["cloudflared_login"]["provider_login_started"] is True
    assert payload["cloudflared_login"]["provider_login_browser_may_open"] is True
    assert payload["cloudflared_login"]["provider_login_writes_origin_cert"] is True
    assert payload["cloudflared_login"]["public_tunnel_started"] is False
    assert payload["cloudflared_login"]["connector_url_recorded"] is False
    assert payload["cloudflared_login"]["origin_cert_present"] is False
    assert payload["cloudflared_login"]["origin_cert_content_read"] is False
    assert payload["governance"]["starts_process"] is True
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is True

    state_path = runtime_root / "status.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["status"] == payload["status"]
    assert state["cloudflared_login"]["status"] == payload["status"]
    assert state["cloudflared_login"]["provider_login_started"] is True
    assert state["cloudflared_login"]["public_tunnel_started"] is False
    assert state["cloudflared_login"]["connector_url_recorded"] is False
    assert state["cloudflared_login"]["origin_cert_content_read"] is False
    assert state["governance"]["starts_process"] is True
    assert state["governance"]["opens_public_tunnel"] is False
    assert state["governance"]["writes_data"] is True

    status = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": "",
        },
    )

    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["status"] == payload["status"]
    assert status_payload["cloudflared_login"]["status"] == payload["status"]
    assert status_payload["cloudflared_login"]["provider_login_started"] is True
    assert status_payload["cloudflared_login"]["public_tunnel_started"] is False
    assert status_payload["cloudflared_login"]["connector_url_recorded"] is False
    assert status_payload["cloudflared_login"]["origin_cert_content_read"] is False
    assert status_payload["governance"]["read_only"] is True

    plan = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": "",
        },
    )

    assert plan.returncode == 0, plan.stderr
    plan_payload = json.loads(plan.stdout)
    assert plan_payload["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    assert plan_payload["cloudflared_login"]["status"] == payload["status"]
    assert plan_payload["cloudflared_login"]["provider_login_started"] is True
    assert plan_payload["cloudflared_login"]["public_tunnel_started"] is False
    assert plan_payload["cloudflared_login"]["connector_url_recorded"] is False
    assert plan_payload["cloudflared_login"]["origin_cert_content_read"] is False
    assert plan_payload["governance"]["read_only"] is True
    assert plan_payload["governance"]["starts_process"] is False
    assert plan_payload["governance"]["opens_public_tunnel"] is False
    assert plan_payload["governance"]["writes_data"] is False


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_named_requires_tunnel_name(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredNamed",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredHostname",
        "francis.example.test",
        "-ExposePublicTunnel",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "cloudflared_named_tunnel_name_required"
    assert payload["blockers"] == ["cloudflared_tunnel_name_required"]
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_named_requires_login_before_state_writes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    fake_profile = tmp_path / "profile"
    fake_bin = tmp_path / "bin"
    fake_profile.mkdir()
    fake_bin.mkdir()
    fake_cloudflared = fake_bin / "cloudflared.cmd"
    fake_cloudflared.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredNamed",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTunnelName",
        "francis",
        "-CloudflaredHostname",
        "francis.example.test",
        "-ExposePublicTunnel",
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": "",
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "cloudflared_login_required"
    assert payload["blockers"] == ["cloudflared_login_required"]
    assert payload["next_operator_step"] == "run_start_cloudflared_login"
    assert "StartCloudflaredLogin" in payload["governed_handoff_command"]
    assert payload["cloudflared_named_start"]["existing_bridge_stopped"] is False
    assert payload["cloudflared_named_start"]["public_tunnel_started"] is False
    assert payload["cloudflared_named_start"]["connector_url_recorded"] is False
    assert payload["cloudflared_named_start"]["origin_cert_content_read"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_cloudflared_named_requires_existing_named_tunnel(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    fake_profile = tmp_path / "profile"
    fake_bin = tmp_path / "bin"
    fake_profile.mkdir()
    fake_bin.mkdir()
    fake_origin_cert = fake_profile / "cert.pem"
    fake_origin_cert.write_text("fake test cert", encoding="utf-8")
    fake_cloudflared = fake_bin / "cloudflared.cmd"
    fake_cloudflared.write_text(
        '@echo off\r\nif "%1"=="tunnel" if "%2"=="info" exit /b 1\r\nexit /b 0\r\n',
        encoding="utf-8",
    )
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartCloudflaredNamed",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTunnelName",
        "francis",
        "-CloudflaredHostname",
        "francis.example.test",
        "-ExposePublicTunnel",
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": str(fake_origin_cert),
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "cloudflared_named_tunnel_missing"
    assert payload["blockers"] == ["cloudflared_named_tunnel_missing"]
    assert payload["next_operator_step"] == "create_cloudflared_named_tunnel_and_route_hostname"
    assert payload["cloudflared_named_tunnel_preflight"]["checked"] is True
    assert payload["cloudflared_named_tunnel_preflight"]["exists"] is False
    assert payload["cloudflared_named_tunnel_preflight"]["output_discarded"] is True
    assert payload["operator_provider_setup_commands"] == [
        "cloudflared tunnel create francis",
        "cloudflared tunnel route dns francis francis.example.test",
    ]
    assert payload["cloudflared_named_start"]["existing_bridge_stopped"] is False
    assert payload["cloudflared_named_start"]["public_tunnel_started"] is False
    assert payload["cloudflared_named_start"]["connector_url_recorded"] is False
    assert payload["cloudflared_named_start"]["provider_tunnel_created"] is False
    assert payload["cloudflared_named_start"]["provider_route_created"] is False
    assert payload["cloudflared_named_start"]["preflight_output_discarded"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_is_read_only(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    assert payload["ok"] is True
    assert payload["status"] == "persistent_ingress_url_needed"
    assert payload["local_endpoint"] == f"http://127.0.0.1:{port}/mcp"
    assert payload["connector_url"]["provided"] is False
    assert payload["connector_url"]["shape_valid"] is False
    assert payload["connector_url"]["source"] == "none"
    assert payload["connector_url"]["reason"] == "connector_url_not_provided"
    assert "RecordUrl" in payload["connector_url"]["record_command"]
    assert payload["provider_readiness"]["cloudflared_named_tunnel"]["name"] == "cloudflared"
    assert payload["provider_readiness"]["cloudflared_named_tunnel"]["named_tunnel_requested"] is False
    assert payload["provider_readiness"]["cloudflared_named_tunnel"]["named_tunnel_preflight"]["checked"] is False
    assert payload["provider_readiness"]["cloudflared_token_tunnel"]["name"] == "cloudflared"
    assert payload["provider_readiness"]["cloudflared_token_tunnel"]["token_file_requested"] is False
    assert payload["provider_readiness"]["cloudflared_token_tunnel"]["token_file_present"] is False
    assert payload["provider_readiness"]["cloudflared_token_tunnel"]["token_file_content_read"] is False
    assert payload["provider_readiness"]["cloudflared_token_tunnel"]["next_operator_step"] == (
        "choose_cloudflared_dashboard_token_file"
    )
    assert payload["provider_readiness"]["ngrok_reserved_domain"]["name"] == "ngrok"
    assert payload["provider_readiness"]["caddy_reverse_proxy"]["name"] == "caddy"
    assert payload["provider_readiness"]["ssh_reverse_tunnel"]["name"] == "ssh"
    assert payload["installer_readiness"]["winget"]["name"] == "winget"
    assert payload["installer_readiness"]["choco"]["name"] == "choco"
    assert payload["installer_readiness"]["scoop"]["name"] == "scoop"
    assert payload["install_command_hints"]["cloudflared_winget"] == (
        "winget install --id Cloudflare.cloudflared --exact"
    )
    assert payload["install_command_hints"]["ngrok_winget"] == "winget install --id Ngrok.Ngrok --exact"
    assert payload["install_command_hints"]["caddy_winget"] == "winget install --id CaddyServer.Caddy --exact"
    handoff = payload["operator_handoff"]
    assert handoff["kind"] == "francis.chatgpt_voice.persistent_ingress_operator_handoff"
    assert handoff["read_only_plan"] is True
    assert handoff["installs_provider"] is False
    assert handoff["opens_tunnel"] is False
    assert handoff["writes_state"] is False
    assert handoff["preferred_provider"] == "cloudflared_named_tunnel"
    assert handoff["local_endpoint"] == f"http://127.0.0.1:{port}/mcp"
    assert handoff["stable_url_placeholder"] == "https://YOUR-STABLE-HOST/mcp"
    assert handoff["install_commands"]["cloudflared_winget"] == (
        "winget install --id Cloudflare.cloudflared --exact --accept-source-agreements --accept-package-agreements"
    )
    assert "cloudflared tunnel login" in handoff["cloudflared_named_tunnel_steps"][1]
    assert "Cloudflare Tunnel in the Zero Trust dashboard" in handoff["cloudflared_token_tunnel_steps"][0]
    assert "do not paste token contents into chat" in handoff["cloudflared_token_tunnel_steps"][2]
    assert "StartCloudflaredLogin" in handoff["governed_handoff_commands"]["start_cloudflared_login"]
    assert "-AuthorizeCloudflaredLogin" in handoff["governed_handoff_commands"]["start_cloudflared_login"]
    assert "PlanPersistentIngress" in handoff["governed_handoff_commands"]["plan_cloudflared_named"]
    assert "CloudflaredTunnelName" in handoff["governed_handoff_commands"]["plan_cloudflared_named"]
    assert "RecordUrl" in handoff["governed_handoff_commands"]["record_url"]
    assert "StartPersistent" in handoff["governed_handoff_commands"]["start_persistent_mcp"]
    assert "StartCloudflaredNamed" in handoff["governed_handoff_commands"]["start_cloudflared_named"]
    assert "-ExposePublicTunnel" in handoff["governed_handoff_commands"]["start_cloudflared_named"]
    assert "StartCloudflaredToken" in handoff["governed_handoff_commands"]["start_cloudflared_token"]
    assert "CloudflaredTokenFile" in handoff["governed_handoff_commands"]["start_cloudflared_token"]
    assert "orb-voice-overlay-lens-validation.ps1" in handoff["governed_handoff_commands"]["validate_bridge"]
    assert "lens-command-palette-monitor.ps1" in handoff["governed_handoff_commands"]["monitor_command_palette"]
    assert "http://127.0.0.1:8787" in payload["provider_config_hints"]["cloudflared_named_tunnel"]
    assert "http://127.0.0.1:8787" in payload["provider_config_hints"]["cloudflared_token_tunnel"]
    assert payload["recommended_provider_order"][:2] == [
        "cloudflared_token_tunnel",
        "cloudflared_named_tunnel",
    ]
    assert payload["localtunnel_replacement"]["localtunnel_supported_only_as_explicit_fallback"] is True
    assert payload["localtunnel_replacement"]["persistent_ingress_required_for_stable_chatgpt_connector"] is True
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_tolerates_missing_windows_install_roots(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    empty_path = tmp_path / "empty-path"
    fake_profile = tmp_path / "profile"
    empty_path.mkdir()
    fake_profile.mkdir()
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        env={
            "PATH": str(empty_path),
            "Path": str(empty_path),
            "ProgramFiles": "",
            "ProgramFiles(x86)": "",
            "TUNNEL_ORIGIN_CERT": "",
            "USERPROFILE": str(fake_profile),
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    cloudflared = payload["provider_readiness"]["cloudflared_named_tunnel"]
    assert cloudflared["available"] is False
    assert cloudflared["path"] == ""
    assert cloudflared["origin_cert_present"] is False
    assert cloudflared["login_required"] is True
    assert cloudflared["named_tunnel_preflight"]["checked"] is False
    assert cloudflared["operator_provider_setup_commands"] == []
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_preflights_named_tunnel_request(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    fake_profile = tmp_path / "profile"
    fake_bin = tmp_path / "bin"
    fake_profile.mkdir()
    fake_bin.mkdir()
    fake_origin_cert = fake_profile / "cert.pem"
    fake_origin_cert.write_text("fake test cert", encoding="utf-8")
    fake_cloudflared = fake_bin / "cloudflared.cmd"
    fake_cloudflared.write_text(
        '@echo off\r\nif "%1"=="tunnel" if "%2"=="info" exit /b 1\r\nexit /b 0\r\n',
        encoding="utf-8",
    )
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTunnelName",
        "francis",
        "-CloudflaredHostname",
        "francis.example.test",
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": str(fake_origin_cert),
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    cloudflared = payload["provider_readiness"]["cloudflared_named_tunnel"]
    assert cloudflared["available"] is True
    assert cloudflared["origin_cert_present"] is True
    assert cloudflared["origin_cert_content_read"] is False
    assert cloudflared["login_required"] is False
    assert cloudflared["requested_tunnel_name"] == "francis"
    assert cloudflared["requested_hostname"] == "francis.example.test"
    assert cloudflared["named_tunnel_requested"] is True
    assert cloudflared["named_tunnel_exists"] is False
    assert cloudflared["named_tunnel_preflight"]["checked"] is True
    assert cloudflared["named_tunnel_preflight"]["exists"] is False
    assert cloudflared["named_tunnel_preflight"]["output_discarded"] is True
    assert cloudflared["operator_provider_setup_commands"] == [
        "cloudflared tunnel create francis",
        "cloudflared tunnel route dns francis francis.example.test",
    ]
    assert cloudflared["next_operator_step"] == "create_cloudflared_named_tunnel_and_route_hostname"
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_preflights_token_file_request(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    fake_profile = tmp_path / "profile"
    fake_bin = tmp_path / "bin"
    token_file = tmp_path / "cloudflared-token.txt"
    fake_profile.mkdir()
    fake_bin.mkdir()
    token_file.write_text("test-token", encoding="utf-8")
    fake_cloudflared = fake_bin / "cloudflared.cmd"
    fake_cloudflared.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTokenFile",
        str(token_file),
        "-CloudflaredHostname",
        "francis.example.test",
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": "",
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    cloudflared_token = payload["provider_readiness"]["cloudflared_token_tunnel"]
    assert cloudflared_token["available"] is True
    assert cloudflared_token["token_file_requested"] is True
    assert cloudflared_token["token_file_present"] is True
    assert cloudflared_token["token_file_content_read"] is False
    assert cloudflared_token["requested_hostname"] == "francis.example.test"
    assert cloudflared_token["hostname_requested"] is True
    assert cloudflared_token["next_operator_step"] == "start_cloudflared_token_tunnel"
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_does_not_emit_blank_dns_route(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    fake_profile = tmp_path / "profile"
    fake_bin = tmp_path / "bin"
    fake_profile.mkdir()
    fake_bin.mkdir()
    fake_origin_cert = fake_profile / "cert.pem"
    fake_origin_cert.write_text("fake test cert", encoding="utf-8")
    fake_cloudflared = fake_bin / "cloudflared.cmd"
    fake_cloudflared.write_text(
        '@echo off\r\nif "%1"=="tunnel" if "%2"=="info" exit /b 1\r\nexit /b 0\r\n',
        encoding="utf-8",
    )
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-CloudflaredTunnelName",
        "francis",
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "USERPROFILE": str(fake_profile),
            "TUNNEL_ORIGIN_CERT": str(fake_origin_cert),
        },
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    cloudflared = payload["provider_readiness"]["cloudflared_named_tunnel"]
    assert cloudflared["requested_tunnel_name"] == "francis"
    assert cloudflared["requested_hostname"] == ""
    assert cloudflared["named_tunnel_requested"] is True
    assert cloudflared["named_tunnel_exists"] is False
    assert cloudflared["operator_provider_setup_commands"] == [
        "cloudflared tunnel create francis",
    ]
    assert cloudflared["next_operator_step"] == "choose_cloudflared_named_hostname"
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_accepts_stable_url_shape(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis.example.test/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "connector_url_shape_valid_record_ready"
    assert payload["connector_url"]["provided"] is True
    assert payload["connector_url"]["shape_valid"] is True
    assert payload["connector_url"]["source"] == "argument"
    assert payload["connector_url"]["reason"] == "connector_url_shape_valid_reachability_not_verified"
    assert payload["connector_url"]["persistent_candidate"] is True
    assert payload["connector_url"]["host"] == "francis.example.test"
    assert payload["connector_url"]["ingress_profile"]["profile"] == "persistent_https_candidate"
    assert payload["connector_url"]["ingress_profile"]["persistent_candidate"] is True
    assert payload["blockers"] == []
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_flags_localtunnel_fallback(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis-voice-178175.loca.lt/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    assert payload["status"] == "localtunnel_fallback_replace_needed"
    assert payload["connector_url"]["provided"] is True
    assert payload["connector_url"]["shape_valid"] is True
    assert payload["connector_url"]["persistent_candidate"] is False
    assert payload["connector_url"]["host"] == "francis-voice-178175.loca.lt"
    assert payload["connector_url"]["ingress_profile"]["profile"] == "localtunnel_ephemeral"
    assert payload["connector_url"]["ingress_profile"]["known_localtunnel"] is True
    assert payload["connector_url"]["ingress_profile"]["persistent_candidate"] is False
    assert payload["blockers"] == ["localtunnel_url_is_not_persistent_ingress"]
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


def test_chatgpt_voice_connector_plan_persistent_ingress_flags_cloudflared_quick_tunnel(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "PlanPersistentIngress",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://example.trycloudflare.com/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.persistent_ingress_plan"
    assert payload["status"] == "cloudflared_quick_tunnel_replace_needed"
    assert payload["connector_url"]["provided"] is True
    assert payload["connector_url"]["shape_valid"] is True
    assert payload["connector_url"]["persistent_candidate"] is False
    assert payload["connector_url"]["host"] == "example.trycloudflare.com"
    assert payload["connector_url"]["ingress_profile"]["profile"] == "cloudflared_quick_ephemeral"
    assert payload["connector_url"]["ingress_profile"]["known_cloudflared_quick_tunnel"] is True
    assert payload["connector_url"]["ingress_profile"]["persistent_candidate"] is False
    assert payload["blockers"] == ["cloudflared_quick_url_is_not_persistent_ingress"]
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_record_url_persists_without_tunnel(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    recorded = _run_connector_script(
        "-Mode",
        "RecordUrl",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis.example.test/mcp",
    )

    assert recorded.returncode == 0, recorded.stderr
    payload = json.loads(recorded.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is True
    assert payload["status"] == "persistent_connector_url_recorded"
    assert payload["connector_url"] == "https://francis.example.test/mcp"
    assert payload["connector_url_source"] == "argument"
    assert payload["ingress_mode"] == "persistent_https"
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_url"]["shape_valid"] is True
    assert payload["processes"]["mcp_launcher"]["pid"] == 0
    assert payload["processes"]["tunnel"]["pid"] == 0
    assert payload["governance"]["read_only"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is True
    assert payload["governance"]["grants_execution_authority"] is False

    state_path = runtime_root / "status.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["status"] == "persistent_connector_url_recorded"
    assert state["ingress_mode"] == "persistent_https"
    assert state["connector_url"] == "https://francis.example.test/mcp"
    assert state["connector_url_source"] == "argument"
    assert state["mcp_launcher_pid"] == 0
    assert state["tunnel_pid"] == 0
    assert state["governance"]["opens_public_tunnel"] is False
    assert state["governance"]["starts_process"] is False

    status = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["status"] == "runtime_state_observed"
    assert status_payload["connector_url"] == "https://francis.example.test/mcp"
    assert status_payload["connector_url_source"] == "runtime_state"
    assert status_payload["ingress_mode"] == "persistent_https"
    assert status_payload["endpoint_status"]["chatgpt_connector"]["connector_url"]["shape_valid"] is True
    assert status_payload["governance"]["read_only"] is True
    assert status_payload["governance"]["starts_process"] is False
    assert status_payload["governance"]["opens_public_tunnel"] is False


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_persistent_rejects_localtunnel(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartPersistent",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis-voice-178175.loca.lt/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "connector_url_not_persistent"
    assert payload["connector_ingress_profile"]["profile"] == "localtunnel_ephemeral"
    assert payload["blockers"] == ["localtunnel_url_is_not_persistent_ingress"]
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_start_persistent_rejects_cloudflared_quick_tunnel(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "StartPersistent",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://example.trycloudflare.com/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "connector_url_not_persistent"
    assert payload["connector_ingress_profile"]["profile"] == "cloudflared_quick_ephemeral"
    assert payload["connector_ingress_profile"]["known_cloudflared_quick_tunnel"] is True
    assert payload["connector_ingress_profile"]["persistent_candidate"] is False
    assert payload["blockers"] == ["cloudflared_quick_url_is_not_persistent_ingress"]
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_record_url_accepts_environment_connector_url(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    recorded = _run_connector_script(
        "-Mode",
        "RecordUrl",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        env={"FRANCIS_CHATGPT_VOICE_CONNECTOR_URL": "https://francis-env.example.test/mcp"},
    )

    assert recorded.returncode == 0, recorded.stderr
    payload = json.loads(recorded.stdout)
    assert payload["ok"] is True
    assert payload["status"] == "persistent_connector_url_recorded"
    assert payload["connector_url"] == "https://francis-env.example.test/mcp"
    assert payload["connector_url_source"] == "environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL"
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is True
    state = json.loads((runtime_root / "status.json").read_text(encoding="utf-8-sig"))
    assert state["connector_url"] == "https://francis-env.example.test/mcp"
    assert state["connector_url_source"] == "environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL"


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_status_flags_localtunnel_subdomain_drift(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    runtime_root.mkdir(parents=True)
    port = _unused_local_port()
    state_path = runtime_root / "status.json"
    state_path.write_text(
        json.dumps(
            {
                "kind": "francis.chatgpt_voice.connector_control.state",
                "status": "started",
                "connector_url": "https://giant-seahorse-21.loca.lt/mcp",
                "connector_url_source": "localtunnel",
                "connector_host": "giant-seahorse-21.loca.lt",
                "requested_tunnel_subdomain": "francis-voice-178175",
                "requested_connector_host": "francis-voice-178175.loca.lt",
                "local_endpoint": f"http://127.0.0.1:{port}/mcp",
                "mcp_launcher_pid": 0,
                "tunnel_pid": 0,
                "updated_at": "2026-06-18T00:00:00Z",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    proc = _run_connector_script(
        "-Mode",
        "Status",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "runtime_state_observed_unstable_localtunnel_url"
    assert payload["connector_url"] == "https://giant-seahorse-21.loca.lt/mcp"
    assert payload["connector_url_source"] == "runtime_state"
    assert payload["localtunnel"]["applicable"] is True
    assert payload["localtunnel"]["requested_subdomain"] == "francis-voice-178175"
    assert payload["localtunnel"]["requested_host"] == "francis-voice-178175.loca.lt"
    assert payload["localtunnel"]["actual_host"] == "giant-seahorse-21.loca.lt"
    assert payload["localtunnel"]["requested_subdomain_honored"] is False
    assert payload["localtunnel"]["stable_for_existing_chatgpt_connector"] is False
    assert payload["localtunnel"]["reason"] == "localtunnel_requested_subdomain_not_honored"
    assert payload["blockers"] == ["localtunnel_requested_subdomain_not_honored"]
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["opens_public_tunnel"] is False


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_record_url_rejects_invalid_shape_without_writing(tmp_path: Path) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "RecordUrl",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "http://127.0.0.1:8787/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "connector_url_shape_invalid"
    assert payload["connector_url_source"] == "argument"
    assert payload["blockers"] == ["connector_url_must_be_https"]
    assert payload["endpoint_status"]["chatgpt_connector"]["connector_url"]["shape_valid"] is False
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()


@pytest.mark.skipif(platform.system() != "Windows", reason="connector control uses Windows process readback")
def test_chatgpt_voice_connector_record_url_rejects_localtunnel_as_persistent_ingress(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "connector-runtime"
    port = _unused_local_port()

    proc = _run_connector_script(
        "-Mode",
        "RecordUrl",
        "-Json",
        "-RuntimeRoot",
        str(runtime_root),
        "-Port",
        str(port),
        "-ConnectorUrl",
        "https://francis-voice-178175.loca.lt/mcp",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.chatgpt_voice.connector_control"
    assert payload["ok"] is False
    assert payload["status"] == "connector_url_not_persistent"
    assert payload["connector_url"] == "https://francis-voice-178175.loca.lt/mcp"
    assert payload["connector_ingress_profile"]["profile"] == "localtunnel_ephemeral"
    assert payload["connector_ingress_profile"]["known_localtunnel"] is True
    assert payload["connector_ingress_profile"]["persistent_candidate"] is False
    assert payload["blockers"] == ["localtunnel_url_is_not_persistent_ingress"]
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["opens_public_tunnel"] is False
    assert payload["governance"]["writes_data"] is False
    assert not runtime_root.exists()
