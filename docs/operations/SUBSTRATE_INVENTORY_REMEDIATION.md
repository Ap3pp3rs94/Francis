# Francis Substrate Inventory Remediation

Reviewed: 2026-07-13

Source: `C:\Users\Ap3pp\Downloads\Francis Substrate Inventory - Sheet1.csv`

Source SHA-256: `F2013C4A8EAB8D715FE0E0644740399031FFC7E22D914A04B8215B7AFAC5814C`

This document records dispositions for all 61 inventory rows. It is an
operations review, not shipped-capability evidence. Current capability posture
remains governed by `docs/operations/COMPLETION_LEDGER.md`, with target-state
direction in `docs/canonical/ROADMAP.md` and plane posture in
`docs/canonical/BUILD_MANIFEST.md`.

## Decisions

- `schemas/` remains the canonical schema root. The untracked `contracts/`
  root is not adopted.
- `FRANCIS_DATA_DIR`, resolved through `francis.kernel.paths.data_dir()`, and
  the repository `data/` layout remain the canonical general runtime-state
  contract. The untracked PowerShell batch may not introduce `.francis/` as a
  parallel receipt, HUD, or agent-state authority.
- The existing `scripts/bootstrap.ps1` remains canonical. The inert
  `scripts/bootstrap.ps1.francis-new` replacement is not adopted.
- Lack of imports is not sufficient evidence to delete roadmap-aligned source.
  Dormant packages remain unshipped and non-authoritative until a dedicated
  package review proves retain, integrate, archive, or remove.
- Tested but unmounted React panels are retained as unshipped operator-surface
  candidates. Mounting them requires a separate shell information-architecture
  slice and live UI proof; their tests alone do not make them user-visible.
- Manual operator scripts are not considered dead solely because no code calls
  them. Governance-sensitive scripts require individual contract and safety
  review before removal or promotion.

## Disposition Matrix

Status meanings:

- `resolved`: the reported concern is fixed or disproven by current repo truth.
- `retain`: the surface is canonical or intentionally retained.
- `quarantine`: untracked parallel work must not be merged or wired as-is.
- `deferred`: a bounded follow-up is required before changing the surface.
- `in_progress`: another active, protected lane owns the remaining change.

