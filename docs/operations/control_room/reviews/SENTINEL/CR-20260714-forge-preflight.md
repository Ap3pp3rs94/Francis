# SENTINEL Review: CR-FORGE-001 Preflight

Review ID: `REVIEW-SENTINEL-20260714-001`

- Reviewer seat: SENTINEL
- Agent session: `019f612d-46f2-78b1-bb84-2942081c86c1`
- Front: `CR-FORGE-001`
- Task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Candidate: `90c4dbe0287c1f169cefad47debab85067dd4fd8`
- Base: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`
- Review mode: read-only static preflight
- Recommendation: `REMEDIATION_REQUIRED`

## Findings

### SENTINEL-001 - Receipt envelope and lineage are not fully bound

`_valid_review_receipt` validates selected fields but not an exact top-level or
governance schema. It accepts any prefixed receipt ID and any positive timestamp.
Readback then returns the complete stored object. An otherwise valid receipt can
therefore carry unknown raw fields, alter latest ordering, use an unbound receipt
ID, or be transplanted beneath another tenant directory without rejection.

Required remediation:

- exact-schema validate or strictly project the receipt and governance envelope;
- bind receipt ID, filename prefix, and containing tenant key to the validated
  fingerprint and live provision lineage;
- prevent untrusted timestamps from controlling truthful latest selection;
- add direct raw-marker, ID, timestamp, filename, and tenant-transplant tests.

### SENTINEL-002 - Invalid enum values can be echoed

Blocked `signal_class` and `direction` values are converted to text and returned.
This contradicts the route's no-raw-signal-echo claim. Unknown values must be
represented by a bounded enum status or redacted placeholder, with marker tests.

### SENTINEL-003 - Nested receipt-directory confinement is unproven

The writer creates `receipts/sd` and exclusively creates the final file, but the
existing structural-isolation proof covers the parent `receipts` domain rather
than the new child. A Windows junction or symlink substitution below the verified
parent is not currently rejected. The final path needs a proven in-root,
non-reparse boundary or equivalent repository-approved confinement check.

This is an escalation-sensitive tenancy boundary. SENTINEL does not approve a
weakened path check or acceptance with this unresolved.

## Static Passes

- The POST route retains `managed_copies.safe_delta.write` scope enforcement.
- Complete fingerprints are compared before idempotent reuse.
- Final-file `open("x")` prevents overwriting an existing final file.
- No approval, export, import, learning, execution, or mutation authority was
  found in the changed call chain.
- `git diff --check d5516a54...90c4dbe` exited `0`.

## Validation Limits

SENTINEL did not run pytest, Ruff, mypy, or a live runtime. Worker acceptance and
the exact rebased full gate remain required. This review proves non-readiness; it
does not certify the candidate after remediation.
