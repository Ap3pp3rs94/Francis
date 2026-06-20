# Francis Current Build Wiring Diagram

This document is a current-state wiring snapshot for the Francis repo. It is
based on:

- `docs/operations/COMPLETION_LEDGER.md`
- `docs/canonical/BUILD_MANIFEST.md`
- `docs/PLANES.md`
- `meta/plane_map.yaml`
- `docs/ARCHITECTURE.md`
- `docs/BUILD_ORDER.md`
- `src/francis/api/app.py`
- `scripts/francis-completion-model.ps1 -Mode Status`

It is not a roadmap replacement and does not move any completion percentage.
The snapshot is documentation-only.

## Current Posture

Roadmap phase: `Phase 2`.

Current priority supported by this diagram:

- keep three worker lanes focused on Stage 17 / Capability Economy construction
- use Worker 4 for full-project CI and wiring verification
- preserve Stage 17 completion-model truth while Capability Economy work remains
  open
- keep the governed runtime spine inspectable: plan -> gate -> execute -> trace
  -> memory

The strongest current wiring is the governed runtime spine: observability and
governance are more real than the finished operator product surface.

Current audit status:

- This diagram is a repo-truth orientation artifact, not a completion claim.
- A Worker 4 CI/wiring pass is responsible for verifying or correcting it
  against `src/francis/api/app.py`, the completion model, and current tests.
- Full CI status must be read from the latest Worker 4 packet or Lead Builder
  validation notes; this file does not imply the full gate passed.

## Runtime Spine

```mermaid
flowchart LR
  classDef strongest fill:#e8f5ed,stroke:#2f6f4e,color:#12351f
  classDef real fill:#fff6df,stroke:#9a6a00,color:#3c2a00
  classDef partial fill:#eef4ff,stroke:#41658a,color:#13273a
  classDef early fill:#f7f0ff,stroke:#6f4aa0,color:#2c1845
  classDef blocked fill:#f8eded,stroke:#9a3c3c,color:#3a1111

  P1["P1_INTERFACE<br/>Chat UI, Lens, API callers<br/>status: partial"]:::partial
  API["FastAPI service<br/>src/francis/api/app.py<br/>mounted route families"]:::partial
  P4["P4_COGNITION<br/>chat router, agent, planning<br/>status: partial"]:::partial
  P5["P5_EVIDENCE<br/>web, ingest evidence, provenance<br/>status: early"]:::early
  P6["P6_SIMULATION<br/>simulation and digital twin routes<br/>status: early"]:::early
  P3["P3_GOVERNANCE<br/>policy, approvals, readiness<br/>status: materially real"]:::real
  P2["P2_IDENTITY<br/>credentials, scopes, delegation<br/>status: partial"]:::partial
  P7["P7_EXECUTION<br/>plugins, supervised exec, lab boundaries<br/>status: partial"]:::partial
  P9["P9_OBSERVABILITY<br/>audit, logs, receipts, trust metrics<br/>status: strongest plane today"]:::strongest
  P8["P8_MEMORY<br/>continuity, memory, knowledge graph<br/>status: partial"]:::partial
  P10["P10_FEDERATION<br/>federation routes and data<br/>status: roadmap-stage"]:::blocked

  P1 --> API
  API --> P4
  P4 --> P5
  P5 --> P4
  P4 --> P6
  P6 --> P4
  P4 --> P3
  P3 <--> P2
  P3 --> P7
  P7 --> P9
  P7 --> P8
  P9 --> P1
  P8 --> P4
  P8 -. "gated, sanitized sharing only" .-> P10
  P10 -. "gated import only" .-> P8

  P1 -. "forbidden shortcut" .-> P7
  P5 -. "forbidden shortcut" .-> P7
  P10 -. "forbidden shortcut" .-> P7
```

Current interpretation:

- Interface exists through the React chat UI, Lens routes, and API routes, but
  the operator experience is not yet a complete ORB console.
- Cognition and execution paths exist, but the full product loop remains
  partial until planning, gates, execution, traces, memory, and UI readback are
  consistently wired for primary operator journeys.
- Governance is materially real, and observability is the strongest plane today.
- Evidence, simulation, and federation remain downstream or gated surfaces, not
  shortcuts into execution.

## Routed Surface Wiring

