param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$Root = '',

  [switch]$UseFixtureSafeTarget,

  [switch]$OperatorApprovedFixtureAction,

  [switch]$OperatorApprovedSummonDecision
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = if ([string]::IsNullOrWhiteSpace($Root)) {
  (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
} else {
  (Resolve-Path $Root).Path
}

& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  $Python = (Get-Command python -ErrorAction Stop).Source
}

$ProofRoot = Join-Path $RepoRoot 'data\logs\operations\one_visible_loop'
New-Item -ItemType Directory -Force -Path $ProofRoot | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmssfff'
$ProofPath = Join-Path $ProofRoot ("francis_one_visible_loop_proof_{0}.json" -f $Stamp)

$env:FRANCIS_ROOT = $RepoRoot
$env:FRANCIS_ONE_VISIBLE_LOOP_PROOF_PATH = $ProofPath
$env:FRANCIS_ONE_VISIBLE_LOOP_USE_FIXTURE_SAFE_TARGET = if ($UseFixtureSafeTarget) { '1' } else { '0' }
$env:FRANCIS_ONE_VISIBLE_LOOP_OPERATOR_APPROVED_FIXTURE_ACTION = if ($OperatorApprovedFixtureAction) { '1' } else { '0' }
$env:FRANCIS_ONE_VISIBLE_LOOP_OPERATOR_APPROVED_SUMMON = if ($OperatorApprovedSummonDecision) { '1' } else { '0' }
$env:FRANCIS_ONE_VISIBLE_LOOP_STATE_ROOT = Join-Path $RepoRoot (".francis\one-visible-loop\{0}" -f $Stamp)

$PythonSource = @'
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.input_actuator.orb_operator import submit_orb_intent


def _repo_root() -> Path:
    return Path(os.environ["FRANCIS_ROOT"]).resolve()


def _run_json_script(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", *args],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    text = (proc.stdout or "").strip()
    payload: dict[str, Any] = {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}
    return {
        "exit_code": proc.returncode,
        "payload": payload,
        "stdout_preview": text[:1000],
        "stderr_preview": (proc.stderr or "").strip()[:1000],
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _overlay_status() -> dict[str, Any]:
    path = _repo_root() / "data" / "runtime" / "lens-overlay" / "status.json"
    payload = _read_json(path)
    orb_visual = payload.get("orb_visual") if isinstance(payload.get("orb_visual"), dict) else {}
    overlay_position = payload.get("overlay_position") if isinstance(payload.get("overlay_position"), dict) else {}
    visible = bool(
        payload.get("overlay_window_visible")
        or payload.get("overlay_runtime", {}).get("overlay_window_visible")
        or payload.get("status") == "overlay_running"
    )
    return {
        "status": "visible" if visible else "missing",
        "path": str(path),
        "overlay_window_visible": visible,
        "always_on_top": bool(payload.get("always_on_top") or payload.get("topmost") or overlay_position.get("always_on_top")),
        "topmost_pin_applied": bool(payload.get("topmost_pin_applied") or overlay_position.get("topmost_pin_applied")),
        "reach_mode": str(overlay_position.get("reach_mode") or orb_visual.get("reach_mode") or ""),
    }


class _FakeWin32Gui:
    def __init__(self) -> None:
        self.windows: dict[int, dict[str, Any]] = {
            100: {
                "title": "Francis One Visible Loop Safe Target",
                "class_name": "SafeWindow",
                "rect": (0, 0, 420, 260),
                "child_hwnd": 101,
                "text": "safe target",
            },
            101: {
                "child": True,
                "class_name": "Edit",
                "rect": (0, 0, 420, 260),
                "text": "",
            },
        }
        self.posts: list[tuple[int, int, int, int]] = []

    def IsWindowVisible(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd].get("visible", True))

    def IsWindowEnabled(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd].get("enabled", True))

    def GetWindowText(self, hwnd: int) -> str:
        return str(self.windows[hwnd].get("text", self.windows[hwnd].get("title", "")))

    def GetClassName(self, hwnd: int) -> str:
        return str(self.windows[hwnd].get("class_name", "Window"))

    def GetWindowRect(self, hwnd: int) -> tuple[int, int, int, int]:
        return tuple(self.windows[hwnd].get("rect", (0, 0, 100, 100)))  # type: ignore[return-value]

    def EnumWindows(self, callback: Any, extra: Any) -> None:
        for hwnd, data in self.windows.items():
            if not data.get("child", False):
                callback(hwnd, extra)

    def ScreenToClient(self, hwnd: int, point: tuple[int, int]) -> tuple[int, int]:
        left, top, _right, _bottom = self.GetWindowRect(hwnd)
        return point[0] - left, point[1] - top

    def ChildWindowFromPoint(self, hwnd: int, _point: tuple[int, int]) -> int:
        child = int(self.windows[hwnd].get("child_hwnd", 0))
        return child or hwnd

    def PostMessage(self, hwnd: int, message: int, wparam: int, lparam: int) -> bool:
        self.posts.append((hwnd, message, wparam, lparam))
        if message == 0x0102:
            self.windows[hwnd]["text"] = str(self.windows[hwnd].get("text", "")) + chr(wparam)
        return True


