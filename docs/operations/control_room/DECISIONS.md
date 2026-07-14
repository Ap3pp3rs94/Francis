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
