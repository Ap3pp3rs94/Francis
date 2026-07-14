# MERIDIAN Review: CR-FORGE-001 Preflight

Review ID: `REVIEW-MERIDIAN-20260714-001`

- Reviewer seat: MERIDIAN
- Agent session: `019f613f-ae1a-7643-ba3d-b3793cc79233`
- Candidate: `90c4dbe0287c1f169cefad47debab85067dd4fd8`
- Base: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`
- Mode: read-only architecture and contract review
- Disposition: `REMEDIATION_REQUIRED`
- ADR verdict: no ADR for narrow remediation within existing isolation ownership;
  an ADR and operator gate are required for a new filesystem trust assumption,
  ACL authority, or handle-level Windows security design

## Findings

1. Readback globally selects one latest receipt across tenants and lets one
   malformed tenant invalidate the complete set. Status then compares that
   global result with one active provision. Latest selection and invalidity must
   be lineage scoped.
2. Persisted candidate `ready` checks are accepted as authority instead of being
   recomputed from persisted candidate values.
3. Safe-delta independently derives tenant paths and policy while structural
   isolation already owns containment and link checks. The remediation must reuse
   an isolation-owned guard; a task-card scope revision is required before
   changing `managed_copy_isolation.py` or adding a shared path module.
4. Blocked readback advertises `logs/managed_copies/safe_delta_reviews.jsonl`
   while the implementation writes tenant-local `receipts/sd/*.json` files.

## Required Remediation

- Validate exact envelope/candidate/governance/check keys and JSON types.
- Recompute candidate checks and return a known-safe projection.
- Bind ID, filename, tenant directory, timestamp, review fingerprint, provision,
  and isolation lineage.
- Select latest deterministically per lineage and isolate invalidity per tenant.
- Reuse the existing structural-isolation path boundary rather than creating a
  competing path contract.
- Correct the old JSONL path claim and its test.

## Evidence And Limits

- Worktree was clean at the exact candidate; parent/base relationship verified.
- All five changed files plus provision/isolation contracts, Stage 18 roadmap,
  ADR inventory, task card, and SENTINEL review were inspected.
- `git diff --check d5516a54..90c4dbe` exited `0`.
- No pytest, Ruff, mypy, runtime, or junction test was run by MERIDIAN.

This review proves non-readiness only. It does not certify a remediated candidate
or any production/runtime effect.
