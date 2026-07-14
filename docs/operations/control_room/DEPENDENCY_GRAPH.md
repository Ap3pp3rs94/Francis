# Francis Control Room Dependency Graph

Updated: 2026-07-14T10:24:54-05:00

## Critical Path

The ledger's first Stage 18 production gate is a real operator-supplied managed-
copy request. That external fact is unavailable and Francis must not invent it.
`CR-FORGE-001` is therefore the highest-priority executable internal engineering
path, not evidence that the production gate closed. `CR-ARGUS-001` and
`CR-LUMEN-001` are approved cross-stage hardening fronts with disjoint write
sets; they do not block FORGE integration.

Integration order is FORGE first after remediation and exact-head review, then
ARGUS and LUMEN in the order their independently rebased heads become green.
Every promotion remains local-only until the operator authorizes a push.

## Front Graph

| Front | Objective / priority | Exact worker commit | Dependencies | Downstream consumers | Unresolved contracts | Validation | Required review | Operator gates | Next executable action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CR-FORGE-001` | Stage 18 hash-only safe-delta candidate review; highest executable internal priority, not the first production gate | `90c4dbe0287c1f169cefad47debab85067dd4fd8` | provision receipt, live structural isolation, tenant safe-delta policy, actor scope | Stage 18 approval/export work after separate authority | exact schema/projection; recomputed semantics; ID/time/file/tenant lineage; per-lineage latest/invalidity; invalid-enum redaction; canonical nested path confinement; receipt-path claim | `VAL-002` interrupted known remediation; `VAL-006` diff-check pass | MERIDIAN and SENTINEL findings complete; HARBOR, VERA, ARCHIVIST after new hash | tenancy/authority weakening, production data/action, promotion uncertainty, push | FORGE executes remediation cycle one; report scope blocker before shared path-owner edits |
| `CR-ARGUS-001` | game-observer readback truth; cheapest first-promotion path | `2e454ba5bc4a9e5f629da463be5696350703fcb2` | frame/receipt identity, foreground process, model boundary, situation-model reader | Lens situation model and later semantic observer use | blocked-state identity and teaching status/IDs/timestamps/counts/text/blockers/review semantics are insufficiently validated before projection | `VAL-003` interrupted known remediation; `VAL-007` diff-check pass | concrete affected reviewers only after new hash | authority or live-observer activation, uncertain promotion, push | ARGUS executes remediation cycle one and is first in the integration queue |
| `CR-LUMEN-001` | loss-resistant native right-click delivery and ring truth; cross-stage hardening | `a1b2c60bced10506cfd53bdfb97aa8b491656cea` | native request producer, overlay queue, visual-lock parity | operator-facing Orb local UI; no broader choreography claim | non-replacing publication; one-publication-per-gesture; bounded discovery bytes/count; strict 32-attempt drain and truthful deferred backlog | `VAL-004` interrupted known remediation; `VAL-008` diff-check pass; ring count statically aligned | HARBOR finding complete; affected reviewers only after new hash | live Orb use, shell/authority change, uncertain promotion, push | LUMEN executes bounded remediation cycle one and compile-checks only |

## Shared Integration Dependencies

- Current local `main`: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`.
- Open Control Room sync `CR-20260714-003` will move local `main`; each worker
  must rebase onto its exact committed head before promotion validation.
- Exact rebased acceptance and `scripts/check.ps1` evidence supersede all
  pre-rebase results.
- GitHub CI `29340258995` applies only to remote `8c84dc4e`, not local Control
  Room or worker commits.
- Unknown `src/francis/cli.py` work is excluded from every front and cannot enter
  an integration candidate without a new owner/card.
