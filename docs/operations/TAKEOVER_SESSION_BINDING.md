# Takeover Session Binding v0

This document records the bounded Takeover/Pilot session contract used by the MCP gateway, screen readback, and input actuator surfaces.

## Status

Takeover session binding is explicit and receipt-backed. It does not grant raw desktop control, shell access, screenshots, pixels, OCR, or unattended autonomy.

The MCP surface exposes:

- `francis.takeover.status`
- `francis.takeover.propose`
- `francis.takeover.start_approved`
- `francis.takeover.end`

## Contract

A Takeover/Pilot session is never implicit. The flow is:

1. Read status with `francis.takeover.status`.
2. Create a proposal with `francis.takeover.propose`.
3. Start only with the exact returned approval phrase through `francis.takeover.start_approved`.
4. End/revoke through `francis.takeover.end`.

Starting a physical-control session remains constrained by the existing Stage 9 takeover substrate. If Stage 8 closure evidence is missing, start attempts return a blocked result instead of faking readiness.

## Safety invariants

- Start requires manual approval.
- End is a revocation/handback surface.
- MCP never receives raw input authority.
- Screen readback remains read-only.
- Input execution still requires its own input proposal and exact approval phrase.
- Physical input still requires `FRANCIS_INPUT_ACTUATOR_ENABLE_REAL=1`.
- Physical input still requires an active Takeover/Pilot control-transfer session.
- Receipts are written for proposal start/end attempts at the session-binding layer.

## Validation

Run:

```powershell
python -m francis.mcp_gateway.smoke
python -m pytest tests/unit/test_takeover_session.py tests/unit/test_mcp_gateway.py tests/unit/test_input_actuator.py
python -m ruff check src/francis/takeover_session src/francis/mcp_gateway tests/unit/test_takeover_session.py tests/unit/test_mcp_gateway.py tests/unit/test_input_actuator.py
python -m mypy src/francis/takeover_session src/francis/mcp_gateway src/francis/input_actuator
```

Expected smoke additions:

```text
tool_count: 17
takeover_proposal_created: True
unapproved_takeover_refused: True
```

## Non-goals

This slice does not add autonomous desktop control, pixel capture, screenshot capture, OCR, browser automation, credential access, or unconditional mouse/keyboard execution.
