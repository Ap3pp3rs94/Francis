# ADR 0009: Francis Unreal Grounded Presence Adapter

Date: 2026-07-09

Updated: 2026-07-10

Status: Accepted; operator-selected implementation live-validated

## Context

Stage 1, Grounded Presence, requires Francis to present calm, useful, truthful,
evidence-linked continuity without fabricating state. The operator selected a
dedicated Unreal Engine 5.8 project at `apps/unreal_presence` and pinned its
engine and project descriptor digests in a versioned selection artifact.

The current Francis architecture already separates Core authority from visual
surfaces. This adapter extends that boundary for Stage 1 without replacing the
native Orb, the governance layer, the memory layer, or the compute substrate.

## Decision

Francis may expose a versioned `francis.grounded_presence.snapshot` to an Unreal
adapter through a bounded local transport. The snapshot is read-only and is
derived from current continuity, operator, Orb, and receipt readbacks.

Unreal may own:

- presentation of grounded presence
- visual state interpolation
- local scene and animation timing
- operator-visible return-to-context presentation

Francis Core remains authoritative for:

- identity and presence truth
- briefing content and evidence linkage
- policy, approvals, and receipts
- memory and retention boundaries
- tool, model, desktop, and compute authority
- adapter health, freshness, and revocation state

The Unreal adapter must not accept authority from the snapshot, invent success,
write Francis memory, execute desktop actions, access the network, or decide
approvals. Events emitted by Unreal remain intents and must enter an existing
governed Francis route before any mutation is considered.

## Stage 1 Contract

The canonical interchange artifact is:

- `schemas/grounded_presence_snapshot.schema.json`
- `schemas/grounded_presence_unreal_selection.schema.json`
- `src/francis/world_state/presence.py`
- `src/francis/unreal_presence_selection.py`
- `/continuity/presence`
- `/continuity/presence/unreal-selection`

The separate transport contract is:

- `schemas/grounded_presence_transport_envelope.schema.json`
- `schemas/grounded_presence_delivery_receipt.schema.json`
- `schemas/grounded_presence_delivery_attempt.schema.json`
- `schemas/grounded_presence_delivery_journal.schema.json`
- `schemas/grounded_presence_ipc_message.schema.json`
- `schemas/grounded_presence_delivery_ack.schema.json`
- `schemas/grounded_presence_intent_event.schema.json`
- `schemas/grounded_presence_intent_receipt.schema.json`
- `src/francis/world_state/presence_transport.py`
- `src/francis/world_state/presence_intent.py`
- `src/francis/unreal_presence_adapter.py`
- `src/francis/unreal_presence_ipc.py`
- `src/francis/unreal_presence_receipts.py`
- `src/francis/unreal_presence_intents.py`
- `src/francis/unreal_presence_intent_ipc.py`

It binds adapter and session identity, a strictly increasing sequence, a
maximum five-second lifetime, and deterministic payload integrity. Its current
producer binding status is explicitly `unbound`; the named-pipe publisher binds
the envelope only at delivery. Process guards are backed by durable,
metadata-only delivery and accepted-intent receipt sequence watermarks. Bound
IPC messages use an injected HMAC-SHA256 key and never expose key material in
the message, receipt, journal, config readback, or logs.

Core key loading is fail-closed through
`FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID` and the strict-base64
`FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64` process environment value. No default key
exists. The loader validates the decoded 32-to-128-byte bound and exposes only
the key identifier and source in readback. The Unreal process must receive the
same secret through its operator-confirmed launch boundary; this ADR does not
authorize storing it in the project, command line, receipt, or payload.

The Core-owned adapter producer validates every envelope before returning it,
owns process-local sequence allocation, retains only bounded envelope metadata,
and reports delivery as unsupported while the pipe binding is absent. Preparing
an envelope does not write memory, write a receipt, contact Unreal, or claim a
delivered visual state. On restart, the producer can restore its sequence floor
from the same durable delivery-receipt watermark before preparing the next
envelope.

The first bound transport is a synchronous Windows named-pipe handshake from
Core to a local renderer consumer. It uses a four-byte little-endian length
prefix plus compact UTF-8 JSON, rejects remote clients, caps connection, ACK,
and message bounds, revalidates expiry after connection, and does not consume
sequence state on timeout. The semantic envelope is wrapped in a versioned,
HMAC-SHA256-authenticated IPC message. The consumer must return a separately
signed acknowledgement correlated to the message, envelope, adapter, session,
sequence, endpoint, and payload digest. Core rejects missing, expired, forged,
or correlation-drifted acknowledgements and requires the consumer to attest a
durably committed deduplication sequence without claiming that rendering was
applied. Only then may Core persist a delivery receipt.

The receipt stores the envelope identity, digest, sequence, endpoint, source
evidence IDs, authentication key identifier, signed acknowledgement identifier,
and durable-dedup posture, but never stores the presence payload or secret.
Delivery for one adapter/session is serialized with a bounded Windows named
mutex, and every publisher force-refreshes the durable receipt-derived sequence
watermark after acquiring that mutex. This removes the prior single-Core-writer
cache race while preserving bounded failure when the mutex cannot be acquired.

Before any pipe write, Core persists a versioned, metadata-only delivery
attempt containing the envelope/session identity, sequence, endpoint, digest,
wire-message identity, and key identifier. A definitive no-client/no-write
failure clears a fresh attempt. Ambiguous partial-write, missing-ACK, or invalid
ACK outcomes retain it. After restart, Core blocks every other envelope and
accepts only the exact envelope/digest/key tuple for reconciliation. That exact
envelope is wrapped in a fresh authenticated message even when its original
short transport lifetime has elapsed; the consumer's required durable sequence
deduplication makes either first acceptance or duplicate acknowledgement safe.

