from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

__all__ = ["ChatMessage", "send_message", "receive_message"]


@dataclass(frozen=True)
class ChatMessage:
    sender: str
    content: str
    timestamp: str


def send_message(message: ChatMessage) -> None:
    try:
        logger.info("Message from %s: %s", message.sender, message.content)
    except Exception as exc:
        logger.error("Failed to send message: %s", exc)


def receive_message() -> ChatMessage | None:
    try:
        return ChatMessage(
            sender="user",
            content="Hello!",
            timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
    except Exception as exc:
        logger.error("Failed to receive message: %s", exc)
        return None
