# HARBOR Review: FORGE Integration Lock Retry

- Review date: 2026-07-14
- Candidate: `cdfc4a23fe030b4e31dbf3b067c39d3e3daae1f8`
- Parent: `246580901b145a7f1f59d9c85d199ffdfdf536d8`
- Scope: `tests/test_lens_host_supervisor_script.py`
- Disposition: `PASS`

## Concrete Question

Does retrying `OSError` and `json.JSONDecodeError` while polling supervisor status
handle transient Windows file replacement/locks without masking persistent
failure, weakening assertions, or creating Ubuntu portability risk?

## Evidence

- The retry remains bounded by the existing eight-second deadline; persistent
  read, decode, stale-heartbeat, or supervisor failures still raise.
- Success still requires `resident_supervising`, a changed `updated_at`, and an
  increased `heartbeat_count`, followed by PID, liveness, lease-mode,
  supervision-start, and timestamp consistency assertions.
- The exception types and `Path.read_text()` are portable. The live lifecycle
  test remains explicitly Windows-only.
- The production PowerShell writer uses atomic replacement with bounded retries,
  so a transient read race is a plausible Windows test-harness condition.
- Exact Windows lifecycle test passed. Changed-file Ruff and format checks passed.

No correction or additional specialist review is required for this delta.