```mermaid
flowchart TB
  classDef ui fill:#eef4ff,stroke:#41658a,color:#13273a
  classDef api fill:#ffffff,stroke:#244a64,color:#142430
  classDef gate fill:#fff6df,stroke:#9a6a00,color:#3c2a00
  classDef data fill:#e8f5ed,stroke:#2f6f4e,color:#12351f

  subgraph Operator["Operator surfaces"]
    ChatUI["apps/chat_ui/src<br/>chat, missions, plugins, ingest, lens, telemetry"]:::ui
    LensUI["Lens and HUD routes<br/>/lens/status, /lens/hud, resident host readbacks"]:::ui
    APIClients["CLI, scripts, API callers"]:::ui
  end

  subgraph API["API service router mount"]
    App["src/francis/api/app.py"]:::api
    Chat["/chat"]:::api
    Missions["/missions"]:::api
    Continuity["/continuity"]:::api
    Completion["/completion-model/status"]:::api
    Approvals["/approvals"]:::gate
    Plugins["/plugins"]:::api
    Forge["/forge"]:::gate
    Ingest["/ingest"]:::gate
    Lens["/lens"]:::api
    Telemetry["/telemetry"]:::data
    MemoryTimeline["/memory/timeline"]:::data
  end

  subgraph Runtime["Runtime subsystems"]
    Agent["src/francis/agent/*<br/>planner, executor, supervised exec"]:::api
    Governance["src/francis/governance/*<br/>policy, approval, redaction"]:::gate
    Identity["src/francis/credentials/*<br/>scope checker, vault, delegation"]:::gate
    PluginRuntime["src/francis/plugin_system/*<br/>registry, sandbox, dispatcher"]:::api
    IngestCore["src/francis/ingest/*<br/>source records, lab, forge services"]:::gate
    Memory["src/francis/memory/*<br/>store, recall, provenance"]:::data
    Observability["src/francis/telemetry/*<br/>audit, metrics, tracing"]:::data
  end

  subgraph Data["Data and receipt stores"]
    ApprovalsData["data/approvals"]:::data
    ArtifactsData["data/artifacts"]:::data
    LogsData["data/logs"]:::data
    MemoryData["data/memory, data/vectors, data/knowledge_graph"]:::data
    PluginsData["data/plugins, data/artifacts/plugins"]:::data
    IngestData["data/ingest"]:::data
  end

  ChatUI --> App
  LensUI --> App
  APIClients --> App

  App --> Chat
  App --> Missions
  App --> Continuity
  App --> Completion
  App --> Approvals
  App --> Plugins
  App --> Forge
  App --> Ingest
  App --> Lens
  App --> Telemetry
  App --> MemoryTimeline

  Chat --> Agent
  Missions --> Agent
  Plugins --> PluginRuntime
  Forge --> PluginsData
  Ingest --> IngestCore
  Lens --> Governance
  Approvals --> Governance
  Governance <--> Identity
  Governance --> ApprovalsData
  Agent --> Governance
  Governance --> PluginRuntime
  Governance --> IngestCore
  PluginRuntime --> ArtifactsData
  IngestCore --> IngestData
  Agent --> Memory
  Memory --> MemoryData
  Agent --> Observability
  PluginRuntime --> Observability
  IngestCore --> Observability
  Observability --> LogsData
```

This is the current wiring shape, not a finished product claim. Several mounted
surfaces are readback-heavy or boundary-heavy. A route existing in the API does
not imply that the corresponding product capability is complete.

## Completion Model and Stage 17 Wiring

```mermaid
flowchart LR
  classDef source fill:#eef4ff,stroke:#41658a,color:#13273a
  classDef readback fill:#e8f5ed,stroke:#2f6f4e,color:#12351f
  classDef denied fill:#f8eded,stroke:#9a3c3c,color:#3a1111
  classDef future fill:#fff6df,stroke:#9a6a00,color:#3c2a00

  Ledger["Completion ledger<br/>docs/operations/COMPLETION_LEDGER.md"]:::source
  Manifest["Build manifest<br/>docs/canonical/BUILD_MANIFEST.md"]:::source
  Model["src/francis/completion_model.py<br/>read-only status projection"]:::readback
  Script["scripts/francis-completion-model.ps1<br/>-Mode Status"]:::readback
  Route["GET /completion-model/status"]:::readback
  Decision["next_continue_decision<br/>selects latest open Stage 17 gap"]:::readback
  Denial["selected-gap contract<br/>writes_repo=false<br/>writes_data=false<br/>execution and mutation authority denied"]:::denied
  Stage17["Stage 17 / Capability Economy<br/>proposal evidence and proposal-review queue remains open"]:::future
  GovernedApply["Future Stage 17 progress must use existing governed routes<br/>dry-run confirmation, bounded scope, focused validation"]:::future

  Ledger --> Model
  Manifest --> Model
  Model --> Script
  Model --> Route
  Route --> Decision
  Script --> Decision
  Decision --> Denial
  Denial --> Stage17
  Stage17 --> GovernedApply
```

