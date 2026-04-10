==============================================================================

FRANCIS — ARCHITECTURE.md

System architecture, runtime topology, and request→action lifecycle

==============================================================================



Purpose

-------

This document is the canonical high-level architecture reference for FRANCIS.

It explains:

   - Core subsystems and their responsibilities

   - Runtime topology (API, daemon, workers, UI)

   - The end-to-end flow: input → reasoning → governance → tools → artifacts

   - Data layout under /data and how persistence is managed

   - Extensibility via connectors, plugins, and specializations

   - Deployment profiles (dev/prod/regulated/airgapped/federated)



Read alongside:

   - docs/PLANES.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/CONCURRENCY.md

   - docs/CONVERSATION_CONTINUITY.md

   - docs/WEB_ACCESS.md

   - docs/INTEGRATION_GUIDE.md



Key code references:

   - apps/api/main.py

   - src/francis/api/app.py

   - src/francis/kernel/orchestrator.py

   - src/francis/governance/*

   - src/francis/agent/*

   - src/francis/llm/*

   - src/francis/plugin_system/*

   - src/francis/chat/continuity/*

   - src/francis/memory/*

   - connectors/*



Design stance:

   - The model is not a security boundary

   - Default deny for tool actions; explicit delegation + approvals for risk

   - Everything important is auditable: decisions, evidence, tool calls

   - Separate "thinking" from "acting" with hard gates in between



==============================================================================





## 0. Architecture in one page



FRANCIS is an **agentic orchestration system** with a strict separation between:

- **Cognition** (planning and synthesis),

- **Governance** (permission + trust + readiness),

- **Execution** (sandboxed tool calls),

- **Memory** (provenance-based storage and retrieval),

- **Telemetry** (auditability, metrics, incident traceability).



The system is designed to run in multiple operational modes:

- **Local dev** (fast iteration, permissive logging)

- **Production** (stable, conservative)

- **Regulated / safety-critical** (strict approvals, narrow scopes)

- **Airgapped** (no external web)

- **Federated** (multiple instances share knowledge under trust controls)





## 1. System boundaries and invariants



### 1.1 Hard invariants (must always hold)

1) **Policy beats model output**

   - No matter what the model suggests, governance gates decide what is allowed.

2) **Default deny for risky tool actions**

   - Especially write/destructive/external communication.

3) **Secrets never enter model context**

   - The model works with handles, references, redacted summaries, or bounded views.

4) **All tool decisions are auditable**

   - Allow/deny is logged with a reason code and policy snapshot.

5) **Provenance is required for persistent knowledge**

   - Persistent memory must contain source metadata, validation status, and confidence.



### 1.2 System boundary (what FRANCIS is and isn’t)

FRANCIS is:

- a policy-driven orchestration kernel + APIs

- a tool/connector runtime with strict gating

- a knowledge/memory system with provenance



FRANCIS is not:

- a “model wrapper” that trusts the model to behave

- a general remote execution framework

- an autonomous offensive security platform





## 2. Top-level runtime topology



FRANCIS typically runs as 3 cooperating processes plus optional workers:



- **API Service** (HTTP + WebSocket)

  - routes, session management, orchestration entrypoint

- **Daemon**

  - background system tasks (learning schedules, cleanup, monitoring, federation sync)

- **Workers**

  - concurrency for tool execution, long-running jobs, simulations, crawls

- **Chat UI**

  - React/Vite UI for interactive operation



### 2.1 Topology diagram (conceptual)



```text

┌───────────────────────────┐

│        Chat UI (Web)       │

│  apps/chat_ui (Vite+React) │

└───────────────┬───────────┘

                │ HTTPS / WS

┌───────────────▼───────────┐

│         API Service         │

│  apps/api + src/francis/api  │

│  - auth/session              │

│  - chat routes               │

│  - tool invocation broker    │

└───────────────┬───────────┘

                │ internal calls / queue

┌───────────────▼───────────┐

│      Kernel / Orchestrator  │

│  src/francis/kernel/*        │

│  - planning                  │

│  - governance gates          │

│  - tool selection            │

│  - evidence + citations       │

└───────────────┬───────────┘

                │

     ┌──────────▼──────────┐

     │   Execution Layer     │

     │ - connectors/*        │

     │ - plugin_system/*     │

     │ - sandbox limits      │

     └──────────┬──────────┘

                │

┌───────────────▼───────────┐

│   Data Plane (/data)        │

│ - logs, artifacts, memory   │

│ - approvals, trust, state   │

│ - domains, vectors, cache   │

└────────────────────────────┘



