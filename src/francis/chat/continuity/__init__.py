from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ConversationStatus",
    "Message",
    "ConversationState",
    "ConversationHistory",
    "ContinuityManager",
]


class ConversationStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class Message:
    """Represents a single message in the conversation."""

    id: uuid.UUID
    timestamp: datetime
    sender: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "sender": self.sender,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            id=uuid.UUID(data["id"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sender=str(data["sender"]),
            content=str(data["content"]),
        )


@dataclass
class ConversationState:
    """Represents the current state of a conversation."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[Message] = field(default_factory=list)

    @property
    def last_message(self) -> Message | None:
        return self.messages[-1] if self.messages else None

    def add_message(self, sender: str, content: str) -> Message:
        msg = Message(
            id=uuid.uuid4(),
            timestamp=datetime.now(timezone.utc),
            sender=str(sender),
            content=str(content),
        )
        self.messages.append(msg)
        return msg

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "status": self.status.value,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationState":
        return cls(
            id=uuid.UUID(data["id"]),
            status=ConversationStatus(data["status"]),
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
        )


@dataclass
class ConversationHistory:
    conversations: dict[uuid.UUID, ConversationState] = field(default_factory=dict)

    def get(self, conversation_id: uuid.UUID) -> ConversationState | None:
        return self.conversations.get(conversation_id)

    def put(self, state: ConversationState) -> None:
        self.conversations[state.id] = state


class ContinuityManager:
    """Manages conversation continuity across interactions."""

    def __init__(self) -> None:
        self.history = ConversationHistory()

    def start_conversation(self) -> uuid.UUID:
        state = ConversationState()
        self.history.put(state)

        # local import avoids circulars
        from .store import save_state

        save_state(state)
        logger.info("New conversation started: %s", state.id)
        return state.id

    def get_conversation_state(self, conversation_id: uuid.UUID) -> ConversationState | None:
        if not isinstance(conversation_id, uuid.UUID):
            logger.warning("conversation_id must be a uuid.UUID")
            return None
        return self.history.get(conversation_id)

    def add_message_to_conversation(self, conversation_id: uuid.UUID, sender: str, content: str) -> Message | None:
        if not isinstance(conversation_id, uuid.UUID):
            logger.warning("conversation_id must be a uuid.UUID")
            return None

        state = self.history.get(conversation_id)
        if state is None:
            logger.warning("Conversation ID %s not found in history", conversation_id)
            return None

        msg = state.add_message(sender, content)

        from .store import save_state

        save_state(state)
        logger.info("Message added + persisted: %s", conversation_id)
        return msg

    def end_conversation(self, conversation_id: uuid.UUID) -> bool:
        if not isinstance(conversation_id, uuid.UUID):
            logger.warning("conversation_id must be a uuid.UUID")
            return False

        state = self.history.get(conversation_id)
        if state is None:
            logger.warning("Conversation ID %s not found in history", conversation_id)
            return False

        state.status = ConversationStatus.COMPLETED  # type: ignore[misc]

        from .store import save_state

        save_state(state)
        logger.info("Conversation ended + persisted: %s", conversation_id)
        return True
