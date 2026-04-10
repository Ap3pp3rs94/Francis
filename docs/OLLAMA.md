==============================================================================

FRANCIS — OLLAMA.md

Local model runtime via Ollama: architecture, configuration, safety, ops

==============================================================================



Purpose

-------

This document defines how FRANCIS uses Ollama to run models locally:

   - Why/when to use Ollama (privacy, latency, airgapped deployments)

   - Provider architecture (native Ollama vs OpenAI-compat layer)

   - Model roster + Modelfiles (pinning, reproducibility, specialization)

   - Configuration (providers, routing, fallbacks, constraints)

   - Safety + governance (trust/approvals, policy gates, auditability)

   - Performance tuning (GPU/CPU, concurrency, caching, keep-alive)

   - Observability (health checks, logs, diagnostics)

   - Operational playbooks (install, pull, reset, upgrade, troubleshooting)



Read alongside:

   - docs/LOCAL_MODELS.md

   - docs/INTEGRATION_GUIDE.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/API_PERMISSIONS.md

   - docs/WEB_ACCESS.md (when web-research routes through local models)

   - config/models/providers/ollama.yaml

   - config/models/providers/ollama_openai_compat.yaml (if used)

   - config/models/routing.yaml

   - config/models/constraints.yaml

   - config/environments/*.yaml

   - config/runtime/concurrency.yaml

   - config/runtime/worker_pool.yaml

   - runtimes/ollama/model_roster.yaml

   - runtimes/ollama/Modelfiles/*.Modelfile

   - scripts/ollama-install.*

   - scripts/ollama-pull-models.ps1

   - scripts/ollama-doctor.ps1

   - scripts/ollama-reset.ps1

   - src/francis/llm/providers/ollama_provider.py

   - src/francis/llm/providers/ollama_openai_compat.py

   - src/francis/llm/providers/registry.py



Design stance

------------

   - Local inference reduces data egress but increases supply-chain risk.

   - Models are treated as *untrusted executors* with governed IO boundaries.

   - Reproducibility matters: pin model ids, versions, and Modelfiles.

   - Default to localhost-only; never expose Ollama unauthenticated to LAN/WAN.

   - Runtime chooses models; policies constrain actions; trust gates execution.



Reference (Ollama):

   - https://ollama.com/

   - https://github.com/ollama/ollama



==============================================================================





## 0. Executive summary



Ollama is the default **local model runtime** for FRANCIS in deployments where:

- privacy and data residency matter,

- latency matters,

- cost control matters,

- or the system operates in **airgapped** / restricted-network mode.



FRANCIS integrates with Ollama through one (or both) of these provider modes:

1) **Native Ollama provider** (preferred): calls Ollama’s API directly.

2) **OpenAI-compatible adapter**: treats Ollama as an OpenAI-like endpoint for

   easier drop-in compatibility (useful when standardizing client code).



Regardless of provider mode:

- Model selection is controlled by `config/models/routing.yaml`.

- Allowed capabilities and constraints are controlled by policies + scopes.

- Tool execution never bypasses governance: a local model has no special rights.





## 1. When to use Ollama (decision criteria)



### 1.1 Recommended use cases

Use Ollama when you need one or more of:

- **Data minimization / privacy**: prompts and retrieved context remain local.

- **Airgapped operation**: no upstream API dependency.

- **Latency**: fast local tokens for interactive workflows.

- **Cost predictability**: stable local compute vs variable token cost.

- **Customization**: local Modelfiles for system-specific tuning.



### 1.2 When NOT to use Ollama

Ollama may not be ideal if:

- your workloads require frontier reasoning quality consistently,

- you need very large context windows beyond local hardware capability,

- you cannot reliably provision GPU/CPU resources,

- or you need vendor-hosted compliance certifications that local hosting cannot

  satisfy on its own.



In these cases, FRANCIS should be configured for:

- hybrid routing (local first; remote fallback),

- or remote-first with local fallback for offline scenarios.





## 2. Integration architecture in FRANCIS



### 2.1 Provider interfaces

FRANCIS treats all model backends as *providers* under `src/francis/llm/providers/*`.



Key components:

- `ollama_provider.py`

  - Native Ollama API integration

  - Streaming support (if enabled)

  - Keep-alive control and request timeouts

- `ollama_openai_compat.py`

  - OpenAI-compatible wrapper layer for Ollama

  - Normalizes request/response schemas for shared client code

- `registry.py`

  - Provider registration and lookup

- `llm/router.py`

  - Selects a model (and provider) based on:

    - task type

    - environment

    - trust mode

    - policy constraints

    - model availability



### 2.2 Runtime assets

FRANCIS keeps Ollama-specific runtime assets in:



- `runtimes/ollama/model_roster.yaml`

  - The curated list of “known good” models and roles

  - Used by routing + tooling for discoverability and pinning

- `runtimes/ollama/Modelfiles/*.Modelfile`

  - Reproducible local builds (system prompts, templates, parameters)

  - Used to create consistent local model variants:

    - `francis-chat.Modelfile`

    - `francis-coder.Modelfile`

    - `francis-deliberate.Modelfile`

    - `francis-reflex.Modelfile`

    - `francis-embed.Modelfile`



### 2.3 Model identity and pinning

A “model id” in FRANCIS should be treated like a dependency version:

- Pin exact model tags/digests where possible.

- Record provenance (who pulled, when, from where, and hash if available).

- Treat unpinned models as “dev-only” unless explicitly approved.



Best practice:

- In production, model changes require approvals (and ideally, a CI pipeline step

  that runs evaluation suites before promotion).





## 3. Configuration files (what matters most)



### 3.1 Provider configuration

Provider configs live in:

- `config/models/providers/ollama.yaml`

- optionally `config/models/providers/ollama_openai_compat.yaml`



Illustrative example (shape, not a strict schema):



```yaml

# config/models/providers/ollama.yaml

provider_id: ollama_local

type: ollama

base_url: "http://127.0.0.1:11434"

default_timeout_seconds: 120

connect_timeout_seconds: 5



# Keep models warm to avoid cold-start latency; tune to hardware constraints.

keep_alive: "10m"



# Safety and stability

max_retries: 2

retry_backoff_ms: 250

streaming: true



# Resource hints (advisory; the runtime may enforce separately)

preferred_device: "gpu"        # gpu|cpu|auto

max_concurrent_requests: 2     # protect local box