def _fixture_action_proof() -> dict[str, Any]:
    use_fixture = os.getenv("FRANCIS_ONE_VISIBLE_LOOP_USE_FIXTURE_SAFE_TARGET") == "1"
    operator_approved = os.getenv("FRANCIS_ONE_VISIBLE_LOOP_OPERATOR_APPROVED_FIXTURE_ACTION") == "1"
    if not use_fixture:
        return {
            "status": "blocked",
            "blocker": "safe_target_not_configured",
            "operator_approved_action": operator_approved,
        }
    if not operator_approved:
        return {
            "status": "blocked",
            "blocker": "operator_approval_required_for_safe_target_action",
            "operator_approved_action": False,
        }

    previous_bridge_enable = os.environ.get("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE")
    previous_state_dir = os.environ.get("FRANCIS_ORB_OPERATOR_STATE_DIR")
    fake = _FakeWin32Gui()
    previous_win32gui = sys.modules.get("win32gui")
    sys.modules["win32gui"] = fake  # type: ignore[assignment]
    os.environ["FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE"] = "1"
    os.environ["FRANCIS_ORB_OPERATOR_STATE_DIR"] = str(Path(os.environ["FRANCIS_ONE_VISIBLE_LOOP_STATE_ROOT"]) / "orb_operator")
    try:
        result = submit_orb_intent(
            {
                "mode": "orb_pointer",
                "actor": "operator.visible_loop.fixture",
                "objective": "one visible loop fixture safe target proof",
                "session_id": "one-visible-loop-fixture",
                "intent": {
                    "kind": "keyboard.type",
                    "x": 24,
                    "y": 32,
                    "text": "Francis visible loop proof",
                },
            }
        )
    finally:
        if previous_win32gui is None:
            sys.modules.pop("win32gui", None)
        else:
            sys.modules["win32gui"] = previous_win32gui
        if previous_bridge_enable is None:
            os.environ.pop("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", None)
        else:
            os.environ["FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE"] = previous_bridge_enable
        if previous_state_dir is None:
            os.environ.pop("FRANCIS_ORB_OPERATOR_STATE_DIR", None)
        else:
            os.environ["FRANCIS_ORB_OPERATOR_STATE_DIR"] = previous_state_dir

    bridge = result.get("backend", {}).get("result", {}) if isinstance(result.get("backend"), dict) else {}
    desktop_bridge = bridge.get("desktop_bridge", {}) if isinstance(bridge.get("desktop_bridge"), dict) else {}
    desktop_bridge_receipt_path = (
        desktop_bridge.get("receipt_path")
        or bridge.get("desktop_bridge_receipt_path")
    )
    target_observer_status = (
        desktop_bridge.get("target_observer_status")
        or bridge.get("target_observer_status")
    )
    return {
        "status": "passed" if result.get("ok") and bridge.get("desktop_effect_confirmed") else "blocked",
        "proof_mode": "fixture_safe_target",
        "operator_approved_action": True,
        "safe_target_title": "Francis One Visible Loop Safe Target",
        "orb_result_status": result.get("status"),
        "operator_receipt_path": result.get("operator_receipt_path"),
        "desktop_bridge_receipt_path": desktop_bridge_receipt_path,
        "desktop_action_sent": bool(bridge.get("desktop_action_sent")),
        "desktop_effect_performed": bool(bridge.get("desktop_effect_performed")),
        "desktop_effect_confirmed": bool(bridge.get("desktop_effect_confirmed")),
        "target_observer_status": str(target_observer_status or ""),
        "raw_input": bool(result.get("governance", {}).get("raw_input")),
        "uses_user_os_cursor": bool(result.get("governance", {}).get("uses_user_os_cursor")),
        "user_mouse_taken": bool(result.get("governance", {}).get("user_mouse_taken")),
        "physical_input_performed": bool(result.get("governance", {}).get("physical_input_performed")),
    }


