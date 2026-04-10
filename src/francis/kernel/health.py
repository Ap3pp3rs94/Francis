from __future__ import annotations

import os
import time

from francis.trust.levels import get_state
from francis.kernel.stack import stack_summary


def health_report() -> dict:
    return {
        "ts": time.time(),
        "env": os.getenv("FRANCIS_ENV", "dev"),
        "trust": get_state(),
        "stack": stack_summary(),
    }
