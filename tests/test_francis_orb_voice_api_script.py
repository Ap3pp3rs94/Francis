from __future__ import annotations

import json
import os
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


def _run_orb_voice_api(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env.pop("FRANCIS_API_ACTOR_SCOPES", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "francis-orb-voice-api.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
        env=run_env,
    )


def test_francis_orb_voice_api_status_is_read_only_without_listener() -> None:
    proc = _run_orb_voice_api("-Mode", "Status", "-Port", str(_unused_local_port()), "-Json")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.orb_voice.api_runtime"
    assert payload["status"] == "not_started"
    assert payload["listener_count"] == 0
    assert payload["health"]["status"] == "not_listening"
    assert payload["required_actor_scopes"]["lens.overlay.voice"] == ["chat.write"]
    assert payload["required_actor_scopes"]["chatgpt.voice"] == [
        "chatgpt.voice.bridge.read",
        "chatgpt.voice.bridge.write",
        "chat.write",
    ]
    assert payload["required_actor_scopes"]["chat_ui.voice"] == [
        "chatgpt.voice.bridge.write",
        "chat.write",
    ]
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["stops_process"] is False
    assert payload["governance"]["grants_execution_authority"] is False
    assert payload["governance"]["grants_mutation_authority"] is False


def test_francis_orb_voice_api_print_scope_policy_preserves_existing_entries() -> None:
    existing = {
        "stage17.operator": ["plugins.write"],
        "lens.overlay.voice": ["existing.scope"],
    }
    proc = _run_orb_voice_api(
        "-Mode",
        "PrintScopePolicy",
        "-Port",
        str(_unused_local_port()),
        "-Json",
        env={"FRANCIS_API_ACTOR_SCOPES": json.dumps(existing)},
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    policy = payload["actor_scope_policy"]
    assert payload["status"] == "policy_ready"
    assert payload["existing_policy_status"] == "parsed"
    assert policy["stage17.operator"] == ["plugins.write"]
    assert policy["lens.overlay.voice"] == ["existing.scope", "chat.write"]
    assert policy["chatgpt.voice"] == [
        "chatgpt.voice.bridge.read",
        "chatgpt.voice.bridge.write",
        "chat.write",
    ]
    assert policy["chat_ui.voice"] == ["chatgpt.voice.bridge.write", "chat.write"]
    assert json.loads(payload["actor_scope_policy_json"]) == policy
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["starts_process"] is False
    assert payload["governance"]["writes_repo"] is False
    assert payload["governance"]["writes_data"] is False


def test_francis_orb_voice_api_script_uses_process_environment_without_global_policy_relaxation() -> None:
    script = (_repo_root() / "scripts" / "francis-orb-voice-api.ps1").read_text(encoding="utf-8")

    assert "Add-ActorScopes -Policy $Policy -Actor 'lens.overlay.voice' -Scopes @('chat.write')" in script
    assert "Add-ActorScopes -Policy $Policy -Actor 'chatgpt.voice'" in script
    assert "Add-ActorScopes -Policy $Policy -Actor 'chat_ui.voice'" in script
    assert "FRANCIS_API_ACTOR_SCOPES" in script
    assert "actor_scope_source = 'process_environment_for_spawned_api_only'" in script
    assert "$Pid" not in script
    assert "grants_execution_authority = $false" in script
    assert "grants_mutation_authority = $false" in script
    assert "opens_public_tunnel = $false" in script
    assert "captures_audio = $false" in script
