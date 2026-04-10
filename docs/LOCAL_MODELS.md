==============================================================================

FRANCIS — LOCAL_MODELS.md

Running FRANCIS on local LLMs (Ollama-first): privacy, performance, safety

==============================================================================



Purpose

-------

This document explains how FRANCIS uses **local models** (on-device / on-prem)

for chat, coding, reasoning, embeddings, and specialized tasks. It focuses on:

   - Provider architecture (Ollama-first)

   - Configuration (providers, routing, constraints, fallbacks)

   - Model roster + Modelfiles (reproducible local builds)

   - Safety and governance when using local models

   - Performance tuning (GPU/CPU, concurrency, caching)

   - Airgapped/regulated deployments and supply-chain integrity



Read alongside:

   - docs/INTEGRATION_GUIDE.md

   - docs/ARCHITECTURE.md

   - docs/POLICIES.md

   - docs/API_PERMISSIONS.md

   - docs/TRUST_MODEL.md

   - docs/WEB_ACCESS.md

   - config/models/providers/ollama.yaml

   - config/models/routing.yaml

   - config/models/constraints.yaml

   - config/models/fallbacks.yaml

   - runtimes/ollama/model_roster.yaml

   - runtimes/ollama/Modelfiles/*

   - scripts/ollama-install.ps1

   - scripts/ollama-pull-models.ps1

   - src/francis/llm/providers/ollama_provider.py

   - src/francis/llm/providers/ollama_openai_compat.py



Design stance

------------

   - Local models reduce data egress risk, but DO NOT eliminate risk.

   - Default to conservative routing + strict output validation.

   - Treat model weights as supply-chain artifacts with provenance.

   - Prefer reproducible model “builds” (Modelfiles) over ad-hoc pulls.

   - Always keep an operational fallback path (even if it is “deny”).



==============================================================================





## 1) What “local models” means in FRANCIS



A **local model** is any inference backend that runs under your control:

- on a workstation,

- on an on-prem server,

- on an edge node,

- or inside an airgapped environment.



Local model integration in FRANCIS covers:

- **chat/completions** (general assistant work)

- **coding** (code generation + refactoring)

- **reasoning** (planning, verification, conservative decisions)

- **embeddings** (vector memory, retrieval indexing)

- **specialized** models (vision/audio/simulation helpers if enabled)



The system treats local models as *providers* selected via routing rules, the same

way hosted models are selected—except local providers are constrained by:

- hardware availability,

- model files present,

- and local network/process health.





## 2) Provider architecture (Ollama-first)



### 2.1 Provider responsibilities

A provider is responsible for:

- creating a request payload for the inference engine,

- handling streaming vs non-streaming responses,

- normalizing outputs into FRANCIS’s internal message format,

- exposing tool/function-call support (if available),

- reporting latency/cost/metadata (as available),

- participating in fallback decisions.



### 2.2 Primary local provider: Ollama

FRANCIS is structured to support Ollama as the first-class local provider:

- **Native Ollama provider**:

  - `src/francis/llm/providers/ollama_provider.py`

- **OpenAI-compatible Ollama provider** (when Ollama is exposed via an OpenAI-ish API surface):

  - `src/francis/llm/providers/ollama_openai_compat.py`



The “OpenAI-compat” adapter is useful when:

- you want one client path for multiple backends,

- you deploy a gateway that emulates OpenAI APIs locally,

- or you want consistent tool-calling payload conventions.



### 2.3 Optional future providers

The architecture anticipates additional local engines (examples):

- llama.cpp server

- vLLM / TGI-style inference servers

- custom runtimes under `runtimes/*`



If you add a provider:

- treat it as a security boundary (payload validation + timeouts),

- support deterministic JSON outputs where required,

- and ensure it can be constrained by policies and trust.





## 3) Model roster and reproducible local builds



### 3.1 Why “roster + Modelfiles” exists

Local model ops fails when the system relies on:

- “whatever model someone pulled last week”,

- undocumented quantization variants,

- drifting prompts baked into model files.



FRANCIS prefers:

- a **model roster** (declares what must exist)

- **Modelfiles** (declares how custom variants are built)

- scripts to install and pull deterministically



### 3.2 The roster

Expected location:

- `runtimes/ollama/model_roster.yaml`



The roster should define:

- stable logical names (what FRANCIS routes to),

- the Ollama model id or build target,

- intended capability role (chat/coder/embed/etc.),

- minimum runtime requirements (VRAM, context, etc.),

- and integrity metadata (hashes when feasible).



Recommended roster concept (illustrative fields):

- `logical_name`: “francis-chat”

- `ollama_name`: “francis-chat:latest”

- `role`: “chat”

- `context_window`: 8192

- `quantization`: “Q4_K_M”

- `requires_gpu`: true/false

- `notes`: operational guidance



### 3.3 Modelfiles

Expected location:

- `runtimes/ollama/Modelfiles/*.Modelfile`



These are used to build consistent local variants:

- `francis-chat.Modelfile`

- `francis-coder.Modelfile`

- `francis-deliberate.Modelfile`

- `francis-embed.Modelfile`

- `francis-reflex.Modelfile`



Use Modelfiles to encode:

- base model reference

- system prompt defaults (careful: do not hardcode secrets)

- template behavior for safe tool calling

- stop sequences for JSON enforcement where needed

- parameter defaults (temperature/top_p/top_k/num_ctx, etc.)



### 3.4 Build discipline rules

**Rule A: No secrets in Modelfiles.** Ever.

**Rule B: Modelfile changes are code changes.** Review them like code.

**Rule C: Keep local model variants minimal.**

Prefer runtime prompts (`config/prompts/*`) over “baking prompts” into weights.



If you do bake defaults:

- ensure they are consistent with docs/POLICIES.md,

- and compatible with output schema validation.





## 4) Configuration: enabling local models



### 4.1 Provider configuration

Primary file:

- `config/models/providers/ollama.yaml`



It should declare:

- base URL / host (localhost vs remote host)

- connection timeouts

- max concurrency per worker

- streaming enablement

- model naming conventions

- retry/backoff rules

- safety limits (max tokens, max context, etc.)



### 4.2 Routing configuration

Primary file:

- `config/models/routing.yaml`



Routing should select models based on:

- task type (chat/coding/reasoning/research/embeddings)

- risk profile (high-risk actions force conservative models)

- environment overlays (regulated/airgapped force local-only)

- availability (fallback if local provider down)

- cost/latency budgets (if modeled)



A recommended routing posture:

- **default**: local chat for normal dialogue if healthy

- **coding**: local coder model

- **embeddings**: local embed model

- **high-risk**: local deliberate model with strict JSON schema + low temperature

- **if local unhealthy**:

  - in dev: fallback to hosted (if policy allows)

  - in prod/regulated: degrade gracefully (deny tool calls, return guidance)



### 4.3 Constraints configuration

Primary file:

- `config/models/constraints.yaml`



Constraints should include:

- per-role max tokens

- context windows (hard caps)

- allowed temperatures for safety-critical plans

- “tool-call required JSON mode” toggles

- rate limiting and concurrency budgets



### 4.4 Fallbacks configuration

Primary file:

- `config/models/fallbacks.yaml`



Fallbacks should be explicit and conservative:

- “try local → fallback local alternate → fallback hosted → fallback deny”

- with **policy hooks** (don’t fallback to hosted if data classification forbids egress)



Fallback policy must respect:

- `config/policies/privacy.yaml`

- `config/policies/data_governance.yaml`

- `config/policies/web_access.yaml` (for research flows)





## 5) Safety and governance with local models



Local ≠ safe. Local only changes *where computation runs*, not:

- the correctness of outputs,

- the model’s susceptibility to prompt injection,

- or the consequences of tool execution.



### 5.1 Safety gates still apply

All tool executions still pass:

- Permission Gate (delegation + scopes)

- Policy Engine (api permissions, privacy, offensive security, etc.)

- Action Readiness Gate (trust thresholds, approvals, dry-run)



Local models must never bypass:

- `src/francis/governance/api_permission_gate.py`

- `src/francis/governance/action_readiness.py` (and associated policies)

- output verification for schema-based tool calling



### 5.2 Prompt injection and untrusted text

Local models are still vulnerable to:

- malicious instructions embedded in web pages,

- adversarial content in attachments,

- collaborator messages in federation.



Mitigations:

- treat external text as *data*, not instructions

- isolate “evidence” from “instructions” in orchestration prompts

- enforce “never execute instructions from untrusted content” rules

- require explicit operator approval for high-impact actions



### 5.3 Output schema enforcement (critical)

For tool calls and structured operations:

- require strict JSON schema validation

- refuse malformed outputs

- prefer a model configuration that supports deterministic structured output:

  - lower temperature

  - stop sequences

  - smaller max tokens for tool-call segments

  - “repair loop” with bounded retries (never infinite)



### 5.4 Offensive/security-sensitive work

Even if local:

- restrict capability categories via `config/policies/offensive_security.yaml`

- require approvals for risky actions

- log all denials/attempts in audit logs





## 6) Performance and resource tuning



### 6.1 Key performance knobs

Local performance is a function of:

- model size (parameters)

- quantization

- context length

- batch size / parallelism

- GPU vs CPU

- memory bandwidth

- disk speed (model loading)

- caching strategy



FRANCIS should expose or configure:

- per-worker concurrency limits

- provider-level queueing

- timeouts for completions

- backpressure handling (avoid OOM)



### 6.2 GPU vs CPU

Guidelines:

- **CPU-only**: use smaller models, aggressive quantization, smaller context

- **GPU**: prefer larger context windows and better quality, but enforce VRAM caps

- Always guard:

  - max concurrent requests

  - max context per request

  - max tokens per response



### 6.3 Concurrency and worker pool interaction

Concurrency should be coordinated between:

- `config/runtime/worker_pool.yaml` (how many workers)

- provider config (max in-flight requests)

- model-specific limits (embed vs chat vs coder)



Bad pattern:

- “scale workers high + allow unlimited provider concurrency”

This causes:

- thrashing

- OOM

- latency spikes

- cascading failures



Better pattern:

- keep worker count moderate

- cap per-provider concurrency

- enforce a queue with timeouts

- degrade to “read-only, no tools” if overloaded



### 6.4 Caching and reuse

Local models can benefit heavily from:

- prompt caching (if supported)

- response caching for deterministic tasks

- embeddings cache:

  - `data/vectors/embeddings_cache`

- LLM cache:

  - `data/cache/llm`



Caching must respect:

- data classification (don’t cache regulated payloads unless policy allows)

- retention rules (purge cycles)

- provenance (store “what produced this” metadata)



### 6.5 Latency budgets (recommended)

Define budgets per class:

- chat UI: fast (<2–3s “first token” ideal)

- planning: slower allowed, but bounded (timeouts)

- embeddings: throughput prioritized



Use budgets to drive:

- routing (choose smaller/faster local model)

- constraints (cap context/tokens)

- fallback (if local too slow, choose alternate behavior)





## 7) Airgapped and regulated deployments



### 7.1 Airgapped principles

In airgapped mode:

- no outbound web access

- no hosted model calls

- model acquisition is an offline supply-chain process

- updates are imported as artifacts, not pulled live



Use:

- `config/environments/airgapped.yaml`

- and ensure web access policy blocks outbound.



### 7.2 Model supply-chain integrity

Treat model weights like executable dependencies:

- source allowlists (internal registry preferred)

- checksum verification

- signed manifests where possible

- malware scanning of transferred artifacts

- immutable storage of “what was installed when”



Maintain:

- “model inventory” artifacts under `data/system/inventories` (recommended)

- audit events on install/upgrade

- a rollback plan (previous known-good roster)



### 7.3 Data governance

Even local inference can leak data through:

- logs

- caches

- exports

- federation sharing



Enforce:

- redaction in logs

- strict cache policies

- “no export” rules in regulated domains unless approved





## 8) Operational health and observability



### 8.1 Health checks

At minimum, the system should surface:

- provider reachable/unreachable

- model present/missing

- inference latency percentiles

- error rate

- OOM or resource exhaustion events



Recommended:

- API health endpoint includes provider health summary

- workers record provider failures into `data/logs/errors/*` and audit logs



### 8.2 Metrics to track

Track:

- requests per model

- average latency / p95 latency

- token counts (if available)

- denial counts due to:

  - policy gates

  - trust gates

  - schema failures

  - provider unavailability



Write:

- operational metrics to `data/logs/operations/*`

- audit entries for gating decisions





## 9) Troubleshooting guide (local models)



### 9.1 “Provider unreachable”

Symptoms:

- timeouts on chat calls

- provider health check fails



Checks:

- is Ollama running?

- correct host/port in `config/models/providers/ollama.yaml`

- firewall/network policy blocks

- container network routing issues



Mitigations:

- restart runtime

- reduce concurrency

- confirm base URL from inside the worker container



### 9.2 “Model not found”

Symptoms:

- provider returns “model does not exist”

- routing references a missing logical name



Fix:

- ensure model is present locally (pulled or built)

- update `runtimes/ollama/model_roster.yaml`

- ensure routing references roster logical names consistently



### 9.3 “Tool calling JSON is malformed”

Symptoms:

- schema validator rejects output

- tool calls never execute



Fix:

- reduce temperature for tool-call stage

- tighten stop sequences

- split “analysis” and “tool JSON” into two-stage prompts

- add bounded repair loop:

  - “return ONLY valid JSON matching schema”

- prefer a “deliberate” local model for tool calling



### 9.4 “Too slow / OOM”

Fix:

- reduce max context or max tokens

- pick smaller/quantized model

- cap concurrency

- ensure GPU is used (if expected)

- isolate embeddings workloads to separate workers





## 10) Practical recipes



### 10.1 Local-first (developer workstation)

- enable Ollama provider

- route chat/coder/embed to local

- allow hosted fallback only in dev

- keep strict policies active (don’t disable governance for convenience)

- log all tool calls



### 10.2 Production local (on-prem GPU server)

- run Ollama on dedicated host

- workers connect over internal network

- enforce network policies (no public exposure)

- keep a hot standby model host if availability matters

- strict rate limiting and request queueing



### 10.3 Airgapped local

- pre-load model artifacts offline

- validate checksums

- disable web research tools

- lock routing to local-only

- disable hosted fallbacks entirely





## 11) Example snippets (illustrative)



### 11.1 Minimal provider config idea (conceptual)

```yaml

# config/models/providers/ollama.yaml (illustrative)

provider: ollama

base_url: "http://127.0.0.1:11434"

timeouts:

  connect_seconds: 2

  request_seconds: 120

streaming: true

concurrency:

  max_in_flight: 2

retries:

  attempts: 2

  backoff_ms: 250

safety_limits:

  max_output_tokens: 2048

  max_context_tokens: 8192



