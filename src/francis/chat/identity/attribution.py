from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "UserIdentity",
    "MessageAttribution",
    "IdentityType",
    "AttributeError",
]


class IdentityType(Enum):
    USER = "user"
    SYSTEM = "system"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class UserIdentity:
    user_id: str
    identity_type: IdentityType
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "identity_type": self.identity_type.value,
            "metadata": dict(self.metadata or {}),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserIdentity | None":
        try:
            return cls(
                user_id=data["user_id"],
                identity_type=IdentityType(data["identity_type"]),
                metadata=data.get("metadata", {}) or {},
                created_at=datetime.fromisoformat(data["created_at"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Failed to create UserIdentity from dict: %s Error: %s", data, exc)
            return None


@dataclass(slots=True)
class MessageAttribution:
    message_id: str
    user_identity: UserIdentity
    attributed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "user_identity": self.user_identity.to_dict(),
            "attributed_at": self.attributed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageAttribution | None":
        try:
            identity = UserIdentity.from_dict(data["user_identity"])
            if identity is None:
                logger.error("Invalid user_identity in attribution payload: %s", data)
                return None
            return cls(
                message_id=data["message_id"],
                user_identity=identity,
                attributed_at=datetime.fromisoformat(data["attributed_at"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Failed to create MessageAttribution from dict: %s Error: %s", data, exc)
            return None

    @property
    def user_id(self) -> str:
        return self.user_identity.user_id

    @property
    def identity_type(self) -> IdentityType:
        return self.user_identity.identity_type


class AttributeError(Exception):
    pass
