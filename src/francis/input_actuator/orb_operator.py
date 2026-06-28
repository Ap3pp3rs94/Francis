from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

from .contracts import InputActuatorError
from .tools import execute_approved_input_action, propose_input_action

ORB_OPERATOR_SURFACE = "francis.orb_operator.v0"
ORB_OPERATOR_STAGE = "Phase 2 / Lens Orb embodied desktop operation"
ORB_POINTER_MODE = "orb_pointer"
ORB_BACKEND_MODES = ("dry_run", "guarded_live", ORB_POINTER_MODE)
ORB_VIRTUAL_POINTER_ID = "francis.orb.primary_virtual_pointer"

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


def _state_root() -> Path:
    override = os.environ.get("FRANCIS_ORB_OPERATOR_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "orb_operator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _receipt_dir() -> Path:
    path = _state_root() / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _virtual_pointer_state_path() -> Path:
    return _state_root() / "virtual_pointer_state.json"


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


def _rect_center(rect: dict[str, Any]) -> tuple[int, int]:
    x = _bounded_coord(rect.get("x"), "rect.x")
    y = _bounded_coord(rect.get("y"), "rect.y")
    width = max(0, _safe_int(rect.get("width"), 0))
    height = max(0, _safe_int(rect.get("height"), 0))
    return (_bounded_coord(x + width // 2, "rect.center_x"), _bounded_coord(y + height // 2, "rect.center_y"))


def _read_virtual_pointer_state() -> dict[str, Any]:
    path = _virtual_pointer_state_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _virtual_pointer_position(payload: dict[str, Any]) -> tuple[int, int]:
    previous = _read_virtual_pointer_state()
    if payload.get("x") is not None and payload.get("y") is not None:
        return _bounded_coord(payload.get("x"), "x"), _bounded_coord(payload.get("y"), "y")
    return (
        _bounded_coord(previous.get("x", 0), "virtual_pointer.x"),
        _bounded_coord(previous.get("y", 0), "virtual_pointer.y"),
    )


def _virtual_pointer_action_status(input_kind: str) -> str:
    if input_kind == "mouse.move":
        return "virtual_pointer_moved"
    if input_kind == "mouse.click":
        return "virtual_pointer_click_recorded"
    if input_kind in {"keyboard.type", "keyboard.hotkey"}:
        return "virtual_pointer_keyboard_event_recorded"
    return "virtual_pointer_event_recorded"


def _write_virtual_pointer_state(
    *,
    input_kind: str,
    payload: dict[str, Any],
    actor: str,
    objective: str,
    session_id: str,
) -> dict[str, Any]:
    x, y = _virtual_pointer_position(payload)
    now = _utc_now()
    public_action = _public_input_action(input_kind, payload)
    requires_bridge = input_kind != "mouse.move"
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
        "last_action": {
            "input_kind": input_kind,
            "status": _virtual_pointer_action_status(input_kind),
            "public_action": public_action,
            "actor": actor,
            "objective": objective,
            "session_id": session_id,
            "desktop_effect_performed": False,
            "physical_input_performed": False,
            "user_os_cursor_moved": False,
            "user_mouse_taken": False,
            "requires_app_bridge_for_desktop_effect": requires_bridge,
        },
        "governance": {
            "virtual_pointer_only": True,
            "controls_user_os_cursor": False,
            "moves_user_mouse": False,
            "physical_input_performed": False,
            "desktop_effect_performed": False,
            "requires_app_bridge_for_desktop_effect": requires_bridge,
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
    def from_dict(cls, payload: dict[str, Any]) -> OrbIntent:
        kind = _clean_text(payload.get("kind") or payload.get("intent")).lower()
        aliases = {
            "move": "move_to",
            "mouse.move": "move_to",
            "mouse.click": "click",
            "keyboard.type": "type_text",
            "keyboard.hotkey": "key_press",
        }
        kind = aliases.get(kind, kind)
        metadata = _coerce_dict(payload.get("metadata"))
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
            "ok": self.result not in {"failed", "blocked"},
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
        proposal_id: str = "",
        approval_phrase: str = "",
    ) -> BackendAttempt:
        payload: dict[str, Any] = {"button": button, "clicks": clicks}
        if x is not None and y is not None:
            payload["x"] = x
            payload["y"] = y
        return self._submit("mouse.click", payload, proposal_id=proposal_id, approval_phrase=approval_phrase)

    def type_text(self, text: str, *, proposal_id: str = "", approval_phrase: str = "") -> BackendAttempt:
        return self._submit("keyboard.type", {"text": text}, proposal_id=proposal_id, approval_phrase=approval_phrase)

    def key_press(self, key: str, *, proposal_id: str = "", approval_phrase: str = "") -> BackendAttempt:
        return self._submit(
            "keyboard.hotkey", {"keys": [key]}, proposal_id=proposal_id, approval_phrase=approval_phrase
        )

    def mouse_drag(self, *_args: Any, **_kwargs: Any) -> BackendAttempt:
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
            },
            error="mouse drag is not yet supported by the governed input actuator",
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
                pointer = _write_virtual_pointer_state(
                    input_kind=kind,
                    payload=payload,
                    actor=self.actor,
                    objective=self.objective,
                    session_id=self.session_id,
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
            state = _coerce_dict(pointer.get("state"))
            last_action = _coerce_dict(state.get("last_action"))
            return BackendAttempt(
                ok=True,
                status=_virtual_pointer_action_status(kind),
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
                        "last_action": last_action,
                    },
                    "desktop_effect_performed": False,
                    "physical_input_performed": False,
                    "user_os_cursor_moved": False,
                    "user_mouse_taken": False,
                    "requires_app_bridge_for_desktop_effect": bool(
                        last_action.get("requires_app_bridge_for_desktop_effect")
                    ),
                },
                governance={
                    "decision": "allow_virtual_pointer",
                    "virtual_pointer_only": True,
                    "dry_run": False,
                    "writes_pointer_state": True,
                    "writes_proposal": False,
                    "raw_input": False,
                    "performed": False,
                    "physical_input_performed": False,
                    "user_os_cursor_controlled": False,
                    "user_mouse_taken": False,
                    "desktop_effect_performed": False,
                    "requires_app_bridge_for_desktop_effect": bool(
                        last_action.get("requires_app_bridge_for_desktop_effect")
                    ),
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
        return IntentResolution(
            feedback_state="clicking",
            input_kind="mouse.click",
            input_payload=payload,
            resolved_target=resolved,
        )

    if intent.kind == "type_text":
        if not intent.text:
            return IntentResolution(feedback_state="blocked", supported=False, reason="type_text_requires_text")
        return IntentResolution(
            feedback_state="typing",
            input_kind="keyboard.type",
            input_payload={"text": intent.text},
            resolved_target={"text_length": len(intent.text), "text_sha256": _hash_text(intent.text)},
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
        return IntentResolution(feedback_state="blocked", supported=False, reason="mouse_drag_backend_not_declared")

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
    if resolution.input_kind == "mouse.click":
        return backend.mouse_click(
            button=str(payload.get("button", "left")),
            clicks=_safe_int(payload.get("clicks"), 1),
            x=payload.get("x"),
            y=payload.get("y"),
            proposal_id=proposal_id,
            approval_phrase=approval_phrase,
        )
    if resolution.input_kind == "keyboard.type":
        return backend.type_text(str(payload["text"]), proposal_id=proposal_id, approval_phrase=approval_phrase)
    if resolution.input_kind == "keyboard.hotkey":
        keys = payload.get("keys") if isinstance(payload.get("keys"), list) else []
        key = _clean_text(keys[0] if keys else "")
        return backend.key_press(key, proposal_id=proposal_id, approval_phrase=approval_phrase)
    if resolution.input_kind == "mouse.drag":
        return backend.mouse_drag()
    raise InputActuatorError(f"unsupported resolved input kind: {resolution.input_kind}")


def _public_input_action(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "mouse.move":
        return {"kind": kind, "x": payload.get("x"), "y": payload.get("y")}
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
    return {
        "decision": backend_attempt.governance.get("decision", "deny"),
        "mode": mode,
        "orb_is_visible_operator_body": True,
        "raw_input": False,
        "screenshots": False,
        "pixels": False,
        "dry_run": bool(backend_attempt.dry_run),
        "virtual_pointer_only": virtual_pointer_only,
        "uses_user_os_cursor": uses_user_os_cursor,
        "user_mouse_taken": uses_user_os_cursor,
        "physical_input_performed": live_allowed,
        "desktop_effect_performed": live_allowed,
        "live_input_performed": live_allowed,
        "input_execution_attempted": bool(backend_attempt.result.get("input_execution_attempted")),
        "input_proposal_written": bool(backend_attempt.result.get("proposal_written")),
        "manual_approval_required_for_execution": mode == "dry_run" or backend_attempt.status == "approval_required",
        "guarded_live_requires_existing_input_approval": True,
        "guarded_live_requires_existing_handoff": True,
        "orb_pointer_requires_app_bridge_for_desktop_effect": bool(
            backend_attempt.result.get("requires_app_bridge_for_desktop_effect")
        ),
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
    ok = backend_attempt.ok and result_status not in {"blocked", "failed"}
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
    if not resolution.supported or backend_attempt.status in {"blocked", "unsupported", "approval_required"}:
        return "blocked"
    if not backend_attempt.ok:
        return "failed"
    if backend_attempt.status.startswith("virtual_pointer_"):
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


def _virtual_pointer_readback() -> dict[str, Any]:
    state = _read_virtual_pointer_state()
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
        "updated_at": _clean_text(state.get("updated_at")),
        "last_action": last_action,
        "state_path": str(_virtual_pointer_state_path()),
        "controls_user_os_cursor": False,
        "user_mouse_taken": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
    }


def latest_orb_operator_state() -> dict[str, Any]:
    pointer = _virtual_pointer_readback()
    receipts = sorted(_receipt_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:1]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a safe Orb operator dry-run sequence.")
    parser.add_argument("--mode", choices=ORB_BACKEND_MODES, default="dry_run")
    parser.add_argument("--x", type=int, default=320)
    parser.add_argument("--y", type=int, default=240)
    parser.add_argument("--text", default="Francis Orb dry-run")
    args = parser.parse_args(argv)
    result = _demo_sequence(args.x, args.y, args.text, args.mode)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    raise SystemExit(main())
