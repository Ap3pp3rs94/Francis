==============================================================================

FRANCIS — CREDENTIAL_DELEGATION.md

Delegations: scoped authority grants bound to credentials, enforced at runtime

==============================================================================



Purpose

-------

This document defines FRANCIS's credential delegation system:

   - What a delegation is (and is not)

   - How delegations bind *authority* to *credentials* safely

   - How delegations reference scopes and policy rules

   - How delegations are created, signed, validated, cached, logged, and revoked

   - How delegation interacts with approvals + trust + sandbox constraints

   - How to avoid confused-deputy, replay, and privilege-escalation failure modes



Read alongside:

   - docs/API_PERMISSIONS.md

   - docs/POLICIES.md

   - docs/TRUST_MODEL.md

   - docs/THREAT_MODEL.md

   - docs/COLLABORATIVE_INTELLIGENCE.md

   - docs/CONCURRENCY.md

   - config/policies/api_permissions.yaml

   - config/policies/approvals.yaml

   - config/policies/credential_usage.yaml

   - config/policies/trust_boundaries.yaml

   - config/policies/sandbox.yaml

   - data/credentials/delegations/_template.delegation.yaml

   - data/credentials/scopes/_template.scopes.yaml

   - data/credentials/vault.db

   - src/francis/credentials/delegation.py

   - src/francis/credentials/scope_checker.py

   - src/francis/credentials/expiration_manager.py

   - src/francis/credentials/usage_logger.py

   - src/francis/credentials/vault.py

   - src/francis/governance/api_permission_gate.py

   - scripts/credential-delegate.ps1



Design stance:

   - Default deny: no delegation → no credential-backed tool access.

   - Least privilege: scopes are narrow; delegations are narrower.

   - Explicit elevation: high-impact operations require approvals and/or trust.

   - Auditability: every delegation creation/validation/use is logged.

   - Revocability: delegations must be invalidatable quickly (no “forever tokens”).



==============================================================================





## 0. Executive summary



A **delegation** is a *signed, time-bounded, scope-bounded authority grant* that

permits a subject identity (human session, service, worker, or federated peer)

to use certain credential-backed tools and operations against specified

resources under explicit constraints.



Delegations are **not secrets**. They are authorizations. Secrets live in the

credential vault. Delegations *reference* credentials and scopes, and runtime

enforcement ensures a credential can only be used when an applicable delegation

(and all policy gates) allow it.



The runtime must enforce:

- identity resolution,

- delegation signature validation,

- scope checks,

- policy checks,

- approvals (if required),

- trust thresholds,

- sandbox constraints,

- logging and redaction.



If any of those fail: **deny, explain safely, and audit**.





## 1. Definitions



### 1.1 Credential

A **credential** is a secret used to authenticate to an external system:

API tokens, OAuth refresh tokens, private keys, DB passwords, etc.



Credentials are stored in:

- `data/credentials/vault.db`



Credentials are never written to:

- logs,

- summaries,

- artifacts,

- prompts,

- delegation files.



### 1.2 Scope

A **scope** is a structured policy object describing what operations and

resources are permitted (and under what constraints).



Scopes live as templates in:

- `data/credentials/scopes/_template.scopes.yaml`



At runtime, scopes are instantiated and referenced by delegations and/or

identity baselines.



### 1.3 Delegation

A **delegation** is an authorization envelope that binds:

- **issuer** (who grants),

- **subject** (who receives),

- **scope set** (what is allowed),

- **constraints** (limits),

- **expiration** (when it stops),

- **context** (why/where it applies),

- and a **signature** (integrity + authenticity).



Delegations live in:

- `data/credentials/delegations/`



Template shape:

- `data/credentials/delegations/_template.delegation.yaml`



### 1.4 Issuer / Subject / Audience

- **Issuer**: identity that creates the delegation (human operator, governance service).

- **Subject**: identity that uses the delegation (worker, daemon, user session, federated peer).

- **Audience**: the runtime(s) that may accept this delegation (prevents token reuse elsewhere).



### 1.5 Authority vs trust

- **Delegation** answers: “Is this identity allowed to attempt this action with these credentials?”

- **Trust** answers: “Should the system execute this now, given uncertainty and risk?”



Both must pass. Delegation alone is not execution permission.



### 1.6 Confused deputy

A **confused deputy** occurs when a privileged component is tricked into using

its authority on behalf of an untrusted requester.



Delegations must prevent:

- untrusted text from causing privileged tool use,

- scope broadening via indirect calls,

- replay across contexts or environments.





## 2. Delegation principles (non-negotiable)



1) **Default deny**

   - If no valid delegation exists for a credential-backed operation, deny.



2) **Least privilege by construction**

   - Delegations must narrow scope templates, never broaden them.

   - Add constraints; do not remove constraints.



3) **Short TTL by default**

   - Delegations should expire quickly (minutes/hours), not days.

   - Long-lived delegations must be exceptional and require approvals.



4) **Audience binding**

   - Delegations are only valid for specific runtime identifiers and environments.



5) **Revocation is real**

   - Delegations must be invalidatable even before expiry.



