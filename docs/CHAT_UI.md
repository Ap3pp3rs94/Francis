==============================================================================

FRANCIS — CHAT_UI.md

Web Chat UI architecture, safety UX, and operator-grade controls

==============================================================================



Purpose

-------

This document defines the design, boundaries, and implementation guidance for

the FRANCIS Chat UI (apps/chat_ui):

   - Operator experience for chat + tool execution visibility

   - Safety-first interaction patterns (approvals, redaction, trust gating)

   - Real-time streaming + event timelines

   - Views for domains, plugins, memory, federation, industrial control

   - UI ↔ API contracts and enforcement expectations



Read alongside:

   - docs/ARCHITECTURE.md

   - docs/API_PERMISSIONS.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/ATTRIBUTION.md

   - docs/ATTACHMENTS.md

   - docs/CONVERSATION_CONTINUITY.md

   - config/policies/api_permissions.yaml

   - config/policies/approvals.yaml

   - config/policies/trust_boundaries.yaml

   - config/policies/web_access.yaml

   - src/francis/api/websocket.py



Design stance:

   - UI is a safety surface, not a “skin”.

   - Backend is source-of-truth for authorization; UI provides guardrails,

     previews, and friction—never silent bypass.

   - All operator-visible “claims” should have provenance/citations when

     applicable.

   - Streaming is first-class: users must see *what is happening now*.



==============================================================================





## 1. Overview



The Chat UI is an operator console for FRANCIS. It is not only a chat window:

it is a *multi-panel system cockpit* exposing:



- **Chat**: streaming responses, tool calls, citations, attachments

- **Approvals**: pending requests, emergency approvals, review artifacts

- **Attachments**: intake, parsing, indexing, redaction previews

- **Trust dashboard**: trust state, metrics, decay, certification status

- **Memory timeline**: episodic/semantic/working memory traces

- **Domain workbench**: domain sources, induced knowledge, runbooks, evals

- **Plugin browser**: registry, specs, generated tools, validation status

- **Web learning monitor**: ingestion pipeline, blocked content, caching

- **Federation hub**: instance registry, shared knowledge sync status

- **Industrial control**: digital twins, simulations, safety validations

- **Operations**: runtime status, logs, incidents, audits



The UI must make it easy to answer:

- “What did it do?”

- “Why did it do it?”

- “What evidence did it use?”

- “Was it allowed?”

- “What changed?”

- “What is the risk if I let it proceed?”





## 2. Tech stack (expected)



The UI is implemented under:

- `apps/chat_ui/` (Vite + React + TypeScript)



Key files:

- `apps/chat_ui/index.html`

- `apps/chat_ui/package.json`

- `apps/chat_ui/src/main.tsx`

- `apps/chat_ui/src/App.tsx`

- `apps/chat_ui/vite.config.ts`

- `apps/chat_ui/tsconfig.json`



Notes:

- `node_modules/` is **never** committed.

- `package-lock.json` is tool-managed and must remain deterministic.





## 3. Runtime modes and environments



FRANCIS supports environment modes (dev, regulated, airgapped, production, etc.).

The UI must surface the current mode prominently and adapt UX accordingly.



### 3.1 Mode banner (mandatory)

Display a persistent banner that includes:

- Environment name (dev/production/regulated/airgapped)

- Trust mode (strict/standard/relaxed) if applicable

- Web access state (enabled/limited/disabled)

- “Writes enabled” / “Writes restricted” indicator



The goal is to prevent operators from forgetting the environment they are in.



### 3.2 Suggested Vite environment variables

These are recommended conventions; the backend remains authoritative.



- `VITE_API_BASE_URL` (e.g., `http://localhost:8000`)

- `VITE_WS_URL` (e.g., `ws://localhost:8000/ws`)

- `VITE_ENV_NAME` (e.g., `dev`, `regulated`)

- `VITE_UI_MODE` (e.g., `operator`, `readonly`)

- `VITE_BUILD_SHA` (optional, shown in settings/about)

- `VITE_FEATURE_FLAGS` (optional JSON string)



The UI must remain functional with safe defaults:

- API base URL defaults to same origin

- WS URL derives from API URL





## 4. Navigation model (product shape)



### 4.1 Primary routes (recommended)

- `/chat` — conversation sessions, streaming, tool trace

- `/approvals` — pending/approved/rejected/emergency

- `/attachments` — intake, parsing results, indexing, redaction

- `/trust` — trust levels, metrics, certifications

- `/memory` — timeline and memory objects (episodic/semantic/etc.)

- `/domains` — domain workbench (sources, induced, runbooks, evals)

- `/plugins` — registry, specs, generator outputs

- `/web-learning` — crawl/ingest monitor, blocked content

- `/federation` — instances, shared knowledge sync

- `/industrial` — twins, simulations, validations

