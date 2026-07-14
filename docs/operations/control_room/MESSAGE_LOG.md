# Francis Control Room Message Index

Updated: 2026-07-14

Material messages live in bounded monthly/front shards. This file is an index,
not an append-only transcript. Closed shards are immutable; corrections are new
messages that reference the original ID.

Roll a shard when it reaches 128 KiB or 250 material messages, whichever occurs
first. Read only the active shard for the affected front plus `cross-front.md`
and `verification.md` unless an index entry points elsewhere.

## Active Shards

| Shard | First ID | Last ID | Purpose |
| --- | --- | --- | --- |
| `messages/2026-07/atlas-operator.md` | `MSG-20260714-001` | `MSG-20260714-009` | operator mandates and ATLAS operating decisions |
| `messages/2026-07/cross-front.md` | `MSG-20260714-003` | `MSG-20260714-003` | front creation and shared dependencies |
| `messages/2026-07/managed-copies-safe-delta.md` | `MSG-20260714-004` | `MSG-20260714-004` | FORGE front |
| `messages/2026-07/game-observer.md` | `MSG-20260714-005` | `MSG-20260714-005` | ARGUS front |
| `messages/2026-07/orb-choreography.md` | `MSG-20260714-006` | `MSG-20260714-006` | LUMEN front |
| `messages/2026-07/verification.md` | `MSG-20260714-007` | `MSG-20260714-008` | validation and independent review |

## Unresolved Messages

- `MSG-20260714-004`: FORGE receipt collision/malformed/readback behavior.
- `MSG-20260714-005`: ARGUS versioned legacy handling and identity lineage.
- `MSG-20260714-006`: LUMEN bounded ordering, deduplication, staleness, and ring
  truth alignment.
- `MSG-20260714-007`: exact-head local full gate and bootstrap/CI extra drift.
- `MSG-20260714-008`: no worker branch is review-ready.

## Current Cross-Front Questions

- No worker-to-worker contract question is unanswered. VERA findings are routed
  to the owning seats through their task cards.
- Promotion order is unresolved until exact worker commits and review evidence
  exist; no branch may depend on pre-rebase validation.

## Archive

No shard is closed yet. Closed shards move under `messages/archive/` and remain
immutable.
