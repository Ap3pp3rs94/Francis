from __future__ import annotations

import ctypes
import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

from .contracts import InputActionResult, InputActionSpec, InputActuatorError

INPUT_ACTUATOR_STAGE = "Stage 9 / Takeover Input Actuator"
_MAX_TEXT_LEN = 240
_MAX_COORD = 10000
_SENSITIVE_TERMS = (
    "password",
    "passcode",
    "secret",
    "token",
    "api_key",
    "apikey",
    "recovery phrase",
    "seed phrase",
)

_ALLOWED_ACTIONS = {
    "mouse.move": InputActionSpec("mouse.move", "Move cursor to bounded coordinates."),
    "mouse.click": InputActionSpec("mouse.click", "Click a bounded mouse button."),
    "keyboard.type": InputActionSpec("keyboard.type", "Type bounded non-sensitive text."),
    "keyboard.hotkey": InputActionSpec("keyboard.hotkey", "Press an allowlisted hotkey chord."),
}

_VK_MAP: dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    "win": 0x5B,
}
for _digit in range(10):
    _VK_MAP[str(_digit)] = 0x30 + _digit
for _offset, _letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _VK_MAP[_letter] = 0x41 + _offset
for _index in range(1, 13):
    _VK_MAP[f"f{_index}"] = 0x6F + _index


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _state_root() -> Path:
    override = os.environ.get("FRANCIS_INPUT_ACTUATOR_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "input_actuator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _proposal_dir() -> Path:
    path = _state_root() / "proposals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _receipt_dir() -> Path:
    path = _state_root() / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _real_input_enabled() -> bool:
    return os.environ.get("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", "").strip() == "1"


def _takeover_snapshot() -> dict[str, Any]:
    try:
        from francis.takeover import takeover_status_snapshot

        snapshot = takeover_status_snapshot(limit=5)
        if isinstance(snapshot, dict):
            return snapshot
    except Exception as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "error": str(exc),
            "control_transfer_active": False,
            "active_session_id": "",
        }
    return {
        "ok": False,
        "status": "unavailable",
        "control_transfer_active": False,
        "active_session_id": "",
    }


def input_status() -> dict[str, Any]:
    takeover = _takeover_snapshot()
    return InputActionResult(
        ok=True,
        status="ready",
        data={
            "stage": INPUT_ACTUATOR_STAGE,
            "source_id": "input_actuator",
            "supported_actions": sorted(_ALLOWED_ACTIONS),
            "backend": "win32.user32" if os.name == "nt" else "dry_run_only",
            "real_input_enabled": _real_input_enabled(),
            "real_input_env_gate": "FRANCIS_INPUT_ACTUATOR_ENABLE_REAL=1",
            "takeover_status": {
                "available": bool(takeover.get("ok")),
                "status": _clean_text(takeover.get("status")),
                "control_transfer_active": bool(takeover.get("control_transfer_active")),
                "active_session_id": _clean_text(takeover.get("active_session_id")),
                "panic_stop_ready": bool(takeover.get("panic_stop_ready")),
                "handback_required": bool(takeover.get("handback_required")),
            },
        },
        governance={
            "read_only": True,
            "does_not_move_mouse": True,
            "does_not_type": True,
            "raw_mcp_input_authority": False,
            "real_input_requires_env_gate": True,
            "real_input_requires_active_takeover": True,
        },
    ).to_dict()


