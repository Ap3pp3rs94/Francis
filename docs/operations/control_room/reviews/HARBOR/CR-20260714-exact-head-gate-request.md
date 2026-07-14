# HARBOR Review Request - Exact-Head Local Gate

Request ID: `REVIEW-HARBOR-20260714-001`

Requested by: ATLAS

Assigned session: `019f6119-b5ef-7721-91c1-5c628ce3ec61`

Applicable local head: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`

Mode: read-only. No file, environment, process, runtime, or ref mutation.

## Concrete Questions

1. Why does local mypy 1.19.1 report `src/francis/cli.py:10: Name
   "typer" already defined on line 8 [no-redef]` after the exact CI-extra sync,
   while all four Mypy jobs passed in GitHub run `29340258995` on unchanged source?
2. Is the root cause environment drift, environment-sensitive source, or both?
3. What is the smallest bounded remediation and exact validation path?
4. Will the same failure block every active worker's full gate?
5. What is the current CI verdict for `8c84dc4e`?

## Files And Evidence In Scope

- `src/francis/cli.py`
- `pyproject.toml`, `uv.lock`, mypy configuration
- `scripts/check.ps1`
- `.github/workflows/ci.yml`
- read-only installed-distribution/version inspection
- GitHub Actions run `29340258995`

## Do Not Touch

- source, tests, lockfiles, environment packages, refs, processes, runtime data,
  live Orb/Lens, worker worktrees, or unknown untracked files

## Acceptance

Return a structured `REVIEW_RESULT` with exact commands/facts, root-cause class,
smallest recommended correction, portability impact, worker impact, CI status,
and any operator gate. Do not claim a branch is promotion-ready.
