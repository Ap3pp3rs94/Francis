# Francis ChatGPT Developer Bridge

## Status

`v0.5` keeps repo verification read-only, keeps the append-only collaboration
prompt relay, adds operator-visible transcript plus chat-handoff readback, and
adds a local Ollama participant path on the same relay. It is not an autonomy
upgrade and it is not a write-capable operator bridge.

## Roadmap fit

This slice supports the current substrate priority of making Francis's governed runtime loop more visible and checkable:

- `P1_INTERFACE`: gives ChatGPT Developer Mode / MCP a small, explicit interface surface.
- `P3_GOVERNANCE`: keeps bridge behavior bounded, read-only, and deny-by-default for sensitive paths.
- `P7_EXECUTION`: exposes supervised-exec receipts as evidence, not as authority.
- `P9_OBSERVABILITY`: makes repo status, ledger state, diff summaries, and
  collaboration relay receipts inspectable.
- `P8_MEMORY`: lets the local Ollama participant reuse the existing chat
  continuity ledger and feedback-memory prompt context instead of creating a
  second memory channel.

## Contract

The bridge may read only bounded repo truth and bounded supervised-exec display
artifacts. Its only write path is the collaboration prompt relay, which appends
bounded, redacted prompt envelopes under Francis data for another agent to read.
It must not mutate repository state, shell state, external services,
credentials, or operator data.

Allowed v0.5 operations:

- read current repo status
- read a non-sensitive UTF-8 repo file by repo-relative path
- search non-sensitive UTF-8 repo files
- read Git status and diff summaries without patch text
- read the completion ledger
- read allowlisted supervised-exec receipt files by run id
- append a bounded collaboration prompt envelope for another Francis-connected agent
- list bounded collaboration prompt envelopes by source, target, or agent
- read the collaboration relay as a bounded operator-visible transcript
- read Codex, Claude, and Ollama collaboration participant enabled state
- toggle known collaboration participants through the local operator UI/API
- return chat-ready handoff text that connected agents must echo in their chats

Denied v0.5 operations:

- arbitrary shell
- patch application
- repo file writes
- file writes outside the collaboration prompt relay
- commits
- pushes
- outside-repo file reads
- `.env`, `.npmrc`, `.pypirc`, key/certificate material, and `.ssh` paths
- path traversal
- external account actions
- autonomous execution from collaboration prompts
- treating the local Ollama model as Francis's brain or authority center
- training or tuning a model from relay text without a separate governed
  receipt-review and operator decision path

## HTTP API

Mounted under `/developer-bridge`:

- `GET /developer-bridge/status`
- `GET /developer-bridge/read-file?path=README.md`
- `GET /developer-bridge/search?query=needle`
- `GET /developer-bridge/git-diff-summary`
- `GET /developer-bridge/completion-ledger`
- `GET /developer-bridge/supervised-exec-receipt?run_id=<run_id>&filename=result.json`
- `GET /developer-bridge/collaboration-transcript?agent=claude&limit=20`
- `GET /developer-bridge/collaboration-agents`
- `POST /developer-bridge/collaboration-agents/toggle`

## Operator transcript readback

The collaboration transcript is a read-only view of Francis-owned relay
receipts. It shows bounded, redacted prompt envelopes that agents submit through
the developer bridge. It does not capture raw MCP JSON-RPC traffic, private
model conversation state, desktop pixels, or external service logs.

Each submitted relay record includes `chat_handoff.chat_text`. Connected agents
must echo that text in their own chat response after submitting or reading relay
entries. This is the governed way for the operator to see what Codex and Claude
say to one another in both chats. Francis cannot silently inject text into a
client chat pane; chat visibility depends on the agent surfacing the returned
handoff after tool use.

## Optional Codex relay responder

`python -m francis.developer_bridge.codex_responder --watch` is a bounded
auto-ack helper for Claude's scheduled relay replies. It only watches
`claude -> codex` relay entries, writes at most one `codex -> claude` relay
reply per source prompt id, and keeps local state under Francis data. It is not
a Codex reasoning loop, does not call shell or external services, and does not
execute or approve prompts.

