# Lens-Orb MCP Status Bridge v0

## Purpose

This bridge is the smallest truthful Stage 6/Lens body-state projection from the visible Lens/Orb layer to the verified MCP substrate.

MCP is one governed nervous system, not the whole Francis system. This bridge lets the Lens/Orb body read that nervous system and display live operator state without claiming residency or granting control authority.

## Existing Lens/Orb surface integration

The bridge is exposed through the existing Lens API namespace instead of creating a second Orb or overlay architecture:

- `GET /lens/mcp/status`
- `GET /lens/orb/mcp-status`

Both routes call `lens_orb_mcp_status_bridge()` and return the same read-only body-state projection. These routes are for Lens/HUD/Chat UI consumers that need a stable body-state readback.

The existing overlay runtime is linked to the same projection by configuration and readback metadata:

- `config/runtime/lens/overlay.json` advertises `mcp_status_route=/lens/mcp/status` and `orb_mcp_status_route=/lens/orb/mcp-status`.
- `scripts/lens-overlay-window.ps1 -Mode Status` includes a read-only `mcp_body_state` link in both top-level overlay status and nested `overlay_runtime` readback.
- The overlay window label displays the MCP body-state route when the overlay runtime is started.

This is a wiring pass only. It does not create a second Orb, a second overlay runtime, or a resident claim.

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

The overlay linkage also remains read-only. It advertises the body-state route to the existing overlay/resident path but does not grant overlay control, window management, local process launch, or mutation authority in status mode.

## Validation target

Run:

```powershell
python -m francis.mcp_gateway.smoke
python -m pytest tests/unit/test_lens_orb_mcp_status_bridge.py tests/unit/test_lens_orb_mcp_status_route.py tests/unit/test_lens_overlay_window_script.py tests/unit/test_lens_mcp_perception.py
python -m ruff check src/francis/lens/mcp_status_bridge.py src/francis/api/routes/lens_mcp_status.py tests/unit/test_lens_orb_mcp_status_bridge.py tests/unit/test_lens_orb_mcp_status_route.py
python -m mypy src/francis/lens/mcp_status_bridge.py src/francis/api/routes/lens_mcp_status.py
```

Expected posture:

- MCP smoke remains green.
- MCP tool count remains at least the known-good baseline of 18.
- `/lens/mcp/status` returns the Lens-Orb bridge projection.
- `scripts/lens-overlay-window.ps1 -Mode Status` reports `mcp_body_state.route=/lens/mcp/status`.
- The bridge is read-only.
- No raw input, screenshot, OCR, pixel, shell, or execution authority is introduced.
