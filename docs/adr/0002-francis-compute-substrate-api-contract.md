# ADR 0002: Francis Compute Substrate API Contract

Date: 2026-07-09

Status: Accepted; first internal/local-dev route implemented under this contract

## Context

Francis now has an internally governed Compute Substrate under the existing Phase 2 / `P7_EXECUTION` direction. The current internal path includes typed task envelopes, resource budgets, worker descriptors, a worker registry, a substrate governor, safe built-in local backend functions, approval consumption, durable approval persistence, durable compute receipt persistence, durable status persistence, adapter request validation, cooperative cancellation/deadline semantics, structured persistence-failure reporting, and internal/local-dev API submission/status routes.

## Problem

Exposing that substrate through an API without a written authority contract would create risk around accidental execution bypass, fake async/recovery claims, raw payload leakage, weak approval semantics, weak status/readback semantics, and adapter behavior that appears more real than it is.

This ADR records the contract that the first internal/local-dev API submission/status route now satisfies and that future Compute Substrate API route expansion must preserve.

## Decision

Implemented and future Compute Substrate API routes must remain narrow wrappers over the existing governed substrate path:

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

## Implemented First Route Surface

As of commit `3953ed26`, Francis has an internal/local-dev, synchronous, in-process route module mounted under `/compute-substrate`:

- `POST /compute-substrate/submit`
- `GET /compute-substrate/status/{task_id}`
- `GET /compute-substrate/status/by-correlation/{correlation_id}`
- `GET /compute-substrate/receipts/{receipt_id}`

The route uses `ApiPermissionGate` before service or receipt-store access, with separate `compute:submit`, `compute:status:read`, and `compute:receipt:read` scopes. API permission authorizes only route access. Substrate approval still authorizes execution.

Submit requests are converted into bounded `TaskEnvelope` / `ComputeSubmission` objects and sent through `ComputeSubstrateService.submit`. Status readback uses the service status surface. The route does not call `SafeLocalBackend`, `SubstrateGovernor`, or backend internals directly for execution, and it does not weaken `approval_required`.

Receipt readback reads bounded compute receipt truth from the configured durable receipt store only. It does not submit work, consume approval, mutate approval/status/receipt stores, expose raw receipt artifacts, or become a general audit-log surface.

Focused API and substrate tests cover permission boundaries, malformed request denial, approval denial and consumption, durable receipt/status persistence, cancellation/deadline truth, receipt/status persistence failure truth, status readback by task id and correlation id, receipt readback by receipt id, redaction, service-boundary enforcement, and adapter validation denial before service submission.

## Non-Goals

This contract and the first internal/local-dev route do not add:

- production-grade public exposure
- public internet exposure
- receipt mutation, receipt listing/export, capability readback, or admin routes
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

Francis route modules are mounted directly under route prefixes rather than under a universal `/api` prefix. The current route module uses the repo-consistent internal prefix `/compute-substrate`.

Implemented endpoints:

- `POST /compute-substrate/submit`
- `GET /compute-substrate/status/{task_id}`
- `GET /compute-substrate/status/by-correlation/{correlation_id}`
- `GET /compute-substrate/receipts/{receipt_id}`

Deferred endpoints:

- `GET /compute-substrate/capabilities` is deferred unless the route only returns bounded capability names and worker descriptors already exposed by `ComputeSubstrateService.known_capabilities` and registry readback.

If a deployment layer later places Francis under `/api`, the same contract applies to the prefixed paths.

## Receipt Readback Route Contract

`GET /compute-substrate/receipts/{receipt_id}` is implemented as an internal/local-dev readback route. It must remain internal/local-dev unless a later governance-reviewed promotion explicitly changes that posture.

The route is read-only. It may expose bounded compute receipt truth, but it must not become a raw artifact dump, general audit-log API, execution endpoint, approval mutation endpoint, status mutation endpoint, memory or learning endpoint, production-grade public audit surface, or new authority surface.

Required route posture:

- permission-gated before any receipt store access
- bounded response only
- no execution
- no approval consumption
- no approval creation, revocation, update, or grant mutation
- no status mutation
- no receipt mutation
- no long-term memory mutation
- no `LiveLearningEvent` persistence
- no model training
- no adapter invocation
- no production or public audit authority

The preferred future read path is:

1. API request.
2. `ApiPermissionGate` or repo-equivalent actor/scope validation.
3. Safe `receipt_id` validation.
4. Configured durable compute receipt readback service or store path.
5. Bounded receipt response.

The route must not:

- call `SafeLocalBackend`
- call backend internals
- trigger `SubstrateGovernor.execute`
- create `TaskEnvelope` execution
- consume approval
- mutate status records
- mutate receipt records
- mutate approval records
- persist `LiveLearningEvent`
- write memory
- train models
- invoke adapters

If a future service wrapper is added for receipt readback, it must preserve the same bounded read-only semantics and must not become a bypass around the substrate authority model.

