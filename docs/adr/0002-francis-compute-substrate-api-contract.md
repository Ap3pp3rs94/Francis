# ADR 0002: Francis Compute Substrate API Contract

Date: 2026-07-09

Status: Accepted as design contract before route implementation

## Context

Francis now has an internally governed Compute Substrate under the existing Phase 2 / `P7_EXECUTION` direction. The current internal path includes typed task envelopes, resource budgets, worker descriptors, a worker registry, a substrate governor, safe built-in local backend functions, approval consumption, durable approval persistence, durable compute receipt persistence, durable status persistence, adapter request validation, cooperative cancellation/deadline semantics, and structured persistence-failure reporting.

## Problem

Exposing that substrate through an API without a written authority contract would create risk around accidental execution bypass, fake async/recovery claims, raw payload leakage, weak approval semantics, weak status/readback semantics, and adapter behavior that appears more real than it is.

This ADR defines the contract that future internal API submission/status routes must satisfy before any route is implemented.

## Decision

Future Compute Substrate API routes must remain narrow wrappers over the existing governed substrate path:

1. API request.
2. `ApiPermissionGate` or a repo-equivalent actor/scope gate.
3. Adapter contract validation for adapter-originated requests, or direct internal request validation for direct internal submissions.
4. `ComputeSubstrateService.submit`.
5. `SubstrateGovernor.execute`.
6. Approval store authorization/consumption when required.
7. Worker registry and backend dispatch through the governor.
8. Durable compute receipt write when configured.
9. Durable status write when configured.
10. Bounded API response.

The API must not call these surfaces to bypass the service path:

- `SafeLocalBackend` directly.
- `SubstrateGovernor` directly, unless a later ADR explicitly changes the service authority boundary.
- `WorkerRegistry` directly for execution.
- Compute receipt stores directly for execution truth mutation.
- Approval stores directly except through governed approval validation or lookup patterns.
- Adapter internals in a way that bypasses `ComputeSubstrateService`.

The substrate remains the authority layer. API routes may submit requests and report bounded truth; they do not become the substrate.

## Non-Goals

This design contract does not implement:

- an API route
- public internet exposure
- fake API capability
- real adapters
- Unreal, VSC-1, desktop Lens, avatar, voice, VM/container, remote worker, or simulation implementation
- async or background execution
- task recovery or task resume
- OS-level CPU or memory enforcement
- distributed locking
- cross-process approval reservation
- durable adapter persistence
- long-term memory persistence
- `LiveLearningEvent` persistence
- model training
- new execution authority

It also does not claim that in-memory stores are production durable, that cooperative cancellation is OS preemption, or that status readback is task recovery.

## Proposed Route Shape

Francis route modules are mounted directly under route prefixes rather than under a universal `/api` prefix. A future route module should therefore use a repo-consistent internal prefix such as `/compute-substrate`.

Initial proposed endpoints:

- `POST /compute-substrate/submit`
- `GET /compute-substrate/status/{task_id}`
- `GET /compute-substrate/status/by-correlation/{correlation_id}`

Deferred endpoints:

- `GET /compute-substrate/receipts/{receipt_id}` is deferred until existing receipt-read patterns define a narrow, redacted compute receipt readback surface.
- `GET /compute-substrate/capabilities` is deferred unless the route only returns bounded capability names and worker descriptors already exposed by `ComputeSubstrateService.known_capabilities` and registry readback.

If a deployment layer later places Francis under `/api`, the same contract applies to the prefixed paths.

## Permission And Actor Contract

Every Compute Substrate API route must use `ApiPermissionGate` or the repo-equivalent permission gate before touching the substrate service.

Required rules:

- Actor identity must be present and known to the permission gate.
- Actor scopes must be explicit.
- Submit permission must be separate from status-read permission.
- Status-read permission must not imply submit permission.
- Receipt-read permission must not imply submit permission.
- Capability-read permission must not imply submit permission.
- Adapter identity must not replace actor authorization.
- Approval grants must not replace API actor authorization.
- API permission authorizes only request submission to the substrate boundary.
- Substrate approval still authorizes execution.
- No route may weaken `approval_required`.
- No route may grant filesystem, network, or GPU authority unless the substrate policy, adapter policy, and task budget all explicitly allow it.

Initial scope names:

- `compute:submit`
- `compute:status:read`
- `compute:receipt:read`
- `compute:capabilities:read`

`compute:admin` is reserved for future administrative operations and is not required for the first route.

## Request Contract

A future submit request should be schema-driven and bounded. The request may include:

- `request_id`
- `actor_id` or an actor summary
- `adapter_id` for adapter-originated requests
- `requested_capability`
- `task_type` or an intent summary
- request-only `payload`
- `payload_summary`
- `resource_budget`
- `risk_level`
- `approval_required`
- `approval_id` or an approval grant reference, if allowed by the route
- cancellation/deadline fields when they can be represented safely
- `correlation_id` or `trace_id`
- `idempotency_key` if a future idempotency contract is added
- `created_at`

Raw payload may be necessary for in-memory task execution. If present, it is request-only by default. It must not be persisted to status records, compute receipts, approval records, adapter records, logs, learning events, or long-term memory unless a later governance-reviewed redaction/storage rule explicitly allows that field.

The API must reject malformed requests safely before creating a `TaskEnvelope`. A request must not be able to downgrade an adapter or policy requirement for approval, network denial, GPU denial, filesystem scope, risk ceiling, runtime budget, memory budget, CPU weight, or compute-unit ceiling.

## Response Contract

