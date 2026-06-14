# Francis MCP Client Setup

## Status

This guide describes the operator-facing setup for connecting an MCP-capable desktop client to Francis's local MCP surfaces.

This is a connection and verification guide. It does not grant raw desktop control, raw shell authority, unattended execution, or background autonomy.

## Roadmap fit

This slice supports the current governed-runtime priority by making the existing MCP surfaces usable without weakening the control spine:

- `P1_INTERFACE`: gives the operator a concrete client connection path.
- `P3_GOVERNANCE`: keeps client usage bounded by approval phrases, environment gates, and refusal receipts.
- `P7_EXECUTION`: exposes governed command/input proposal flows rather than raw execution.
- `P9_OBSERVABILITY`: gives smoke checks and receipt/readback commands for verifying truth.

## Local prerequisites

Run from the repository root:

```powershell
cd D:\Francis
```

Install the local project and MCP-capable extras in the active Python environment:

```powershell
uv sync --frozen --extra core --extra web --extra dev
```

If `uv` is not available, use the repository bootstrap path first:

```powershell
.\scripts\bootstrap.ps1
```

## Smoke check

Before connecting any external client, verify the Francis MCP gateway registry and refusal path:

```powershell
cd D:\Francis
python -m francis.mcp_gateway.smoke
```

Expected shape:

```text
Francis MCP smoke
  ok: True
  mcp_sdk_available: True
  tool_count: 11
  missing_tools: []
  health_status: ready
  input_status: ready
  proposal_created: True
  unapproved_input_refused: True
```

If `ok` is not `True`, do not connect a client until the failure is understood.

## MCP surfaces

Francis currently has two MCP-facing surfaces:

1. Developer bridge MCP wrapper
2. Governed MCP gateway tools

### Developer bridge MCP wrapper

The developer bridge is read-only. It is for bounded repo verification and evidence inspection.

Start it with:

```powershell
cd D:\Francis
$env:FRANCIS_DEV_BRIDGE_TRANSPORT = "streamable-http"
python -m francis.developer_bridge.mcp_server
```

Contract boundary:

- can read bounded repo truth
- can read bounded supervised-exec receipt artifacts
- cannot write files
- cannot run arbitrary shell
- cannot commit or push
- cannot read secrets
- cannot operate external accounts

### Governed MCP gateway

The governed MCP gateway exposes health, repo, command proposal, receipt, and input actuator tools through Francis-owned contracts.

The tool registry is validated by:

```powershell
python -m francis.mcp_gateway.smoke
```

The expected tool count is currently `11`.

## Client configuration template

Use this shape in MCP-capable clients that support local command-backed servers.

```json
{
  "mcpServers": {
    "francis-dev-bridge": {
      "command": "python",
      "args": ["-m", "francis.developer_bridge.mcp_server"],
      "cwd": "D:\\Francis",
      "env": {
        "FRANCIS_DEV_BRIDGE_TRANSPORT": "streamable-http"
      }
    }
  }
}
```

Keep client configuration local. Do not paste API keys, GitHub tokens, `.env` content, signing metadata, or credentials into MCP client configuration.

## Safe default behavior

The safe default is read/propose/refuse, not execute.

The client may ask Francis to propose actions, but Francis must preserve the proposal -> approval -> execution/receipt boundary.

Required defaults:

- no arbitrary shell
- no automatic approval
- no raw mouse or keyboard control
- no credential typing
- no external side effects without an explicit governed path
- receipts are checked evidence, not authority

## Input actuator approval flow

The input actuator supports bounded action proposals for:

- `mouse.move`
- `mouse.click`
- `keyboard.type`
- `keyboard.hotkey`

Authority path:

```text
MCP client / AI caller
  -> Francis input actuator proposal
  -> manual approval phrase
  -> real-input environment gate
  -> active Takeover/Pilot control-transfer session
  -> local backend
  -> receipt/readback
```

Approved input actions are dry-run receipts unless real execution is explicitly enabled and a Takeover/Pilot control-transfer session is active.

Real execution is disabled unless:

```powershell
$env:FRANCIS_INPUT_ACTUATOR_ENABLE_REAL = "1"
```

Even with that environment gate, real input remains blocked without an active Takeover/Pilot session.

## Example: propose input safely

The exact MCP client UI differs by client, but the request shape should remain bounded:

```json
{
  "actor": "operator-client",
  "objective": "move pointer to a visible safe target after operator review",
  "kind": "mouse.move",
  "payload": {
    "x": 500,
    "y": 500
  }
}
```

The expected result is a proposal id plus an approval phrase requirement.

Do not execute the proposal unless the operator approves the exact action.

## Example: refusal check

A bad approval phrase must be refused:

```json
{
  "proposal_id": "<proposal id>",
  "approval_phrase": "not-approved"
}
```

Expected status:

```text
approval_required
```

This refusal path is part of the smoke check and must stay green.

## Receipts and readback

After any proposal or attempted execution, inspect receipts/readbacks through the relevant Francis tool surface rather than trusting the client transcript alone.

Minimum readback questions:

- What action was proposed?
- Who/what actor proposed it?
- Was approval required?
- Was approval supplied?
- Was real execution enabled?
- Was a Takeover/Pilot session active?
- Was the result a dry run, refusal, or executed action?
- Was sensitive typed text redacted?

## Operator safety rules

Never configure an MCP client to bypass Francis governance.

Do not expose:

- raw shell execution
- raw mouse movement
- raw keyboard typing
- unrestricted file reads
- repository writes
- Git commits or pushes
- `.env`, `.npmrc`, `.pypirc`, signing material, SSH keys, or credential files
- external account operations

If an MCP client asks for broader permissions, refuse the configuration and add a narrower Francis-owned tool instead.

## Troubleshooting

### `mcp_sdk_available: False`

The MCP Python dependency is missing from the active environment. Re-run the dependency setup command and then re-run the smoke check.

### `missing_tools` is not empty

The client should not connect. The local gateway registry is not matching the expected contract.

### `unapproved_input_refused: False`

The client should not connect. The approval/refusal boundary is not behaving safely.

### Real input does nothing

This is expected unless both are true:

1. `FRANCIS_INPUT_ACTUATOR_ENABLE_REAL = "1"`
2. An active Takeover/Pilot control-transfer session exists

Without both, approved input proposals remain dry-run receipt events.

## Validation before handoff

For this setup surface, run:

```powershell
cd D:\Francis
python -m francis.mcp_gateway.smoke
python -m pytest tests/test_developer_bridge.py tests/unit/test_input_actuator.py tests/unit/test_mcp_input_actuator.py tests/unit/test_mcp_gateway.py
python -m ruff check docs/operations/MCP_CLIENT_SETUP.md src/francis/developer_bridge src/francis/input_actuator src/francis/mcp_gateway tests/test_developer_bridge.py tests/unit/test_input_actuator.py tests/unit/test_mcp_input_actuator.py tests/unit/test_mcp_gateway.py
python -m mypy src/francis/developer_bridge src/francis/input_actuator src/francis/mcp_gateway
```

Full validation before merge when practical:

```powershell
.\scripts\check.ps1
```

## Non-goals

This setup does not add:

- real desktop autonomy
- raw MCP cursor control
- raw MCP keyboard control
- external service side effects
- background task authority
- policy bypasses
- new Orb/HUD surfaces

Those require separate governed slices and validation.
