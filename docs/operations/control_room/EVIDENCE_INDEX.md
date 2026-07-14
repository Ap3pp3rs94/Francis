# Francis Control Room Evidence Index

Updated: 2026-07-14, sync cycle `CR-20260714-004`

This index points to bounded evidence. Large logs and archives remain outside Git
when appropriate, but their path, hash, applicable commit, and claim must be
recorded here. An index entry does not upgrade unverified evidence.

| Evidence ID | Front | Evidence | Applicable commit | Claim supported | Status |
| --- | --- | --- | --- | --- | --- |
| `EVD-20260714-001` | cross-front | `handoffs/CR-20260714-mixed-tree-transfer.md`; archive `D:\Francis-archives\control-room-activation-20260714-091739` with per-file SHA256 | `8c84dc4e` assignment base | exact dirty-front preservation and transfer provenance | verified by ATLAS; not acceptance evidence |
| `EVD-20260714-002` | all three | `reviews/VERA/CR-20260714-preflight.md`; agent `019f6100-9955-78f0-abda-5abd175b953a` | `8c84dc4e` | independent preflight findings and non-readiness | verified report; no tests run by VERA |
| `EVD-20260714-003` | Control Room baseline | GitHub CodeQL run `29340258957` | `8c84dc4e` | CodeQL completed successfully | verified at last GitHub read |
| `EVD-20260714-004` | Control Room baseline | GitHub CI run `29340258995` | `8c84dc4e` | current CI outcome | Ubuntu 3.12/3.13 passed; Windows 3.12/3.13 pytest pending; no final verdict |
| `EVD-20260714-005` | local baseline | first `scripts/check.ps1` output summarized in `MSG-20260714-007` | `8c84dc4e` | local environment omitted CI `bridge` extra | verified failure; invalid as passing gate |
| `EVD-20260714-006` | CLAUDE historical candidate | `D:\Francis\FRANCIS_SUBSTRATE_INVENTORY.csv` | unknown | possible historical substrate inventory | unverified provenance and applicable head |
| `EVD-20260714-007` | local exact-head gate | `scripts/check.ps1`; direct mypy reproduction; `MSG-20260714-010` | `d5516a54e9b939b2ae076f3be7b338b6cd2ed762` | branch/Ruff/format pass but mypy optional-import failure | verified exit 1 before environment repair |
| `EVD-20260714-008` | local environment | HARBOR review; locked Typer reinstall; import probe | `d5516a54e9b939b2ae076f3be7b338b6cd2ed762` | local Typer metadata/payload drift repaired | import repair verified; later static-pass record is incomplete and not reusable gate evidence |
| `EVD-20260714-009` | clean exact snapshot | short detached worktree `D:\fv`; `VAL-20260714-001` | `d5516a54e9b939b2ae076f3be7b338b6cd2ed762` | exact-source pytest after long-path/editable-source harness invalidation | interrupted for integration priority; no verdict claimed |
| `EVD-20260714-010` | CR-FORGE-001 | commits `90c4dbe0`/`cd9cd504`; exact specialist reviews; `VAL-014`; `CR-DEC-0012` | `cd9cd50422115761a2340e3d322b449516f85b0d` | cycle-one focused evidence and exact path-owner/fingerprint blockers | focused pass; final cycle-two reassignment authorized; not promotion-ready |
| `EVD-20260714-011` | CR-ARGUS-001 | commit `683134a7`; exact specialist reviews; `VAL-009`/`010` | `683134a7cccd6b4dd1b1cd1604d2641615f07307` | focused pass plus teaching/readback scope blockers | parked; no promotion claim |
| `EVD-20260714-012` | CR-LUMEN-001 | commit `60070438`; exact specialist reviews; `VAL-011`/`013` | `600704383d71c072b29a29e4061c86977f38a245` | focused/build pass plus durable sequence/outcome ownership blockers | parked; no promotion or live claim |
| `EVD-20260714-013` | CR-003 integrity | `reviews/ARCHIVIST/CR-20260714-003-precommit.md` | open sync over `d5516a54` | precommit consistency and evidence gaps | changes required; reviewed snapshot must not be committed unchanged |

Future entries must identify the exact tested commit. Pre-rebase worker evidence
cannot support promotion of a different rebased commit.
