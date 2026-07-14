# VERA Preflight Review - CR-20260714

Review source: VERA agent `019f6100-9955-78f0-abda-5abd175b953a`

Reviewed base: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`

Disposition: all three fronts remain `ACTIVE`; none is review-ready.

## FORGE

- Malformed JSON may be converted to an empty object and overwritten.
- A different full fingerprint sharing the 16-character filename prefix may be
  reported as `already_reviewed`.
- GET readback may expose an unvalidated latest object.
- Missing evidence: collision, malformed file, post-write drift, long path, and
  exclusive-create behavior.

## ARGUS

- The portable `getattr(ctypes, "WinDLL", None)` pattern is preserved.
- Expanded mandatory observation and heartbeat fields still use version 1.
- The situation validator does not yet validate all target, process, model,
  scene, classification, and teaching lineage before acceptance.
- The environment override can accept an arbitrary absolute model path.

## LUMEN

- The queue has no bound, TTL, backlog readback, or duplicate suppression.
- Ordering is based on canonical-first plus filesystem time/name rather than a
  durable numeric sequence.
- Existing tests cover only a two-request happy path.
- Renderer, overlay, and visual-lock documentation say eight main rings while
  `src/francis/lens/host_manifest.py` still publishes fifteen.

## Validation Performed By VERA

- Read repository governance, ledger, brief, protocol, cards, decisions, ADR
  0008, and commit `adcb62a2`.
- Verified branch/worktree identity, status, upstream, diff, and ancestry.
- `git diff --check` passed on each transferred tracked patch.
- No pytest, Ruff, mypy, native build, GitHub query, or live-runtime check ran.
- No file, ref, process, runtime state, or receipt was mutated.

ATLAS transcription note: the transfer archive and hashes existed outside the
repository but were not visible to VERA. They are now registered in
`control_room/handoffs/CR-20260714-mixed-tree-transfer.md`; this corrects the
provenance gap without changing VERA's acceptance findings.
