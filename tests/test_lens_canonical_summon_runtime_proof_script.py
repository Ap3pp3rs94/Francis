from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_proof(data_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-canonical-summon-runtime-proof.ps1"),
            "-Mode",
            "Status",
            "-DataDir",
            str(data_root),
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _write_runtime(data_root: Path, renderer_pid: int, *, correlated: bool = True) -> None:
    now = datetime.now(UTC).isoformat()
    process_pid = os.getpid()
    request_id = "summon-global_hotkey-test"
    orb_request_id = request_id if correlated else "mismatched-request"
    overlay_root = data_root / "runtime" / "lens-overlay"
    summon_root = data_root / "runtime" / "lens-summon"
    hotkey_root = data_root / "runtime" / "lens-hotkey"
    tray_root = data_root / "runtime" / "lens-tray"
    supervisor_root = data_root / "runtime" / "lens-host-supervisor"
    renderer_root = data_root / "runtime" / "native-orb-renderer"
    receipt_root = data_root / "lens" / "summon" / "receipts"
    orb_receipt_root = overlay_root / "orb-controls"
    for path in (
        overlay_root,
        summon_root,
        hotkey_root,
        tray_root,
        supervisor_root,
        renderer_root,
        receipt_root,
        orb_receipt_root,
    ):
        path.mkdir(parents=True, exist_ok=True)

    orb_receipt_path = orb_receipt_root / "orb-control-test.json"
    orb_receipt_path.write_text(
        json.dumps(
            {
                "kind": "lens.overlay.orb_control.receipt",
                "receipt_id": "orb-control-test",
                "action": "panel_open",
                "status": "panel_open",
                "trigger": "global_hotkey",
                "request_id": orb_request_id,
            }
        ),
        encoding="utf-8",
    )
    summon_receipt_path = receipt_root / "lsum_test.json"
    summon_receipt_path.write_text(
        json.dumps(
            {
                "kind": "lens.summon.execution_receipt",
                "receipt_id": "lsum_test",
                "status": "native_surface_opened",
                "trigger": "global_hotkey",
                "request_id": request_id,
                "opened": True,
                "browser_opened": False,
                "physical_input_performed": False,
                "orb_control_receipt_path": str(orb_receipt_path),
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (summon_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.local_launcher",
                "status": "native_surface_opened",
                "ok": True,
                "trigger": "global_hotkey",
                "opened": True,
                "browser_opened": False,
                "native_request_consumed": True,
                "native_request": {"request_id": request_id},
                "receipt_id": "lsum_test",
                "receipt_path": str(summon_receipt_path),
                "execution_authority_ready": True,
                "controls_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
                "updated_at": now,
            }
        ),
        encoding="utf-8",
    )
    (overlay_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.overlay.runtime_state",
                "status": "overlay_running",
                "pid": process_pid,
                "overlay_window_visible": True,
                "always_on_top": True,
                "orb_controls": {"latest_request_id": request_id, "latest_trigger": "global_hotkey"},
                "native_renderer": {"pid": renderer_pid},
            }
        ),
        encoding="utf-8",
    )
    (hotkey_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": process_pid,
                "hotkey_bound": True,
                "launch_on_hotkey": True,
                "press_count": 1,
                "global_hotkey": "Ctrl+Alt+F",
            }
        ),
        encoding="utf-8",
    )
    (tray_root / "status.json").write_text(
        json.dumps({"kind": "lens.tray.runtime_state", "status": "tray_running", "pid": process_pid}),
        encoding="utf-8",
    )
    (supervisor_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "supervisor_pid": process_pid,
                "observed_pid": process_pid,
                "resident_supervised_runtime": True,
            }
        ),
        encoding="utf-8",
    )
    (renderer_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "francis.native_orb_renderer.runtime_status",
                "status": "running",
                "process_id": renderer_pid,
                "active_renderer": True,
            }
        ),
        encoding="utf-8",
    )


def test_canonical_summon_runtime_proof_is_read_only_and_rejects_mismatched_receipts(tmp_path: Path) -> None:
    _write_runtime(tmp_path / "data", os.getpid(), correlated=False)

    proc = _run_proof(tmp_path / "data")

    assert proc.returncode == 1, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.canonical_runtime.proof"
    assert payload["status"] == "blocked"
    assert "canonical_summon_request_correlation_not_proven" in payload["blockers"]
    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "canonical_runtime_only": True,
        "launches_process": False,
        "stops_process": False,
        "restarts_process": False,
        "writes_runtime_state": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "memory_write": False,
        "mutation_authority_granted": False,
    }


def test_canonical_summon_runtime_proof_reports_missing_evidence_without_crashing(tmp_path: Path) -> None:
    proc = _run_proof(tmp_path / "missing-data")

    assert proc.returncode == 1, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "blocked"
    assert payload["evidence_age_seconds"]["summon_status"] == -1
    assert payload["evidence_age_seconds"]["summon_receipt"] == -1
    assert "canonical_summon_evidence_fresh_not_proven" in payload["blockers"]
    assert payload["summon_anywhere"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows process-name proof")
def test_canonical_summon_runtime_proof_accepts_one_correlated_renderer(tmp_path: Path) -> None:
    renderer_query = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-Command",
            "@(Get-Process -Name native_orb_renderer -ErrorAction SilentlyContinue).Id -join ','",
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=10,
    )
    existing_renderer_pids = [int(value) for value in renderer_query.stdout.strip().split(",") if value.strip()]
    if len(existing_renderer_pids) > 1:
        pytest.skip("success fixture requires zero or one existing native renderer")

    renderer: subprocess.Popen[bytes] | None = None
    if existing_renderer_pids:
        renderer_pid = existing_renderer_pids[0]
    else:
        source = Path(os.environ["SystemRoot"]) / "System32" / "ping.exe"
        renderer_exe = tmp_path / "native_orb_renderer.exe"
        shutil.copy2(source, renderer_exe)
        renderer = subprocess.Popen(
            [str(renderer_exe), "-n", "30", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        renderer_pid = renderer.pid
    try:
        _write_runtime(tmp_path / "data", renderer_pid)

        proc = _run_proof(tmp_path / "data")

        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(proc.stdout)
        assert payload["status"] == "proof_passed"
        assert payload["summon_anywhere"] is True
        assert payload["os_level_summon"] is True
        assert payload["renderer_process_count"] == 1
        assert payload["request_id"] == "summon-global_hotkey-test"
        assert payload["checks"]["no_browser_fallback"] is True
        assert payload["checks"]["no_physical_input"] is True
        assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    finally:
        if renderer is not None:
            renderer.terminate()
            renderer.wait(timeout=10)
