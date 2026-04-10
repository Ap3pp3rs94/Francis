from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ProactiveMessage", "EtiquetteDecision", "EtiquetteResult", "evaluate_message"]


class EtiquetteDecision(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    DEFER = "defer"


@dataclass(frozen=True)
class ProactiveMessage:
    content: str
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "created_at": self.created_at,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class EtiquetteResult:
    decision: EtiquetteDecision
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "metadata": dict(self.metadata or {}),
        }


def evaluate_message(message: ProactiveMessage, context: dict[str, Any] | None = None) -> EtiquetteResult:
    if context is None:
        context = {}
    if not isinstance(context, dict):
        logger.warning("evaluate_message expected dict context")
        context = {}

    if not isinstance(message, ProactiveMessage):
        return EtiquetteResult(EtiquetteDecision.BLOCK, "invalid_message_type")

    content = str(message.content).strip()
    if not content:
        return EtiquetteResult(EtiquetteDecision.BLOCK, "empty_message")

    if not context.get("opt_in", True):
        return EtiquetteResult(EtiquetteDecision.BLOCK, "opt_out")

    min_interval = int(context.get("min_interval_s", 60))
    last_sent = float(context.get("last_sent_ts", 0.0))
    now = time.time()
    if now - last_sent < min_interval:
        return EtiquetteResult(
            EtiquetteDecision.DEFER,
            "cooldown",
            metadata={"wait_s": max(0.0, min_interval - (now - last_sent))},
        )

    return EtiquetteResult(EtiquetteDecision.ALLOW, "ok")