def propose_input_action(args: dict[str, Any]) -> dict[str, Any]:
    actor = _clean_text(args.get("actor"), "unknown")[:240]
    objective = _clean_text(args.get("objective"), "unspecified")[:500]
    session_id = _clean_text(args.get("session_id"))[:160]
    kind = _clean_text(args.get("kind"))
    payload = _coerce_payload(args.get("payload"))

    action = _validate_action(kind, payload)
    proposal = {
        "proposal_id": "",
        "kind": kind,
        "payload": action["payload"],
        "public_action": action["public_action"],
        "actor": actor,
        "objective": objective,
        "session_id": session_id,
        "created_at": _utc_now(),
        "requires_manual_approval": True,
        "requires_real_input_env_gate_for_physical_execution": True,
        "requires_active_takeover_for_physical_execution": True,
    }
    proposal_id = hashlib.sha256(json.dumps(proposal, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    proposal["proposal_id"] = proposal_id

    path = _proposal_dir() / f"{proposal_id}.json"
    path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")

    return InputActionResult(
        ok=True,
        status="approval_required",
        data={
            "proposal_id": proposal_id,
            "proposal_path": str(path),
            "approval_phrase": f"APPROVE INPUT {proposal_id}",
            "action_preview": action["public_action"],
            "real_input_enabled": _real_input_enabled(),
        },
        governance={
            "read_only": False,
            "writes_proposal": True,
            "moves_mouse": False,
            "types_keyboard": False,
            "manual_approval_required": True,
            "raw_mcp_input_authority": False,
        },
    ).to_dict()


def execute_approved_input_action(args: dict[str, Any]) -> dict[str, Any]:
    proposal_id = _clean_text(args.get("proposal_id"))
    approval_phrase = _clean_text(args.get("approval_phrase"))

    if not proposal_id:
        raise InputActuatorError("proposal_id is required")

    if approval_phrase != f"APPROVE INPUT {proposal_id}":
        return InputActionResult(
            ok=False,
            status="approval_required",
            data={
                "proposal_id": proposal_id,
                "expected_approval_phrase": f"APPROVE INPUT {proposal_id}",
            },
            governance={
                "read_only": False,
                "moves_mouse": False,
                "types_keyboard": False,
                "manual_approval_required": True,
                "raw_mcp_input_authority": False,
            },
            error="approval phrase missing or incorrect",
        ).to_dict()

    proposal_path = _proposal_dir() / f"{proposal_id}.json"
    if not proposal_path.exists():
        return InputActionResult(
            ok=False,
            status="not_found",
            data={"proposal_id": proposal_id},
            governance={"read_only": False, "raw_mcp_input_authority": False},
            error="proposal not found",
        ).to_dict()

    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    if not isinstance(proposal, dict):
        raise InputActuatorError("proposal is malformed")

    kind = _clean_text(proposal.get("kind"))
    payload = _coerce_payload(proposal.get("payload"))
    validated = _validate_action(kind, payload)
    public_action = validated["public_action"]
    real_enabled = _real_input_enabled()
    takeover = _takeover_snapshot()
    active_takeover = bool(takeover.get("control_transfer_active"))

    if real_enabled and not active_takeover:
        receipt = _write_receipt(
            "blocked-active-takeover-required",
            {
                "proposal": _public_proposal(proposal),
                "public_action": public_action,
                "real_input_enabled": real_enabled,
                "blocked_reason": "active_takeover_required_for_real_input",
            },
        )
        return InputActionResult(
            ok=False,
            status="blocked_active_takeover_required",
            data={
                "proposal_id": proposal_id,
                "receipt_id": receipt["receipt_id"],
                "receipt_path": receipt["receipt_path"],
                "public_action": public_action,
            },
            governance={
                "read_only": False,
                "moves_mouse": False,
                "types_keyboard": False,
                "manual_approval_consumed": True,
                "real_input_enabled": real_enabled,
                "active_takeover_required": True,
                "raw_mcp_input_authority": False,
            },
            error="real input requires an active Takeover/Pilot control-transfer session",
        ).to_dict()

    backend_result = _perform_input_action(kind, payload, real_enabled=real_enabled)
    receipt = _write_receipt(
        "execute-approved",
        {
            "proposal": _public_proposal(proposal),
            "public_action": public_action,
            "backend_result": backend_result,
            "real_input_enabled": real_enabled,
        },
    )
    ok = bool(backend_result.get("ok"))
    return InputActionResult(
        ok=ok,
        status=_clean_text(backend_result.get("status"), "complete" if ok else "failed"),
        data={
            "proposal_id": proposal_id,
            "receipt_id": receipt["receipt_id"],
            "receipt_path": receipt["receipt_path"],
            "public_action": public_action,
            "backend_result": backend_result,
        },
        governance={
            "read_only": False,
            "moves_mouse": kind.startswith("mouse.") and bool(backend_result.get("performed")),
            "types_keyboard": kind.startswith("keyboard.") and bool(backend_result.get("performed")),
            "manual_approval_consumed": True,
            "real_input_enabled": real_enabled,
            "dry_run": bool(backend_result.get("dry_run")),
            "raw_mcp_input_authority": False,
            "receipt_written": True,
        },
        error=_clean_text(backend_result.get("error")) or None,
    ).to_dict()


def input_receipts_readback(args: dict[str, Any]) -> dict[str, Any]:
    receipt_id = _clean_text(args.get("receipt_id"))
    if not receipt_id:
        receipts = sorted(_receipt_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:20]
        return InputActionResult(
            ok=True,
            status="ready",
            data={"receipts": [item.stem for item in receipts]},
            governance={"read_only": True, "raw_mcp_input_authority": False},
        ).to_dict()

    path = _receipt_dir() / f"{receipt_id}.json"
    if not path.exists():
        return InputActionResult(
            ok=False,
            status="not_found",
            data={"receipt_id": receipt_id},
            governance={"read_only": True, "raw_mcp_input_authority": False},
            error="receipt not found",
        ).to_dict()

    return InputActionResult(
        ok=True,
        status="ready",
        data={"receipt": json.loads(path.read_text(encoding="utf-8"))},
        governance={"read_only": True, "raw_mcp_input_authority": False},
    ).to_dict()


def _perform_input_action(kind: str, payload: dict[str, Any], *, real_enabled: bool) -> dict[str, Any]:
    if not real_enabled:
        return {
            "ok": True,
            "status": "dry_run",
            "performed": False,
            "dry_run": True,
            "reason": "FRANCIS_INPUT_ACTUATOR_ENABLE_REAL is not enabled",
        }

    if os.name != "nt":
        return {
            "ok": False,
            "status": "unsupported_platform",
            "performed": False,
            "dry_run": False,
            "error": "real input backend currently supports Windows only",
        }

    try:
        if kind == "mouse.move":
            _move_mouse(int(payload["x"]), int(payload["y"]))
        elif kind == "mouse.click":
            x = payload.get("x")
            y = payload.get("y")
            if x is not None and y is not None:
                _move_mouse(int(x), int(y))
            _click_mouse(str(payload.get("button", "left")), int(payload.get("clicks", 1)))
        elif kind == "keyboard.type":
            _type_text(str(payload["text"]))
        elif kind == "keyboard.hotkey":
            _hotkey([str(key) for key in payload["keys"]])
        else:
            raise InputActuatorError(f"unsupported input action: {kind}")
    except Exception as exc:
        return {
            "ok": False,
            "status": "backend_error",
            "performed": False,
            "dry_run": False,
            "error": str(exc),
        }

    return {
        "ok": True,
        "status": "performed",
        "performed": True,
        "dry_run": False,
        "backend": "win32.user32",
    }


def _move_mouse(x: int, y: int) -> None:
    user32 = getattr(ctypes, "windll").user32
    user32.SetCursorPos(x, y)


def _click_mouse(button: str, clicks: int) -> None:
    flags = {
        "left": (0x0002, 0x0004),
        "right": (0x0008, 0x0010),
        "middle": (0x0020, 0x0040),
    }.get(button)
    if flags is None:
        raise InputActuatorError(f"unsupported mouse button: {button}")

    user32 = getattr(ctypes, "windll").user32
    down, up = flags
    for _ in range(max(1, min(clicks, 3))):
        user32.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.03)
        user32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.03)


