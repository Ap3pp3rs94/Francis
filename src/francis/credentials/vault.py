from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CredentialRecord", "CredentialVault"]


@dataclass(frozen=True)
class CredentialRecord:
    credential_id: str
    secret: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class CredentialVault:
    def __init__(self) -> None:
        self._records: dict[str, CredentialRecord] = {}

    def put(self, record: CredentialRecord) -> bool:
        if not isinstance(record, CredentialRecord):
            logger.warning("put expected CredentialRecord")
            return False
        self._records[record.credential_id] = record
        return True

    def get(self, credential_id: str) -> CredentialRecord | None:
        if not isinstance(credential_id, str) or not credential_id.strip():
            logger.warning("get expected non-empty credential_id")
            return None
        return self._records.get(credential_id)
