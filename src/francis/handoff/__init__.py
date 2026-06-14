"""Receipt-backed cross-organ handoff (takeover -> input)."""

from francis.handoff.handoff import (
    HANDOFF_SURFACE,
    bind_input_to_takeover,
    handoff_audit,
    handoff_receipts,
    verify_input_handoff,
)

__all__ = [
    "HANDOFF_SURFACE",
    "bind_input_to_takeover",
    "handoff_audit",
    "handoff_receipts",
    "verify_input_handoff",
]