def _type_text(text: str) -> None:
    user32 = getattr(ctypes, "windll").user32
    for character in text:
        code = ord(character)
        user32.keybd_event(0, code, 0x0004, 0)
        user32.keybd_event(0, code, 0x0004 | 0x0002, 0)
        time.sleep(0.005)


def _hotkey(keys: list[str]) -> None:
    user32 = getattr(ctypes, "windll").user32
    vks = [_vk_for_key(key) for key in keys]
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.01)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, 0x0002, 0)
        time.sleep(0.01)


def _validate_action(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind not in _ALLOWED_ACTIONS:
        raise InputActuatorError(f"unsupported input action: {kind}")

    if kind == "mouse.move":
        x = _bounded_coord(payload.get("x"), "x")
        y = _bounded_coord(payload.get("y"), "y")
        move_payload = {"x": x, "y": y}
        return {"payload": move_payload, "public_action": {"kind": kind, **move_payload}}

    if kind == "mouse.click":
        click_payload: dict[str, Any] = {
            "button": _safe_button(payload.get("button")),
            "clicks": max(1, min(_safe_int(payload.get("clicks"), 1), 3)),
        }
        if payload.get("x") is not None and payload.get("y") is not None:
            click_payload["x"] = _bounded_coord(payload.get("x"), "x")
            click_payload["y"] = _bounded_coord(payload.get("y"), "y")
        return {"payload": click_payload, "public_action": {"kind": kind, **click_payload}}

    if kind == "keyboard.type":
        text = str(payload.get("text", ""))
        if not text:
            raise InputActuatorError("keyboard.type requires text")
        if len(text) > _MAX_TEXT_LEN:
            raise InputActuatorError(f"keyboard.type text exceeds {_MAX_TEXT_LEN} characters")
        _refuse_sensitive_text(text)
        return {
            "payload": {"text": text},
            "public_action": {
                "kind": kind,
                "text_length": len(text),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
        }

    if kind == "keyboard.hotkey":
        keys = payload.get("keys")
        if not isinstance(keys, list) or not keys:
            raise InputActuatorError("keyboard.hotkey requires keys")
        safe_keys = [_safe_key(key) for key in keys]
        if len(safe_keys) > 4:
            raise InputActuatorError("keyboard.hotkey supports at most 4 keys")
        return {"payload": {"keys": safe_keys}, "public_action": {"kind": kind, "keys": safe_keys}}

    raise InputActuatorError(f"unsupported input action: {kind}")


def _bounded_coord(value: Any, name: str) -> int:
    number = _safe_int(value, -1)
    if number < 0 or number > _MAX_COORD:
        raise InputActuatorError(f"{name} coordinate out of bounds")
    return number


def _safe_button(value: Any) -> str:
    button = _clean_text(value, "left").lower()
    if button not in {"left", "right", "middle"}:
        raise InputActuatorError(f"unsupported mouse button: {button}")
    return button


def _safe_key(value: Any) -> str:
    key = _clean_text(value).lower()
    if key not in _VK_MAP:
        raise InputActuatorError(f"unsupported hotkey key: {key}")
    return key


def _vk_for_key(key: str) -> int:
    normalized = key.lower().strip()
    if normalized not in _VK_MAP:
        raise InputActuatorError(f"unsupported hotkey key: {key}")
    return _VK_MAP[normalized]


def _refuse_sensitive_text(text: str) -> None:
    lowered = text.lower()
    if any(term in lowered for term in _SENSITIVE_TERMS):
        raise InputActuatorError("keyboard.type refuses sensitive credential-like text")


def _public_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": _clean_text(proposal.get("proposal_id")),
        "kind": _clean_text(proposal.get("kind")),
        "public_action": proposal.get("public_action") if isinstance(proposal.get("public_action"), dict) else {},
        "actor": _clean_text(proposal.get("actor"))[:240],
        "objective": _clean_text(proposal.get("objective"))[:500],
        "session_id": _clean_text(proposal.get("session_id"))[:160],
        "created_at": _clean_text(proposal.get("created_at")),
    }


def _write_receipt(kind: str, payload: dict[str, Any]) -> dict[str, str]:
    receipt_id = f"input_{kind}_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": f"francis.input_actuator.{kind}",
        "receipt_id": receipt_id,
        "stage": INPUT_ACTUATOR_STAGE,
        "source_id": "input_actuator",
        "created_at": _utc_now(),
        "payload": payload,
        "governance": {
            "raw_mcp_input_authority": False,
            "manual_approval_required": True,
            "real_input_requires_env_gate": True,
            "real_input_requires_active_takeover": True,
            "receipt_written": True,
        },
    }
    path = _receipt_dir() / f"{receipt_id}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"receipt_id": receipt_id, "receipt_path": str(path)}
