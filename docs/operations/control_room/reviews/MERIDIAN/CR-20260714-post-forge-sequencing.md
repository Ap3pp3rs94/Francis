# MERIDIAN Review: Post-FORGE Sequencing

- Review date: 2026-07-14
- ARGUS candidate: `683134a7cccd6b4dd1b1cd1604d2641615f07307`
- LUMEN candidate: `600704383d71c072b29a29e4061c86977f38a245`
- Disposition: unpark ARGUS after FORGE promotion; keep LUMEN parked

## Concrete Question

Which parked front offers the highest-value smallest executable roadmap-aligned
slice without live Orb access, new authority, or invented Stage 18 facts?

## Decision Evidence

ARGUS requires a bounded extension into the existing game-apprenticeship teaching
consumer compatibility boundary: explicit v1/v2 handling, direct observer-to-
recorder composition tests, conservative legacy-heartbeat projection, and stale
or rotated receipt-lineage behavior. Likely additional scope is limited to
`src/francis/apprenticeship_game_teaching.py` and its direct unit/composition
tests. API scope is not justified unless direct composition proves it necessary.

LUMEN remains parked because restart-safe global sequence allocation and producer
failure readback require a new durable cross-process allocator/outcome contract
across C++, PowerShell, persistence, and runtime status. That is materially larger
and touches protected Orb/shell truth surfaces without native or live proof.

ARGUS must remain read-only, local-only, foreground-bound, no-input, no-launch,
and no-new-authority. Promotion would be cross-stage hardening, not Stage 18 or
production managed-copy evidence.

No tests or runtime processes were started. Both existing branch ranges passed
read-only `git diff --check`; FORGE promotion remains a prerequisite.