Current completion-model readback truth:

- `current_phase` is `Phase 2`.
- `stage17_status.status` is `open`.
- The selected Stage 17 gap is read-only worker routing, not apply authority.
- The selected gap is not queue-count evidence.
- The selected gap is not proposal-evidence reference proof.
- The selected gap is not publication proof.
- The selected gap is not worker-readback, worker-publication handoff, or worker
  execution liveness proof.
- The completion model does not declare numeric baseline percentages.

## Authority Boundaries

```mermaid
flowchart TB
  classDef request fill:#eef4ff,stroke:#41658a,color:#13273a
  classDef gate fill:#fff6df,stroke:#9a6a00,color:#3c2a00
  classDef action fill:#ffffff,stroke:#244a64,color:#142430
  classDef receipt fill:#e8f5ed,stroke:#2f6f4e,color:#12351f
  classDef deny fill:#f8eded,stroke:#9a3c3c,color:#3a1111

  Request["Operator or API request"]:::request
  Normalize["Structured request<br/>plane and intent classification"]:::request
  Plan["Plan or proposal<br/>P4_COGNITION"]:::action
  Policy["Policy and approval gate<br/>P3_GOVERNANCE"]:::gate
  Identity["Identity and scope check<br/>P2_IDENTITY"]:::gate
  Execute["Authorized execution only<br/>P7_EXECUTION"]:::action
  Trace["Audit, trace, receipt<br/>P9_OBSERVABILITY"]:::receipt
  Memory["Allowed continuity update<br/>P8_MEMORY"]:::receipt
  Deny["Denied or blocked with reason<br/>no hidden execution"]:::deny

  Request --> Normalize
  Normalize --> Plan
  Plan --> Policy
  Policy --> Identity
  Identity --> Policy
  Policy -->|allow with satisfied gates| Execute
  Policy -->|deny or approval required| Deny
  Identity -->|scope missing| Deny
  Execute --> Trace
  Execute --> Memory
  Trace --> Request
  Memory --> Plan
```

Protected shortcuts:

- No direct `P1_INTERFACE -> P7_EXECUTION`.
- No direct `P5_EVIDENCE -> P7_EXECUTION`.
- No direct `P10_FEDERATION -> P7_EXECUTION`.
- No privileged action without `P3_GOVERNANCE` plus `P2_IDENTITY`.
- Readbacks can expose status, blockers, receipts, and next required gates; they
  do not grant mutation or execution authority by themselves.

## Plane Readiness Snapshot

| Plane | Current status | Current wiring signal | Main remaining risk |
| --- | --- | --- | --- |
| `P0_FOUNDATION` | partial | bootstrap, settings, kernel paths, API app startup | build contract still needs full ORB alignment |
| `P1_INTERFACE` | partial | chat UI, Lens, API route families | operator must still infer too much ORB state |
| `P2_IDENTITY` | partial | credentials, scope checker, delegation, API permission gates | identity is not yet unmistakable across every privileged route |
| `P3_GOVERNANCE` | materially real | approvals, policy engine, readiness, redaction, mutation matrix | must keep closing bypass and consistency gaps |
| `P4_COGNITION` | partial | chat router, agent, planning/proposal modules | plan-to-gate-to-result flow is not yet uniformly productized |
| `P5_EVIDENCE` | early | web/evidence docs, ingest provenance, explanation evidence | evidence must stay provenance-rich and injection-safe |
| `P6_SIMULATION` | early | simulation, industrial, digital twin routes | not yet a trusted production validation surface |
| `P7_EXECUTION` | partial | supervised exec, plugin runtime, ingest lab boundaries | broader authorization, sandbox, artifact, and explanation consistency remains |
| `P8_MEMORY` | partial | continuity, mission receipts, memory store/recall/provenance | retrieval and operator-facing continuity story need strengthening |
| `P9_OBSERVABILITY` | strongest plane today | audit, logs, metrics, traces, completion model readbacks | must avoid becoming a backdoor memory store or fake progress signal |
| `P10_FEDERATION` | roadmap-stage | federation routes and data folders exist | must not bypass sanitization, trust, governance, or execution gates |

## Use

Use this file as a fast orientation diagram before choosing or reviewing a
bounded implementation slice. For authoritative shipped posture, read the
completion ledger first. For target architecture, read the canonical roadmap and
ORB plane documents.
