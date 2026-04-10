from __future__ import annotations

import logging

from francis.agent.local_actions import try_handle
from francis.chat.continuity.ledger import append
from francis.llm.client import generate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Francis. Speak like a calm, competent operator: concise, human, forward-moving. "
    "Answer directly first, then offer the next best action in one clean step. "
    "Avoid narration about internal logging or system behavior unless asked. "
    "Prefer plain language over jargon, but switch to technical precision when needed. "
    "Do not mention memory, summaries, topics, or artifacts unless asked."
)


def handle(text: str, use_llm: bool = False) -> str:
    if not isinstance(text, str):
        logger.warning("handle received non-string input")
        text = str(text)
    append("user", text, {})

    action = try_handle(text)
    if action.handled:
        append("assistant", action.message, {"mode": "action"})
        return action.message

    reply = ""
    if use_llm:
        prompt = f"{SYSTEM_PROMPT}\n\nUser: {text}\nFrancis:"
        try:
            reply = generate(prompt)
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            reply = ""

    if not reply:
        reply = _fallback_reply(text, llm_requested=use_llm)
    append("assistant", reply, {"mode": "llm" if use_llm else "stub"})
    return reply


def _fallback_reply(text: str, *, llm_requested: bool) -> str:
    lowered = (text or "").strip().lower()
    if not lowered:
        return "Tell me what you want handled and the outcome you want."
    if any(token in lowered for token in ("hi", "hello", "hey")):
        base = "Hey. Tell me your goal and any constraints, and I will handle it."
        if llm_requested:
            return f"{base} If you want richer replies, make sure the model is running."
        return base
    if "help" in lowered or "how do" in lowered:
        return "Give me the task, the constraints, and the deadline. I will take it from there."
    if llm_requested:
        return "I can proceed in basic mode. Tell me the exact task and constraints."
    return "Tell me the exact task and constraints, and I will handle it."