### Receipt Id Validation

Receipt IDs must use the approved safe character set already established by compute receipt storage: ASCII letters, digits, underscores, and hyphens only, with the implementation-defined length bound. Future route validation must reject:

- empty strings
- whitespace-only strings
- `../` and `..\`
- slashes and backslashes
- absolute paths
- Windows drive prefixes
- dots
- colons
- unusual path separators
- IDs outside the approved safe character set

Receipt readback must fail closed:

- unsafe receipt IDs must return a bounded malformed or invalid ID denial such as `unsafe_receipt_id`
- unsafe IDs must not be normalized into safe aliases
- unsafe IDs must not reach filesystem paths
- unknown safe IDs must return a bounded `receipt_not_found` or unknown response, not a traceback

### Receipt Store Requirements

Receipt readback requires a configured durable compute receipt store. Missing, in-memory-only, or unsupported receipt stores must return a bounded `receipt_store_unavailable` or `unsupported_operation` response.

The route must not invent global or user-specific paths, hardcode USB paths, or hardcode `D:\Francis` runtime data paths. Focused tests must use temporary data roots. The local JSON receipt store remains local durability only; it does not implement distributed receipt coordination, cross-process locking, retention policy, cleanup policy, backup policy, or production audit durability.

### Bounded Receipt Response

Safe response fields may include:

- `receipt_id`
- `task_id`
- `correlation_id` or `trace_id`
- `worker_id` if already receipt-safe
- `capability` or task-type summary
- `execution_status`
- `approval_required`
- `approval_satisfied`
- safe `approval_id` reference
- `approval_decision`
- `approval_denial_reason`
- `approval_consumed`
- `approval_scope_summary`
- `receipt_persisted`
- resource budget summary with filesystem scope summarized, not raw paths
- `cancellation_requested`
- `cancellation_reason`
- `timed_out`
- `timeout_stage`
- `started_at_ms`
- `finished_at_ms`
- `duration_ms`
- `created_at_ms` or timestamp
- status reference if safe
- schema version or receipt version if present
- bounded warnings or limitations

The response must not include:

- raw task payload
- raw execution output
- secrets
- raw approval notes
- raw model prompts
- broad filesystem paths
- traceback strings
- full exception details
- arbitrary user content beyond bounded receipt-safe summaries
- raw adapter metadata
- raw logs
- a full audit trail beyond the single compute receipt

Receipt readback may show only the bounded approval summary already recorded in the compute receipt. It must not read or expose full approval grant records, reveal raw approval notes, consume approvals, revoke approvals, create approvals, or mutate approvals. The approval store remains separate from the receipt store.

Receipt readback reports bounded execution receipt truth. Status readback reports task status. Status-read scope does not imply receipt-read, and receipt-read scope does not imply status-read unless a future policy explicitly combines them. Receipt readback must not mutate status records and must not claim task recovery, task resume, async execution, or background execution.

Receipt readback may include bounded adapter or request summary only if it is already present in receipt-safe fields. It must not expose raw adapter payloads or raw adapter metadata, must not imply any real adapter exists, and must not give adapters read authority by identity alone. Actor permission remains required.

## Permission And Actor Contract

Every Compute Substrate API route must use `ApiPermissionGate` or the repo-equivalent permission gate before touching the substrate service.

Required rules:

- Actor identity must be present and known to the permission gate.
- Actor scopes must be explicit.
- Submit permission must be separate from status-read permission.
- Status-read permission must not imply submit permission.
- Receipt-read permission must be separate from submit permission.
- Receipt-read permission must be separate from status-read permission.
- Submit permission must not imply receipt-read permission.
- Status-read permission must not imply receipt-read permission.
- Receipt-read permission must not imply submit permission.
- Receipt-read permission must not imply approval authority.
- Receipt-read permission must not imply admin authority.
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

Submit requests are schema-driven and bounded. The request may include:

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
- missing receipt-read scope
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
- malformed receipt id
- unsafe receipt id
- receipt store unavailable
- receipt not found
- receipt store read failed
- receipt schema or version unsupported
- receipt redaction failure
- route not enabled or local-dev only
- unknown task or missing status record

The route should follow existing Francis denial-body style: `status`, `error`, a bounded `governance` object, and explicit false authority flags where relevant, such as no shell, no process start, no memory write, and no execution authority granted by the denial.

Receipt persistence failure, status persistence failure, and backend execution failure must remain separate. A status persistence failure must not make a successful execution look failed, and a backend execution failure must not be hidden behind successful status persistence.

Future receipt readback errors should use bounded stable codes such as `receipt_not_found`, `unsafe_receipt_id`, `receipt_store_unavailable`, `receipt_store_read_failed`, `receipt_redaction_failed`, and `unsupported_operation`. If an error includes a message, it must be bounded and sanitized.

## Store Configuration Contract

Durable stores remain separate:

- Durable compute receipt persistence proves what happened during execution attempts.
- Durable status persistence reports bounded task state and readback.
- Durable approval persistence proves why Francis was allowed to attempt execution.

Production-grade API submission requires a configured durable compute receipt store. Production-grade status readback requires a configured durable status store. Approval-required API submissions require a configured durable approval store before they can be treated as production-grade.

In-memory stores may be acceptable for local development and focused tests only. Responses must report them as non-durable. In-memory status readback must not be described as durable persistence.

Receipt readback requires a configured durable compute receipt store before it is considered usable. Missing or in-memory-only receipt stores must return bounded unavailable or unsupported responses, not fake durable readback. Receipt readback must not hardcode store roots, user profile paths, USB paths, or repository-local runtime data paths; store roots must be configured through the repo's runtime configuration patterns.

Durable adapter persistence is not required for the first API route because adapter contracts remain internal and contract-only.

## Concurrency And Operational Contract

Current local JSON stores provide local persistence only. They do not implement distributed locking, cross-process approval reservation, cross-process status coordination, or multi-process receipt coordination.

The current first API route is local/internal/dev and must remain so until these concerns are addressed:

- cross-process approval reservation
- durable store root configuration policy
- multi-process status and receipt coordination
- runtime data-root backup policy
- retention/cleanup policy for status records
- retention/cleanup policy for compute receipts

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
- no approval-note secrets in receipt readback
- no user directory or USB path leakage
- no arbitrary log content in receipt readback
- response fields must be schema-driven and length-bounded
- errors must use stable bounded codes or summaries

## Future Route Test Contract

Current route and substrate tests prove the following for the first internal/local-dev route. Future route expansion must preserve this coverage or add equivalent focused tests:

- unauthorized actor is denied
- missing scope is denied
- submit scope allows submit but not unrelated operations
- status-read scope allows readback but not submit
- missing `compute:receipt:read` scope is denied for receipt readback
- submit scope does not allow receipt read
- status-read scope does not allow receipt read
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

The `GET /compute-substrate/receipts/{receipt_id}` route requires focused tests proving:

- unauthorized actor is denied
- missing `compute:receipt:read` scope is denied
- submit scope does not allow receipt read
- status-read scope does not allow receipt read
- safe receipt ID read succeeds
- unknown receipt ID returns `receipt_not_found` or unknown
- unsafe receipt IDs are rejected
- path traversal receipt IDs are rejected
- absolute path and Windows drive-prefix receipt IDs are rejected
- receipt store unavailable returns bounded `receipt_store_unavailable`
- receipt store read failure returns bounded `receipt_store_read_failed`
- corrupt/decode receipt files and unsupported receipt schema/version return bounded read-failed or unsupported responses separately from not-found when the configured store exposes that distinction
- receipt redaction failure returns bounded `receipt_redaction_failed`
- response includes `receipt_id`, `task_id`, approval summary, execution status, and `receipt_persisted` truth
- response excludes raw task payload
- response excludes raw execution output
- response excludes approval-note secret
- response excludes model prompt
- response excludes broad filesystem path
- response excludes traceback and full exception details
- receipt read does not trigger execution
- receipt read does not consume approval
- receipt read does not mutate status
- receipt read does not mutate receipt
- receipt read does not persist learning or memory
- existing submit/status API checkpoint remains passing

## Consequences

The first internal/local-dev Compute Substrate API route is implemented under this contract. Future Compute Substrate API expansion remains gated by it.

The first API route is a narrow wrapper over `ComputeSubstrateService`. Substrate internals remain authoritative. Future adapters must not bypass the adapter gateway, service, governor, approval, receipt, and status path. This contract exposes only internal/local-dev submission/status capability and documents a future receipt readback contract. It does not implement receipt readback, create production-grade public exposure, create general audit authority, add async/background execution, add recovery/resume, add real adapters, add durable adapter persistence, add OS-level resource enforcement, add memory persistence, add live-learning persistence, add model training, or add new execution authority.

## Open Questions And Follow-Ups

- Whether future API scope names should align with existing `operations.run` or remain compute-specific.
- Production exposure and configuration posture beyond the current internal/local-dev route.
- Cross-process approval reservation.
- Durable store root configuration policy.
- Status retention and cleanup policy.
- Receipt retention and cleanup policy.
- Whether output-returning routes are allowed or must be separate from submission/status routes.
- Whether receipt readback should support correlation or task lookup, or only `receipt_id`.
- Whether receipt readback can ever expose bounded execution output; this likely requires a separate future policy and route.
- Audit export format if a broader export surface is needed later.
- API rate limiting and local-only binding requirements before any production exposure.
- Capability readback route design.
- OS-level resource enforcement design.
- VM/container backend contract.
- `LiveLearningEvent` persistence governance.
- First real adapter proof after API contract and route hardening.
