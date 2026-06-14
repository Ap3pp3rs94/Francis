# Lens-Orb MCP Status Bridge v0

## Purpose

This bridge is the smallest truthful Stage 6/Lens body-state projection from the visible Lens/Orb layer to the verified MCP substrate.

MCP is one governed nervous system, not the whole Francis system. This bridge lets the Lens/Orb body read that nervous system and display live operator state without claiming residency or granting control authority.

## What it reads

The bridge aggregates safe MCP readbacks for:

- `francis.health`
- `francis.repo.status`
- `francis.screen.status`
- `francis.screen.session`
- `francis.takeover.status`
- `francis.input.status`
- optional `francis.receipts.readback`
- optional `francis.handoff.audit`

It also checks whether the developer bridge module is importable so the body-state readback can show whether the builder interface organ is present.

## What it reports

`lens_orb_mcp_status_bridge()` returns a read-only body-state projection with:

- MCP tool count and required-tool gaps
- per-component status for screen, takeover, input, repo, and gateway health
- developer bridge status
- latest MCP receipt id when available
- visible badges for operator display
- embodied posture:
  - `read_only`
  - `pilot_ready`
  - `takeover_ready`
  - `takeover_active`
  - `degraded`

`takeover_active` is only reported when the takeover/session readback reports real active control transfer. The bridge does not create active state.

## Governance boundaries

The bridge is read-only. It does not:

- start or end takeover
- propose or execute input
- execute shell commands outside existing readback tools
- capture screenshots
- perform OCR
- read pixels
- grant mutation authority
- grant execution authority
- claim resident overlay/runtime status

The bridge intentionally reports `resident=false` and `resident_claim=not_enabled_by_mcp_status_bridge`.

## Validation target

Run:

```powershell
python -m francis.mcp_gateway.smoke
python -m pytest tests/unit/test_lens_orb_mcp_status_bridge.py tests/unit/test_lens_mcp_perception.py
python -m ruff check src/francis/lens/mcp_status_bridge.py tests/unit/test_lens_orb_mcp_status_bridge.py
python -m mypy src/francis/lens/mcp_status_bridge.py
```

Expected posture:

- MCP smoke remains green.
- MCP tool count remains at least the known-good baseline of 18.
- The bridge is read-only.
- No raw input, screenshot, OCR, pixel, shell, or execution authority is introduced.
