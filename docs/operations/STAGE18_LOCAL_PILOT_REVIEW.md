# Stage 18 Local Pilot Review

The authorization object is
`docs/operations/STAGE18_LOCAL_PILOT_AUTHORIZATION_PACKAGE.json`. It is a
proposal with no authority effect. It deliberately remains non-executable until
its listed operator decisions and implementation blockers are resolved.

## Canonical target

The package targets only the Stage 18 `copy_creation_contract` check and its
`copy_creation_runtime_proof` evidence requirement. It cannot advance the other
seven checks for the reasons embedded in the package. The current completion
audit remains 1 of 8.

## Missing implementation

1. The runtime-start producer is fixed to
   `stage18_fixed_fixture_runtime_v1`, labels every receipt
   `fixture_software_only`, and exposes the production runtime identity as
   inactive. A separate fixed non-fixture local-pilot producer is required; the
   existing fixture must not be relabelled.
2. The Docker backend is fixed to a BusyBox fixture script and creates its own
   proof-owned tenant inputs. It does not launch an operating managed-copy
   artifact against the provisioned tenant boundary. The pilot runtime artifact,
   image/config fingerprint, fixed command, and exact provisioned mounts must be
   implemented and approval-bound.
3. `copy_creation_runtime_proof` currently verifies the process-start receipt.
   The Docker ready/heartbeat/cleanup chain is not a canonical source for that
   recorder. A verifier must correlate provision, structural isolation,
   runtime-start approval, container-isolation approval, image/container
   identity, current heartbeat, and non-fixture evidence class under lock.
4. Actor scopes are currently configuration grants, not a native single-run,
   expiring, revocable lease. The pilot package requires that enforcement rather
   than a persistent scope grant.
5. Existing cleanup authority is fixture-only. A pilot-only bounded stop path
   must revalidate exact container ownership and preserve tenant state. General
   production stop, replacement, decommission, and rogue containment remain out
   of scope.

Until these five items exist, authorizing or executing the package would not
truthfully produce canonical non-fixture evidence.

## Isolation-module structural review

`src/francis/managed_copy_container_isolation.py` is large, but line count alone
does not justify a refactor. Its current orchestration is cohesive and validated.
Three real contract boundaries are visible:

1. **Contract and approval binding:** constants, payload typing, proposal,
   descriptor construction, approval validation, and immutable identity fields.
2. **Docker backend:** fixed command construction, Docker preflight, image and
   engine identity, inspect normalization, mount checks, and exact cleanup.
3. **Evidence:** security-profile diagnostics, heartbeat validation, receipt
   schemas, immutable writes, and redacted failure projection.

A split is recommended only when the non-fixture pilot backend is implemented,
because adding a second runtime class to the existing fixture orchestration risks
mixing evidence classes. Keep
`managed_copy_container_isolation.py` as the public orchestrator and extract:

- `managed_copy_container_contract.py` for typed descriptors and approvals;
- `managed_copy_docker_backend.py` for fixed Docker operations and normalized
  observations;
- `managed_copy_container_evidence.py` for diagnostics and receipt validation.

Do not move code until characterization tests pin the current public contract,
generic blocker names, cleanup ordering, and immutable receipt shapes. No split
is needed merely to reduce the file length.

## Review boundary

This package does not create a tenant, grant a scope, request or decide an
approval, start Docker, start a container, touch VSC-1, access the live Orb, or
record runtime evidence. The next action is operator review of the exact package,
not execution.
