from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["RetrievalStrategy", "Message", "ChatContinuity", "retrieve_conversation_history"]


class RetrievalStrategy(Enum):
    LATEST_MESSAGES = "latest_messages"
    KEYWORD_SEARCH = "keyword_search"


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    timestamp: datetime
    sender: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "sender": self.sender,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            id=str(data["id"]),
            timestamp=datetime.fromisoformat(str(data["timestamp"])),
            sender=str(data["sender"]),
            content=str(data["content"]),
        )


@dataclass(slots=True)
class ChatContinuity:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatContinuity":
        return cls(
            session_id=str(data["session_id"]),
            messages=[Message.from_dict(m) for m in (data.get("messages") or [])],
            metadata=dict(data.get("metadata") or {}),
        )

    @property
    def last_message_timestamp(self) -> datetime | None:
        return self.messages[-1].timestamp if self.messages else None


def retrieve_conversation_history(
    chat_continuity: ChatContinuity,
    strategy: RetrievalStrategy,
    keyword: str | None = None,
    limit: int = 10,
) -> list[Message]:
    """Return messages by strategy, falling back to an empty list on errors."""
    if not isinstance(chat_continuity, ChatContinuity):
        logger.warning("chat_continuity must be a ChatContinuity")
        return []
    if not isinstance(strategy, RetrievalStrategy):
        logger.warning("strategy must be a RetrievalStrategy")
        return []
    if not isinstance(limit, int) or limit <= 0:
        logger.warning("limit must be a positive int")
        return []

    logger.debug("Retrieving history: strategy=%s keyword=%s limit=%s", strategy, keyword, limit)

    if strategy == RetrievalStrategy.LATEST_MESSAGES:
        return chat_continuity.messages[-limit:]

    if strategy == RetrievalStrategy.KEYWORD_SEARCH:
        if not keyword or not isinstance(keyword, str):
            logger.warning("keyword must be provided for KEYWORD_SEARCH strategy")
            return []
        k = keyword.lower()
        matches = [m for m in chat_continuity.messages if k in m.content.lower()]
        return matches[:limit]

    logger.warning("Invalid retrieval strategy: %s", strategy)
    return []
