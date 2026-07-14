# Francis Control Room Decisions

## CR-DEC-0001 - Named durable seats

- Date: 2026-07-14
- Issue: agent sessions are replaceable and coordination must survive context loss
- Agents involved: ATLAS, FORGE, ARGUS, LUMEN, VERA
- Evidence considered: operator Control Room directive; repository's existing
  task-card and session-brief pattern
- Decision: use durable named seats with repository-backed seat state and
  structured messages
- Affected fronts: all Control Room fronts
- Affected task cards: all active and future cards
- Affected contracts: coordination/provenance only
- ADR required: no; this is an operating protocol, not product architecture
- Operator involvement: explicitly directed by operator

## CR-DEC-0002 - Isolated branch workflow for current mixed tree

- Date: 2026-07-14
- Issue: three independent fronts currently share a dirty `main` worktree
- Agents involved: ATLAS, FORGE, ARGUS, LUMEN, VERA
- Evidence considered: `CONTRIBUTING.md` permits `codex/*` branches for isolated
  review and recovery safety; current index and worktree contain independent
  front-specific diffs
- Decision: preserve each front, create one named branch/worktree per worker, and
  fast-forward only independently reviewed green work back to `main`
- Affected fronts: CR-FORGE-001, CR-ARGUS-001, CR-LUMEN-001
- Affected task cards: all three active cards
- Affected contracts: repository workflow and attribution
- ADR required: no
- Operator involvement: explicitly directed by operator

## CR-DEC-0003 - Live Orb process exclusion

- Date: 2026-07-14
- Issue: visual code is dirty while a canonical Orb process family is live
- Agents involved: ATLAS, LUMEN, VERA
- Evidence considered: active operator constraints; ADR 0008 native runtime
  boundary; Orb task-card do-not-touch list
- Decision: no active front may stop, restart, replace, activate, or modify the
  live Orb/Lens process family or runtime data
- Affected fronts: CR-ARGUS-001, CR-LUMEN-001
- Affected task cards: Lens game observer; Orb visual/choreography
- Affected contracts: native renderer, overlay lifecycle, readback truth
- ADR required: no; preserves accepted ADR 0008
- Operator involvement: prior explicit operator constraint retained

## CR-DEC-0004 - No fabricated Stage 18 production facts

- Date: 2026-07-14
- Issue: safe-delta code can be tested with fixtures, but production has no real
  managed-copy customer request or tenant
- Agents involved: ATLAS, FORGE, VERA
- Evidence considered: completion ledger and production readback posture
- Decision: CR-FORGE-001 may use test-isolated fixtures only; it may not create a
  production request, tenant, approval, export, import, or learning record
- Affected fronts: CR-FORGE-001
- Affected task cards: managed-copy safe delta
- Affected contracts: Stage 18 request/provision/isolation/safe-delta chain
- ADR required: no
- Operator involvement: production facts and approvals remain operator-only

## CR-DEC-0005 - Correct LUMEN front to transferred repo truth

- Date: 2026-07-14
- Issue: the proposed Orb visual/choreography card did not match the transferred
  patch, which implements right-click request queue durability plus a visual-lock
  ring-count correction
- Agents involved: ATLAS, LUMEN, VERA
- Evidence considered: LUMEN KICKOFF, exact five-file diff, ADR 0008 boundaries
- Decision: retain the coherent transferred patch under LUMEN, revise CR-LUMEN-001
  to right-click delivery/visual-lock alignment, and keep canonical state-to-
  choreography mapping as a separate future front
- Affected fronts: CR-LUMEN-001; future choreography front
- Affected task cards: `orb-visual-choreography.md` (revised in place)
- Affected contracts: native right-click request, overlay queue/readback, visual
  lock, native renderer status
- ADR required: no; the decision narrows work to existing contracts
- Operator involvement: no new authority or live-runtime decision required

## CR-DEC-0006 - Version expanded Lens observer contracts

- Date: 2026-07-14
- Issue: transferred producer/consumer code adds mandatory governance fields while
  retaining v1 observation and heartbeat versions
- Agents involved: ATLAS, ARGUS, VERA
- Evidence considered: ARGUS KICKOFF, strict situation-model validators, persisted
  status/readback compatibility requirement, portable loader audit
- Decision: expanded producer contracts require a new version; readers must
  explicitly recognize legacy v1 payloads and handle missing new governance facts
  conservatively rather than silently treating them as the new contract