- `/operations` — logs, health, alerts, audit



### 4.2 Role-based visibility

The UI may hide routes a user cannot access, but must:

- still allow deep-link attempts (then show a clear “not authorized” screen)

- never imply a capability is enabled if backend denies it



This is *defense-in-depth* UX, not a security boundary.





## 5. Core UI concepts



### 5.1 Conversation session

A session is a stable object with:

- session id

- participants/identity context

- created_at / updated_at

- environment snapshot reference

- current trust state reference

- ledger pointer(s) (conversation continuity)



### 5.2 Message

A message is an object with:

- `role`: user | assistant | system | tool

- `content`: text + structured blocks

- `status`: streaming | final | error | blocked | needs_approval

- `citations`: list of evidence references (see ATTRIBUTION.md)

- `attachments`: refs to ingested artifacts

- `tool_calls`: structured tool invocations + results



### 5.3 Tool call trace (first-class)

Operators must be able to expand a message and see:

- tool name + operation

- parameters (with sensitive fields redacted)

- permission evaluation result (allow/deny + reason class)

- trust gate result (approved/blocked/requires approval)

- timing (start/end/duration)

- outputs (redacted) + provenance ids



### 5.4 Decisions are visible

If the system denies something, the UI should show:

- **what** was attempted

- **which gate** denied it (permissions / policy / trust / sandbox)

- **why** at a safe level

- **what to do next** (request approval / narrow scope / provide evidence)





## 6. Streaming and real-time



FRANCIS has realtime primitives (`src/francis/api/websocket.py`).

The UI must support:



### 6.1 Streaming assistant output

- incremental tokens/chunks

- partial rendering that remains stable (avoid reflow jitter)

- “Stop generating” and “Pause stream” controls (client-side cancellation)

- durable finalization (store final message and trace)



### 6.2 Event stream

A separate event channel should carry:

- tool call started/finished

- approval requested/approved/rejected

- web learning ingest started/blocked

- trust state changes

- runbook generation completed

- simulation completed/failed



Operators should not have to “refresh to see reality”.



### 6.3 Reconnect safety

On reconnect:

- UI must reconcile stream position with backend session state

- UI must not duplicate messages

- UI should show a “recovered after disconnect” indicator





## 7. Safety UX patterns (mandatory)



### 7.1 Redaction-aware rendering

If any message includes sensitive data:

- render redacted placeholders

- show classification badges (public/internal/confidential/regulated)

- provide “copy redacted” default behavior

- provide “view sensitive” only if backend grants explicit permission



Never rely on frontend-only redaction.



### 7.2 Approval-required interactions

For actions requiring approval:

- show a clear “This action requires approval” block

- include:

  - action summary

  - risk rationale (policy references)

  - approval type (standard/emergency)

  - diff/preview of intended changes when applicable

- provide:

  - “Request approval” flow

  - “Modify request” suggestions (narrow scope, read-only alternative)



### 7.3 Dangerous action friction

For destructive/irreversible operations:

- require explicit confirmation

- show:

  - affected resources

  - rollback availability

  - audit log destination

- prefer “dry run” preview first, if supported



### 7.4 Evidence visibility (ATTRIBUTION compliance)

If the assistant asserts non-trivial facts:

- show citations inline or in an “Evidence” drawer

- allow operators to open evidence objects (attachments, web snippets, tool rows)

- show retrieval time and source type



### 7.5 Prompt injection defense UI

When content is sourced from the web or attachments:

- label it (“From web”, “From attachment”, etc.)

- show warnings if it contains tool instructions

- provide “strip instructions” toggle for review views





## 8. UI ↔ API contract expectations



The Chat UI interacts with the API service (`apps/api/main.py` + `src/francis/api/*`).



### 8.1 Recommended HTTP endpoints (illustrative)

- `GET /health`

- `POST /chat/send` (or session-scoped equivalent)

- `GET /chat/sessions`

- `GET /chat/sessions/{id}`

- `GET /chat/sessions/{id}/ledger`

- `POST /attachments/intake`

- `GET /attachments/{id}`

- `POST /approvals/request`

- `GET /approvals?status=pending`

- `POST /approvals/{id}/resolve`

- `GET /trust/state`

- `GET /domains`

- `GET /plugins`

- `GET /operations/logs`



### 8.2 WebSocket channels (illustrative)

- `/ws/chat/{session_id}` — message streaming + tool trace events

- `/ws/events` — global events (approvals, trust, ops)



### 8.3 Error model (strongly recommended)

All API errors should map into a stable shape:

```json

{

  "error": {

    "code": "PERMISSION_DENIED",

    "message": "Denied by API permission gate.",

    "gate": "api_permissions",

    "details_safe": { "policy_ref": "config/policies/api_permissions.yaml#..." },

    "request_id": "req_...",

    "timestamp": "..."

  }

}



