from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class ActorKind(str, Enum):
    AGENT = "agent"
    SYSTEM = "system"
    USER = "user"


@dataclass(frozen=True)
class RunContext:
    run_id: UUID
    actor_kind: ActorKind
    actor_name: str
    reason: str

