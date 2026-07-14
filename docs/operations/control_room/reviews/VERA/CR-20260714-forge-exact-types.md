# VERA FORGE Exact-Type Review

Date: 2026-07-14
Parent: `1ca30a048f07111861c07e59a8a6afc9b9b606df`
Candidate: `246580901b145a7f1f59d9c85d199ffdfdf536d8`

Disposition: `PASS`.

The regression is discriminating for the original acceptance failure: it proves
the baseline receipt valid, deep-copies otherwise-valid structure, mutates one
nested Boolean at a time to equal-valued integer `0`/`1`, preserves exact
keys/candidate structure, recomputes the outer receipt fingerprint, and requires
fail-closed readback. Reverting to equality-only validation would make the test
fail.

Worker evidence on the exact candidate: focused regression exit `0`, 1 passed;
three-file card suite exit `0`, 57 passed; changed-path Ruff, format, mypy, and
diff-check all exit `0`. VERA independently ran exact-range diff-check with
exit `0`; no pytest or runtime action ran in review. Full `scripts/check.ps1`
remains ATLAS-owned promotion evidence.
