from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "francis-api-actor-scope-env.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        env=run_env,
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def _json_stdout(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert proc.stdout.strip(), proc.stderr
    return json.loads(proc.stdout)


def test_francis_api_actor_scope_env_applies_scope_and_writes_receipt(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env_path = root / ".env"
    env_path.write_text(
        'FRANCIS_API_ACTOR_SCOPES={"test.federation.write":["federation.write"]}\n',
        encoding="utf-8",
    )

    proc = _run_script(
        "-Mode",
        "Apply",
        "-Root",
        str(root),
        "-Actor",
        "codex.builder",
        "-Scope",
        "federation.stage16.sleep_resume.confirmation.write",
        "-Reason",
        "test_stage16_actor_scope_env",
        env={"FRANCIS_ENV_PROFILE": "dev"},
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = _json_stdout(proc)
    assert payload["ok"] is True
    assert payload["status"] == "applied"
    assert payload["actor"] == "codex.builder"
    assert payload["scope"] == "federation.stage16.sleep_resume.confirmation.write"
    assert payload["changed"] is True
    assert payload["writes_env_file"] is True
    assert payload["writes_receipt"] is True
    assert payload["writes_confirmation_receipt"] is False
    assert payload["writes_evidence"] is False
    assert payload["marks_stage16_closed"] is False
    assert payload["governance"]["dev_or_workstation_only"] is True
    assert payload["governance"]["does_not_mark_stage16_closed"] is True

    line = next(
        line
        for line in env_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("FRANCIS_API_ACTOR_SCOPES=")
    )
    policy = json.loads(line.split("=", 1)[1])
    assert policy["test.federation.write"] == ["federation.write"]
    assert policy["codex.builder"] == ["federation.stage16.sleep_resume.confirmation.write"]

    receipt_path = Path(payload["receipt_path"])
    assert receipt_path.exists()
    assert root.resolve() in receipt_path.resolve().parents
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    assert receipt["kind"] == "francis.api.actor_scope_env.receipt"
    assert receipt["actor"] == "codex.builder"
    assert receipt["scope"] == "federation.stage16.sleep_resume.confirmation.write"
    assert receipt["decision"] == "scope_added_to_repo_env"
    assert receipt["writes_confirmation_receipt"] is False
    assert receipt["marks_stage16_closed"] is False
    assert receipt["governance"]["preserves_existing_actor_scopes"] is True


def test_francis_api_actor_scope_env_blocks_production_profile(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    proc = _run_script(
        "-Mode",
        "Apply",
        "-Root",
        str(root),
        "-Actor",
        "codex.builder",
        "-Scope",
        "federation.stage16.sleep_resume.confirmation.write",
        env={"FRANCIS_ENV_PROFILE": "production"},
    )

    assert proc.returncode == 1
    payload = _json_stdout(proc)
    assert payload["ok"] is False
    assert payload["status"] == "blocked_env_profile"
    assert payload["error"] == "env_profile_not_allowed"
    assert payload["writes_env_file"] is False
    assert payload["writes_receipt"] is False
    assert payload["marks_stage16_closed"] is False
    assert not (root / ".env").exists()
    assert not (root / "data").exists()