Submission responses must return bounded summaries only. A response may include:

- `request_id`
- `task_id`
- `correlation_id` or `trace_id`
- `accepted`
- `denied`
- `status`
- `denial_reason`
- `approval_required`
- `approval_satisfied`
- safe `approval_id` reference
- `receipt_id`
- `receipt_persisted`
- `durable_status_persistence`
- `status_write_attempted`
- `status_write_succeeded`
- `status_persisted`
- `status_persistence_failed`
- bounded `status_persistence_error`
- `cancellation_requested`
- `timed_out`
- `timeout_stage`
- `started_at_ms`
- `finished_at_ms`
- `duration_ms`
- bounded warnings or limitations

Responses must not include:

- raw task payload
- raw execution output unless a future output route explicitly permits bounded output and proves redaction
- secrets
- raw approval notes
- raw model prompts
- broad filesystem paths
- traceback strings
- full exception details
- arbitrary user content beyond bounded summaries

## Denial And Error Semantics

The API must preserve distinct truth states. It must not collapse unrelated outcomes into one generic success or failure value.

At minimum, response bodies must distinguish:

- API permission denied
- malformed request
- unsupported API operation
- adapter validation denied
- missing approval
- invalid approval
- expired approval
- revoked approval
- already-consumed approval
- budget denial
- worker unavailable
- capability unavailable
- cancellation before execution
- deadline expired before execution
- backend execution failure
- receipt persistence failure
- status persistence failure
- unknown task or missing status record

The route should follow existing Francis denial-body style: `status`, `error`, a bounded `governance` object, and explicit false authority flags where relevant, such as no shell, no process start, no memory write, and no execution authority granted by the denial.

Receipt persistence failure, status persistence failure, and backend execution failure must remain separate. A status persistence failure must not make a successful execution look failed, and a backend execution failure must not be hidden behind successful status persistence.

## Store Configuration Contract

Durable stores remain separate:

- Durable compute receipt persistence proves what happened during execution attempts.
- Durable status persistence reports bounded task state and readback.
- Durable approval persistence proves why Francis was allowed to attempt execution.

Production-grade API submission requires a configured durable compute receipt store. Production-grade status readback requires a configured durable status store. Approval-required API submissions require a configured durable approval store before they can be treated as production-grade.

In-memory stores may be acceptable for local development and focused tests only. Responses must report them as non-durable. In-memory status readback must not be described as durable persistence.

Durable adapter persistence is not required for the first API route because adapter contracts remain internal and contract-only.

## Concurrency And Operational Contract

Current local JSON stores provide local persistence only. They do not implement distributed locking, cross-process approval reservation, cross-process status coordination, or multi-process receipt coordination.

The first API route, when implemented, must be marked local/internal/dev until these concerns are addressed:

- cross-process approval reservation
- durable store root configuration policy
- multi-process status and receipt coordination
- runtime data-root backup policy
- retention/cleanup policy for status records

The API contract does not solve repository storage durability or backup. The repository may run from local removable storage during development, so code changes still require disciplined commit/push anchoring. Runtime stores need their own configured local data roots and backup policy.

## Security And Redaction Contract

API request validation, response construction, status records, receipts, approval records, logs, and future readback surfaces must not become side channels for sensitive content.

Required redaction and boundedness rules:

- no tracebacks in API responses
- no raw path leakage
- no secret leakage
- no raw approval-note leakage
- no raw model-prompt leakage
- no broad filesystem-path leakage
- no raw task payloads in status, receipts, logs, approvals, adapter records, or learning events by default
- no raw execution outputs in response by default
- response fields must be schema-driven and length-bounded
- errors must use stable bounded codes or summaries

## Future Route Test Contract

Before a Compute Substrate API route is implemented, route tests must prove:

- unauthorized actor is denied
- missing scope is denied
- submit scope allows submit but not unrelated operations
- status-read scope allows readback but not submit
- receipt-read scope does not allow submit
- malformed request is denied safely
- request cannot downgrade `approval_required`
- request cannot enable network, GPU, or filesystem authority beyond policy
- `approval_required=True` without valid durable approval is denied
- `approval_required=True` with valid durable approval executes through the governed path
- durable approval is consumed through the API path
- durable compute receipt persists through the API path
- durable status persists through the API path
- status readback by `task_id` works
- status readback by `correlation_id` works
- receipt persistence failure response is truthful
- status persistence failure response is truthful
- adapter validation denial response is truthful
- cancellation/deadline response is truthful
- no raw payload, output, secret, approval note, model prompt, or broad path is returned
- route does not call backend or governor directly when the service is the authority surface
- route makes no async, recovery, or resume claims
- `tests/test_api_executor_substrate.py` remains passing

## Consequences

Future Compute Substrate API implementation is gated by this contract.

The first API route should be a narrow wrapper over `ComputeSubstrateService`. Substrate internals remain authoritative. Future adapters must not bypass the adapter gateway, service, governor, approval, receipt, and status path. This contract enables safer API implementation but does not expose API capability yet.

## Open Questions And Follow-Ups

- Final API scope names and whether they should align with existing `operations.run` or remain compute-specific.
- Whether the first route is local-only, dev-only, or operator-internal by configuration.
- Cross-process approval reservation.
- Durable store root configuration policy.
- Status retention and cleanup policy.
- Whether output-returning routes are allowed or must be separate from submission/status routes.
- Receipt readback route shape and redaction limits.
- OS-level resource enforcement design.
- VM/container backend contract.
- `LiveLearningEvent` persistence governance.
- First real adapter proof after API contract and route hardening.
