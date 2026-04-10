from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CredentialOwner", "CredentialAttribution"]


@dataclass(frozen=True)
class CredentialOwner:
    owner_id: str
    owner_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CredentialAttribution:
    credential_id: str
    owner: CredentialOwner
    attributed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "credential_id": self.credential_id,
            "owner": {
                "owner_id": self.owner.owner_id,
                "owner_type": self.owner.owner_type,
                "metadata": dict(self.owner.metadata or {}),
            },
            "attributed_at": self.attributed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CredentialAttribution | None":
        try:
            owner_payload = payload["owner"]
            owner = CredentialOwner(
                owner_id=str(owner_payload["owner_id"]),
                owner_type=str(owner_payload["owner_type"]),
                metadata=dict(owner_payload.get("metadata") or {}),
            )
            return cls(
                credential_id=str(payload["credential_id"]),
                owner=owner,
                attributed_at=datetime.fromisoformat(payload["attributed_at"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("Invalid attribution payload: %s", exc)
            return None
