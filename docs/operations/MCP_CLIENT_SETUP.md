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

Install the local project and MCP-capable extras in the active Python environment.
The MCP SDK lives in the `bridge` extra, so it **must** be included or
`mcp_sdk_available` will be `False` in the smoke check:

```powershell
uv sync --extra core --extra web --extra dev --extra bridge
```

If `uv sync --frozen` reports `mcp` missing from the lock (the `bridge` extra may
predate the current lockfile), refresh the lock once with `uv lock`, then re-run
the sync above. As a direct fallback in any active environment:

```powershell
.\.venv\Scripts\python.exe -m pip install "mcp>=1.2.0"
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
  tool_count: 23
  missing_tools: []
  health_status: ready
  screen_status: ready
  screen_session_status: ready
  screen_readback_safe: True
  takeover_status: ready
  takeover_proposal_created: True
  unapproved_takeover_refused: True
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

The developer bridge keeps repo verification read-only, adds an append-only
collaboration prompt relay, exposes a read-only transcript plus chat handoff
text for those relay receipts, and exposes read-only collaboration-agent status
for Codex, Claude, and local Ollama. It is for bounded repo verification,
evidence inspection, and queued Codex/Claude/Ollama prompt handoffs.

Start the streamable HTTP bridge with:

```powershell
cd D:\Francis
$env:FRANCIS_DEV_BRIDGE_TRANSPORT = "streamable-http"
$env:FRANCIS_DEV_BRIDGE_HOST = "127.0.0.1"
$env:FRANCIS_DEV_BRIDGE_PORT = "8788"
python -m francis.developer_bridge.mcp_server
```

Contract boundary:

- can read bounded repo truth
- can read bounded supervised-exec receipt artifacts
- can append bounded, redacted collaboration prompt envelopes
- can list bounded collaboration prompt envelopes
- can read the collaboration relay as a bounded operator-visible transcript
- can read Codex, Claude, and Ollama collaboration participant status
- can return chat-ready handoff text that connected agents must echo
- cannot write repo files
- cannot write files outside the collaboration prompt relay
- cannot run arbitrary shell
- cannot commit or push
- cannot read secrets
- cannot operate external accounts
- cannot execute collaboration prompts
- cannot train or tune a model
- cannot treat a model/client as execution authority by default

Operator transcript readback:

```powershell
cd D:\Francis
python -m francis Communication --agent claude --limit 20
python -m francis Communication --brief --hide-auto-acks --watch --new-only --poll-seconds 5 --limit 30
```

The transcript shows Francis-owned relay receipts only. It does not capture raw
MCP JSON-RPC traffic, private model conversation state, desktop pixels, or
external service logs.

Relay submissions and transcript reads return `chat_handoff.chat_text`.
Connected agents must echo that text in their own chat response when they submit
or read relay entries, so the operator can see the Codex/Claude handoff in both
chat panes. Francis cannot silently write into either chat UI from the
background; visibility is mediated through tool results and agent echo.

Optional bounded Codex responder for a scheduled Claude relay task:

```powershell
cd D:\Francis
python -m francis.developer_bridge.codex_responder --watch --ignore-existing --source-agent claude --poll-seconds 5 --cooldown-seconds 15
python -m francis.developer_bridge.codex_responder --watch --ignore-existing --source-agent ollama --poll-seconds 2 --cooldown-seconds 0
```

This helper auto-acks new relay entries targeted at Codex for the selected
source agent, writes at most one Codex relay reply per source id, and records
local state under Francis data. Codex auto-acks include a
`no_response_requested=true` marker so the local Ollama participant can show the
acknowledgement without answering it again. Auto-ack visible text is intentionally
compact: receipt id, objective, short preview, and no-authority marker only. The
auto-ack lane is
event-gated rather than cooldown-gated: Codex watches for completed
`ollama -> codex` receipts and responds once per source receipt id. It does not
perform Codex reasoning, execute prompts, mutate repo files, approve actions,
run shell, commit, push, or contact external services.

Optional bounded Codex/Ollama conversation driver:

```powershell
cd D:\Francis
python -m francis.developer_bridge.collaboration_driver --watch --ignore-existing --poll-seconds 5 --max-turns 0 --turn-gap-seconds 30 --summary-every-turns 6 --repeat-closed --session-gap-seconds 10
```

The conversation driver exists so the Communication window has a clean
event-gated sequence to show. It submits the next bounded `codex -> ollama`
question only after the previous matching `ollama -> codex` receipt exists, then
waits for the configured turn gap before prompting again. `--max-turns 0` means
there is no hard session cap. The driver writes bounded collaboration-note
receipts under
`data/integrations/developer_bridge/collaboration_driver/notes/`, typed
collaboration-insight receipts under the matching `insights/` directory, typed
failure/loop learning receipts under `learning_events/`, compact context-contract
receipts under `context_contracts/`, writes periodic summaries under
`summaries/`, and appends compact summary entries to the existing continuity
ledger so later turns can carry shared context without transcript dumping.
Driver prompts reference `francis1-collaboration-compact-contract-v1` instead of
restating stable identity/governance text every turn. Insight receipts use
`schema_version=developer_bridge_collaboration_insight_v1` and project each
bounded exchange into an advisory review shape: finding, build issue,
implementation candidate, memory candidate, action boundary, review status, and
source relay ids. They are a Codex/operator review surface, not a memory
promotion, approval, execution, model-tuning, or repository-mutation authority.
The read-only collaboration review surface is available at
`GET /developer-bridge/collaboration-review` and MCP
`collaboration_review_tool`; it turns recent insight receipts into concrete
review candidates with `concrete_repo_surface`, `review_artifact`, quality flags,
and a `review_recommendation`. Review candidates remain advisory readback and
must be checked against repo truth before implementation.
Learning receipts use
`schema_version=developer_bridge_collaboration_learning_v1` and record repeated
meta loops as bounded memory material with no full transcript storage and no
memory-write authority. The local model participant is named `Francis1` and is
prompted to speak in first person through the Ollama provider lane;
`source_agent=ollama` remains provider provenance for auditability, not identity.
The driver does not run shell, mutate the repo, approve actions, commit, push,
train the model, or turn Codex/Francis1 into an authority center.

Preferred supervised Codex/Ollama runtime:

```powershell
cd D:\Francis
python -m francis communication-runtime --watch --poll-seconds 10
```

The runtime supervisor keeps the event-gated Codex/Ollama helper pair and the
bounded conversation driver alive, and records its receipt at
`data/integrations/developer_bridge/collaboration_runtime/state.json`. It only
starts the fixed local helper commands documented above. It does not start
arbitrary commands, grant model execution authority, mutate repo files, approve
actions, commit, push, or contact external services.

Optional local Ollama participant:

```powershell
cd D:\Francis
python -m francis.developer_bridge.ollama_participant --watch --ignore-existing --source-agent codex --poll-seconds 2 --cooldown-seconds 0
```

The Ollama participant watches completed `codex -> ollama` relay receipts,
reuses the existing Francis chat prompt path, reads existing
continuity/feedback-memory context, calls the existing local Ollama client,
writes conversation-ledger and relay receipts, and responds back to Codex once
per source receipt id. The Codex lane and the Ollama lane are both
event-gated, not cooldown-gated. If local Ollama returns no text, it records an
explicit unavailable relay instead of faking a model answer.

Identity boundary: `source_agent=ollama` and `target_agent=ollama` are relay
provenance and provider-lane labels, not Francis identity. The local model
participant is named `Francis1`; Ollama is the runtime/provider name. This does
not make Francis1 Francis's brain or grant authority; it prevents provider
provenance from becoming the conversation's self-concept.

Governed access boundary: Francis1 is treated as the primary local Francis
intelligence participant for this collaboration lane, while Codex and Claude are
external guidance sources. Francis1's available context is only what Francis
supplies through existing prompt and receipt paths: continuity/feedback-memory
context, relay receipts, review candidates, summaries, learning receipts, and
operator-visible Chat UI state when present. Its write path remains limited to
conversation-ledger and collaboration-relay receipts. It still has no raw host
access, shell authority, repository mutation authority, approval authority,
model-training authority, or memory-promotion authority.

The Chat UI can act as the operator console for enabling or disabling Codex,
Claude, and Ollama relay participation. That operator-console role is explicit:
`client_can_be_operator_console=true` and
`client_is_automatic_execution_authority=false`.

### Governed MCP gateway

The governed MCP gateway exposes health, repo, command proposal, receipt, screen/session
readback, Takeover/Pilot session, input actuator, and takeover->input handoff-audit tools
through Francis-owned contracts.

The tool registry is validated by:

```powershell
python -m francis.mcp_gateway.smoke
```

The expected tool count is currently `23`.

## Client configuration template

Use this shape in MCP-capable clients that support local command-backed servers. Command-backed clients such as
Claude/Cowork speak MCP over stdio to the child process; do not set `streamable-http`
in that entry.

```json
{
  "mcpServers": {
    "francis-dev-bridge": {
      "command": "python",
      "args": ["-m", "francis.developer_bridge.mcp_server"],
      "cwd": "D:\\Francis",
      "env": {
        "FRANCIS_DEV_BRIDGE_TRANSPORT": "stdio"
      }
    }
  }
}
```

Keep client configuration local. Do not paste API keys, GitHub tokens, `.env` content, signing metadata, or credentials into MCP client configuration.

## Safe default behavior

The safe default is read/propose/refuse, not execute.

The client may ask Francis to propose actions, but Francis must preserve the proposal -> approval -> execution/receipt boundary.
The client may submit collaboration prompts, but those prompts are queued receipts only and do not grant execution authority.
The client must echo returned `chat_handoff.chat_text` when using the collaboration relay.

Required defaults:

- no arbitrary shell
- no automatic approval
- no raw mouse or keyboard control
- no credential typing
- no external side effects without an explicit governed path
- no autonomous execution from prompt relay messages
- receipts are checked evidence, not authority

## Screen/session readback

`francis.screen.status` and `francis.screen.session` expose a safe read-only context surface.

This surface may report:

- screen readback contract status
- operating platform
- active Takeover/Pilot session indicators
- whether real input is enabled
- bounded active-window title readback when the host supports it
- recent receipt ids without receipt content
- available governed action surface

This surface does **not** capture screenshots, pixels, OCR, raw screen frames, or raw input control.

Title readback can be redacted with:

```powershell
$env:FRANCIS_SCREEN_READBACK_REDACT_TITLES = "1"
```

When title redaction is enabled, Francis returns title length and a short hash instead of the visible title text.

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
- Did screen/session readback avoid screenshots and pixels?

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
- screenshot or pixel capture authority

If an MCP client asks for broader permissions, refuse the configuration and add a narrower Francis-owned tool instead.

## Troubleshooting

### `mcp_sdk_available: False`

The MCP Python dependency is missing from the active environment. Re-run the dependency setup command and then re-run the smoke check.

### Developer bridge port is already in use

The Francis API often uses `127.0.0.1:8000`. Keep the developer bridge local and choose another free port:

```powershell
$env:FRANCIS_DEV_BRIDGE_TRANSPORT = "streamable-http"
$env:FRANCIS_DEV_BRIDGE_HOST = "127.0.0.1"
$env:FRANCIS_DEV_BRIDGE_PORT = "8788"
python -m francis.developer_bridge.mcp_server
```

### `missing_tools` is not empty

The client should not connect. The local gateway registry is not matching the expected contract.

### `screen_readback_safe: False`

The client should not connect. The readback surface is reporting screenshots, pixels, raw shell, or another unsafe capability.

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
python -m pytest tests/test_developer_bridge.py tests/unit/test_screen_readback.py tests/unit/test_input_actuator.py tests/unit/test_mcp_input_actuator.py tests/unit/test_mcp_gateway.py
python -m ruff check docs/operations/MCP_CLIENT_SETUP.md src/francis/developer_bridge src/francis/screen_readback src/francis/input_actuator src/francis/mcp_gateway tests/test_developer_bridge.py tests/unit/test_screen_readback.py tests/unit/test_input_actuator.py tests/unit/test_mcp_input_actuator.py tests/unit/test_mcp_gateway.py
python -m mypy src/francis/developer_bridge src/francis/screen_readback src/francis/input_actuator src/francis/mcp_gateway
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
- screenshot capture
- pixel/OCR capture
- external service side effects
- background task authority
- policy bypasses
- new Orb/HUD surfaces

Those require separate governed slices and validation.
