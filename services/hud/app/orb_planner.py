from __future__ import annotations

import json
import re
from typing import Any

from francis_llm import chat

_ALLOWED_STEP_KINDS = {
    "mouse.move",
    "mouse.click",
    "keyboard.type",
    "keyboard.key",
    "keyboard.shortcut",
}


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except Exception:
            return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_step(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    kind = str(row.get("kind", "")).strip().lower()
    if kind not in _ALLOWED_STEP_KINDS:
        return None
    args = row.get("args", {}) if isinstance(row.get("args"), dict) else {}
    normalized_args: dict[str, Any] = {}
    if kind == "mouse.move":
        for key in ("x", "y"):
            value = args.get(key)
            if value is None:
                return None
            normalized_args[key] = int(round(float(value)))
        normalized_args["coordinate_space"] = str(args.get("coordinate_space", "display")).strip().lower() or "display"
    elif kind == "mouse.click":
        button = str(args.get("button", "left")).strip().lower() or "left"
        normalized_args["button"] = "right" if button == "right" else "left"
        if "double" in args:
            normalized_args["double"] = bool(args.get("double"))
        if "x" in args and args.get("x") is not None:
            normalized_args["x"] = int(round(float(args.get("x"))))
        if "y" in args and args.get("y") is not None:
            normalized_args["y"] = int(round(float(args.get("y"))))
        if "x" in normalized_args or "y" in normalized_args:
            normalized_args["coordinate_space"] = str(args.get("coordinate_space", "display")).strip().lower() or "display"
    elif kind == "keyboard.type":
        text = str(args.get("text", ""))
        if not text.strip():
            return None
        normalized_args["text"] = text
    elif kind == "keyboard.key":
        key = str(args.get("key", "")).strip().lower()
        if not key:
            return None
        normalized_args["key"] = key
    elif kind == "keyboard.shortcut":
        keys = args.get("keys", [])
        if isinstance(keys, str):
            keys = [keys]
        if not isinstance(keys, list) or not keys:
            return None
        normalized_args["keys"] = [str(value).strip().lower() for value in keys if str(value).strip()]
        if not normalized_args["keys"]:
            return None
    delay_ms = max(0, min(2000, int(row.get("delay_ms", row.get("pause_ms", 0)) or 0)))
    return {
        "kind": kind,
        "args": normalized_args,
        "reason": str(row.get("reason", "")).strip() or "Carry out the next Orb desktop step.",
        "interaction": str(row.get("interaction", "")).strip().lower(),
        "delay_ms": delay_ms,
    }


def _normalize_plan(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    steps = [
        normalized
        for normalized in (_normalize_step(row) for row in payload.get("steps", []))
        if normalized is not None
    ]
    if not steps:
        return None
    return {
        "title": str(payload.get("title", "")).strip() or "Orb desktop plan",
        "summary": str(payload.get("summary", "")).strip() or "Carry out the requested desktop action through the Orb shell.",
        "reasoning": [
            str(value).strip()
            for value in payload.get("reasoning", [])
            if str(value).strip()
        ][:6],
        "mode_requirement": str(payload.get("mode_requirement", "pilot")).strip().lower() or "pilot",
        "auto_execute": bool(payload.get("auto_execute", False)),
        "steps": steps,
    }


def _heuristic_plan(message: str) -> dict[str, Any] | None:
    normalized = " ".join(str(message or "").strip().lower().split())
    launch_match = re.match(r"^(?:open|launch|start|run)\s+(.+)$", normalized)
    if launch_match:
        target = launch_match.group(1).strip(" .")
        if target:
            return {
                "reply": f"I can open {target} through Start search in Pilot mode.",
                "thought": f"Ready to open {target} through Start search.",
                "plan": {
                    "title": f"Open {target.title()}",
                    "summary": f"Open {target} through the Windows Start search path instead of a direct process launch.",
                    "reasoning": [
                        "This is a visible desktop navigation task, so Francis should use the same Windows path the user would use rather than a hidden direct launch.",
                        "Keyboard navigation is the most reliable path here, so left versus right click is not needed for this task.",
                    ],
                    "mode_requirement": "pilot",
                    "auto_execute": False,
                    "steps": [
                        {
                            "kind": "keyboard.shortcut",
                            "args": {"keys": ["ctrl", "esc"]},
                            "reason": "Open the Start menu so Francis can search like the user.",
                            "interaction": "keyboard_navigation",
                            "delay_ms": 180,
                        },
                        {
                            "kind": "keyboard.type",
                            "args": {"text": target},
                            "reason": f"Type {target} into Start search.",
                            "interaction": "keyboard_navigation",
                            "delay_ms": 180,
                        },
                        {
                            "kind": "keyboard.key",
                            "args": {"key": "enter"},
                            "reason": f"Open the highlighted {target} result from Start search.",
                            "interaction": "keyboard_navigation",
                            "delay_ms": 220,
                        },
                    ],
                },
            }
    if "right click" in normalized or "context menu" in normalized:
        return {
            "reply": "I can open the context menu from the current cursor target in Pilot mode.",
            "thought": "Context menu path is ready.",
            "plan": {
                "title": "Open Context Menu",
                "summary": "Use a right click at the current cursor target.",
                "reasoning": [
                    "A context menu requires a right click, not a left click.",
                    "The click choice is visible in the plan so the interaction stays governed.",
                ],
                "mode_requirement": "pilot",
                "auto_execute": False,
                "steps": [
                    {
                        "kind": "mouse.click",
                        "args": {"button": "right"},
                        "reason": "Right click the current cursor target to open its context menu.",
                        "interaction": "right_click",
                        "delay_ms": 180,
                    }
                ],
            },
        }
    return None


def build_orb_chat_plan(
    *,
    message: str,
    orb_context: dict[str, Any],
    perception: dict[str, Any],
    snapshot: dict[str, Any],
    short_term_messages: list[dict[str, Any]],
    long_term_memory: dict[str, Any],
) -> dict[str, Any]:
    user_message = str(message or "").strip()
    heuristic = _heuristic_plan(user_message)

    system_prompt = (
        "You are Francis, a governed autonomous operator speaking through the Orb. "
        "You are not a generic assistant and you are not a detached chatbot. "
        "The user is sovereign, Francis is the operator. "
        "Every turn is grounded in explicit mode, posture, run state, visible desktop context, and receipts. "
        "Planning and execution are separate. You decide the plan; the shell executes later. "
        "Return JSON only with keys reply, thought, and plan. "
        "If desktop action is required, plan visible user-like steps only. "
        "Choose left versus right click deliberately and explain the interaction choice in the reasoning and step reason. "
        "Do not directly launch processes when a visible Windows navigation path is better. "
        "If no desktop action is needed, set plan to null and reply as Francis in a calm operator voice."
    )
    prompt_payload = {
        "operator_state": {
            "mode": orb_context.get("mode"),
            "posture": orb_context.get("posture"),
            "summary": orb_context.get("summary"),
            "detail": orb_context.get("detail"),
            "run_state": orb_context.get("run_state"),
            "operator": orb_context.get("operator"),
            "interjection": orb_context.get("interjection"),
            "authority": orb_context.get("authority"),
        },
        "snapshot": {
            "control": snapshot.get("control", {}),
            "objective": snapshot.get("objective", {}),
            "current_work": snapshot.get("current_work", {}),
            "runs": snapshot.get("runs", {}),
        },
        "perception": {
            "summary": perception.get("summary"),
            "detail_summary": perception.get("detail_summary"),
            "window": perception.get("window"),
            "cards": perception.get("cards"),
        },
        "short_term_memory": short_term_messages[-10:],
        "long_term_memory": long_term_memory,
        "allowed_step_kinds": sorted(_ALLOWED_STEP_KINDS),
        "user_message": user_message,
        "output_contract": {
            "reply": "string",
            "thought": "string",
            "plan": {
                "title": "string",
                "summary": "string",
                "reasoning": ["string"],
                "mode_requirement": "pilot",
                "auto_execute": False,
                "steps": [
                    {
                        "kind": "keyboard.shortcut | keyboard.type | keyboard.key | mouse.move | mouse.click",
                        "args": {"...": "..."},
                        "reason": "why this exact interaction is correct",
                        "interaction": "left_click | right_click | keyboard_navigation | pointer_navigation",
                        "delay_ms": 120,
                    }
                ],
            },
        },
    }

    response_text = ""
    try:
        response = chat(
            "orb.desktop_analysis.operator_loop",
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
            ],
            timeout=60.0,
            options={"temperature": 0.15},
        )
        if isinstance(response, dict):
            message_payload = response.get("message", {})
            if isinstance(message_payload, dict):
                response_text = str(message_payload.get("content", "")).strip()
            elif response.get("response"):
                response_text = str(response.get("response", "")).strip()
    except Exception:
        response_text = ""

    extracted = _extract_json_object(response_text)
    plan = _normalize_plan(extracted.get("plan")) if extracted else None
    if plan is None and heuristic:
        plan = _normalize_plan(heuristic.get("plan"))
    reply = str(extracted.get("reply", "")).strip() if extracted else ""
    if not reply and heuristic:
        reply = str(heuristic.get("reply", "")).strip()
    if not reply:
        reply = response_text or "I am holding the request in view, but I do not have a grounded plan yet."
    thought = str(extracted.get("thought", "")).strip() if extracted else ""
    if not thought and heuristic:
        thought = str(heuristic.get("thought", "")).strip()
    if not thought and plan:
        thought = str(plan.get("summary", "")).strip()

    return {
        "reply": reply,
        "thought": thought,
        "plan": plan,
        "raw_response": response_text,
        "planner": "ollama",
    }
