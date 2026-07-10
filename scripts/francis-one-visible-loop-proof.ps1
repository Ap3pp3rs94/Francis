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


def _canonical_summon_runtime_observed(result: dict[str, Any]) -> bool:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    required_checks = (
        "summon_status",
        "evidence_fresh",
        "global_hotkey_trigger",
        "request_consumed",
        "request_correlation",
        "summon_receipt",
        "orb_control_receipt",
        "overlay_runtime",
        "hotkey_runtime",
        "tray_runtime",
        "supervised_resident_host",
        "single_canonical_renderer",
        "authority_ready",
        "no_browser_fallback",
        "no_physical_input",
    )
    return bool(
        result.get("exit_code") == 0
        and payload.get("ok") is True
        and payload.get("kind") == "lens.summon.canonical_runtime.proof"
        and payload.get("status") == "proof_passed"
        and payload.get("source") == "canonical_live_runtime_readback"
        and all(checks.get(name) is True for name in required_checks)
    )


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


def _operator_decision_queue(
    summon_payload: dict[str, Any],
    host_payload: dict[str, Any],
    canonical_payload: dict[str, Any],
    canonical_runtime_observed: bool,
) -> dict[str, Any]:
    if canonical_runtime_observed:
        return {
            "status": "canonical_summon_authority_already_evidenced",
            "queued_decision_count": 0,
            "decisions": [],
            "evidence_source": "canonical_live_summon_runtime_readback",
            "summon_receipt_id": str(canonical_payload.get("summon_receipt_id") or ""),
            "orb_control_receipt_id": str(canonical_payload.get("orb_control_receipt_id") or ""),
        }

    missing = summon_payload.get("missing_required_before_enable")
    missing_requirements = [str(item) for item in missing] if isinstance(missing, list) else []
    first_missing = str(summon_payload.get("first_missing_required_before_enable") or "")
    if not first_missing and missing_requirements:
        first_missing = missing_requirements[0]
    if not first_missing:
        return {
            "status": "no_operator_decision_queued",
            "queued_decision_count": 0,
            "decisions": [],
        }

    decision_by_requirement: dict[str, dict[str, Any]] = {
        "resident_host_process": {
            "decision_id": "approve_resident_host_process_supervision_authority_request",
            "question": (
                "Austin: approve the governed process-supervision authority path "
                "for the Francis resident host prerequisite?"
            ),
            "authority_required": str(host_payload.get("authority_required") or "process_supervision_authority"),
            "current_runtime_status": str(host_payload.get("status") or "blocked"),
            "next_operator_command": (
                ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                "-Mode RequestNext -Actor <actor> -ConfirmRequest"
            ),
            "proof_script": "scripts/lens-host-supervisor.ps1 -Mode Status",
            "follow_up_after_approval": (
                "Use the resulting approval id for the existing GrantNext and ExecuteNext "
                "handoffs; do not self-grant."
            ),
        },
        "global_hotkey_binding": {
            "decision_id": "approve_global_hotkey_binding_authority_request",
            "question": "Austin: approve the governed Ctrl+Alt+F global hotkey binding authority path?",
            "authority_required": "hotkey_registration_authority",
            "current_runtime_status": "global_hotkey_binding_runtime_missing",
            "next_operator_command": (
                ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                "-Mode RequestNext -Actor <actor> -ConfirmRequest"
            ),
            "proof_script": "scripts/lens-hotkey-binding.ps1 -Mode Status",
            "follow_up_after_approval": (
                "Use the resulting approval id for the existing GrantNext and ExecuteNext "
                "handoffs; do not self-grant."
            ),
        },
        "summon_binding": {
            "decision_id": "approve_summon_binding_authority_request",
            "question": "Austin: approve the governed summon-binding authority path?",
            "authority_required": "summon_authority",
            "current_runtime_status": "summon_binding_missing",
            "next_operator_command": (
                ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 "
                "-Mode RequestNext -Actor <actor> -ConfirmRequest"
            ),
            "proof_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
            "follow_up_after_approval": (
                "Use the resulting approval id for the existing GrantNext and ExecuteNext "
                "handoffs; do not self-grant."
            ),
        },
    }
    decision = dict(
        decision_by_requirement.get(
            first_missing,
            {
                "decision_id": f"approve_{first_missing}_authority_request",
                "question": f"Austin: approve the governed authority path for {first_missing}?",
                "authority_required": "operator_authority",
                "current_runtime_status": "blocked",
                "next_operator_command": ".\\scripts\\lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status",
                "proof_script": "scripts/lens-summon-preflight.ps1 -Mode Status",
                "follow_up_after_approval": "Return to the prerequisite bring-up plan for the next bounded handoff.",
            },
        )
    )
    decision.update(
        {
            "first_missing_required_before_enable": first_missing,
            "missing_required_before_enable": missing_requirements,
            "requires_explicit_operator_decision": True,
            "script_would_request_authority_if_run": True,
            "script_would_grant_authority": False,
            "script_would_execute": False,
            "script_would_mutate_runtime_now": False,
            "self_granted": False,
        }
    )
    return {
        "status": "operator_decision_required",
        "queued_decision_count": 1,
        "decisions": [decision],
    }


