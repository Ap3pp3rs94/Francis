from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ImpersonationLevel(Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    FULL_ACCESS = "full_access"


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    username: str

    def to_dict(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "username": self.username}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User | None":
        if not isinstance(data, dict):
            logger.error("User.from_dict: data must be a dict")
            return None
        try:
            return cls(user_id=str(data["user_id"]), username=str(data["username"]))
        except (KeyError, TypeError) as exc:
            logger.error("User.from_dict failed: %s", exc)
            return None


@dataclass(slots=True)
class ImpersonationPolicy:
    policy_id: str
    subject: User
    target: User
    level: ImpersonationLevel
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.validate():
            logger.warning("ImpersonationPolicy validation failed for policy_id=%s", self.policy_id)

    def validate(self) -> bool:
        if not isinstance(self.subject, User):
            logger.warning("Invalid type for subject: %s", type(self.subject).__name__)
            return False
        if not isinstance(self.target, User):
            logger.warning("Invalid type for target: %s", type(self.target).__name__)
            return False
        if not isinstance(self.level, ImpersonationLevel):
            logger.warning("Invalid impersonation level: %s", self.level)
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "subject": self.subject.to_dict(),
            "target": self.target.to_dict(),
            "level": self.level.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImpersonationPolicy | None":
        try:
            subject = User.from_dict(data["subject"])
            target = User.from_dict(data["target"])
            if subject is None or target is None:
                logger.error("Invalid subject/target in impersonation policy payload: %s", data)
                return None
            level = ImpersonationLevel(data["level"])
            created_at = datetime.fromisoformat(data["created_at"])
            updated_at = datetime.fromisoformat(data["updated_at"])
            return cls(
                policy_id=data["policy_id"],
                subject=subject,
                target=target,
                level=level,
                created_at=created_at,
                updated_at=updated_at,
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Invalid impersonation policy data: %s", exc)
            return None

    @property
    def is_active(self) -> bool:
        return self.updated_at >= self.created_at


__all__ = ["ImpersonationPolicy", "User", "ImpersonationLevel"]