After a valid signed ACK, Core persists the separate versioned, metadata-only
delivery journal before it attempts the final delivery receipt. If receipt
persistence fails, a restarted publisher restores that journal and retrying the
exact envelope repairs the receipt without reconnecting to or re-sending the
payload. Neither recovery artifact stores the presence payload or secret.

The reverse channel is a separate inbound Windows named pipe. It accepts only
HMAC-authenticated IPC wrappers carrying
`francis.grounded_presence.intent_event.v1` events with four whitelisted intent
kinds, typed targets, source-envelope correlation, short expiry, integrity, and
monotonic event sequence. Core validates and persists an intent decision
receipt, including for forged or otherwise rejected events, but does not call
the named route or apply mutation. Panic-stop input is therefore represented as
a safety request for the existing Core route, not as renderer-held stop
authority. Accepted intent receipt history restores the per-session sequence
watermark after a Core restart, so a previously accepted event remains a replay
after restart.

The snapshot must expose:

- a stable kind, schema version, and generation timestamp
- grounded presence state plus a separate, immutable calm-tone contract
- lossless return-to-context objective, reason, next step, governance hold,
  latest meaningful timestamp, and evidence references
- one request-only intent projection with mission, operation, gate, approval,
  and receipt correlation; the projection never grants execution authority
- per-source continuity, operator, and Orb freshness with observed, partial,
  stale, missing-evidence, and invalid-timestamp semantics
- observed voice identity only when the live overlay readback is ready; input
  listening and output speaking remain independently nullable, output speaking
  is projected only from an explicit live overlay activity status, and a
  provider identity alone must not be presented as observed activity
- renderer-ready mode, semantic, activity, incident, execution, handback,
  approval, and panic-stop state without converting missing observations into
  false values
- Unreal engine target and explicit technology-selection status
- explicit false authority fields and limitations
- blockers when evidence or receipt linkage is incomplete

The snapshot is the semantic renderer payload, not the transport envelope. A
separate versioned local IPC envelope must add adapter/session identity,
monotonic sequencing, expiry, and replay rejection before an Unreal process is
connected.

## Technology Selection Decision

The operator-selected implementation uses a C++ runtime module, a Slate operator
surface, Lumen dynamic lighting, Substrate-ready state materials, Niagara
ambient motion, Enhanced Input request intents, and procedural presence
geometry. It does not adopt Nanite, MetaHuman, PCG, Motion Matching, or another
technology by implication. Extending that stack requires another explicit
selection decision and must not expand adapter authority.

The selection handoff is a separate, versioned, read-only artifact loaded only
from the explicit `FRANCIS_UNREAL_PRESENCE_SELECTION_PATH` environment value.
It records an operator confirmation, the Unreal 5.8 root and build changelist,
the `.uproject` path, a typed non-empty technology list, and immutable false
authority fields. It pins both `Engine/Build/Build.version` and the project
descriptor by SHA-256. Core reports the selection as stale if either file
drifts and never launches Unreal, writes the selection, or treats selection as
runtime observation. Missing, relative, UNC, malformed, wrong-version,
authority-expanding, and digest-drifted selections fail closed.

The canonical `scripts/francis.ps1 api` entrypoint supplies the pinned repository
selection path through that environment contract only for the API child process
when no operator override exists, then restores the caller environment exactly.
Direct or alternate API launch paths must provide the same explicit value; Core
does not search for or infer another Unreal project.

The repository contains the selected Francis project at
`apps/unreal_presence/FrancisPresence.uproject`. Projects from another product
or workspace remain out of scope and must not be adopted merely because local
discovery can find them.

## Runtime Implementation

The dedicated Unreal runtime consumes authenticated Core envelopes over a
local-only Windows named pipe, durably commits its per-session dedup watermark,
returns a signed acknowledgement, applies the accepted projection, and writes
only metadata plus bounded renderer status. A second authenticated named pipe
carries whitelisted request intents back to Core. Core validates and receipts
those intents but does not dispatch them or apply mutation.

The launcher injects a fresh HMAC key through process environment only, records
process identity without persisting the secret, supports a bounded test expiry,
refuses to overwrite an active launch, bounds screenshot writes to the dedicated
runtime directory, and transactionally stops only its owned processes when
startup or receipt commit fails. It restores every caller environment entry
after child process creation. Renderer state is exposed through
`schemas/grounded_presence_unreal_runtime_status.schema.json`,
`/continuity/presence/unreal-runtime`, the continuity presence projection, the
operator UI, and the read-only Orb overlay projection. A non-default bounded
session must configure the same session identifier in the API and renderer
launch; mismatched identities fail closed. None of those readbacks grants
execution, desktop, network, memory-write, or approval authority.

Stale snapshots remain blocked from render application. Delivery attempts and
journals reconcile ambiguous writes and post-ACK receipt failures without
persisting the presence payload or secret. Session-scoped durable dedup prevents
accepted envelopes and intents from becoming fresh work after restart.
The host change detector excludes only volatile generation, observation, and age
clock fields from its semantic digest. Those fields remain present and validated
in every envelope; semantic state changes and the bounded heartbeat still
publish. This prevents timestamp-only delivery churn from racing governed intent
source correlation.

## Validation Gate

The implementation gate requires schema and projection tests, named-pipe and
recovery tests, API/UI readback tests, successful native and Unreal builds, and
a bounded live loop proving authenticated delivery, render application, signed
ACK, receipt linkage, governed intent return, live API observation, and final
process cleanup. A screenshot or snapshot alone is not runtime proof, and a
successful runtime proof does not grant residency or close unrelated roadmap
stages.