| ID | Surface | Disposition | Evidence or required action |
|---:|---|---|---|
| 01 | `francis.config.json` | quarantine | No tracked consumer; references the rejected parallel `.francis/receipts` lane. |
| 02 | `contracts/receipt.schema.json` | quarantine | `schemas/` is the referenced and policy-declared contract root. |
| 03 | `pyproject.toml` | retain | Existing dependency and extras contract remains canonical. |
| 04 | `schemas/` | retain | Canonical schema root; consumers reference `schemas/*.schema.json`. |
| 05 | `Francis.PowerShell.psm1` | quarantine | Parallel control plane uses noncanonical state and contains the roadmap-path defect. |
| 06 | `Francis.PowerShell.psd1` | quarantine | Belongs to row 05; wildcard exports require narrowing before any adoption. |
| 07 | `scripts/audit.ps1` | quarantine | Thin wrapper depends on the quarantined module. |
| 08 | `scripts/validate.ps1` | quarantine | Duplicates the canonical `scripts/check.ps1` lane through row 05. |
| 09 | `scripts/bootstrap.ps1.francis-new` | quarantine | Inert replacement would regress the canonical bootstrap and change state roots. |
| 10 | `scripts/bootstrap.ps1` | retain | Canonical environment and runtime bootstrap remains wired. |
| 11 | `src/francis/creativity/` | deferred | No live imports found; retain as unshipped pending roadmap-aware package review. |
| 12 | `src/francis/cross_domain/` | deferred | No live imports found; cross-domain coherence remains roadmap-aligned target state. |
| 13 | `src/francis/temporal/` | deferred | No live imports found; retain as unshipped pending package review. |
| 14 | `src/francis/symbiosis/` | deferred | No live imports found; retain as unshipped pending package review. |
| 15 | `src/francis/system_intelligence/` | deferred | No live imports found; retain as unshipped pending package review. |
| 16 | `src/francis/metalearn/` | deferred | No live imports found; retain as unshipped pending package review. |
| 17 | `src/francis/domain_intelligence/` | deferred | Live domain routes use another path; migration or removal needs contract comparison. |
| 18 | reflection, self-model, writing, internet leaf modules | deferred | No live imports found; review each package boundary before removal. |
| 19 | `src/francis/adversarial/` | retain | Four modules are wired through `adversarial_hardening`; audit the remainder separately. |
| 20 | `src/francis/collective/` | retain | Swarm classes are wired through `francis.swarm`; audit other modules separately. |
| 21 | four placeholder API routes | resolved | Digital twin, resilience, and evolution report `not_implemented`; simulation reports `partial` for its governed virtual-workfield contract and denies execution readiness. |
| 22 | `src/francis/api/app.py` | retain | Router registration is valid; truthful readiness belongs to each route. |
| 23 | wired Python runtime core | retain | No broad rewrite or deletion authorized by this inventory. |
| 24 | `main.tsx` and `App.tsx` | retain | Current operator shell entrypoints. |
| 25 | unmounted feature panels | deferred | Retain unshipped; integrate through a dedicated user-facing shell and visual validation slice. |
| 26 | live shell, Lens, voice, chat, settings | retain | Current user-facing UI path. |
| 27 | native Orb and build output | resolved | Orb work remains protected; `**/build/` is already ignored. |
| 28 | repository tools | deferred | Verify restore and quarantine tooling through their own contract tests before consolidation. |
| 29 | README, agent rules, workflows | retain | Canonical repository and CI control surfaces. |
| 30 | PowerShell roadmap-path defect | quarantine | Defect is contained in row 05; do not fix or promote that parallel lane in isolation. |
| 31 | canonical and operational docs | retain | Ledger and canonical docs retain their authority order. |
| 32 | topic docs for dormant subsystems | deferred | Treat as target-state design, not shipped evidence; add a standard posture banner before wider publication. |
| 33 | topic docs for live subsystems | retain | Still subordinate to ledger truth. |
| 34 | tests and Python cache output | resolved | Tests remain canonical; `__pycache__/` is already ignored. |
| 35 | `data/` | retain | Canonical general runtime-state root, overridable with `FRANCIS_DATA_DIR`. |
| 36 | `apps/unreal_presence/` | retain | Grounded-presence adapter is roadmap-aligned and wired. |
| 37 | generated chat UI plugin | resolved | `apps/**/plugins/generated/**` is already ignored as runtime output. |
| 38 | `scripts/watch-francis.ps1` | quarantine | Depends on row 05; do not add a second watcher lane as-is. |
| 39 | `scripts/francis-agent.ps1` | quarantine | Duplicates resident Lens/observer concerns and writes parallel `.francis` receipts. |
| 40 | `scripts/francis-health-server.ps1` | quarantine | Duplicates API and Lens health surfaces through an untracked HTTP listener. |
| 41 | `scripts/set-francis-secret.ps1` | quarantine | Do not create a second credential authority without a credential-vault contract review. |
| 42 | `scripts/register-francis-agent-task.ps1` | quarantine | Scheduled residency must use the governed resident-host lane and receipts. |
| 43 | `Francis.PowerShell.Tests.ps1` | quarantine | Tests the rejected lane and writes non-isolated receipts. |
| 44 | `scripts/check.ps1` | retain | Canonical repository validation gate. |
| 45 | `scripts/doctor.ps1` | retain | Canonical health entrypoint through `francis.ps1`. |
| 46 | `scripts/watch-francis-live.ps1` | deferred | Retain current observer; portability of the user-specific root needs a bounded follow-up. |
| 47 | `scripts/francis.ps1` | retain | Canonical CLI wrapper. |
| 48 | `scripts/dev.ps1` | retain | Canonical local development launcher. |
| 49 | `scripts/assert-runtime-root.ps1` | retain | Canonical mirror-checkout guard. |
| 50 | `scripts/check-branch-state.ps1` | retain | Canonical branch-state gate. |
| 51 | `requirements/` | retain | Keep; dependency-sync verification remains part of normal validation. |
| 52 | `scripts/lens-host.ps1` | retain | Protected resident-host control surface. |
| 53 | `scripts/lens-overlay-window.ps1` | in_progress | Protected concurrent Orb/voice work; untouched by this review. |
| 54 | Lens core scripts | retain | Governed Lens execution lane. |
| 55 | Lens proof scripts | deferred | Retain until Stage 6 evidence dependencies permit safe consolidation. |
| 56 | Stage 16 federation scripts | retain | Historical proof and closure lane; no deletion from this audit. |
| 57 | FR-017 scripts | retain | Physical-evidence test lane remains intentional. |
| 58 | `scripts/francis-completion-model.ps1` | in_progress | Protected concurrent completion-model work; untouched by this review. |
| 59 | manual/orphan script set | deferred | Review each CLI contract; prioritize governance-sensitive reset and overnight scripts. |
| 60 | documentation-only script set | deferred | Retain as operator commands; add focused tests before promotion or removal. |
| 61 | wired single-purpose scripts | retain | Existing consumers justify retention. |

## Validation Gates

Before a `deferred` source package can be removed:

1. prove tracked and dynamic consumers are absent;
2. map the package to roadmap and manifest commitments;
3. identify schema, receipt, data, and documentation dependencies;
4. run focused tests after the proposed deletion;
5. run `scripts/check.ps1`; and
6. update the completion ledger only if a documented gate materially changes.

Before a quarantined PowerShell surface can be adopted, it must use the
canonical data and receipt contracts, avoid parallel health and residency
authority, isolate test writes, expose bounded exports, and pass a direct
governance review.
