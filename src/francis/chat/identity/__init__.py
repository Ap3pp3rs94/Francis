from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["UserIdentity", "IdentityStatus", "create_user_identity", "validate_user_identity"]


class IdentityStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class UserIdentity:
    user_id: str
    username: str
    email: str
    status: IdentityStatus = field(default=IdentityStatus.ACTIVE)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserIdentity | None":
        try:
            return cls(
                user_id=data["user_id"],
                username=data["username"],
                email=data["email"],
                status=IdentityStatus(data["status"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Failed to deserialize UserIdentity from dict: %s Error: %s", data, exc)
            return None

    @property
    def is_active(self) -> bool:
        return self.status == IdentityStatus.ACTIVE


def create_user_identity(user_id: str, username: str, email: str) -> UserIdentity | None:
    if not user_id or not isinstance(user_id, str):
        logger.error("Invalid user_id provided: %r", user_id)
        return None
    if not username or not isinstance(username, str):
        logger.error("Invalid username provided: %r", username)
        return None
    if not email or not isinstance(email, str) or "@" not in email:
        logger.error("Invalid email provided: %r", email)
        return None
    return UserIdentity(user_id=user_id, username=username, email=email)


def validate_user_identity(identity: UserIdentity) -> bool:
    if not isinstance(identity, UserIdentity):
        logger.error("Invalid type provided for identity: %s", type(identity))
        return False

    if not identity.user_id or not identity.username or not identity.email:
        logger.warning("Invalid user identity data: %s", identity.to_dict())
        return False

    if "@" not in identity.email:
        logger.warning("Invalid email address: %s", identity.email)
        return False

    if not isinstance(identity.status, IdentityStatus):
        logger.warning("Invalid status for user identity: %r", identity.status)
        return False

    return True
