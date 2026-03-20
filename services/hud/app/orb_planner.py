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
_ACTION_VERB_PATTERN = re.compile(
    r"^(?:please\s+)?(?:open|launch|start|run|click|right click|left click|type|enter|press|save|close|minimize|maximize|scroll|select)\b",
    re.IGNORECASE,
)
_POLITE_ACTION_PATTERN = re.compile(
    r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:open|launch|start|run|click|right click|left click|type|enter|press|save|close|minimize|maximize|scroll|select)\b",
    re.IGNORECASE,
)
_DIRECTIVE_ACTION_PATTERN = re.compile(
    r"^(?:i\s+want\s+you\s+to|go\s+ahead\s+and|please\s+go\s+ahead\s+and|do\s+this:)\s+(?:open|launch|start|run|click|right click|left click|type|enter|press|save|close|minimize|maximize|scroll|select)\b",
    re.IGNORECASE,
)
_CONVERSATION_PREFIX_PATTERN = re.compile(
    r"^(?:what|why|how|when|where|who|which|explain|describe|summarize|tell me|help me understand|walk me through)\b",
    re.IGNORECASE,
)


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


def _normalize_turn_text(message: str) -> str:
    return " ".join(str(message or "").strip().split())


def _is_explicit_action_request(message: str) -> bool:
    normalized = _normalize_turn_text(message)
    if not normalized:
        return False
    return bool(
        _ACTION_VERB_PATTERN.match(normalized)
        or _POLITE_ACTION_PATTERN.match(normalized)
        or _DIRECTIVE_ACTION_PATTERN.match(normalized)
    )


def _is_conversation_request(message: str) -> bool:
    normalized = _normalize_turn_text(message)
    if not normalized:
        return False
    lowered = normalized.lower()
    if _is_explicit_action_request(normalized):
        return False
    if lowered.endswith("?"):
        return True
    return bool(_CONVERSATION_PREFIX_PATTERN.match(normalized))


def _normalize_intent_kind(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"conversation.answer", "conversation", "chat.answer", "answer"}:
        return "conversation.answer"
    if normalized in {"desktop.action", "action", "desktop", "execute"}:
        return "desktop.action"
    return ""


def _describe_control_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized == "observe":
        return "Observe is read-only. Francis gathers context and suggests, but does not mutate or execute."
    if normalized == "assist":
        return "Assist prepares plans, drafts, and guidance, but the user still decides what executes."
    if normalized == "pilot":
        return "Pilot is takeover-on-command inside explicit scope. Francis can act, but the work stays visible, revocable, and receipted."
    if normalized == "away":
        return "Away is bounded continuity for approved work while the user is absent. Scope, policy, and receipts still govern every step."
    return ""


def _build_conversation_fallback(
    *,
    user_message: str,
    orb_context: dict[str, Any],
    perception: dict[str, Any],
    snapshot: dict[str, Any],
) -> str:
    normalized = _normalize_turn_text(user_message).lower()
    if not normalized:
        return ""

    if "pilot" in normalized and "mode" in normalized:
        return _describe_control_mode("pilot")
    if "assist" in normalized and "mode" in normalized:
        return _describe_control_mode("assist")
    if "observe" in normalized and "mode" in normalized:
        return _describe_control_mode("observe")
    if "away" in normalized and "mode" in normalized:
        return _describe_control_mode("away")

    if any(
        phrase in normalized
        for phrase in (
            "what do you see",
            "what are you seeing",
            "what can you see",
            "what do you have in view",
            "what is on screen",
            "what's on screen",
        )
    ):
        perception_summary = str(perception.get("summary", "")).strip()
        if perception_summary:
            return perception_summary
        return "I do not have a live perception frame attached right now."

    if any(
        phrase in normalized
        for phrase in (
            "what are you doing",
            "what is your state",
            "what's your state",
            "what are you focused on",
        )
    ):
        orb_summary = str(orb_context.get("summary", "")).strip()
        if orb_summary:
            return orb_summary

    current_mode = str(snapshot.get("control", {}).get("mode", "")).strip().lower()
    current_mode_summary = _describe_control_mode(current_mode)
    if current_mode_summary and normalized.endswith("?"):
        return f"Francis is currently in {current_mode.title()}. {current_mode_summary}"

    return ""


def _infer_turn_intent(
    *,
    user_message: str,
    parsed: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    parsed_intent = parsed.get("intent") if isinstance(parsed, dict) and isinstance(parsed.get("intent"), dict) else {}
    parsed_kind = _normalize_intent_kind(parsed_intent.get("kind") if isinstance(parsed_intent, dict) else "")
    explicit_action = _is_explicit_action_request(user_message)
    conversational = _is_conversation_request(user_message)

    if parsed_kind == "desktop.action":
        kind = "desktop.action"
    elif parsed_kind == "conversation.answer":
        kind = "conversation.answer"
    elif explicit_action and plan:
        kind = "desktop.action"
    elif conversational:
        kind = "conversation.answer"
    elif plan:
        kind = "desktop.action"
    else:
        kind = "conversation.answer"

    if kind != "desktop.action":
        return {
            "kind": "conversation.answer",
            "confidence": "likely" if conversational or parsed_kind == "conversation.answer" else "uncertain",
            "should_execute": False,
        }

    should_execute = bool(
        (isinstance(parsed, dict) and parsed.get("should_execute") is True)
        or (isinstance(plan, dict) and plan.get("auto_execute") is True)
        or explicit_action
    )
    return {
        "kind": "desktop.action",
        "confidence": "likely" if explicit_action or parsed_kind == "desktop.action" else "uncertain",
        "should_execute": should_execute,
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
                "auto_execute": True,
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
                "auto_execute": True,
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
        "Return JSON only with keys reply, thought, intent, should_execute, and plan. "
        "If the user is asking a question, discussing options, asking how or why, or otherwise talking with Francis, "
        "set intent.kind to conversation.answer, set should_execute to false, and set plan to null. "
        "If the user is explicitly telling Francis to carry out a desktop action now, set intent.kind to desktop.action. "
        "Set should_execute to true only when the user is explicitly asking Francis to perform the action on this turn. "
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
            "intent": {
                "kind": "conversation.answer | desktop.action",
                "confidence": "likely | uncertain",
            },
            "should_execute": False,
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
    intent = _infer_turn_intent(user_message=user_message, parsed=extracted, plan=plan)
    if intent["kind"] != "desktop.action":
        plan = None
    elif isinstance(plan, dict):
        plan["auto_execute"] = bool(intent["should_execute"])
    reply = str(extracted.get("reply", "")).strip() if extracted else ""
    if not reply and heuristic:
        reply = str(heuristic.get("reply", "")).strip()
    if not reply and intent["kind"] != "desktop.action":
        reply = _build_conversation_fallback(
            user_message=user_message,
            orb_context=orb_context,
            perception=perception,
            snapshot=snapshot,
        )
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
        "intent": intent,
        "should_execute": bool(intent["should_execute"]),
        "raw_response": response_text,
        "planner": "ollama",
    }
