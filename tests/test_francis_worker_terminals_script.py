import json
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


def _run_launcher(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "start-francis-worker-terminals.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
    )


def _run_coordinator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "francis-worker-coordinator.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=90,
    )


def test_francis_worker_terminal_launcher_lists_four_bounded_prompts() -> None:
    proc = _run_launcher("-Mode", "ListPrompts")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.worker_terminal.prompts"
    assert payload["ok"] is True
    workers = {item["worker_id"]: item for item in payload["workers"]}
    assert set(workers) == {
        "worker-1-orb-voice-proof",
        "worker-2-lens-overlay-spatial",
        "worker-3-voice-receipts",
        "worker-4-stage17-completion",
    }
    assert all(item["prompt_exists"] for item in workers.values())
    for worker in workers.values():
        prompt = Path(worker["prompt_path"]).read_text(encoding="utf-8")
        assert "Do not change the Orb appearance" in prompt or "Do not touch Orb visual files" in prompt
        assert "Restart Continuum" in prompt
        assert "Commit or push" in prompt


def test_francis_worker_terminal_launcher_status_is_read_only() -> None:
    proc = _run_launcher("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.worker_terminal.status"
    assert payload["ok"] is True
    assert len(payload["workers"]) == 4
    for worker in payload["workers"]:
        assert worker["session_path"].endswith(f"{worker['worker_id']}.json")
        assert "launcher_process_id" not in worker
        assert "physical_console_observed" in worker
        assert "visible_terminal_evidence" in worker
        assert "codex_child_alive" in worker
        assert "prompt_sha256" in worker
        assert "launch_mode" in worker
        assert "visible_terminal_requested" in worker
        assert isinstance(worker["codex_child_process_ids"], list)


def test_francis_worker_terminal_launcher_accepts_worker_prompt_override(tmp_path: Path) -> None:
    prompt = tmp_path / "worker-1-dispatch.md"
    prompt.write_text("# Worker override\n\nDo not change the Orb appearance.\n", encoding="utf-8")

    proc = _run_launcher(
        "-Mode",
        "ListPrompts",
    )
    assert proc.returncode == 0, proc.stderr
    assert prompt.read_text(encoding="utf-8").startswith("# Worker override")


def test_francis_worker_coordinator_supports_bounded_no_launch_iteration(tmp_path: Path) -> None:
    state_root = tmp_path / "coordinator"
    proc = _run_coordinator(
        "-Mode",
        "Run",
        "-MaxIterations",
        "1",
        "-PollSeconds",
        "5",
        "-NoLaunch",
        "-StateRoot",
        str(state_root),
    )

    assert proc.returncode == 0, proc.stderr
    status = json.loads((state_root / "status.json").read_text(encoding="utf-8-sig"))
    assert status["kind"] == "francis.worker_terminal.coordinator.status"
    assert status["state"] == "completed_max_iterations"
    assert status["iteration"] == 1
    assert status["uncontrolled_recursion_allowed"] is False
    assert status["one_codex_child_per_lane"] is True
    assert status["project_manager_dispatch"] is True
    assert status["worker_launch_mode"] == "Background"
    assert "readback_root" in status
    assert (state_root / "dispatches").is_dir() or status["no_launch"] is True
    receipts = (state_root / "receipts.jsonl").read_text(encoding="utf-8-sig").splitlines()
    assert any("francis.worker_terminal.coordinator.iteration" in line for line in receipts)


def test_francis_worker_coordinator_generates_individual_pm_dispatches(tmp_path: Path) -> None:
    state_root = tmp_path / "coordinator"
    proc = _run_coordinator(
        "-Mode",
        "Run",
        "-MaxIterations",
        "1",
        "-PollSeconds",
        "5",
        "-NoLaunch",
        "-ForcePromptAll",
        "-StateRoot",
        str(state_root),
    )

    assert proc.returncode == 0, proc.stderr
    dispatches = sorted((state_root / "dispatches").glob("worker-*-iteration-1.md"))
    assert len(dispatches) == 4
    by_name = {path.name: path.read_text(encoding="utf-8-sig") for path in dispatches}
    assert "Project-manager direction: advance the next smallest Orb voice proof slice." in by_name[
        "worker-1-orb-voice-proof-iteration-1.md"
    ]
    assert "Project-manager direction: advance the next smallest lens-to-overlay spatial contract slice." in by_name[
        "worker-2-lens-overlay-spatial-iteration-1.md"
    ]
    assert "Project-manager direction: advance the next smallest voice receipt or provider-boundary slice." in by_name[
        "worker-3-voice-receipts-iteration-1.md"
    ]
    assert "Project-manager direction: advance the next smallest Stage 17 or completion-model truth slice." in by_name[
        "worker-4-stage17-completion-iteration-1.md"
    ]
    for text in by_name.values():
        assert "Current Build Snapshot" in text
        assert "Dirty Worktree" in text
        assert "Previous Worker Readback" in text
        assert "Write a concise lane readback" in text
        assert "Do not change the Orb appearance" in text or "Do not touch Orb visual files" in text


def test_francis_worker_coordinator_stop_writes_stop_flag(tmp_path: Path) -> None:
    state_root = tmp_path / "coordinator"
    proc = _run_coordinator("-Mode", "Stop", "-StateRoot", str(state_root))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "francis.worker_terminal.coordinator.stop"
    assert payload["ok"] is True
    assert payload["stop_requested"] is True
    assert (state_root / "stop.flag").is_file()
