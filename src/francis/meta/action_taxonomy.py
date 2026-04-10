from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

__all__ = ["ActionType", "ActionTaxonomy"]


class ActionType(Enum):
    QUERY = "query"
    UPDATE = "update"
    EXECUTE = "execute"


@dataclass(frozen=True)
class ActionTaxonomy:
    action: ActionType
    description: str
