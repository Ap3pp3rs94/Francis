"""TEMP STUB: Local actions module was quarantined and is temporarily simplified to keep imports working.
Please restore the actual local action detection logic when the repo content is recovered."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LocalActionOutcome:
    handled: bool = False
    message: str = ""


def try_handle(text: str) -> LocalActionOutcome:
    """Always return 'not handled' while the real logic is offline."""
    logger.debug("Local actions stub invoked; returning no-op outcome for %r", text)
    return LocalActionOutcome()