Recommended cadence for a Claude task that runs every two minutes:

```powershell
python -m francis.developer_bridge.codex_responder --watch --ignore-existing --poll-seconds 30 --cooldown-seconds 120
```

Console readback:

```powershell
python -m francis.developer_bridge.collaboration_log --agent claude --limit 20
```

Machine-readable readback:

```powershell
python -m francis.developer_bridge.collaboration_log --json --limit 20
```

## Local Ollama participant

`python -m francis.developer_bridge.ollama_participant --watch` makes the local
Ollama-backed model a collaboration participant named `ollama`. It watches relay
entries targeted at `ollama`, builds the prompt through the existing Francis chat
prompt path, reads existing continuity and feedback-memory context, calls the
existing `francis.llm.client.generate` Ollama client, writes conversation-ledger
receipts, and appends one `ollama -> <source>` relay reply per source prompt id.

Recommended first cadence:

```powershell
python -m francis.developer_bridge.ollama_participant --watch --ignore-existing --poll-seconds 30 --cooldown-seconds 120
```

The Ollama participant is local intelligence substrate only:

- it may reason and reply through the relay
- it may leave conversation-ledger and relay receipts
- it may read bounded memory prompt context through the existing chat path
- it is prompted as `Francis1`, the primary local Francis intelligence
  participant, while Codex and Claude remain external guidance sources
- it may use only Francis-provided context surfaces such as continuity,
  feedback-memory, relay, review, summary, learning, and operator-visible Chat
  UI state when those surfaces are present
- it may not execute, mutate files, approve actions, commit, push, train itself,
  promote memory, bypass governance, or become the final authority over Francis

If Ollama is unavailable or returns no text, the participant writes an explicit
unavailable relay response instead of pretending a model answered.

## Agent toggles and client-as-operator boundary

The Chat UI may serve as the operator console for collaboration controls. This
does not make the client automatic execution authority. The status readback
returns both facts explicitly:

- `client_can_be_operator_console=true`
- `client_is_automatic_execution_authority=false`

Known participant toggles are `codex`, `claude`, and `ollama`. Disabling a known
participant blocks new relay submissions involving that participant and causes
local responders for that participant to stop answering.

## Optional MCP wrapper

`src/francis/developer_bridge/mcp_server.py` exposes the same read-only tools behind an optional MCP server.

Install with the bridge extra once the dependency is accepted into the local environment:

```powershell
pip install -e ".[bridge,web,dev]"
```

Streamable HTTP transport for URL-based clients:

```powershell
$env:FRANCIS_DEV_BRIDGE_TRANSPORT = "streamable-http"
$env:FRANCIS_DEV_BRIDGE_HOST = "127.0.0.1"
$env:FRANCIS_DEV_BRIDGE_PORT = "8788"
python -m francis.developer_bridge.mcp_server
```

Command-backed local MCP clients such as Claude/Cowork should launch the same
module with `FRANCIS_DEV_BRIDGE_TRANSPORT=stdio`.

## Operating rule

Receipts are claims until checked against repo status, diff summaries, and validation logs. ChatGPT may use this bridge to audit evidence, but it must not infer write authority from read access.

Collaboration relay prompts and transcript rows are also claims. They are queued
prompt envelopes, not commands, approvals, or execution receipts.

## Validation

Narrow validation for this slice:

```powershell
python -m compileall src/francis/developer_bridge src/francis/api/routes/developer_bridge.py
python -m pytest tests/test_developer_bridge.py
python -m ruff check src/francis/developer_bridge src/francis/api/routes/developer_bridge.py tests/test_developer_bridge.py apps/chat_ui/src/App.tsx apps/chat_ui/src/chat
python -m mypy src/francis/developer_bridge src/francis/api/routes/developer_bridge.py
cd apps/chat_ui; npm run test -- src/chat/index.test.ts
```

Full repo validation before merge when practical:

```powershell
.\scripts\check.ps1
```
