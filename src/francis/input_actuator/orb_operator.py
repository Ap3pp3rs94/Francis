from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir, repo_root

from .contracts import InputActuatorError
from .orb_desktop_bridge import perform_orb_desktop_action
from .tools import execute_approved_input_action, propose_input_action

ORB_OPERATOR_SURFACE = "francis.orb_operator.v0"
ORB_OPERATOR_STAGE = "Phase 2 / Lens Orb embodied desktop operation"
ORB_POINTER_MODE = "orb_pointer"
ORB_BACKEND_MODES = ("dry_run", "guarded_live", ORB_POINTER_MODE)
ORB_VIRTUAL_POINTER_ID = "francis.orb.primary_virtual_pointer"
ORB_ARRIVAL_REQUIRED_INPUT_KINDS = frozenset({"mouse.click", "mouse.drag", "keyboard.type"})
ORB_POINTER_ARRIVAL_TIMEOUT_MS_ENV = "FRANCIS_ORB_POINTER_ARRIVAL_TIMEOUT_MS"
ORB_POINTER_DEFAULT_ARRIVAL_TIMEOUT_MS = 8000
ORB_POINTER_MAX_ARRIVAL_TIMEOUT_MS = 30000

ORB_FEEDBACK_STATES = (
    "idle",
    "observing",
    "aiming",
    "moving",
    "clicking",
    "typing",
    "blocked",
    "failed",
    "complete",
)
_MAX_COORD = 10000
_DEFAULT_ACTOR = "francis.orb_operator"
_DEFAULT_OBJECTIVE = "Orb embodied desktop operation"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _state_root(*, create: bool = True) -> Path:
    override = os.environ.get("FRANCIS_ORB_OPERATOR_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "orb_operator"
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _receipt_dir(*, create: bool = True) -> Path:
    path = _state_root(create=create) / "receipts"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _virtual_pointer_state_path(*, create: bool = True) -> Path:
    return _state_root(create=create) / "virtual_pointer_state.json"


def _input_actuator_state_root() -> Path:
    override = os.environ.get("FRANCIS_INPUT_ACTUATOR_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "input_actuator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _input_proposal_path(proposal_id: str) -> Path:
    return _input_actuator_state_root() / "proposals" / f"{proposal_id}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_coord(value: Any, name: str) -> int:
    number = _safe_int(value, -1)
    if number < 0 or number > _MAX_COORD:
        raise InputActuatorError(f"{name} coordinate out of bounds")
    return number


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_intent_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _receipt_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _rect_center(rect: dict[str, Any]) -> tuple[int, int]:
    x = _bounded_coord(rect.get("x"), "rect.x")
    y = _bounded_coord(rect.get("y"), "rect.y")
    width = max(0, _safe_int(rect.get("width"), 0))
    height = max(0, _safe_int(rect.get("height"), 0))
    return (_bounded_coord(x + width // 2, "rect.center_x"), _bounded_coord(y + height // 2, "rect.center_y"))


def _read_virtual_pointer_state(*, create: bool = True) -> dict[str, Any]:
    path = _virtual_pointer_state_path(create=create)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _orb_arrival_required(input_kind: str) -> bool:
    return input_kind in ORB_ARRIVAL_REQUIRED_INPUT_KINDS


def _orb_arrival_timeout_seconds() -> float:
    timeout_ms = _safe_int(
        os.environ.get(ORB_POINTER_ARRIVAL_TIMEOUT_MS_ENV),
        ORB_POINTER_DEFAULT_ARRIVAL_TIMEOUT_MS,
    )
    return float(max(500, min(timeout_ms, ORB_POINTER_MAX_ARRIVAL_TIMEOUT_MS))) / 1000.0


def _orb_virtual_pointer_receipt_path(pointer_updated_at: str) -> Path:
    request_id = f"orb-virtual-pointer-{_receipt_digest(pointer_updated_at)}"
    return data_dir() / "runtime" / "lens-overlay" / "orb-position-commands" / f"{request_id}.json"


def _contact_phase_for_input_kind(input_kind: str) -> str:
    if input_kind == "mouse.click":
        return "click_press"
    if input_kind == "mouse.drag":
        return "drag_press"
    if input_kind == "keyboard.type":
        return "type_press"
    return ""


def _with_orb_action_phase(payload: dict[str, Any], *, input_kind: str, phase: str) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["orb_action_phase"] = phase
    enriched["requires_orb_arrival_readback"] = _orb_arrival_required(input_kind)
    contact_phase = _contact_phase_for_input_kind(input_kind)
    if contact_phase:
        enriched["pending_contact_phase"] = contact_phase
        enriched["contact_visual_required"] = True
    return enriched


def _await_orb_arrival_readback(
    *,
    pointer_state: dict[str, Any],
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    pointer_updated_at = _clean_text(pointer_state.get("updated_at"))
    if not pointer_updated_at:
        return {
            "ok": False,
            "status": "blocked_orb_arrival_timeout",
            "reason": "pointer_updated_at_missing",
            "orb_virtual_pointer_applied": False,
            "native_renderer_move_applied": False,
            "timeout_ms": 0,
        }
    timeout = (
        _orb_arrival_timeout_seconds()
        if timeout_seconds is None
        else max(0.5, min(timeout_seconds, ORB_POINTER_MAX_ARRIVAL_TIMEOUT_MS / 1000.0))
    )
    receipt_path = _orb_virtual_pointer_receipt_path(pointer_updated_at)
    deadline = time.monotonic() + timeout
    last_receipt: dict[str, Any] = {}
    progress_receipt_observed = False
    while time.monotonic() <= deadline:
        receipt = _read_json_object(receipt_path)
        if receipt:
            last_receipt = receipt
            status = _clean_text(receipt.get("status"))
            if status.endswith("_travel_started") and bool(receipt.get("ok")) and not progress_receipt_observed:
                progress_receipt_observed = True
                travel_duration_seconds = float(max(0, _safe_int(receipt.get("travel_duration_ms"), 0))) / 1000.0
                progress_budget = max(3.0, min(travel_duration_seconds + 4.0, 12.0))
                deadline = max(deadline, time.monotonic() + progress_budget)
            overlay_applied = bool(
                receipt.get("applied")
                or receipt.get("runtime_overlay_position_changed")
                or receipt.get("orb_virtual_pointer_applied")
            )
            native_applied = bool(receipt.get("native_renderer_move_applied"))
            if (
                status == "orb_virtual_pointer_applied"
                and bool(receipt.get("ok"))
                and overlay_applied
                and native_applied
            ):
                return {
                    "ok": True,
                    "status": status,
                    "receipt_id": receipt_path.stem,
                    "receipt_path": str(receipt_path),
                    "pointer_updated_at": pointer_updated_at,
                    "orb_virtual_pointer_applied": True,
                    "native_renderer_move_applied": True,
                    "native_renderer_move_status": _clean_text(receipt.get("native_renderer_move_status")),
                    "travelled_to_target": bool(receipt.get("travelled_to_target")),
                    "contact_visual_applied": bool(receipt.get("contact_visual_applied")),
                    "progress_receipt_observed": progress_receipt_observed,
                    "timeout_ms": int(round(timeout * 1000.0)),
                }
        time.sleep(0.05)
    return {
        "ok": False,
        "status": "blocked_orb_arrival_timeout",
        "receipt_id": receipt_path.stem,
        "receipt_path": str(receipt_path),
        "pointer_updated_at": pointer_updated_at,
        "orb_virtual_pointer_applied": False,
        "native_renderer_move_applied": bool(last_receipt.get("native_renderer_move_applied")),
        "last_receipt_status": _clean_text(last_receipt.get("status")),
        "progress_receipt_observed": progress_receipt_observed,
        "timeout_ms": int(round(timeout * 1000.0)),
    }


def _virtual_pointer_position(input_kind: str, payload: dict[str, Any]) -> tuple[int, int]:
    previous = _read_virtual_pointer_state()
    if input_kind == "mouse.drag" and payload.get("target_x") is not None and payload.get("target_y") is not None:
        return _bounded_coord(payload.get("target_x"), "target_x"), _bounded_coord(payload.get("target_y"), "target_y")
    if payload.get("x") is not None and payload.get("y") is not None:
        return _bounded_coord(payload.get("x"), "x"), _bounded_coord(payload.get("y"), "y")
    return (
        _bounded_coord(previous.get("x", 0), "virtual_pointer.x"),
        _bounded_coord(previous.get("y", 0), "virtual_pointer.y"),
    )


def _virtual_pointer_action_status(input_kind: str, payload: dict[str, Any] | None = None) -> str:
    safe_payload = payload or {}
    if input_kind == "mouse.move":
        return "virtual_pointer_moved"
    if input_kind == "orb.carry":
        phase = _clean_text(safe_payload.get("carry_phase") or safe_payload.get("visible_orb_phase")).lower()
        if phase == "source_center":
            return "virtual_pointer_carry_started"
        if phase == "destination_center":
            return "virtual_pointer_carry_released"
        return "virtual_pointer_carry_recorded"
    if input_kind == "mouse.click":
        if _clean_text(safe_payload.get("button"), "left").lower() == "right":
            return "virtual_pointer_right_click_recorded"
        return "virtual_pointer_click_recorded"
    if input_kind == "mouse.drag":
        return "virtual_pointer_drag_recorded"
    if input_kind in {"keyboard.type", "keyboard.hotkey"}:
        return "virtual_pointer_keyboard_event_recorded"
    return "virtual_pointer_event_recorded"


def _virtual_pointer_gesture(input_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if input_kind == "mouse.click":
        button = _clean_text(payload.get("button"), "left").lower()
        return {
            "kind": "right_click" if button == "right" else "click",
            "button": button,
            "clicks": max(1, min(_safe_int(payload.get("clicks"), 1), 3)),
            "x": payload.get("x"),
            "y": payload.get("y"),
            "orb_action_phase": _clean_text(payload.get("orb_action_phase"), "travel"),
            "pending_contact_phase": _clean_text(payload.get("pending_contact_phase")),
            "visible_orb_body_only": True,
        }
    if input_kind == "mouse.drag":
        return {
            "kind": "drag",
            "button": _clean_text(payload.get("button"), "left").lower(),
            "start": {
                "x": _bounded_coord(payload.get("x"), "x"),
                "y": _bounded_coord(payload.get("y"), "y"),
            },
            "end": {
                "x": _bounded_coord(payload.get("target_x"), "target_x"),
                "y": _bounded_coord(payload.get("target_y"), "target_y"),
            },
            "orb_action_phase": _clean_text(payload.get("orb_action_phase"), "travel"),
            "pending_contact_phase": _clean_text(payload.get("pending_contact_phase")),
            "visible_orb_body_only": True,
        }
    if input_kind == "keyboard.type":
        text = str(payload.get("text", ""))
        return {
            "kind": "type_contact",
            "text_length": len(text),
            "text_sha256": _hash_text(text),
            "orb_action_phase": _clean_text(payload.get("orb_action_phase"), "travel"),
            "pending_contact_phase": _clean_text(payload.get("pending_contact_phase")),
            "visible_orb_body_only": True,
            "francis_owned_cursor": True,
        }
    if input_kind == "orb.carry":
        phase = _clean_text(payload.get("carry_phase") or payload.get("visible_orb_phase"), "carry").lower()
        target_id = _clean_text(payload.get("semantic_target_id"))[:120]
        target_kind = _clean_text(payload.get("semantic_target_kind"))[:64]
        return {
            "kind": "carry",
            "phase": phase,
            "carry_state": _carry_state_for_phase(phase),
            "semantic_target_id": target_id,
            "semantic_target_kind": target_kind,
            "stable_identity_digest": _clean_text(payload.get("stable_identity_digest"))[:64],
            "desktop_position_index": _safe_int(payload.get("desktop_position_index"), -1),
            "point": {
                "x": _bounded_coord(payload.get("x"), "x"),
                "y": _bounded_coord(payload.get("y"), "y"),
            },
            "visible_orb_body_only": True,
            "francis_owned_cursor": True,
        }
    return {}


def _virtual_pointer_contact_state(input_kind: str, payload: dict[str, Any], gesture: dict[str, Any]) -> dict[str, Any]:
    contact_phase = _clean_text(payload.get("pending_contact_phase") or gesture.get("pending_contact_phase"))
    required = payload.get("contact_visual_required") is True or bool(contact_phase)
    return {
        "required": required,
        "pending_contact_phase": contact_phase,
        "orb_action_phase": _clean_text(payload.get("orb_action_phase") or gesture.get("orb_action_phase"), "travel"),
        "input_kind": input_kind,
        "visible_orb_body_only": True,
        "controls_user_os_cursor": False,
        "grants_execution_authority": False,
    }


def _carry_state_for_phase(phase: str) -> str:
    if phase == "source_center":
        return "grabbed"
    if phase == "destination_center":
        return "released"
    return "carrying"


def _virtual_pointer_carry_state(input_kind: str, payload: dict[str, Any], gesture: dict[str, Any]) -> dict[str, Any]:
    if input_kind != "orb.carry":
        return {"active": False, "carry_state": "none", "held_target": {}}
    carry_state = _clean_text(gesture.get("carry_state"), "carrying")
    target_id = _clean_text(gesture.get("semantic_target_id"))[:120]
    target_kind = _clean_text(gesture.get("semantic_target_kind"))[:64]
    released = carry_state == "released"
    return {
        "active": not released,
        "carry_state": carry_state,
        "held_target": {}
        if released
        else {
            "semantic_target_id": target_id,
            "semantic_target_kind": target_kind,
            "stable_identity_digest": _clean_text(payload.get("stable_identity_digest"))[:64],
            "desktop_position_index": _safe_int(payload.get("desktop_position_index"), -1),
        },
        "last_target": {
            "semantic_target_id": target_id,
            "semantic_target_kind": target_kind,
            "desktop_position_index": _safe_int(payload.get("desktop_position_index"), -1),
        },
    }


def _write_virtual_pointer_state(
    *,
    input_kind: str,
    payload: dict[str, Any],
    actor: str,
    objective: str,
    session_id: str,
    resolved_position: tuple[int, int] | None = None,
    desktop_bridge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    x, y = resolved_position or _virtual_pointer_position(input_kind, payload)
    now = _utc_now()
    public_action = _public_input_action(input_kind, payload)
    gesture = _virtual_pointer_gesture(input_kind, payload)
    carry_state = _virtual_pointer_carry_state(input_kind, payload, gesture)
    contact_state = _virtual_pointer_contact_state(input_kind, payload, gesture)
    requires_bridge = input_kind not in {"mouse.move", "orb.carry"}
    requires_arrival = payload.get("requires_orb_arrival_readback") is True or _orb_arrival_required(input_kind)
    bridge = desktop_bridge if isinstance(desktop_bridge, dict) else {}
    desktop_action_sent = bool(bridge.get("desktop_action_sent"))
    desktop_effect_performed = bool(bridge.get("desktop_effect_performed"))
    desktop_effect_confirmed = bool(bridge.get("desktop_effect_confirmed"))
    orb_action_phase = _clean_text(payload.get("orb_action_phase"), "travel")
    state = {
        "ok": True,
        "kind": "francis.orb_operator.virtual_pointer_state",
        "surface": ORB_OPERATOR_SURFACE,
        "stage": ORB_OPERATOR_STAGE,
        "pointer_id": ORB_VIRTUAL_POINTER_ID,
        "updated_at": now,
        "mode": ORB_POINTER_MODE,
        "x": x,
        "y": y,
        "position": {"x": x, "y": y, "source": "orb_virtual_pointer"},
        "carrying": bool(carry_state.get("active")),
        "carry_state": carry_state,
        "contact_state": contact_state,
        "last_action": {
            "input_kind": input_kind,
            "status": _virtual_pointer_action_status(input_kind, payload),
            "public_action": public_action,
            "gesture": gesture,
            "carry_state": carry_state,
            "contact_state": contact_state,
            "orb_action_phase": orb_action_phase,
            "requires_orb_arrival_readback": requires_arrival,
            "actor": actor,
            "objective": objective,
            "session_id": session_id,
            "desktop_bridge_status": _clean_text(bridge.get("status")),
            "desktop_bridge_receipt_id": _clean_text(bridge.get("receipt_id")),
            "desktop_bridge_receipt_path": _clean_text(bridge.get("receipt_path")),
            "desktop_action_sent": desktop_action_sent,
            "desktop_effect_performed": desktop_effect_performed,
            "desktop_effect_confirmed": desktop_effect_confirmed,
            "physical_input_performed": False,
            "user_os_cursor_moved": False,
            "user_mouse_taken": False,
            "requires_app_bridge_for_desktop_effect": requires_bridge and not desktop_effect_performed,
        },
        "gesture": gesture,
        "governance": {
            "virtual_pointer_only": True,
            "francis_owned_cursor": True,
            "controls_user_os_cursor": False,
            "moves_user_mouse": False,
            "physical_input_performed": False,
            "desktop_action_sent": desktop_action_sent,
            "desktop_effect_performed": desktop_effect_performed,
            "desktop_effect_confirmed": desktop_effect_confirmed,
            "requires_app_bridge_for_desktop_effect": requires_bridge and not desktop_effect_performed,
            "requires_orb_arrival_readback": requires_arrival,
            "orb_action_phase": orb_action_phase,
            "receipt_required_for_actions": True,
        },
    }
    path = _virtual_pointer_state_path()
    _write_json(path, state)
    return {"path": str(path), "state": state}


@dataclass(frozen=True)
class OrbIntent:
    """A visible Orb intention before it becomes a desktop input action."""

    kind: str
    x: int | None = None
    y: int | None = None
    target_id: str = ""
    rect: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    button: str = "left"
    clicks: int = 1
    key: str = ""
    window_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def move_to(cls, x: int, y: int, **metadata: Any) -> OrbIntent:
        return cls(kind="move_to", x=x, y=y, metadata=metadata)

    @classmethod
    def hover_target(cls, *, target_id: str = "", rect: dict[str, Any] | None = None, **metadata: Any) -> OrbIntent:
        return cls(kind="hover_target", target_id=target_id, rect=rect or {}, metadata=metadata)

    @classmethod
    def click(
        cls,
        *,
        x: int | None = None,
        y: int | None = None,
        target_id: str = "",
        rect: dict[str, Any] | None = None,
        button: str = "left",
        clicks: int = 1,
        **metadata: Any,
    ) -> OrbIntent:
        return cls(
            kind="click",
            x=x,
            y=y,
            target_id=target_id,
            rect=rect or {},
            button=button,
            clicks=clicks,
            metadata=metadata,
        )

    @classmethod
    def type_text(cls, text: str, **metadata: Any) -> OrbIntent:
        return cls(kind="type_text", text=text, metadata=metadata)

    @classmethod
    def key_press(cls, key: str, **metadata: Any) -> OrbIntent:
        return cls(kind="key_press", key=key, metadata=metadata)

    @classmethod
    def focus_window(cls, window_ref: str, **metadata: Any) -> OrbIntent:
        return cls(kind="focus_window", window_ref=window_ref, metadata=metadata)

    @classmethod
    def inspect_area(cls, rect: dict[str, Any], **metadata: Any) -> OrbIntent:
        return cls(kind="inspect_area", rect=rect, metadata=metadata)

    @classmethod
    def mouse_drag(
        cls,
        *,
        x: int,
        y: int,
        target_x: int,
        target_y: int,
        button: str = "left",
        **metadata: Any,
    ) -> OrbIntent:
        drag_metadata = {**metadata, "target_x": target_x, "target_y": target_y}
        return cls(kind="mouse_drag", x=x, y=y, button=button, metadata=drag_metadata)

    @classmethod
    def orb_carry_desktop_icon(
        cls,
        *,
        x: int,
        y: int,
        semantic_target_id: str,
        semantic_target_kind: str = "desktop_icon",
        carry_phase: str = "carrying",
        **metadata: Any,
    ) -> OrbIntent:
        carry_metadata = {
            **metadata,
            "semantic_target_id": semantic_target_id,
            "semantic_target_kind": semantic_target_kind,
            "carry_phase": carry_phase,
        }
        return cls(kind="orb_carry_desktop_icon", x=x, y=y, metadata=carry_metadata)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OrbIntent:
        kind = _clean_text(payload.get("kind") or payload.get("intent")).lower()
        aliases = {
            "move": "move_to",
            "mouse.move": "move_to",
            "mouse.click": "click",
            "mouse.drag": "mouse_drag",
            "keyboard.type": "type_text",
            "keyboard.hotkey": "key_press",
        }
        kind = aliases.get(kind, kind)
        metadata = _coerce_dict(payload.get("metadata"))
        if kind == "mouse_drag":
            if payload.get("target_x") is not None:
                metadata["target_x"] = _bounded_coord(payload.get("target_x"), "target_x")
            if payload.get("target_y") is not None:
                metadata["target_y"] = _bounded_coord(payload.get("target_y"), "target_y")
        return cls(
            kind=kind,
            x=payload.get("x") if payload.get("x") is None else _bounded_coord(payload.get("x"), "x"),
            y=payload.get("y") if payload.get("y") is None else _bounded_coord(payload.get("y"), "y"),
            target_id=_clean_text(payload.get("target_id")),
            rect=_coerce_dict(payload.get("rect") or payload.get("target_rect")),
            text=str(payload.get("text", "")),
            button=_clean_text(payload.get("button"), "left").lower(),
            clicks=max(1, min(_safe_int(payload.get("clicks"), 1), 3)),
            key=_clean_text(payload.get("key") or payload.get("keys"), "").lower(),
            window_ref=_clean_text(payload.get("window_ref")),
            metadata=metadata,
        )

    def public_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "target_id": self.target_id,
            "key": self.key,
            "window_ref": self.window_ref,
            "metadata": dict(self.metadata),
        }
        if self.kind in {"click", "mouse_drag"}:
            payload["button"] = self.button
            payload["clicks"] = self.clicks
        if self.x is not None:
            payload["x"] = self.x
        if self.y is not None:
            payload["y"] = self.y
        if self.rect:
            payload["rect"] = dict(self.rect)
        if self.text:
            payload["text_length"] = len(self.text)
            payload["text_sha256"] = _hash_text(self.text)
        return {key: value for key, value in payload.items() if value not in ("", {}, None)}


@dataclass(frozen=True)
class IntentResolution:
    feedback_state: str
    input_kind: str = ""
    input_payload: dict[str, Any] = field(default_factory=dict)
    resolved_target: dict[str, Any] = field(default_factory=dict)
    supported: bool = True
    reason: str = ""


@dataclass(frozen=True)
class BackendAttempt:
    ok: bool
    status: str
    mode: str
    backend: str
    input_kind: str = ""
    proposal_id: str = ""
    approval_phrase: str = ""
    input_receipt_id: str = ""
    input_receipt_path: str = ""
    performed: bool = False
    dry_run: bool = True
    result: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "status": self.status,
            "mode": self.mode,
            "backend": self.backend,
            "input_kind": self.input_kind,
            "proposal_id": self.proposal_id,
            "approval_phrase": self.approval_phrase,
            "input_receipt_id": self.input_receipt_id,
            "input_receipt_path": self.input_receipt_path,
            "performed": self.performed,
            "dry_run": self.dry_run,
            "result": self.result,
            "governance": self.governance,
        }
        if self.error:
            payload["error"] = self.error
        return {key: value for key, value in payload.items() if value not in ("", {}, None)}


@dataclass(frozen=True)
class OperatorReceipt:
    timestamp: str
    mission_id: str
    session_id: str
    requested_intent: dict[str, Any]
    resolved_target: dict[str, Any]
    backend: dict[str, Any]
    mode: str
    result: str
    feedback_state: str
    governance: dict[str, Any]
    error: str = ""
    receipt_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.result not in {"failed", "blocked"} and not self.result.startswith("blocked_"),
            "kind": "francis.orb_operator.receipt",
            "surface": ORB_OPERATOR_SURFACE,
            "stage": ORB_OPERATOR_STAGE,
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "created_at": self.timestamp,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "requested_intent": self.requested_intent,
            "resolved_target": self.resolved_target,
            "backend": self.backend,
            "mode": self.mode,
            "result": self.result,
            "feedback_state": self.feedback_state,
            "supported_feedback_states": list(ORB_FEEDBACK_STATES),
            "governance": self.governance,
        }
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class DesktopInputBackend:
    """Governed Orb-to-desktop backend wrapper.

    Dry-run mode writes an Orb operator receipt and a governed input proposal; it
    never calls the physical input executor. Guarded-live mode only delegates to
    the existing input actuator execution path when an approved proposal phrase is
    supplied, leaving takeover/handoff/env gates load-bearing. Orb-pointer mode
    updates Francis's own virtual pointer state and never touches the user's OS
    cursor or keyboard.
    """

    mode: str = "dry_run"
    actor: str = _DEFAULT_ACTOR
    objective: str = _DEFAULT_OBJECTIVE
    session_id: str = ""

    def __post_init__(self) -> None:
        if self.mode not in ORB_BACKEND_MODES:
            raise InputActuatorError("DesktopInputBackend mode must be dry_run, guarded_live, or orb_pointer")

    def mouse_move(self, x: int, y: int, *, proposal_id: str = "", approval_phrase: str = "") -> BackendAttempt:
        return self._submit("mouse.move", {"x": x, "y": y}, proposal_id=proposal_id, approval_phrase=approval_phrase)

    def mouse_click(
        self,
        *,
        button: str = "left",
        clicks: int = 1,
        x: int | None = None,
        y: int | None = None,
        expected_target_title: str = "",
        proposal_id: str = "",
        approval_phrase: str = "",
    ) -> BackendAttempt:
        payload: dict[str, Any] = {"button": button, "clicks": clicks}
        if x is not None and y is not None:
            payload["x"] = x
            payload["y"] = y
        if expected_target_title:
            payload["expected_target_title"] = expected_target_title
        return self._submit("mouse.click", payload, proposal_id=proposal_id, approval_phrase=approval_phrase)

    def type_text(
        self,
        text: str,
        *,
        expected_target_title: str = "",
        proposal_id: str = "",
        approval_phrase: str = "",
    ) -> BackendAttempt:
        payload = {"text": text}
        if expected_target_title:
            payload["expected_target_title"] = expected_target_title
        return self._submit("keyboard.type", payload, proposal_id=proposal_id, approval_phrase=approval_phrase)

    def key_press(self, key: str, *, proposal_id: str = "", approval_phrase: str = "") -> BackendAttempt:
        return self._submit(
            "keyboard.hotkey", {"keys": [key]}, proposal_id=proposal_id, approval_phrase=approval_phrase
        )

    def mouse_drag(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        target_x: int | None = None,
        target_y: int | None = None,
        button: str = "left",
        desktop_shell_target_required: bool = False,
        semantic_target_id: str = "",
        desktop_position_index: int = -1,
        stable_identity_digest: str = "",
        proposal_id: str = "",
        approval_phrase: str = "",
    ) -> BackendAttempt:
        if self.mode == ORB_POINTER_MODE:
            if x is None or y is None or target_x is None or target_y is None:
                return BackendAttempt(
                    ok=False,
                    status="blocked",
                    mode=self.mode,
                    backend="francis.orb_virtual_pointer",
                    input_kind="mouse.drag",
                    governance={
                        "decision": "deny",
                        "reason": "mouse_drag_requires_start_and_target_coordinates",
                        "virtual_pointer_only": True,
                        "raw_input": False,
                        "performed": False,
                        "physical_input_performed": False,
                        "user_mouse_taken": False,
                    },
                    error="mouse drag requires start and target coordinates",
                )
            payload: dict[str, Any] = {"x": x, "y": y, "target_x": target_x, "target_y": target_y, "button": button}
            if desktop_shell_target_required:
                payload["desktop_shell_target_required"] = True
                payload["semantic_target_id"] = semantic_target_id
                payload["desktop_position_index"] = desktop_position_index
                payload["stable_identity_digest"] = stable_identity_digest
            return self._submit("mouse.drag", payload, proposal_id=proposal_id, approval_phrase=approval_phrase)

        return BackendAttempt(
            ok=False,
            status="unsupported",
            mode=self.mode,
            backend="francis.input_actuator",
            input_kind="mouse.drag",
            governance={
                "decision": "deny",
                "reason": "mouse_drag_backend_not_declared",
                "raw_input": False,
                "performed": False,
                "physical_input_performed": False,
                "user_mouse_taken": False,
            },
            error="mouse drag is not yet supported by the governed input actuator",
        )

    def orb_carry(
        self,
        *,
        x: int,
        y: int,
        semantic_target_id: str,
        semantic_target_kind: str,
        stable_identity_digest: str,
        desktop_position_index: int,
        carry_phase: str,
        proposal_id: str = "",
        approval_phrase: str = "",
    ) -> BackendAttempt:
        if self.mode != ORB_POINTER_MODE:
            return BackendAttempt(
                ok=False,
                status="unsupported",
                mode=self.mode,
                backend="francis.orb_virtual_pointer",
                input_kind="orb.carry",
                governance={
                    "decision": "deny",
                    "reason": "orb_carry_requires_virtual_pointer_mode",
                    "virtual_pointer_only": self.mode == ORB_POINTER_MODE,
                    "raw_input": False,
                    "performed": False,
                    "physical_input_performed": False,
                    "user_mouse_taken": False,
                },
                error="Orb carry is supported only by the Francis virtual pointer",
            )
        return self._submit(
            "orb.carry",
            {
                "x": x,
                "y": y,
                "semantic_target_id": semantic_target_id,
                "semantic_target_kind": semantic_target_kind,
                "stable_identity_digest": stable_identity_digest,
                "desktop_position_index": desktop_position_index,
                "carry_phase": carry_phase,
            },
            proposal_id=proposal_id,
            approval_phrase=approval_phrase,
        )

    def _submit(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        proposal_id: str = "",
        approval_phrase: str = "",
    ) -> BackendAttempt:
        if self.mode == ORB_POINTER_MODE:
            try:
                resolved_position = _virtual_pointer_position(kind, payload)
                bridge_payload = dict(payload)
                bridge_payload.setdefault("x", resolved_position[0])
                bridge_payload.setdefault("y", resolved_position[1])
                arrival_required = _orb_arrival_required(kind)
                pointer_payload = (
                    _with_orb_action_phase(payload, input_kind=kind, phase="travel")
                    if arrival_required
                    else dict(payload)
                )
                pointer = _write_virtual_pointer_state(
                    input_kind=kind,
                    payload=pointer_payload,
                    actor=self.actor,
                    objective=self.objective,
                    session_id=self.session_id,
                    resolved_position=resolved_position,
                    desktop_bridge={},
                )
                state = _coerce_dict(pointer.get("state"))
                last_action = _coerce_dict(state.get("last_action"))
                orb_arrival: dict[str, Any] = {"required": arrival_required, "ok": not arrival_required}
                if arrival_required:
                    orb_arrival = _await_orb_arrival_readback(pointer_state=state)
                    if not bool(orb_arrival.get("ok")):
                        return BackendAttempt(
                            ok=False,
                            status="blocked_orb_arrival_timeout",
                            mode=self.mode,
                            backend="francis.orb_virtual_pointer",
                            input_kind=kind,
                            performed=False,
                            dry_run=False,
                            result={
                                "input_execution_attempted": False,
                                "proposal_written": False,
                                "virtual_pointer_updated": True,
                                "pointer_state_path": _clean_text(pointer.get("path")),
                                "pointer_state": {
                                    "pointer_id": _clean_text(state.get("pointer_id")),
                                    "x": _safe_int(state.get("x")),
                                    "y": _safe_int(state.get("y")),
                                    "updated_at": _clean_text(state.get("updated_at")),
                                    "carrying": bool(state.get("carrying")),
                                    "carry_state": state.get("carry_state")
                                    if isinstance(state.get("carry_state"), dict)
                                    else {},
                                    "contact_state": state.get("contact_state")
                                    if isinstance(state.get("contact_state"), dict)
                                    else {},
                                    "last_action": last_action,
                                },
                                "desktop_bridge": {},
                                "desktop_bridge_status": "",
                                "desktop_bridge_receipt_id": "",
                                "desktop_bridge_receipt_path": "",
                                "desktop_action_sent": False,
                                "desktop_effect_performed": False,
                                "desktop_effect_confirmed": False,
                                "physical_input_performed": False,
                                "user_os_cursor_moved": False,
                                "user_mouse_taken": False,
                                "requires_app_bridge_for_desktop_effect": bool(
                                    last_action.get("requires_app_bridge_for_desktop_effect")
                                ),
                                "orb_arrival": orb_arrival,
                                "orb_arrival_required": True,
                                "orb_arrival_satisfied": False,
                                "bridge_fired_after_arrival": False,
                                "action_fired_without_orb_arrival": False,
                                "unembodied_action_blocked": True,
                            },
                            governance={
                                "decision": "deny",
                                "reason": "orb_arrival_readback_required_before_desktop_action",
                                "virtual_pointer_only": True,
                                "dry_run": False,
                                "writes_pointer_state": True,
                                "writes_proposal": False,
                                "raw_input": False,
                                "performed": False,
                                "physical_input_performed": False,
                                "user_os_cursor_controlled": False,
                                "user_mouse_taken": False,
                                "desktop_action_sent": False,
                                "desktop_effect_performed": False,
                                "desktop_effect_confirmed": False,
                                "requires_orb_arrival_readback": True,
                                "orb_arrival_satisfied": False,
                                "bridge_fired_after_arrival": False,
                                "action_fired_without_orb_arrival": False,
                                "unembodied_action_blocked": True,
                            },
                            error="Orb arrival readback timed out before desktop action",
                        )

                if arrival_required:
                    bridge_payload["orb_arrival_receipt_id"] = _clean_text(orb_arrival.get("receipt_id"))
                    bridge_payload["orb_arrival_satisfied"] = True
                    bridge_payload["orb_embodied_action"] = True
                desktop_bridge = (
                    perform_orb_desktop_action(
                        input_kind=kind,
                        payload=bridge_payload,
                        actor=self.actor,
                        objective=self.objective,
                        session_id=self.session_id,
                    )
                    if kind not in {"mouse.move", "orb.carry"}
                    else {}
                )
            except Exception as exc:
                return BackendAttempt(
                    ok=False,
                    status="blocked",
                    mode=self.mode,
                    backend="francis.orb_virtual_pointer",
                    input_kind=kind,
                    governance={
                        "decision": "deny",
                        "virtual_pointer_only": True,
                        "raw_input": False,
                        "performed": False,
                        "physical_input_performed": False,
                        "user_mouse_taken": False,
                    },
                    error=str(exc),
                )
            desktop_bridge_dict = desktop_bridge if isinstance(desktop_bridge, dict) else {}
            desktop_action_sent = bool(desktop_bridge_dict.get("desktop_action_sent"))
            desktop_effect_performed = bool(desktop_bridge_dict.get("desktop_effect_performed"))
            desktop_effect_confirmed = bool(desktop_bridge_dict.get("desktop_effect_confirmed"))
            physical_input_performed = bool(desktop_bridge_dict.get("physical_input_performed"))
            user_os_cursor_moved = bool(desktop_bridge_dict.get("uses_user_os_cursor"))
            user_mouse_taken = bool(desktop_bridge_dict.get("user_mouse_taken"))
            requires_app_bridge = bool(last_action.get("requires_app_bridge_for_desktop_effect"))
            requires_app_bridge_for_desktop_effect = requires_app_bridge and not desktop_effect_performed
            action_fired_without_arrival = bool(desktop_bridge) and arrival_required and not bool(orb_arrival.get("ok"))
            return BackendAttempt(
                ok=True,
                status=_virtual_pointer_action_status(kind, pointer_payload),
                mode=self.mode,
                backend="francis.orb_virtual_pointer",
                input_kind=kind,
                performed=False,
                dry_run=False,
                result={
                    "input_execution_attempted": False,
                    "proposal_written": False,
                    "virtual_pointer_updated": True,
                    "pointer_state_path": _clean_text(pointer.get("path")),
                    "pointer_state": {
                        "pointer_id": _clean_text(state.get("pointer_id")),
                        "x": _safe_int(state.get("x")),
                        "y": _safe_int(state.get("y")),
                        "updated_at": _clean_text(state.get("updated_at")),
                        "carrying": bool(state.get("carrying")),
                        "carry_state": state.get("carry_state") if isinstance(state.get("carry_state"), dict) else {},
                        "contact_state": state.get("contact_state")
                        if isinstance(state.get("contact_state"), dict)
                        else {},
                        "last_action": last_action,
                    },
                    "desktop_bridge": desktop_bridge_dict,
                    "desktop_bridge_status": _clean_text(desktop_bridge_dict.get("status")),
                    "desktop_bridge_receipt_id": _clean_text(desktop_bridge_dict.get("receipt_id")),
                    "desktop_bridge_receipt_path": _clean_text(desktop_bridge_dict.get("receipt_path")),
                    "desktop_action_sent": desktop_action_sent,
                    "desktop_effect_performed": desktop_effect_performed,
                    "desktop_effect_confirmed": desktop_effect_confirmed,
                    "physical_input_performed": physical_input_performed,
                    "user_os_cursor_moved": user_os_cursor_moved,
                    "user_mouse_taken": user_mouse_taken,
                    "requires_app_bridge_for_desktop_effect": requires_app_bridge_for_desktop_effect,
                    "orb_arrival": orb_arrival,
                    "orb_arrival_required": arrival_required,
                    "orb_arrival_satisfied": bool(orb_arrival.get("ok")),
                    "bridge_fired_after_arrival": desktop_action_sent
                    and (not arrival_required or bool(orb_arrival.get("ok"))),
                    "action_fired_without_orb_arrival": action_fired_without_arrival,
                    "unembodied_action": action_fired_without_arrival,
                    "unembodied_action_blocked": False,
                },
                governance={
                    "decision": "allow_virtual_pointer",
                    "virtual_pointer_only": True,
                    "dry_run": False,
                    "writes_pointer_state": True,
                    "writes_proposal": False,
                    "raw_input": False,
                    "performed": False,
                    "physical_input_performed": physical_input_performed,
                    "user_os_cursor_controlled": user_os_cursor_moved,
                    "user_mouse_taken": user_mouse_taken,
                    "desktop_action_sent": desktop_action_sent,
                    "desktop_effect_performed": desktop_effect_performed,
                    "desktop_effect_confirmed": desktop_effect_confirmed,
                    "requires_app_bridge_for_desktop_effect": requires_app_bridge_for_desktop_effect,
                    "requires_orb_arrival_readback": arrival_required,
                    "orb_arrival_satisfied": bool(orb_arrival.get("ok")),
                    "bridge_fired_after_arrival": desktop_action_sent
                    and (not arrival_required or bool(orb_arrival.get("ok"))),
                    "action_fired_without_orb_arrival": action_fired_without_arrival,
                    "unembodied_action": action_fired_without_arrival,
                    "unembodied_action_blocked": False,
                },
            )

        if self.mode == "dry_run":
            try:
                proposal = propose_input_action(
                    {
                        "actor": self.actor,
                        "objective": self.objective,
                        "session_id": self.session_id,
                        "kind": kind,
                        "payload": payload,
                    }
                )
            except Exception as exc:
                return BackendAttempt(
                    ok=False,
                    status="blocked",
                    mode=self.mode,
                    backend="francis.input_actuator",
                    input_kind=kind,
                    governance={
                        "decision": "deny",
                        "dry_run": True,
                        "performed": False,
                        "raw_input": False,
                    },
                    error=str(exc),
                )
            data = _coerce_dict(proposal.get("data"))
            return BackendAttempt(
                ok=bool(proposal.get("ok")),
                status="dry_run_proposed",
                mode=self.mode,
                backend="francis.input_actuator",
                input_kind=kind,
                proposal_id=_clean_text(data.get("proposal_id")),
                approval_phrase=_clean_text(data.get("approval_phrase")),
                performed=False,
                dry_run=True,
                result={
                    "input_execution_attempted": False,
                    "proposal_written": True,
                    "proposal_path": _clean_text(data.get("proposal_path")),
                    "public_action": data.get("action_preview") if isinstance(data.get("action_preview"), dict) else {},
                },
                governance={
                    "decision": "allow_dry_run",
                    "dry_run": True,
                    "writes_proposal": True,
                    "manual_approval_required_for_execution": True,
                    "raw_input": False,
                    "performed": False,
                },
            )

        if not proposal_id or not approval_phrase:
            return BackendAttempt(
                ok=False,
                status="approval_required",
                mode=self.mode,
                backend="francis.input_actuator",
                input_kind=kind,
                governance={
                    "decision": "deny",
                    "reason": "approved_input_proposal_required",
                    "dry_run": False,
                    "raw_input": False,
                    "performed": False,
                },
                error="guarded_live requires proposal_id and exact approval_phrase",
            )

        matched, mismatch_reason = _proposal_matches_input_action(proposal_id, kind, payload)
        if not matched:
            return BackendAttempt(
                ok=False,
                status="blocked",
                mode=self.mode,
                backend="francis.input_actuator",
                input_kind=kind,
                proposal_id=proposal_id,
                governance={
                    "decision": "deny",
                    "reason": mismatch_reason,
                    "dry_run": False,
                    "raw_input": False,
                    "performed": False,
                },
                error=mismatch_reason,
            )

        result = execute_approved_input_action({"proposal_id": proposal_id, "approval_phrase": approval_phrase})
        data = _coerce_dict(result.get("data"))
        backend_result = _coerce_dict(data.get("backend_result"))
        return BackendAttempt(
            ok=bool(result.get("ok")),
            status=_clean_text(result.get("status"), "blocked"),
            mode=self.mode,
            backend="francis.input_actuator",
            input_kind=kind,
            proposal_id=proposal_id,
            input_receipt_id=_clean_text(data.get("receipt_id")),
            input_receipt_path=_clean_text(data.get("receipt_path")),
            performed=bool(backend_result.get("performed")),
            dry_run=bool(backend_result.get("dry_run")),
            result={
                "input_execution_attempted": True,
                "public_action": data.get("public_action") if isinstance(data.get("public_action"), dict) else {},
                "backend_result": backend_result,
            },
            governance={
                "decision": "allow_if_existing_gates_allow" if result.get("ok") else "deny",
                "raw_input": False,
                "performed": bool(backend_result.get("performed")),
                "dry_run": bool(backend_result.get("dry_run")),
                "manual_approval_consumed": bool(result.get("governance", {}).get("manual_approval_consumed")),
                "real_input_enabled": bool(result.get("governance", {}).get("real_input_enabled")),
            },
            error=_clean_text(result.get("error")),
        )


def _resolve_intent(intent: OrbIntent) -> IntentResolution:
    if intent.kind == "move_to":
        if intent.x is None or intent.y is None:
            return IntentResolution(feedback_state="blocked", supported=False, reason="move_to_requires_coordinates")
        return IntentResolution(
            feedback_state="moving",
            input_kind="mouse.move",
            input_payload={"x": _bounded_coord(intent.x, "x"), "y": _bounded_coord(intent.y, "y")},
            resolved_target={"x": intent.x, "y": intent.y, "source": "coordinates"},
        )

    if intent.kind == "hover_target":
        if intent.x is not None and intent.y is not None:
            x, y = _bounded_coord(intent.x, "x"), _bounded_coord(intent.y, "y")
        elif intent.rect:
            x, y = _rect_center(intent.rect)
        else:
            return IntentResolution(feedback_state="blocked", supported=False, reason="hover_target_requires_location")
        return IntentResolution(
            feedback_state="aiming",
            input_kind="mouse.move",
            input_payload={"x": x, "y": y},
            resolved_target={"x": x, "y": y, "target_id": intent.target_id, "source": "target"},
        )

    if intent.kind == "orb_carry_desktop_icon":
        if intent.x is None or intent.y is None:
            return IntentResolution(
                feedback_state="blocked",
                supported=False,
                reason="orb_carry_desktop_icon_requires_coordinates",
            )
        semantic_target_id = _clean_text(intent.metadata.get("semantic_target_id") or intent.target_id)[:120]
        semantic_target_kind = _clean_text(intent.metadata.get("semantic_target_kind"), "desktop_icon")[:64]
        carry_phase = _clean_text(
            intent.metadata.get("carry_phase") or intent.metadata.get("visible_orb_phase"), "carry"
        )
        if not semantic_target_id:
            return IntentResolution(
                feedback_state="blocked",
                supported=False,
                reason="orb_carry_desktop_icon_requires_semantic_target",
            )
        x, y = _bounded_coord(intent.x, "x"), _bounded_coord(intent.y, "y")
        stable_identity_digest = _clean_text(intent.metadata.get("stable_identity_digest"))[:64]
        desktop_position_index = _safe_int(intent.metadata.get("desktop_position_index"), -1)
        return IntentResolution(
            feedback_state="moving",
            input_kind="orb.carry",
            input_payload={
                "x": x,
                "y": y,
                "semantic_target_id": semantic_target_id,
                "semantic_target_kind": semantic_target_kind,
                "stable_identity_digest": stable_identity_digest,
                "desktop_position_index": desktop_position_index,
                "carry_phase": carry_phase,
            },
            resolved_target={
                "x": x,
                "y": y,
                "semantic_target_id": semantic_target_id,
                "semantic_target_kind": semantic_target_kind,
                "stable_identity_digest_present": bool(stable_identity_digest),
                "desktop_position_index": desktop_position_index,
                "carry_phase": carry_phase,
                "source": "semantic_desktop_target",
            },
        )

    if intent.kind == "click":
        payload: dict[str, Any] = {"button": intent.button, "clicks": intent.clicks}
        resolved: dict[str, Any] = {"target_id": intent.target_id, "button": intent.button, "clicks": intent.clicks}
        if intent.x is not None and intent.y is not None:
            x, y = _bounded_coord(intent.x, "x"), _bounded_coord(intent.y, "y")
            payload.update({"x": x, "y": y})
            resolved.update({"x": x, "y": y, "source": "coordinates"})
        elif intent.rect:
            x, y = _rect_center(intent.rect)
            payload.update({"x": x, "y": y})
            resolved.update({"x": x, "y": y, "source": "rect_center"})
        expected_target_title = _clean_text(intent.metadata.get("expected_target_title"))
        if expected_target_title:
            payload["expected_target_title"] = expected_target_title
            resolved["expected_target_title_present"] = True
            resolved["expected_target_title_sha256"] = _hash_text(expected_target_title)
        return IntentResolution(
            feedback_state="clicking",
            input_kind="mouse.click",
            input_payload=payload,
            resolved_target=resolved,
        )

    if intent.kind == "type_text":
        if not intent.text:
            return IntentResolution(feedback_state="blocked", supported=False, reason="type_text_requires_text")
        input_payload = {"text": intent.text}
        resolved_target: dict[str, Any] = {
            "text_length": len(intent.text),
            "text_sha256": _hash_text(intent.text),
        }
        expected_target_title = _clean_text(intent.metadata.get("expected_target_title"))
        if expected_target_title:
            input_payload["expected_target_title"] = expected_target_title
            resolved_target["expected_target_title_present"] = True
            resolved_target["expected_target_title_sha256"] = _hash_text(expected_target_title)
        return IntentResolution(
            feedback_state="typing",
            input_kind="keyboard.type",
            input_payload=input_payload,
            resolved_target=resolved_target,
        )

    if intent.kind == "key_press":
        if not intent.key:
            return IntentResolution(feedback_state="blocked", supported=False, reason="key_press_requires_key")
        return IntentResolution(
            feedback_state="typing",
            input_kind="keyboard.hotkey",
            input_payload={"keys": [intent.key]},
            resolved_target={"keys": [intent.key]},
        )

    if intent.kind == "inspect_area":
        if not intent.rect:
            return IntentResolution(feedback_state="blocked", supported=False, reason="inspect_area_requires_rect")
        x, y = _rect_center(intent.rect)
        return IntentResolution(
            feedback_state="observing",
            supported=True,
            reason="metadata_only_no_pixels_or_screenshot",
            resolved_target={"x": x, "y": y, "rect": dict(intent.rect), "actual_observed_region": "metadata_only"},
        )

    if intent.kind == "focus_window":
        return IntentResolution(feedback_state="blocked", supported=False, reason="focus_window_backend_not_declared")

    if intent.kind == "mouse_drag":
        if intent.x is None or intent.y is None:
            return IntentResolution(feedback_state="blocked", supported=False, reason="mouse_drag_requires_coordinates")
        target_x = intent.metadata.get("target_x")
        target_y = intent.metadata.get("target_y")
        if target_x is None or target_y is None:
            return IntentResolution(feedback_state="blocked", supported=False, reason="mouse_drag_requires_target")
        x, y = _bounded_coord(intent.x, "x"), _bounded_coord(intent.y, "y")
        end_x, end_y = _bounded_coord(target_x, "target_x"), _bounded_coord(target_y, "target_y")
        desktop_shell_target_required = intent.metadata.get("desktop_shell_target_required") is True
        semantic_target_id = _clean_text(intent.metadata.get("semantic_target_id"))[:120]
        stable_identity_digest = _clean_text(intent.metadata.get("stable_identity_digest"))[:64]
        desktop_position_index = _safe_int(intent.metadata.get("desktop_position_index"), -1)
        drag_payload: dict[str, Any] = {"x": x, "y": y, "target_x": end_x, "target_y": end_y, "button": intent.button}
        if desktop_shell_target_required:
            drag_payload.update(
                {
                    "desktop_shell_target_required": True,
                    "semantic_target_id": semantic_target_id,
                    "stable_identity_digest": stable_identity_digest,
                    "desktop_position_index": desktop_position_index,
                }
            )
        return IntentResolution(
            feedback_state="moving",
            input_kind="mouse.drag",
            input_payload=drag_payload,
            resolved_target={
                "x": x,
                "y": y,
                "target_x": end_x,
                "target_y": end_y,
                "button": intent.button,
                "source": "coordinates",
                "desktop_shell_target_required": desktop_shell_target_required,
                "semantic_target_id": semantic_target_id,
            },
        )

    return IntentResolution(feedback_state="blocked", supported=False, reason=f"unsupported_orb_intent:{intent.kind}")


def _run_backend(
    backend: DesktopInputBackend,
    resolution: IntentResolution,
    *,
    proposal_id: str = "",
    approval_phrase: str = "",
) -> BackendAttempt:
    if not resolution.supported:
        return BackendAttempt(
            ok=False,
            status="blocked",
            mode=backend.mode,
            backend="francis.input_actuator",
            input_kind=resolution.input_kind,
            governance={
                "decision": "deny",
                "reason": resolution.reason,
                "raw_input": False,
                "performed": False,
            },
            error=resolution.reason,
        )

    if not resolution.input_kind:
        return BackendAttempt(
            ok=True,
            status="metadata_only",
            mode=backend.mode,
            backend="francis.orb_operator",
            dry_run=True,
            governance={
                "decision": "allow_readback_only",
                "reason": resolution.reason,
                "raw_input": False,
                "performed": False,
                "screenshots": False,
                "pixels": False,
            },
            result={"input_execution_attempted": False, "metadata_only": True},
        )

    payload = resolution.input_payload
    if resolution.input_kind == "mouse.move":
        return backend.mouse_move(payload["x"], payload["y"], proposal_id=proposal_id, approval_phrase=approval_phrase)
    if resolution.input_kind == "orb.carry":
        return backend.orb_carry(
            x=payload["x"],
            y=payload["y"],
            semantic_target_id=_clean_text(payload.get("semantic_target_id")),
            semantic_target_kind=_clean_text(payload.get("semantic_target_kind")),
            stable_identity_digest=_clean_text(payload.get("stable_identity_digest")),
            desktop_position_index=_safe_int(payload.get("desktop_position_index"), -1),
            carry_phase=_clean_text(payload.get("carry_phase"), "carry"),
            proposal_id=proposal_id,
            approval_phrase=approval_phrase,
        )
    if resolution.input_kind == "mouse.click":
        return backend.mouse_click(
            button=str(payload.get("button", "left")),
            clicks=_safe_int(payload.get("clicks"), 1),
            x=payload.get("x"),
            y=payload.get("y"),
            expected_target_title=_clean_text(payload.get("expected_target_title")),
            proposal_id=proposal_id,
            approval_phrase=approval_phrase,
        )
    if resolution.input_kind == "keyboard.type":
        return backend.type_text(
            str(payload["text"]),
            expected_target_title=_clean_text(payload.get("expected_target_title")),
            proposal_id=proposal_id,
            approval_phrase=approval_phrase,
        )
    if resolution.input_kind == "keyboard.hotkey":
        keys = payload.get("keys") if isinstance(payload.get("keys"), list) else []
        key = _clean_text(keys[0] if keys else "")
        return backend.key_press(key, proposal_id=proposal_id, approval_phrase=approval_phrase)
    if resolution.input_kind == "mouse.drag":
        return backend.mouse_drag(
            x=payload.get("x"),
            y=payload.get("y"),
            target_x=payload.get("target_x"),
            target_y=payload.get("target_y"),
            button=str(payload.get("button", "left")),
            desktop_shell_target_required=payload.get("desktop_shell_target_required") is True,
            semantic_target_id=_clean_text(payload.get("semantic_target_id")),
            desktop_position_index=_safe_int(payload.get("desktop_position_index"), -1),
            stable_identity_digest=_clean_text(payload.get("stable_identity_digest")),
            proposal_id=proposal_id,
            approval_phrase=approval_phrase,
        )
    raise InputActuatorError(f"unsupported resolved input kind: {resolution.input_kind}")


def _public_input_action(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "mouse.move":
        return {"kind": kind, "x": payload.get("x"), "y": payload.get("y")}
    if kind == "orb.carry":
        return {
            "kind": kind,
            "x": payload.get("x"),
            "y": payload.get("y"),
            "semantic_target_id": _clean_text(payload.get("semantic_target_id"))[:120],
            "semantic_target_kind": _clean_text(payload.get("semantic_target_kind"))[:64],
            "desktop_position_index": _safe_int(payload.get("desktop_position_index"), -1),
            "carry_phase": _clean_text(payload.get("carry_phase"), "carry")[:80],
        }
    if kind == "mouse.click":
        public: dict[str, Any] = {
            "kind": kind,
            "button": _clean_text(payload.get("button"), "left"),
            "clicks": _safe_int(payload.get("clicks"), 1),
        }
        if payload.get("x") is not None and payload.get("y") is not None:
            public["x"] = payload.get("x")
            public["y"] = payload.get("y")
        return public
    if kind == "mouse.drag":
        drag_public: dict[str, Any] = {
            "kind": kind,
            "button": _clean_text(payload.get("button"), "left"),
            "x": payload.get("x"),
            "y": payload.get("y"),
            "target_x": payload.get("target_x"),
            "target_y": payload.get("target_y"),
        }
        if payload.get("desktop_shell_target_required") is True:
            drag_public["desktop_shell_target_required"] = True
            drag_public["semantic_target_id"] = _clean_text(payload.get("semantic_target_id"))[:120]
            drag_public["desktop_position_index"] = _safe_int(payload.get("desktop_position_index"), -1)
        return drag_public
    if kind == "keyboard.type":
        text = str(payload.get("text", ""))
        return {"kind": kind, "text_length": len(text), "text_sha256": _hash_text(text)}
    if kind == "keyboard.hotkey":
        raw_keys = payload.get("keys")
        keys: list[Any] = raw_keys if isinstance(raw_keys, list) else []
        return {"kind": kind, "keys": [_clean_text(item).lower() for item in keys]}
    return {"kind": kind}


def _proposal_matches_input_action(proposal_id: str, kind: str, payload: dict[str, Any]) -> tuple[bool, str]:
    path = _input_proposal_path(proposal_id)
    if not path.exists():
        return False, "input_proposal_not_found"
    try:
        proposal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "input_proposal_unreadable"
    if not isinstance(proposal, dict):
        return False, "input_proposal_malformed"
    proposal_kind = _clean_text(proposal.get("kind"))
    if proposal_kind != kind:
        return False, "input_proposal_kind_mismatch"
    public_action = proposal.get("public_action") if isinstance(proposal.get("public_action"), dict) else {}
    if public_action != _public_input_action(kind, payload):
        return False, "input_proposal_public_action_mismatch"
    return True, ""


def _operator_governance(
    *,
    mode: str,
    resolution: IntentResolution,
    backend_attempt: BackendAttempt,
) -> dict[str, Any]:
    live_allowed = mode == "guarded_live" and backend_attempt.performed
    uses_user_os_cursor = live_allowed and backend_attempt.input_kind.startswith("mouse.")
    virtual_pointer_only = mode == ORB_POINTER_MODE
    orb_desktop_action_sent = virtual_pointer_only and bool(backend_attempt.result.get("desktop_action_sent"))
    orb_desktop_effect_performed = virtual_pointer_only and bool(backend_attempt.result.get("desktop_effect_performed"))
    orb_desktop_effect_confirmed = virtual_pointer_only and bool(backend_attempt.result.get("desktop_effect_confirmed"))
    orb_pointer_uses_user_cursor = virtual_pointer_only and bool(
        backend_attempt.governance.get("user_os_cursor_controlled")
    )
    orb_pointer_physical_input = virtual_pointer_only and bool(
        backend_attempt.governance.get("physical_input_performed")
    )
    orb_pointer_user_mouse_taken = virtual_pointer_only and bool(backend_attempt.governance.get("user_mouse_taken"))
    return {
        "decision": backend_attempt.governance.get("decision", "deny"),
        "mode": mode,
        "orb_is_visible_operator_body": True,
        "raw_input": False,
        "screenshots": False,
        "pixels": False,
        "dry_run": bool(backend_attempt.dry_run),
        "virtual_pointer_only": virtual_pointer_only,
        "uses_user_os_cursor": uses_user_os_cursor or orb_pointer_uses_user_cursor,
        "user_mouse_taken": uses_user_os_cursor or orb_pointer_user_mouse_taken,
        "physical_input_performed": live_allowed or orb_pointer_physical_input,
        "desktop_action_sent": orb_desktop_action_sent,
        "desktop_effect_performed": live_allowed or orb_desktop_effect_performed,
        "desktop_effect_confirmed": orb_desktop_effect_confirmed,
        "live_input_performed": live_allowed,
        "input_execution_attempted": bool(backend_attempt.result.get("input_execution_attempted"))
        or orb_desktop_action_sent,
        "input_proposal_written": bool(backend_attempt.result.get("proposal_written")),
        "manual_approval_required_for_execution": mode == "dry_run" or backend_attempt.status == "approval_required",
        "guarded_live_requires_existing_input_approval": True,
        "guarded_live_requires_existing_handoff": True,
        "orb_pointer_requires_app_bridge_for_desktop_effect": bool(
            backend_attempt.result.get("requires_app_bridge_for_desktop_effect")
        ),
        "orb_arrival_required": bool(backend_attempt.result.get("orb_arrival_required")),
        "orb_arrival_satisfied": bool(backend_attempt.result.get("orb_arrival_satisfied")),
        "bridge_fired_after_arrival": bool(backend_attempt.result.get("bridge_fired_after_arrival")),
        "action_fired_without_orb_arrival": bool(backend_attempt.result.get("action_fired_without_orb_arrival")),
        "unembodied_action": bool(backend_attempt.result.get("unembodied_action")),
        "unembodied_action_blocked": bool(backend_attempt.result.get("unembodied_action_blocked")),
        "feedback_state_truthful": True,
        "unsupported_reason": "" if resolution.supported else resolution.reason,
        "receipt_written": True,
    }


def _write_operator_receipt(receipt: OperatorReceipt) -> dict[str, str]:
    receipt_id = receipt.receipt_id or f"orb_operator_{uuid.uuid4().hex[:12]}"
    payload = OperatorReceipt(
        timestamp=receipt.timestamp,
        mission_id=receipt.mission_id,
        session_id=receipt.session_id,
        requested_intent=receipt.requested_intent,
        resolved_target=receipt.resolved_target,
        backend=receipt.backend,
        mode=receipt.mode,
        result=receipt.result,
        feedback_state=receipt.feedback_state,
        governance=receipt.governance,
        error=receipt.error,
        receipt_id=receipt_id,
    ).to_dict()
    path = _receipt_dir() / f"{receipt_id}.json"
    _write_json(path, payload)
    return {"receipt_id": receipt_id, "receipt_path": str(path)}


def submit_orb_intent(args: dict[str, Any]) -> dict[str, Any]:
    raw_intent = _coerce_dict(args.get("intent")) or args
    intent = OrbIntent.from_dict(raw_intent)
    mode = _clean_text(args.get("mode"), "dry_run")
    actor = _clean_text(args.get("actor"), _DEFAULT_ACTOR)[:240]
    objective = _clean_text(args.get("objective"), _DEFAULT_OBJECTIVE)[:500]
    mission_id = _clean_text(args.get("mission_id"))[:160]
    session_id = _clean_text(args.get("session_id"))[:160]
    approval_phrase = _clean_text(args.get("approval_phrase"))
    proposal_id = _clean_text(args.get("proposal_id"))

    backend = DesktopInputBackend(mode=mode, actor=actor, objective=objective, session_id=session_id)
    resolution = _resolve_intent(intent)
    backend_attempt = _run_backend(
        backend,
        resolution,
        proposal_id=proposal_id,
        approval_phrase=approval_phrase,
    )
    result_status = _operator_result_status(resolution, backend_attempt)
    feedback_state = _operator_feedback_state(resolution, backend_attempt)
    governance = _operator_governance(mode=mode, resolution=resolution, backend_attempt=backend_attempt)
    receipt = OperatorReceipt(
        timestamp=_utc_now(),
        mission_id=mission_id,
        session_id=session_id,
        requested_intent=intent.public_dict(),
        resolved_target=resolution.resolved_target,
        backend=backend_attempt.to_dict(),
        mode=mode,
        result=result_status,
        feedback_state=feedback_state,
        governance=governance,
        error=backend_attempt.error,
    )
    receipt_ref = _write_operator_receipt(receipt)
    ok = backend_attempt.ok and result_status not in {"blocked", "failed"} and not result_status.startswith("blocked_")
    return {
        "ok": ok,
        "status": result_status,
        "surface": ORB_OPERATOR_SURFACE,
        "stage": ORB_OPERATOR_STAGE,
        "feedback_state": feedback_state,
        "intent": intent.public_dict(),
        "resolved_target": resolution.resolved_target,
        "backend": backend_attempt.to_dict(),
        "operator_receipt_id": receipt_ref["receipt_id"],
        "operator_receipt_path": receipt_ref["receipt_path"],
        "governance": governance,
        "error": backend_attempt.error or None,
    }


def submit_orb_sequence(args: dict[str, Any]) -> dict[str, Any]:
    intents = _coerce_intent_list(args.get("intents"))
    if not intents:
        raise InputActuatorError("submit_orb_sequence requires at least one intent")

    shared = {
        "mode": _clean_text(args.get("mode"), "dry_run"),
        "actor": _clean_text(args.get("actor"), _DEFAULT_ACTOR),
        "objective": _clean_text(args.get("objective"), _DEFAULT_OBJECTIVE),
        "mission_id": _clean_text(args.get("mission_id")),
        "session_id": _clean_text(args.get("session_id")),
    }
    results = [submit_orb_intent({**shared, "intent": intent}) for intent in intents]
    return {
        "ok": all(bool(item.get("ok")) for item in results),
        "status": "complete" if all(bool(item.get("ok")) for item in results) else "partial_or_blocked",
        "surface": ORB_OPERATOR_SURFACE,
        "stage": ORB_OPERATOR_STAGE,
        "mode": shared["mode"],
        "results": results,
        "receipt_paths": [
            str(item.get("operator_receipt_path")) for item in results if item.get("operator_receipt_path")
        ],
        "governance": {
            "raw_input": False,
            "dry_run": shared["mode"] == "dry_run",
            "virtual_pointer_only": shared["mode"] == ORB_POINTER_MODE,
            "uses_user_os_cursor": any(bool(item.get("governance", {}).get("uses_user_os_cursor")) for item in results),
            "user_mouse_taken": any(bool(item.get("governance", {}).get("user_mouse_taken")) for item in results),
            "receipt_written": True,
            "sequence_count": len(results),
        },
    }


def _operator_result_status(resolution: IntentResolution, backend_attempt: BackendAttempt) -> str:
    if backend_attempt.status.startswith("blocked_"):
        return backend_attempt.status
    if not resolution.supported or backend_attempt.status in {"blocked", "unsupported", "approval_required"}:
        return "blocked"
    if not backend_attempt.ok:
        return "failed"
    if backend_attempt.status.startswith("virtual_pointer_"):
        if backend_attempt.result.get("requires_app_bridge_for_desktop_effect") and not backend_attempt.result.get(
            "desktop_effect_performed"
        ):
            return "visible_only"
        return "complete"
    if backend_attempt.status == "dry_run_proposed":
        return "dry_run"
    if backend_attempt.status == "metadata_only":
        return "complete"
    if backend_attempt.performed:
        return "complete"
    if backend_attempt.dry_run:
        return "dry_run"
    return _clean_text(backend_attempt.status, "complete")


def _operator_feedback_state(resolution: IntentResolution, backend_attempt: BackendAttempt) -> str:
    if backend_attempt.status.startswith("blocked_"):
        return "blocked"
    if not resolution.supported or backend_attempt.status in {"blocked", "unsupported", "approval_required"}:
        return "blocked"
    if not backend_attempt.ok:
        return "failed"
    if backend_attempt.status.startswith("virtual_pointer_"):
        return "complete"
    if backend_attempt.status in {"dry_run_proposed", "metadata_only"}:
        return resolution.feedback_state
    if backend_attempt.performed or backend_attempt.dry_run:
        return "complete"
    return resolution.feedback_state


def operator_receipts_readback(args: dict[str, Any] | None = None) -> dict[str, Any]:
    safe_args = args or {}
    receipt_id = _clean_text(safe_args.get("receipt_id"))
    limit = max(1, min(_safe_int(safe_args.get("limit"), 20), 100))
    if receipt_id:
        path = _receipt_dir() / f"{receipt_id}.json"
        if not path.exists():
            return {
                "ok": False,
                "status": "not_found",
                "surface": ORB_OPERATOR_SURFACE,
                "receipt_id": receipt_id,
                "governance": {"read_only": True, "raw_input": False},
                "error": "operator receipt not found",
            }
        return {
            "ok": True,
            "status": "ready",
            "surface": ORB_OPERATOR_SURFACE,
            "receipt": json.loads(path.read_text(encoding="utf-8")),
            "governance": {"read_only": True, "raw_input": False},
        }

    receipts = sorted(_receipt_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]
    return {
        "ok": True,
        "status": "ready",
        "surface": ORB_OPERATOR_SURFACE,
        "receipts": [item.stem for item in receipts],
        "governance": {"read_only": True, "raw_input": False},
    }


def _virtual_pointer_readback(*, create_dirs: bool = True) -> dict[str, Any]:
    state = _read_virtual_pointer_state(create=create_dirs)
    if not state:
        return {
            "available": False,
            "pointer_id": ORB_VIRTUAL_POINTER_ID,
            "mode": ORB_POINTER_MODE,
            "controls_user_os_cursor": False,
            "user_mouse_taken": False,
            "physical_input_performed": False,
        }
    last_action = _coerce_dict(state.get("last_action"))
    return {
        "available": True,
        "pointer_id": _clean_text(state.get("pointer_id"), ORB_VIRTUAL_POINTER_ID),
        "mode": _clean_text(state.get("mode"), ORB_POINTER_MODE),
        "x": _safe_int(state.get("x")),
        "y": _safe_int(state.get("y")),
        "position": state.get("position") if isinstance(state.get("position"), dict) else {},
        "carrying": bool(state.get("carrying")),
        "carry_state": state.get("carry_state") if isinstance(state.get("carry_state"), dict) else {},
        "contact_state": state.get("contact_state") if isinstance(state.get("contact_state"), dict) else {},
        "updated_at": _clean_text(state.get("updated_at")),
        "last_action": last_action,
        "state_path": str(_virtual_pointer_state_path(create=create_dirs)),
        "controls_user_os_cursor": False,
        "user_mouse_taken": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
    }


def latest_orb_operator_state(*, create_dirs: bool = True) -> dict[str, Any]:
    pointer = _virtual_pointer_readback(create_dirs=create_dirs)
    receipt_root = _receipt_dir(create=create_dirs)
    receipts = (
        sorted(receipt_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:1]
        if receipt_root.exists()
        else []
    )
    if not receipts:
        return {
            "state": "idle",
            "feedback_state": "idle",
            "supported_states": list(ORB_FEEDBACK_STATES),
            "source": ORB_OPERATOR_SURFACE,
            "read_only": True,
            "receipt_id": "",
            "receipt_path": "",
            "virtual_pointer": pointer,
            "grants_execution_authority": False,
        }
    path = receipts[0]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "state": "failed",
            "feedback_state": "failed",
            "supported_states": list(ORB_FEEDBACK_STATES),
            "source": ORB_OPERATOR_SURFACE,
            "read_only": True,
            "receipt_id": path.stem,
            "receipt_path": str(path),
            "virtual_pointer": pointer,
            "grants_execution_authority": False,
            "error": "latest_operator_receipt_unreadable",
        }
    feedback_state = _clean_text(receipt.get("feedback_state"), "idle")
    return {
        "state": feedback_state if feedback_state in ORB_FEEDBACK_STATES else "idle",
        "feedback_state": feedback_state,
        "supported_states": list(ORB_FEEDBACK_STATES),
        "source": ORB_OPERATOR_SURFACE,
        "read_only": True,
        "receipt_id": _clean_text(receipt.get("receipt_id"), path.stem),
        "receipt_path": str(path),
        "latest_intent": receipt.get("requested_intent") if isinstance(receipt.get("requested_intent"), dict) else {},
        "latest_result": _clean_text(receipt.get("result")),
        "virtual_pointer": pointer,
        "uses_user_os_cursor": bool(_coerce_dict(receipt.get("governance")).get("uses_user_os_cursor")),
        "user_mouse_taken": bool(_coerce_dict(receipt.get("governance")).get("user_mouse_taken")),
        "physical_input_performed": bool(_coerce_dict(receipt.get("governance")).get("physical_input_performed")),
        "grants_execution_authority": False,
    }


def _demo_sequence(x: int, y: int, text: str, mode: str) -> dict[str, Any]:
    return submit_orb_sequence(
        {
            "mode": mode,
            "actor": "manual.orb_operator_dry_run",
            "objective": "manual dry-run Orb move click type proof",
            "session_id": f"manual-{uuid.uuid4().hex[:8]}",
            "intents": [
                {"kind": "move_to", "x": x, "y": y},
                {"kind": "click", "x": x, "y": y, "button": "left", "clicks": 1},
                {"kind": "type_text", "text": text},
            ],
        }
    )


def _visible_gesture_demo_sequence(
    *,
    x: int,
    y: int,
    drag_to_x: int,
    drag_to_y: int,
    step_delay: float,
) -> dict[str, Any]:
    shared = {
        "mode": ORB_POINTER_MODE,
        "actor": "manual.orb_operator_visible_gesture_demo",
        "objective": "visible Orb left-click drag and right-click proof",
        "session_id": f"manual-gesture-{uuid.uuid4().hex[:8]}",
    }
    start_x, start_y = _bounded_coord(x, "x"), _bounded_coord(y, "y")
    end_x, end_y = _bounded_coord(drag_to_x, "drag_to_x"), _bounded_coord(drag_to_y, "drag_to_y")
    drag_points: list[tuple[int, int]] = []
    for index in range(1, 5):
        ratio = index / 4
        drag_points.append((round(start_x + ((end_x - start_x) * ratio)), round(start_y + ((end_y - start_y) * ratio))))

    intents: list[dict[str, Any]] = [
        {"kind": "move_to", "x": start_x, "y": start_y},
        {"kind": "click", "x": start_x, "y": start_y, "button": "left", "clicks": 1},
    ]
    current_x, current_y = start_x, start_y
    for target_x, target_y in drag_points:
        intents.append(
            {
                "kind": "mouse_drag",
                "x": current_x,
                "y": current_y,
                "target_x": target_x,
                "target_y": target_y,
                "button": "left",
            }
        )
        current_x, current_y = target_x, target_y
    intents.append({"kind": "click", "x": end_x, "y": end_y, "button": "right", "clicks": 1})

    results: list[dict[str, Any]] = []
    safe_delay = max(0.0, min(float(step_delay), 5.0))
    for intent in intents:
        results.append(submit_orb_intent({**shared, "intent": intent}))
        if safe_delay:
            time.sleep(safe_delay)

    return {
        "ok": all(bool(item.get("ok")) for item in results),
        "status": "complete" if all(bool(item.get("ok")) for item in results) else "partial_or_blocked",
        "surface": ORB_OPERATOR_SURFACE,
        "stage": ORB_OPERATOR_STAGE,
        "mode": ORB_POINTER_MODE,
        "results": results,
        "receipt_paths": [
            str(item.get("operator_receipt_path")) for item in results if item.get("operator_receipt_path")
        ],
        "governance": {
            "raw_input": False,
            "virtual_pointer_only": True,
            "uses_user_os_cursor": False,
            "user_mouse_taken": False,
            "physical_input_performed": False,
            "desktop_effect_performed": False,
            "receipt_written": True,
            "sequence_count": len(results),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a safe Orb operator dry-run sequence.")
    parser.add_argument("--mode", choices=ORB_BACKEND_MODES, default="dry_run")
    parser.add_argument("--x", type=int, default=320)
    parser.add_argument("--y", type=int, default=240)
    parser.add_argument("--drag-to-x", type=int, default=640)
    parser.add_argument("--drag-to-y", type=int, default=420)
    parser.add_argument("--step-delay", type=float, default=0.8)
    parser.add_argument("--gesture-demo", action="store_true")
    parser.add_argument("--text", default="Francis Orb dry-run")
    args = parser.parse_args(argv)
    if args.gesture_demo:
        result = _visible_gesture_demo_sequence(
            x=args.x,
            y=args.y,
            drag_to_x=args.drag_to_x,
            drag_to_y=args.drag_to_y,
            step_delay=args.step_delay,
        )
    else:
        result = _demo_sequence(args.x, args.y, args.text, args.mode)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    raise SystemExit(main())
