from __future__ import annotations

import json
import os
import shutil
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


def _run_setup(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-elevenlabs-voice-setup.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        env=env,
        timeout=60,
    )


def _env_without_elevenlabs() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "FRANCIS_ELEVENLABS_API_KEY",
        "ELEVENLABS_API_KEY",
        "FRANCIS_ELEVENLABS_VOICE_ID",
        "ELEVENLABS_VOICE_ID",
    ):
        env.pop(key, None)
    return env


def test_elevenlabs_voice_setup_status_is_secret_safe_when_missing(tmp_path: Path) -> None:
    proc = _run_setup(
        "-Mode",
        "Status",
        "-EnvironmentScope",
        "ProcessOnly",
        "-DataDir",
        str(tmp_path / "data"),
        env=_env_without_elevenlabs(),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.overlay.elevenlabs_voice_setup"
    assert payload["status"] == "ready"
    assert payload["ready"] is False
    assert payload["elevenlabs"]["configured"] is False
    assert payload["elevenlabs"]["api_key_present"] is False
    assert payload["elevenlabs"]["voice_id_present"] is False
    assert set(payload["elevenlabs"]["missing_configuration"]) == {"api_key", "voice_id"}
    assert payload["elevenlabs"]["credential_values_redacted"] is True
    assert payload["elevenlabs"]["stores_secret_in_repo"] is False
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["writes_repo_secret"] is False
    assert payload["governance"]["logs_secret_value"] is False
    assert "FRANCIS_ELEVENLABS_API_KEY" not in proc.stderr


def test_elevenlabs_voice_setup_status_reads_process_env_without_leaking_values(tmp_path: Path) -> None:
    env = _env_without_elevenlabs()
    env["FRANCIS_ELEVENLABS_API_KEY"] = "sk_test_should_not_appear"
    env["FRANCIS_ELEVENLABS_VOICE_ID"] = "voice_test_should_not_appear"

    proc = _run_setup(
        "-Mode",
        "Status",
        "-EnvironmentScope",
        "ProcessOnly",
        "-DataDir",
        str(tmp_path / "data"),
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ready"] is True
    assert payload["elevenlabs"]["configured"] is True
    assert payload["elevenlabs"]["api_key_present"] is True
    assert payload["elevenlabs"]["api_key_source"] == "Process:FRANCIS_ELEVENLABS_API_KEY"
    assert payload["elevenlabs"]["voice_id_present"] is True
    assert payload["elevenlabs"]["voice_id_source"] == "Process:FRANCIS_ELEVENLABS_VOICE_ID"
    assert payload["elevenlabs"]["missing_configuration"] == []
    assert "sk_test_should_not_appear" not in proc.stdout
    assert "voice_test_should_not_appear" not in proc.stdout


def test_elevenlabs_voice_setup_configure_requires_explicit_confirmation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_setup(
        "-Mode",
        "Configure",
        "-EnvironmentScope",
        "ProcessOnly",
        "-DataDir",
        str(data_dir),
        "-VoiceId",
        "voice_test_should_not_appear",
        env=_env_without_elevenlabs(),
    )

    assert proc.returncode == 2, proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "confirm_configure_required"
    assert payload["governance"]["explicit_confirmation_required"] is True
    assert payload["governance"]["mutation_target"] == "user_environment_variables"
    assert "voice_test_should_not_appear" not in proc.stdout

    receipt = data_dir / "runtime" / "lens-overlay" / "elevenlabs-voice-setup.json"
    assert receipt.is_file()
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8-sig"))
    assert receipt_payload["error"] == "confirm_configure_required"
    assert receipt_payload["receipt_path"] == "data/runtime/lens-overlay/elevenlabs-voice-setup.json"


def test_elevenlabs_voice_setup_list_voices_refuses_without_api_key(tmp_path: Path) -> None:
    proc = _run_setup(
        "-Mode",
        "ListVoices",
        "-EnvironmentScope",
        "ProcessOnly",
        "-DataDir",
        str(tmp_path / "data"),
        "-Search",
        "soft female should not be logged",
        "-MaxVoices",
        "5",
        env=_env_without_elevenlabs(),
    )

    assert proc.returncode == 2, proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "elevenlabs_api_key_required"
    assert payload["governance"]["read_only"] is True
    assert payload["governance"]["remote_request"] is True
    assert payload["governance"]["sends_speech_text_to_remote_provider"] is False
    assert payload["governance"]["sends_search_to_remote_provider"] is True
    assert payload["governance"]["search_value_redacted"] is True
    assert payload["governance"]["logs_secret_value"] is False
    assert payload["voice_catalog"]["endpoint"] == "https://api.elevenlabs.io/v2/voices"
    assert payload["voice_catalog"]["remote_request_attempted"] is False
    assert payload["voice_catalog"]["api_key_source"] == ""
    assert payload["voice_catalog"]["transient_api_key"] is False
    assert payload["voice_catalog"]["stores_api_key"] is False
    assert payload["voice_catalog"]["requested_page_size"] == 5
    assert payload["voice_catalog"]["search_provided"] is True
    assert payload["voice_catalog"]["search_value_redacted"] is True
    assert payload["voice_catalog"]["voices"] == []
    assert "soft female should not be logged" not in proc.stdout
    assert "soft female should not be logged" not in proc.stderr


def test_elevenlabs_voice_setup_script_is_confirm_gated_and_secret_safe() -> None:
    script = (_repo_root() / "scripts" / "lens-elevenlabs-voice-setup.ps1").read_text(encoding="utf-8")

    assert "ValidateSet('Status', 'Configure', 'Clear', 'ListVoices')" in script
    assert "[System.Security.SecureString]$ApiKeySecret" in script
    assert "Read-Host 'ElevenLabs API key' -AsSecureString" in script
    assert "SecureStringToBSTR" in script
    assert "ZeroFreeBSTR" in script
    assert "function Invoke-ElevenLabsVoiceCatalogList" in script
    assert "function ConvertTo-VoiceCatalogEntry" in script
    assert "https://api.elevenlabs.io/v2/voices" in script
    assert "'xi-api-key' = $ApiKey" in script
    assert "Convert-SecretToPlainText -Secret $ApiKeyOverrideSecret" in script
    assert "script_parameter:ApiKeySecret" in script
    assert "transient_api_key = ($ApiKeySource -eq 'script_parameter:ApiKeySecret')" in script
    assert "stores_api_key = $false" in script
    assert "search_value_redacted = $true" in script
    assert "sends_speech_text_to_remote_provider = $false" in script
    assert "confirm_configure_required" in script
    assert "confirm_clear_required" in script
    assert "SetEnvironmentVariable('FRANCIS_ELEVENLABS_API_KEY', $ApiKeyPlainText, 'User')" in script
    assert "SetEnvironmentVariable('FRANCIS_ELEVENLABS_VOICE_ID', $BoundedVoiceId, 'User')" in script
    assert "credential_values_redacted = $true" in script
    assert "logs_secret_value = $false" in script
    assert "writes_repo_secret = $false" in script
    assert "stores_secret_in_repo = $false" in script
