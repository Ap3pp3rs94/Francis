from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from powershell_script_runner import run_powershell_script


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, relative_path: str, body: str, message: str) -> str:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _git(repo, "add", relative_path)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _normalized_console_text(value: str) -> str:
    without_ansi = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    without_error_view_margins = re.sub(r"(?m)^\s*\|\s?", "", without_ansi)
    return re.sub(r"\s+", " ", without_error_view_margins)


def _diverged_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "francis-tests@example.invalid")
    _git(repo, "config", "user.name", "Francis Tests")
    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "branch", "-M", "codex/test")
    _git(repo, "config", "remote.origin.url", "https://example.invalid/francis.git")
    _git(repo, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/codex/test", "HEAD")
    _git(repo, "config", "branch.codex/test.remote", "origin")
    _git(repo, "config", "branch.codex/test.merge", "refs/heads/codex/test")

    _commit(repo, "local.txt", "local\n", "local branch work")
    origin_base = _git(repo, "rev-parse", "refs/remotes/origin/main")
    _git(repo, "checkout", "-B", "tmp-origin-main", origin_base)
    remote_head = _commit(repo, "remote.txt", "remote\n", "origin main work")
    _git(repo, "update-ref", "refs/remotes/origin/main", remote_head)
    _git(repo, "checkout", "codex/test")
    return repo


def test_check_branch_state_console_normalizer_tolerates_power_shell_wrapping() -> None:
    wrapped = (
        "\x1b[31;1mRebase or\x1b[0m\n"
        "   | merge origin/main before continuing.\n"
        "   | branch: codex/test\n"
        "   | upstream:\n"
        "   | origin/codex/test"
    )

    normalized = _normalized_console_text(wrapped)

    assert "Rebase or merge origin/main" in normalized
    assert "branch: codex/test" in normalized
    assert "upstream: origin/codex/test" in normalized


def test_check_branch_state_reports_divergence_counts(tmp_path: Path) -> None:
    if not shutil.which("git"):
        pytest.skip("git is not available")
    repo = _diverged_repo(tmp_path)

    result = run_powershell_script(
        _powershell(),
        _repo_root() / "scripts" / "check-branch-state.ps1",
        ["-Root", str(repo)],
        cwd=_repo_root(),
        timeout_seconds=30,
    )

    combined = f"{result.stdout}\n{result.stderr}"
    normalized = _normalized_console_text(combined)
    assert result.returncode != 0
    assert "Branch 'codex/test' is behind or diverged from 'origin/main'." in normalized
    assert "branch: codex/test" in normalized
    assert "upstream: origin/codex/test" in normalized
    assert "HEAD:" in normalized
    assert "origin/main:" in normalized
    assert "merge-base:" in normalized
    assert "HEAD...origin/main: ahead 1, behind 1" in normalized
    assert "HEAD...upstream: ahead 1, behind 0" in normalized


def test_check_branch_state_json_reports_divergence_counts(tmp_path: Path) -> None:
    if not shutil.which("git"):
        pytest.skip("git is not available")
    repo = _diverged_repo(tmp_path)

    result = run_powershell_script(
        _powershell(),
        _repo_root() / "scripts" / "check-branch-state.ps1",
        ["-Root", str(repo), "-Json"],
        cwd=_repo_root(),
        timeout_seconds=30,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["reason"] == "branch_behind_or_diverged_from_origin_main"
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["branch"] == "codex/test"
    assert payload["upstream"] == "origin/codex/test"
    assert payload["head"]
    assert payload["origin_main"]
    assert payload["merge_base"]
    assert payload["head_origin_main"] == {"ahead": 1, "behind": 1}
    assert payload["head_upstream"] == {"ahead": 1, "behind": 0}
