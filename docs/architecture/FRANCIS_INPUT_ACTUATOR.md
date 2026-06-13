# Francis Input Actuator v0

Francis Input Actuator v0 gives the existing Takeover/Orb substrate governed hands without rebuilding the Orb, HUD, renderer, or overlay.

## What this is

A local adapter for bounded mouse/keyboard actions:

- `mouse.move`
- `mouse.click`
- `keyboard.type`
- `keyboard.hotkey`

## What this is not

It is not raw MCP mouse authority.

It is not raw MCP keyboard authority.

It is not a second Orb.

It is not a replacement HUD.

It is not a background autonomy grant.

## Authority path

```text
MCP client / AI caller
  -> Francis input actuator proposal
  -> manual approval phrase
  -> real-input environment gate
  -> active Takeover/Pilot control-transfer session
  -> local backend
  -> receipt/readback
```

## Real execution gate

Physical mouse/keyboard execution is disabled unless:

```powershell
$env:FRANCIS_INPUT_ACTUATOR_ENABLE_REAL = "1"
```

Even with that environment gate enabled, real execution requires an active Takeover/Pilot control-transfer session.

Without the environment gate, approved actions are dry-run receipts.

## Safety invariants

- No arbitrary shell.
- No raw MCP input authority.
- No physical input without explicit approval.
- No physical input without an active Takeover/Pilot session.
- No credential-like text typing.
- Receipts redact keyboard text by storing only length and SHA-256 in public action/receipt surfaces.
- Panic/handback remain owned by the existing Takeover substrate.