def _file_contains_all(path: Path, needles: list[str]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return all(needle in text for needle in needles)


def _chat_lens_visibility_contract(action: dict[str, Any]) -> dict[str, Any]:
    repo = _repo_root()
    lens_source = repo / "apps" / "chat_ui" / "src" / "lens" / "index.ts"
    lens_test = repo / "apps" / "chat_ui" / "src" / "lens" / "index.test.ts"
    presentation_demo = repo / "scripts" / "francis-presentation-demo.ps1"
    proof_path = os.getenv("FRANCIS_ONE_VISIBLE_LOOP_PROOF_PATH", "")
    receipt_trace_paths = [
        proof_path,
        str(action.get("operator_receipt_path") or ""),
        str(action.get("desktop_bridge_receipt_path") or ""),
    ]
    lens_status_contract_verified = _file_contains_all(
        lens_source,
        [
            "stage6_readiness",
            "prerequisite_bringup",
            "operator_sequence",
            "presentStage6PrerequisiteBringup",
        ],
    )
    lens_status_test_contract_verified = _file_contains_all(
        lens_test,
        [
            "presentStage6PrerequisiteBringup",
            "operator_sequence_command_availability",
            "stage6_readiness.prerequisite_bringup.operator_sequence.operator_command",
        ],
    )
    presentation_demo_contract_verified = _file_contains_all(
        presentation_demo,
        [
            "receipt_trace_status_paths",
            "target_observer_status",
            "desktop_effect_confirmed",
            "actual_chat_ui_render_verified",
            "actual_lens_ui_render_verified",
        ],
    )
    receipt_trace_artifact_paths_present = all(bool(path) for path in receipt_trace_paths)
    contract_verified = (
        lens_status_contract_verified
        and lens_status_test_contract_verified
        and presentation_demo_contract_verified
        and receipt_trace_artifact_paths_present
    )
    return {
        "status": "ui_contract_visible_render_unverified" if contract_verified else "ui_contract_gap",
        "receipt_trace_status_paths": receipt_trace_paths,
        "receipt_trace_artifact_paths_present": receipt_trace_artifact_paths_present,
        "lens_status_contract_verified": lens_status_contract_verified,
        "lens_status_test_contract_verified": lens_status_test_contract_verified,
        "presentation_demo_contract_verified": presentation_demo_contract_verified,
        "render_validation_required": "browser_or_live_chat_lens_ui_proof",
        "actual_chat_ui_render_verified": False,
        "actual_lens_ui_render_verified": False,
    }


repo = _repo_root()
summon = _run_json_script(str(repo / "scripts" / "lens-summon-preflight.ps1"), "-Mode", "Status")
summon_payload = summon["payload"]
host_supervisor = _run_json_script(str(repo / "scripts" / "lens-host-supervisor.ps1"), "-Mode", "Status")
host_supervisor_payload = host_supervisor["payload"]
canonical_summon = _run_json_script(
    str(repo / "scripts" / "lens-canonical-summon-runtime-proof.ps1"),
    "-Mode",
    "Status",
    "-DataDir",
    str(repo / "data"),
)
canonical_summon_payload = canonical_summon["payload"]
canonical_summon_runtime_observed = _canonical_summon_runtime_observed(canonical_summon)
canonical_checks = (
    canonical_summon_payload.get("checks")
    if isinstance(canonical_summon_payload.get("checks"), dict)
    else {}
)
overlay = _overlay_status()
action = _fixture_action_proof()
operator_decision_queue = _operator_decision_queue(
    summon_payload,
    host_supervisor_payload,
    canonical_summon_payload,
    canonical_summon_runtime_observed,
)
chat_lens_visibility = _chat_lens_visibility_contract(action)
operator_approved_summon = os.getenv("FRANCIS_ONE_VISIBLE_LOOP_OPERATOR_APPROVED_SUMMON") == "1"
summon_authority_evidence_observed = bool(operator_approved_summon or canonical_summon_runtime_observed)
summon_ready = bool(
    canonical_summon_runtime_observed or not bool(summon_payload.get("missing_required_before_enable"))
)
resident_supervised_runtime = bool(
    canonical_checks.get("supervised_resident_host") is True
    or host_supervisor_payload.get("resident_supervised_runtime")
)
actual_render_verified = bool(
    chat_lens_visibility.get("actual_chat_ui_render_verified") is True
    and chat_lens_visibility.get("actual_lens_ui_render_verified") is True
)
visible_loop_ready = (
    summon_authority_evidence_observed
    and summon_ready
    and resident_supervised_runtime
    and overlay.get("overlay_window_visible") is True
    and action.get("status") == "passed"
    and actual_render_verified
)
if not summon_authority_evidence_observed:
    next_operator_decision = "approve_summon_enable_and_live_safe_target_bridge_proof"
elif action.get("status") != "passed":
    next_operator_decision = "configure_and_approve_live_safe_target_bridge_proof"
elif not actual_render_verified:
    next_operator_decision = "perform_browser_or_live_chat_lens_ui_proof"
else:
    next_operator_decision = "none"
proof = {
    "kind": "francis.one_visible_loop.proof",
    "mode": "Status",
    "created_at": datetime.now(UTC).isoformat(),
    "proof_path": os.getenv("FRANCIS_ONE_VISIBLE_LOOP_PROOF_PATH", ""),
    "status": "passed" if visible_loop_ready else "blocked",
    "next_operator_decision": next_operator_decision,
    "summon": {
        "operator_approved_summon_decision": operator_approved_summon,
        "summon_authority_evidence_observed": summon_authority_evidence_observed,
        "canonical_runtime_readback_observed": canonical_summon_runtime_observed,
        "status": (
            canonical_summon_payload.get("summon_readiness_status_after_execute", "ready_for_operator_review")
            if canonical_summon_runtime_observed
            else summon_payload.get("status", "unknown")
        ),
        "global_hotkey": (
            canonical_summon_payload.get("global_hotkey", "")
            if canonical_summon_runtime_observed
            else summon_payload.get("global_hotkey", "")
        ),
        "required_before_enable": summon_payload.get("required_before_enable", []),
        "missing_required_before_enable": (
            [] if canonical_summon_runtime_observed else summon_payload.get("missing_required_before_enable", [])
        ),
        "first_missing_required_before_enable": (
            "" if canonical_summon_runtime_observed else summon_payload.get("first_missing_required_before_enable", "")
        ),
        "hotkey_runtime_readback": summon_payload.get("hotkey_runtime_readback", {}),
        "tray_runtime_readback": summon_payload.get("tray_runtime_readback", {}),
        "overlay_runtime_readback": summon_payload.get("overlay_runtime_readback", {}),
        "next_smallest_truthful_gap": (
            "one_visible_loop_safe_target_effect_and_render_proof"
            if canonical_summon_runtime_observed
            else summon_payload.get("next_smallest_truthful_gap", "")
        ),
        "preflight_status": summon_payload.get("status", "unknown"),
        "preflight_missing_required_before_enable": summon_payload.get("missing_required_before_enable", []),
        "canonical_runtime_readback": {
            "exit_code": canonical_summon.get("exit_code"),
            "status": canonical_summon_payload.get("status", "missing"),
            "source": canonical_summon_payload.get("source", ""),
            "request_id": canonical_summon_payload.get("request_id", ""),
            "summon_receipt_id": canonical_summon_payload.get("summon_receipt_id", ""),
            "orb_control_receipt_id": canonical_summon_payload.get("orb_control_receipt_id", ""),
            "overlay_pid": canonical_summon_payload.get("overlay_pid", 0),
            "hotkey_pid": canonical_summon_payload.get("hotkey_pid", 0),
            "tray_pid": canonical_summon_payload.get("tray_pid", 0),
            "supervisor_pid": canonical_summon_payload.get("supervisor_pid", 0),
            "resident_host_pid": canonical_summon_payload.get("resident_host_pid", 0),
            "renderer_pid": canonical_summon_payload.get("renderer_pid", 0),
            "renderer_process_count": canonical_summon_payload.get("renderer_process_count", 0),
            "checks": canonical_checks,
            "blockers": canonical_summon_payload.get("blockers", []),
        },
    },
    "resident_host": {
        "status": (
            "supervised_resident_runtime_observed"
            if canonical_summon_runtime_observed
            else host_supervisor_payload.get("status", "unknown")
        ),
        "readback_source": (
            "canonical_live_summon_runtime_readback"
            if canonical_summon_runtime_observed
            else "lens_host_supervisor_status"
        ),
        "resident_supervised_runtime": resident_supervised_runtime,
        "supervisor_process_alive": bool(
            canonical_summon_runtime_observed or host_supervisor_payload.get("supervisor_process_alive")
        ),
        "supervisor_pid": canonical_summon_payload.get("supervisor_pid", 0),
        "resident_host_pid": canonical_summon_payload.get("resident_host_pid", 0),
        "authority_required": host_supervisor_payload.get("authority_required", ""),
        "authority_granted": bool(
            canonical_checks.get("authority_ready") is True or host_supervisor_payload.get("authority_granted")
        ),
        "next_smallest_truthful_gap": (
            "one_visible_loop_safe_target_effect_and_render_proof"
            if canonical_summon_runtime_observed
            else host_supervisor_payload.get("next_smallest_truthful_gap", "")
        ),
        "generic_supervisor_status": host_supervisor_payload.get("status", "unknown"),
    },
    "orb_presence": overlay,
    "operator_action": action,
    "operator_decision_queue": operator_decision_queue,
    "chat_lens_visibility": chat_lens_visibility,
    "governance": {
        "does_not_self_enable_summon": True,
        "does_not_default_enable_desktop_bridge": True,
        "canonical_runtime_readback_only": True,
        "physical_input_used": False,
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