- Affected fronts: CR-ARGUS-001
- Affected task cards: `lens-game-observer.md`
- Affected contracts: `lens.game.observation`, situation-model heartbeat/readback
- ADR required: no; this is a compatible schema evolution inside existing
  architecture
- Operator involvement: no authority or live-process decision required

## CR-DEC-0007 - Commit local Control Room state and gate every push

- Date: 2026-07-14
- Issue: repository files are not durable organizational memory until committed,
  while publishing is an external action
- Agents involved: OPERATOR, ATLAS
- Evidence considered: operator Control Room addendum; dirty main status
- Decision: every material sync is an exact docs-only local-main commit named
  `ops(control-room): sync CR-YYYYMMDD-NNN`; pushing any ref remains operator-only
- Affected fronts: all
- Affected task cards: all current and future cards
- Affected contracts: operating memory, external/public action boundary
- ADR required: no
- Operator involvement: explicitly directed and retained for every push

## CR-DEC-0008 - Deny live services without a runtime lease

- Date: 2026-07-14
- Issue: worktrees do not isolate data roots, ports, processes, or the live Orb
- Agents involved: OPERATOR, ATLAS, FORGE, ARGUS, LUMEN
- Evidence considered: operator addendum; port and state-root readback at
  2026-07-14T09:37:19-05:00
- Decision: each mutating card receives a unique runtime lease; current cards
  permit tests/compile only and deny all persistent services and real Orb access
- Affected fronts: CR-FORGE-001, CR-ARGUS-001, CR-LUMEN-001
- Affected task cards: all three active cards
- Affected contracts: runtime isolation and protected live paths
- ADR required: no; this is execution containment
- Operator involvement: explicit operating mandate

## CR-DEC-0009 - Durable specialist seats do not imply staffed agents

- Date: 2026-07-14
- Issue: expanded scrutiny requires stable roles without fabricated activity
- Agents involved: OPERATOR, ATLAS
- Evidence considered: addendum role charters and current agent-session inventory
- Decision: add CLAUDE, MERIDIAN, SENTINEL, HARBOR, ARCHIVIST, and ECHO as durable
  seats; mark them unstaffed/unverified until a real session or bridge exists
- Affected fronts: all
- Affected task cards: cards name concrete review questions
- Affected contracts: review provenance and liveness
- ADR required: no
- Operator involvement: explicit role definition

## CR-DEC-0010 - Route VERA preflight findings into worker acceptance

- Date: 2026-07-14
- Issue: VERA found acceptance gaps beyond each worker's first KICKOFF finding
- Agents involved: ATLAS, VERA, FORGE, ARGUS, LUMEN
- Evidence considered: `reviews/VERA/CR-20260714-preflight.md`; transfer handoff
- Decision: keep every front `ACTIVE`, expand only the bounded acceptance contract
  needed for fail-closed receipt/readback, observer identity/versioning, and
  queue/ring truth; no front is review-ready
- Affected fronts: CR-FORGE-001, CR-ARGUS-001, CR-LUMEN-001
- Affected task cards: all three active cards
- Affected contracts: safe-delta readback; observer lineage; queue and visual lock
- ADR required: unverified until MERIDIAN reviews any final architecture impact
- Operator involvement: no gated product action is performed

## CR-DEC-0011 - Bound hardening cycles and local-main documentation drift

- Date: 2026-07-14
- Issue: the protocol had no numeric remediation ceiling or docs-only movement
  budget, allowing defensible hardening and Control Room commits to indefinitely
  delay promotion
- Agents involved: ATLAS; external reviewer challenge; ARCHIVIST evidence audit
- Evidence considered:
  `reviews/ATLAS_EXTERNAL_THROUGHPUT_CHALLENGE_2026-07-14.txt`, three first
  candidate commits, specialist findings, and open CR-003 drift
- Decision: after a first reviewable candidate, permit at most two remediation
  cycles; cycle one handles card-mapped findings and cycle two only regressions
  introduced by cycle one. Split, park, or escalate a third independent issue
  set. Hold at most one open Control Room sync and freeze local-main docs movement
  once a candidate becomes review-ready until it is promoted or rejected.
- Affected fronts: all current and future fronts
- Affected task cards: all current and future cards
- Affected contracts: scope containment, review economics, validation scheduling,
  and exact-head promotion
- ADR required: no; this is an operating constraint
- Operator involvement: no gated product/authority action; push and stage closure
  remain operator-only
