# Francis Control Room Evidence Index

Updated: 2026-07-14, sync cycle `CR-20260714-002`

This index points to bounded evidence. Large logs and archives remain outside Git
when appropriate, but their path, hash, applicable commit, and claim must be
recorded here. An index entry does not upgrade unverified evidence.

| Evidence ID | Front | Evidence | Applicable commit | Claim supported | Status |
| --- | --- | --- | --- | --- | --- |
| `EVD-20260714-001` | cross-front | `handoffs/CR-20260714-mixed-tree-transfer.md`; archive `D:\Francis-archives\control-room-activation-20260714-091739` with per-file SHA256 | `8c84dc4e` assignment base | exact dirty-front preservation and transfer provenance | verified by ATLAS; not acceptance evidence |
| `EVD-20260714-002` | all three | `reviews/VERA/CR-20260714-preflight.md`; agent `019f6100-9955-78f0-abda-5abd175b953a` | `8c84dc4e` | independent preflight findings and non-readiness | verified report; no tests run by VERA |
| `EVD-20260714-003` | Control Room baseline | GitHub CodeQL run `29340258957` | `8c84dc4e` | CodeQL completed successfully | verified at last GitHub read |
| `EVD-20260714-004` | Control Room baseline | GitHub CI run `29340258995` | `8c84dc4e` | current CI outcome | pending at last read; no verdict claimed |
| `EVD-20260714-005` | local baseline | first `scripts/check.ps1` output summarized in `MSG-20260714-007` | `8c84dc4e` | local environment omitted CI `bridge` extra | verified failure; invalid as passing gate |
| `EVD-20260714-006` | CLAUDE historical candidate | `D:\Francis\FRANCIS_SUBSTRATE_INVENTORY.csv` | unknown | possible historical substrate inventory | unverified provenance and applicable head |

Future entries must identify the exact tested commit. Pre-rebase worker evidence
cannot support promotion of a different rebased commit.
