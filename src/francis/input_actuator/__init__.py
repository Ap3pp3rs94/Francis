"""Governed Francis input actuator.

This package adds bounded input-action contracts behind the existing
Francis Orb/Takeover substrate. It does not rebuild the Orb/HUD and it
does not expose raw mouse or keyboard authority directly to MCP callers.
"""

from .tools import (
    execute_approved_input_action,
    input_receipts_readback,
    input_status,
    propose_input_action,
)

__all__ = [
    "execute_approved_input_action",
    "input_receipts_readback",
    "input_status",
    "propose_input_action",
]