6) **Every use is audited**

   - Tool execution must record which delegation authorized the credential use.



7) **No delegation implies no secret access**

   - The vault must refuse credential materialization without a valid delegation context.





## 3. Delegation lifecycle



### 3.1 Create

A delegation is created only by an allowed issuer:

- human operator (explicit action),

- governance service (policy-driven),

- emergency workflow (break-glass).



Creation should:

- compute a stable `delegation_id`,

- attach a justification and policy references,

- bind to the subject identity,

- reference scope IDs,

- set TTL and constraints,

- sign the delegation envelope.



### 3.2 Distribute / store

Delegations are distributed as non-secret artifacts:

- written to `data/credentials/delegations/` (or delivered to the subject via secure channel),

- cached by runtime (short-lived cache only),

- optionally replicated to federated peers only if allowed by policy.



### 3.3 Validate (runtime)

Before any credential-backed tool call, runtime must:

- resolve identity and environment,

- locate candidate delegations,

- validate signatures and integrity,

- validate issuer allowlist,

- validate time bounds (nbf/exp),

- validate audience binding,

- validate scope references exist and are allowed,

- validate constraints and resource targeting,

- validate approvals and trust thresholds if required,

- log decision.



### 3.4 Use (tool execution)

Tool execution must receive:

- resolved delegation id(s),

- effective scope set,

- constraint object,

- redaction policy,

- correlation id for logs.



### 3.5 Revoke / expire

Delegations become invalid if:

- expired (time),

- revoked (explicit),

- issuer key rotated/invalidated,

- environment changes violate audience binding,

- trust boundary policy changes require re-approval.



### 3.6 Archive

Expired/revoked delegations may be moved to an archive location and retained per

data governance policy. Retention must not include secrets.





## 4. Delegation data model



### 4.1 File format

Delegations are stored as YAML (human-inspectable) but validated against a

canonical, signature-checked representation.



Recommended approach:

- store in YAML,

- canonicalize to JSON for signing and verification (stable key ordering),

- attach signature metadata.



### 4.2 Required fields (recommended contract)



- `delegation_version`: schema version (e.g., `1`)

- `delegation_id`: stable id (hash or UUID)

- `issuer`:

  - `issuer_id`

  - `issuer_type` (human|service|federated)

  - `issuer_key_id` (KID)

- `subject`:

  - `subject_id`

  - `subject_type` (user_session|daemon|worker|federated_peer)

- `audience`:

  - `runtime_ids` (allowlist)

  - `environment_profiles` (dev|production|regulated|airgapped|etc.)

- `time_bounds`:

  - `issued_at`

  - `not_before` (optional)

  - `expires_at`

- `scope_refs`:

  - list of scope identifiers (and optional inline narrowing constraints)

- `credential_refs`:

  - list of credential ids in the vault this delegation may activate

  - optional mapping from credential → allowed tool/provider

- `constraints`:

  - rate limits, max rows/results, file path allowlists, domain allowlists, etc.

- `requires_approvals` (optional):

  - list of approval types or specific approval ids

- `trust_requirements` (optional):

  - minimum trust level, allowed trust mode, “dry-run required” flags

- `purpose`:

  - human-readable description

  - ticket/incident reference (optional)

- `policy_refs`:

  - which policies/rulesets govern this delegation

- `signature`:

  - algorithm

  - signature value (base64)

  - signed digest of canonical payload



### 4.3 Example delegation (illustrative)



```yaml

delegation_version: 1

delegation_id: del_2f7f3b0f7a0a4a1b



issuer:

  issuer_id: operator:austin

  issuer_type: human

  issuer_key_id: kid_ed25519_operator_austin_01



subject:

  subject_id: worker:domain_induction

  subject_type: worker



audience:

  runtime_ids:

    - runtime:francis-local-01

  environment_profiles:

    - dev

    - workstation



time_bounds:

  issued_at: "2026-01-01T00:00:00Z"

  not_before: "2026-01-01T00:00:00Z"

  expires_at: "2026-01-01T02:00:00Z"



scope_refs:

  - scope_id: github_repo_readonly

    narrow:

      resources:

        github:

          orgs: ["YourOrg"]

          repos: ["Francis"]

      constraints:

        rate_limit:

          per_minute: 30



credential_refs:

  - credential_id: cred_github_pat_01

    provider: github

    tools: ["github"]

    methods: ["read"]



constraints:

  max_payload_bytes: 200000

  max_results: 200

  network:

    allowed_domains: ["api.github.com"]

  redaction:

    deny_fields: ["Authorization", "token", "cookie"]



requires_approvals: []

trust_requirements:

  min_trust_level: "standard"

  allow_writes: false

  dry_run_required: false



purpose:

  summary: "Read-only GitHub access for domain induction."

  reference: "ticket:FR-102"



policy_refs:

  - config/policies/api_permissions.yaml

  - config/policies/credential_usage.yaml

  - config/policies/trust_boundaries.yaml



signature:

  algorithm: "ed25519"

  signed_payload_digest: "sha256:9b2c...f1a0"

  value_b64: "MEUCIQDv...<snip>...=="



