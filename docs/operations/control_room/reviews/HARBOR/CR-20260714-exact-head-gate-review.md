# HARBOR Review - Exact-Head Local Gate

Review ID: `REVIEW-HARBOR-20260714-001`

Review source: HARBOR agent `019f6119-b5ef-7721-91c1-5c628ce3ec61`

Applicable local head: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`

Disposition: review complete; source branches remain below promotion readiness.

## Root Cause

- Both local and CI select `mypy==1.19.1` and `typer==0.21.2`.
- Local Typer metadata and `typer.exe` existed, but all 17 recorded
  `typer/*.py` files were missing; `find_spec("typer")` returned `None`.
- The locked wheel hash matched `uv.lock` and contained all 17 modules. Fresh CI
  environments therefore resolve Typer and all four remote Mypy jobs passed.
- Immediate failure class: local package integrity drift, not version drift.
- Secondary source class: `src/francis/cli.py` deliberately supports missing
  Typer, but its declaration/import form is mypy-sensitive when Typer is absent.

## Worker Impact

All three worker worktrees junction `.venv` to `D:\Francis\.venv`. HARBOR
reproduced the same `cli.py:10 [no-redef]` failure in each before repair. The
environment repair therefore had to be coordinated and performed only after no
worker-owned test/type process was observed.

## Evidence

- Local RECORD: 25 rows, 17 missing Typer modules.
- Locked wheel: 56,728 bytes, matching locked SHA256, 17 modules present.
- Normal frozen sync and `uv pip check` did not detect missing payload files.
- `uv sync --dry-run --reinstall-package typer ...` selected only Typer.
- GitHub run `29340258995`: all four Mypy jobs passed; Pytest still in progress
  at review completion; tested head `8c84dc4e`.

## Recommendation

1. Reinstall the locked Typer package and verify importability.
2. Validate the exact committed head from a clean worktree.
3. Preserve the concurrent three-line `src/francis/cli.py` candidate and review
   it separately with present/absent-Typer regression coverage.

HARBOR changed no file, package, ref, process, or runtime state. ATLAS performed
the approved package repair after the review and records that evidence separately.