repo = _repo_root()
summon = _run_json_script(str(repo / "scripts" / "lens-summon-preflight.ps1"), "-Mode", "Status")
summon_payload = summon["payload"]
overlay = _overlay_status()
action = _fixture_action_proof()
operator_approved_summon = os.getenv("FRANCIS_ONE_VISIBLE_LOOP_OPERATOR_APPROVED_SUMMON") == "1"
summon_ready = not bool(summon_payload.get("missing_required_before_enable"))
visible_loop_ready = (
    bool(operator_approved_summon)
    and summon_ready
    and overlay.get("overlay_window_visible") is True
    and action.get("status") == "passed"
)
proof = {
    "kind": "francis.one_visible_loop.proof",
    "mode": "Status",
    "created_at": datetime.now(UTC).isoformat(),
    "proof_path": os.getenv("FRANCIS_ONE_VISIBLE_LOOP_PROOF_PATH", ""),
    "status": "passed" if visible_loop_ready else "blocked",
    "next_operator_decision": (
        "approve_summon_enable_and_live_safe_target_bridge_proof"
        if not visible_loop_ready
        else "none"
    ),
    "summon": {
        "operator_approved_summon_decision": operator_approved_summon,
        "status": summon_payload.get("status", "unknown"),
        "global_hotkey": summon_payload.get("global_hotkey", ""),
        "required_before_enable": summon_payload.get("required_before_enable", []),
        "missing_required_before_enable": summon_payload.get("missing_required_before_enable", []),
        "next_smallest_truthful_gap": summon_payload.get("next_smallest_truthful_gap", ""),
    },
    "orb_presence": overlay,
    "operator_action": action,
    "chat_lens_visibility": {
        "status": "proof_artifact_visible",
        "receipt_trace_status_paths": [
            os.getenv("FRANCIS_ONE_VISIBLE_LOOP_PROOF_PATH", ""),
            str(action.get("operator_receipt_path") or ""),
            str(action.get("desktop_bridge_receipt_path") or ""),
        ],
        "actual_chat_ui_render_verified": False,
        "actual_lens_ui_render_verified": False,
    },
    "governance": {
        "does_not_self_enable_summon": True,
        "does_not_default_enable_desktop_bridge": True,
        "fixture_safe_target_is_not_live_desktop_completion": action.get("proof_mode") == "fixture_safe_target",
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_memory_write_authority": False,
    },
}
print(json.dumps(proof, indent=2, ensure_ascii=False, sort_keys=True))
'@

$OutputText = $PythonSource | & $Python -
if ([string]::IsNullOrWhiteSpace($OutputText)) {
  throw 'One visible loop proof produced no JSON output.'
}
$OutputText | Set-Content -LiteralPath $ProofPath -Encoding UTF8
$OutputText
