# FRANCIS - COMPLETION_LEDGER

Shipped-state ledger for the current repository posture, hardening progress, and
productization gaps.

This file is intentionally narrower than `docs/canonical/ROADMAP.md`. The roadmap
defines the target state. This ledger records what is materially true in the repo,
using direct inspection plus validation that was actually run.

## 1. Document contract

Use this file for:

- current build posture
- high-confidence validated surfaces
- known gaps that still block a truthful "finished" claim
- the latest targeted validation evidence
- the first continuity/orientation source for recurring build automations

Do not use this file for:

- aspirational future capabilities
- unverified completion claims
- UI/demo descriptions that outrun server truth
- casual rewrites of canonical roadmap direction

Automation rule:

- recurring build automations should read this ledger first before re-reading the
  full canonical roadmap set
- canonical roadmap docs should be re-read when this ledger is missing, stale,
  contradicted by repo truth, or when milestone/workstream closure is being
  evaluated
- update this ledger at the end of a run when a validated surface materially
  changed, a major blocker was removed, or the strongest truthful build posture
  changed
- update `docs/canonical/BUILD_MANIFEST.md` or other canonical roadmap docs only
  when their own update contracts are actually met
- completion percentages are evidence claims, not progress decoration. They must
  be tied to a known baseline, validated repo evidence, and explicit remaining
  blockers; prompt-only, admin-only, diagnosis-only, or documentation-only turns
  must not move overall Francis or current build-phase percentages unless they
  close a documented governance/readiness gate with validation evidence.

## 2. Current build phase

Francis is in `Phase 2` per `docs/canonical/BUILD_MANIFEST.md`.

The strongest current posture is still the governed runtime spine, not the finished
operator product surface:

- `P9_OBSERVABILITY`: strongest plane today
- `P3_GOVERNANCE`: materially real
- `P1_INTERFACE`: partial
- `P7_EXECUTION`: partial
- `P8_MEMORY`: partial

Current active workstream: Managed Copies Platform / Stage 18 groundwork.
Stage 17 / Capability Economy is ledger-closed by governed receipt
`stage17_capability_economy_closure_afd0fa32f7d1`, recorded at code head
`cf8d1fb1745f0c3f51850c82cd79ddb214c4644b` after all six canonical software
criteria read ready.
The current goal is continued Stage 18 runtime-evidence closure. A governed
synthetic local managed-copy lifecycle now executes the real Francis
`tenant_work_briefing` runtime in a constrained Docker container and supplies the
canonical copy-creation receipt, advancing the completion audit to 2 of 8. No
persistent actor holds the temporary proof scopes, and no production tenant or
customer startup receipt exists. Production copy creation and incident
determination still require
real operator-supplied tenant, policy, runtime, and incident facts; those facts
are not inferred or fabricated.

Stage 6 Lens MVP is ledger-closed against its five canonical acceptance criteria,
and Stages 7 through 16 retain their existing receipt-backed closures.

Older phase-history prose was moved to
`docs/operations/archive/COMPLETION_LEDGER_STATIC_HISTORY_2026-07-03.md` so the
main ledger stays under bounded readback limits without deleting evidence.

## 3. High-confidence current slice

Recent committed checkpoint before the active Orb-presence slice:
`60d21916 docs(operations): compact completion ledger readback`.

What is materially true now:

- Francis summon config uses `Ctrl+Alt+F`, avoiding the known local Claude
  Desktop `Ctrl+Alt+Space` collision on this machine.
- `scripts/lens-hotkey-binding.ps1` records `hotkey_already_owned` as a visible
  blocked runtime receipt when Win32 `RegisterHotKey` fails.
- PowerShell status, Python preflight/readiness, and OS-binding execution
  preserve that blocker and point to `choose_unclaimed_global_hotkey`.
- Stage 6 summon authority was enabled through delegated operator approval, and
  the canonical `Ctrl+Alt+F` hotkey now produces correlated summon and Orb-control
  receipts without physical input or user-cursor takeover.
- The live Lens overlay can run as a virtual-screen coordinate plane including
  the taskbar, with the Orb moving inside that plane instead of being confined
  to a small window.
- The Orb click box remains bounded to the Orb core while the visual may extend
  outside that click box; hit testing passes through outside the Orb core.
- Ctrl+M one-shot Orb placement is bounded to overlay-owned position mutation
  and travels over render frames instead of snapping to the clicked point.
- The right-click Orb panel is small, receipted, and bounded to feature toggles
  plus chat/voice handoff metadata; it does not grant desktop execution.
- Continuous no-wake voice chat is not free-running; it is gated to Ctrl+V
  push-to-talk readback.
- The Orb desktop bridge now has a redacted post-action target observer. When
  the bridge is explicitly enabled and a safe target's observable UI state
  changes after posted messages, `desktop_effect_confirmed` can become true.
- `scripts/ollama-doctor.ps1` now completes as a bounded health receipt instead
  of hanging or throwing on local CLI/Event Log/process readback quirks.
- The live Francis1/Ollama status replay now produces readable output through a
  same-provider readability repair when the primary local model returns
  unreadable output; the forced-garbage path still rewrites to
  `unreadable_rewritten` without leaking raw salad.
- The one-visible-loop proof now consumes hash-bound browser screenshots and a
  DOM snapshot of the live Chat and Lens surfaces, then confirms a governed
  disposable-target effect without physical input or user-cursor takeover.
- The canonical Orb runtime identity readback exposes the locked ring/color
  contract from `docs/operations/ORB_VISUAL_LOCK.md`, one native renderer, and
  aligned ElevenLabs input/output/readiness fields; live readback clears both
  ring/color and voice-provider identity drift.
- A dedicated Unreal Engine 5.8 Grounded Presence project now renders a
  Core-authored, receipt-linked projection over authenticated local named pipes.
  Its reverse path is request-only and default-deny; it grants no execution,
  desktop, network, memory-write, or approval authority.

## 4. Latest validation evidence

> Older dated entries are archived under docs/operations/archive/ (see scripts/archive-completion-ledger.ps1).
> Historical undated ledger body is archived under docs/operations/archive/COMPLETION_LEDGER_STATIC_HISTORY_2026-07-03.md.

### 2026-07-24 - Stage 18 copy-creation runtime proof accepted

Current posture: Stage 18 remains open and now reads 2 of 8. The governed
copy-creation path used a temporary actor scope and exact one-run lease to start
the real Francis `tenant_work_briefing` runtime in a constrained local Docker
container. It independently verified useful output, wrote immutable ready,
cleanup, lifecycle, and canonical runtime-evidence receipts, consumed the lease,
denied replay, and removed the exact proof-owned container.

Evidence:

- Execution base `3755f14979a36ae267978a9b2a7ba4adcf04d793` had terminal-success
  CI run `30106315056` and CodeQL run `30106315070`.
- Proof run `mciso-20260724t180103z-final2` selected `pilot-001` from the
  synthetic tenant input and produced ready receipt
  `mcir_ready_60ba7c6034c1435f97d2019b`, lifecycle receipt
  `mclc_f20cb2f14421298a2df09781`, and canonical runtime-evidence receipt
  `mcre_343b8d15387ff7acb8bd135e`.
- The canonical evidence receipt binds source fingerprint
  `28eed77d59d45ea3ca809a82714570c26ebc260fd1fb124516484857c85a07ea`
  and record fingerprint
  `343b8d15387ff7acb8bd135e6055917c33257893003d93eacb96552e44cf2d39`.
- The exact pilot lease reached `consumed`; replay returned
  `api_permission_denied`. Cleanup removed the exact container, post-removal
  inspection failed as required, and zero Francis proof containers remained.
- Durable readback without a process-scoped proof-root override validates the
  server-resolved lifecycle source, clears the copy-creation blocker, reports
  2 of 8, and names
  `stage18_tenant_isolation_runtime_source_receipt_missing` as the next gap.
- The complete managed-copy container-isolation unit suite passed with the
  separately authorized real-proof test skipped. Ruff, formatting, targeted
  mypy, and scoped diff checks passed.

Boundaries:

- The proof used synthetic local tenant data and temporary process-local
  authority. It created no persistent actor grant, production tenant, customer
  fact, external network action, Orb/VSC-1 interaction, or production evidence.
- The result closes only `copy_creation_runtime_proof`. It does not prove
  production tenant isolation, clear FR-018, close Stage 18, or satisfy any of
  the six remaining Stage 18 runtime gates.

### 2026-07-17 - Real Francis runtime composed with governed Docker lifecycle

Current posture: Phase 2 and Stage 18 remain open. The fixed Docker lifecycle
now composes the non-fixture Francis managed-copy runtime instead of the BusyBox
fixture. The governed path binds a process-local pilot lease, separate exact
runtime-start and container-isolation approvals, provisioned and structurally
verified tenant lineage, fixed image and runtime fingerprints, constrained
mounts, container identity, runtime handshake and heartbeat, the bounded
`tenant_work_briefing` operation, independently recomputed output, and exact
container cleanup.

Evidence:

- Focused lifecycle tests exercise the complete adapter through a fixed fake
  Docker transport and verify the generated security profile, image identity,
  mount set, useful operation, output fingerprint, PID correlation, failure
  cleanup, and exact removal behavior.
- Permission and mutation-authority tests prove an exact pilot-lease binding is
  consumed before payload processing or filesystem and Docker effects.
- Changed-path Ruff, formatting, mypy, and diff checks pass.

Remaining truthful gap:

- Classification is `INTEGRATED CAPABILITY`, not `PROVEN CAPABILITY`. No real
  Docker image was built and no container was launched in this slice; fake
  transport tests prove composition logic, not Docker runtime behavior.
- No persistent actor grant, live invocation, production evidence, or canonical
  runtime evidence was recorded. The completion audit remains 1 of 8 and Stage
  18, FR-018, production, customer, and physical-validation claims remain
  prohibited.

### 2026-07-17 - Non-fixture managed-copy local process vertical

Current posture: Phase 2 and Stage 18 remain open. Francis now has an internal
non-fixture managed-copy process path that is distinct from the BusyBox and
heartbeat-only fixtures. An exact process-local pilot lease and approval bind a
real provisioned and structurally verified copy to one fixed Francis program.
That program reads bounded tenant-local synthetic work items, produces an
actionable priority briefing, emits identity-correlated handshake, heartbeat,
operation, startup, and cleanup receipts, and is stopped by an exact second
lease binding.

Evidence:

- The existing end-to-end managed-copy creation journey now provisions and
  structurally verifies the tenant before starting the fixed Francis subprocess.
- The subprocess completes the tenant briefing, the controller independently
  verifies process creation identity, lineage, heartbeat, input/output hashes,
  and the operation receipt, and the operator route reads the true result.
- Governed stop revalidates the exact PID and creation token, seals the pilot
  lease, records cleanup, and leaves no managed-copy runtime process alive.
- Focused runtime, permission-gate, fixture-start compatibility, mutation-route,
  and complete managed-copy API tests pass with changed-path static checks.

Remaining truthful gap:

- Classification is `INTERNAL COMPONENT with an isolated test-only vertical`.
  No persistent actor grant or real operator pilot lease exists, so this is not
  yet an operator-available product capability.
- The local host process is not Docker-isolated. Its operation performs no
  network activity by implementation, but OS-level network and filesystem
  isolation are not claimed. The proven Docker adapter still targets the
  BusyBox fixture rather than this Francis runtime.
- No canonical runtime evidence was recorded and the completion audit remains
  1 of 8. Stage 18, FR-018, production, customer, and physical-validation claims
  remain prohibited.

### 2026-07-17 - Canonical rogue-recovery runtime verifier contract

Current posture: Phase 2 and Stage 18 remain open. The runtime-evidence
recorder now recognizes `rogue_recovery_runtime_proof` and independently
revalidates the owned provisioning, live structural-isolation, latest integrity
drift, governed rogue-assessment, containment disposition, and deterministic
recovery-plan lineage before it could accept a canonical recovery source.

Evidence:

- Focused verifier, runtime-evidence recorder, completion-projection, and full
  managed-copy API contract tests pass.
- Exact-schema validation rejects fixture, weaker, malformed, injected,
  hash-mismatched, self-consistent synthetic, and stale owned-lineage sources.
- Changed-path Ruff, format, targeted mypy, and repository diff checks pass.

Remaining truthful gap:

- Francis has no governed exact-runtime-halt receipt producer. After all
  existing read-only lineage validates, the verifier therefore fails closed at
  `stage18_rogue_recovery_runtime_halt_receipt_not_implemented` before trusting
  quarantine, evidence preservation, replacement, verification, or continuity
  restoration claims.
- No actor scope or approval was created, no runtime action occurred, and no
  canonical runtime evidence was recorded. The completion audit remains 1 of 8;
  Stage 18 closure, FR-018 clearance, production action, and physical-validation
  claims remain prohibited.

### 2026-07-17 - Current-evidence rogue-recovery plan preflight

Current posture: Phase 2 and Stage 18 remain open. The governed
`/managed-copies/rogue-recovery-review` route now produces a deterministic,
read-only recovery plan only when the scoped actor supplies exact current owned
lineage, the latest integrity evidence still matches live drift, and the latest
linked triage disposition is `containment_authorization_required`.

Evidence:

- Focused planner, rogue-recovery, integrity, permission-gate, managed-copy API,
  and mutation-authority matrix tests pass.
- Static malformed or injected payloads fail before owned lineage reads. Stale,
  substituted, duplicate, cross-evidence, and non-containment inputs fail
  closed; changed-path Ruff, format, targeted mypy, and diff checks pass.
- Independent authority/security and acceptance reviews found no blocking
  issues in the exact affected delta.

Remaining truthful gap:

- The plan is operator-review preparation only. It does not declare the copy
  rogue, open or resolve an incident, halt or quarantine a runtime, preserve
  evidence, replace a copy, restore continuity, write a recovery receipt, or
  grant execution or mutation authority.
- The first executable boundary is a separately governed exact runtime-halt
  action and operator approval. No such authority or approval was created.
- No tenant, runtime, Docker, Orb, VSC-1, or production state changed. The
  completion audit remains 1 of 8; Stage 18 closure, FR-018 clearance, and
  physical-validation claims remain prohibited.

### 2026-07-16 - Safe-delta runtime-evidence verifier software

Current posture: Phase 2 and Stage 18 remain open. The Stage 18 runtime-evidence
recorder now recognizes `safe_delta_runtime_proof` and independently revalidates
the existing provision, structural-isolation, safe-delta review, safe-delta
approval, and export-authorization receipt chain before it could accept a
canonical safe-delta runtime source.

Evidence:

- Focused verifier, runtime-evidence recorder, completion-review, managed-copy
  API, permission-gate, and mutating-route authority tests pass.
- Exact-schema validation rejects fixture, malformed, injected, hash-mismatched,
  and self-asserted source lineage; changed-path Ruff, format, targeted mypy, and
  repository diff checks pass.

Remaining truthful gap:

- Francis has no governed safe-delta export-artifact executor or independently
  owned immutable export-artifact receipt producer. After all existing lineage
  validates, the verifier therefore fails closed at
  `stage18_safe_delta_runtime_export_artifact_receipt_not_implemented`.
- No actor scope or approval was created, no export ran, no tenant or runtime
  state changed, and no canonical runtime evidence was recorded. The completion
  audit remains 1 of 8; Stage 18 closure, FR-018 clearance, production action,
  and physical-validation claims remain prohibited.

### 2026-07-16 - Canonical tenant-isolation runtime verifier contract

Current posture: Phase 2 and Stage 18 remain open. The runtime-evidence recorder
now recognizes the exact `tenant_isolation_runtime_proof` /
`tenant_isolation_runtime_receipt` pair and delegates it to a dedicated,
read-only canonical source verifier. The verifier requires an exact non-fixture
source and current-state schema, independently reloads the owned provisioning
and live-aligned structural-isolation lineage, and requires bounded proof links
for runtime identity, container security, tenant data, memory, receipts,
connectors, policy, support authority, and cross-tenant denial.

Evidence:

- Focused verifier and runtime-evidence tests prove missing, malformed,
  self-asserted, fixture, stale, weaker, cross-kind, and linked-proof-tampered
  evidence fails closed without creating runtime state.
- The managed-copy completion and API contract suites retain eight exact proof
  slots while reporting two recorder-supported requirements.
- The production verifier rejects a self-consistent synthetic receipt bundle
  because its named provisioning lineage is not present in the owning store.
- Changed-path Ruff, format, targeted mypy, and repository diff checks pass.

Remaining truthful gap:

- No canonical non-fixture managed-copy runtime producer exists. The current
  runtime-start producer remains fixture-only, and live pilot approval/lease
  correlation is not implemented; the verifier therefore cannot return
  production readiness from current repository artifacts.
- No actor grant, lease activation, tenant, Docker invocation, managed-copy
  runtime, canonical evidence, Orb, or VSC-1 action occurred.
- The completion audit remains 1 of 8. This verifier contract does not close the
  tenant-isolation gate, authorize the local pilot, clear FR-018, or close Stage
  18.

### 2026-07-16 - Process-local managed-copy pilot scope leases

Current posture: Phase 2 and Stage 18 remain open. Francis now has a native,
opt-in `ApiPermissionGate` extension for one process-local pilot lease bound to
an exact actor, package and fingerprint, pilot run, runtime nonce, operator
decision fingerprint, ordered scope/route/method/action bindings, and a maximum
30-minute lifetime. Binding consumption, revocation, and final sealing are
serialized under one process lock; a restarted process begins with no leases and
therefore cannot silently rehydrate prior authority.

Evidence:

- Focused lease and existing permission-gate tests pass, including issuance and
  expiry boundaries, revocation, exact-binding mismatches, ordered consumption,
  replay, concurrency, wildcard/static-scope interaction, restart loss, and
  redacted denial evidence.
- The complete managed-copy API suite and managed-copy fixture runtime/container
  unit suites pass without activating lease mode.
- Changed-path Ruff, format, targeted mypy, and repository diff checks pass.
- Independent authority/security and acceptance reviews passed after exact
  action correlation, ordering, issuance-boundary, and maximum-duration findings
  were remediated.

Remaining truthful gap:

- No managed-copy route enables lease mode, no lease registry is populated by
  production configuration, and no persistent or process-scoped actor grant was
  created. The local pilot package remains a proposal without approval IDs.
- No tenant, managed copy, Docker container, runtime, canonical evidence, Orb, or
  VSC-1 state was accessed or changed by this slice.
- The completion audit remains 1 of 8. No Stage 18 closure, pilot authorization,
  FR-018 clearance, or physical-validation claim is made.

### 2026-07-16 - Fixed-image Docker managed-copy isolation fixture

Current posture: Phase 2 and Stage 18 remain open. Francis now has a dedicated
`managed_copies.container_isolation.execute` authority contract for one fixed,
digest-pinned BusyBox fixture container on Docker Desktop's WSL2 Linux engine.
The launch is bound to separate runtime-start and container-isolation approvals,
fixed mounts and command fingerprints, a non-root identity, no network, a
read-only root filesystem, dropped capabilities, no-new-privileges, bounded
resources, exact container identity, heartbeat, and cleanup receipts.

Evidence:

- Real fixture proof `mciso-verify-20260716t173418z` passed against the frozen
  linux/amd64 image digest and produced hash-bound ready and cleanup receipts.
- The proof demonstrated bounded tenant-A fixture access and tenant-B mount
  denial, then removed the exact proof container. A post-run exact-container
  inspect confirmed absence; the pre-existing VSC-1 container identities,
  running/health states, mount fingerprints, and configuration fingerprints
  remained unchanged.
- Focused container-isolation, complete managed-copy API/runtime evidence/runtime
  start/completion-review tests, changed-path Ruff, format, targeted mypy, and
  repository diff checks pass.
- Independent authority review passed the fixed security profile and bounded
  diagnostic receipt. Independent acceptance review accepted the fixture proof,
  receipt lineage, and cleanup evidence.

Remaining truthful gap:

- This is isolated fixture evidence only. No persistent actor received either
  authority scope, no production tenant or managed copy was created, and no live
  or production runtime evidence was recorded.
- The bounded tenant-B mount denial is not comprehensive production tenant
  isolation. The completion audit remains 1 of 8, and no Stage 18 closure,
  FR-018 clearance, or physical-validation claim is made.
- The next meaningful milestone requires an explicitly authorized operator-owned
  local pilot managed copy and canonical non-fixture runtime evidence.

### 2026-07-16 - Stage 18 completion audit consumes canonical runtime evidence

Current posture: Phase 2 and Stage 18 remain open. Each Stage 18 completion
check now derives runtime readiness from its exact canonical runtime-evidence
slot rather than static contract flags. The projection requires one unique slot,
`passed` and `receipt_ready`, an ASCII-safe receipt ID, the expected proof kind,
and the expected source-contract route. Stage 17 additionally remains correlated
to the current canonical closure receipt.

Evidence:

- Focused completion-projection, runtime-evidence, managed-copy API, and mounted-
  route contract tests pass.
- Malformed, missing, duplicate, misrouted, wrong-kind, unattributed, Unicode,
  non-string, and overlength receipt projections fail closed.
- Changed-path Ruff, format, targeted mypy, and repository diff checks pass.
- Independent affected-delta review passed after the malformed-projection
  findings were remediated.

Remaining truthful gap:

- The audit remains 1 of 8. This wiring makes future canonical runtime evidence
  consumable but does not create a production receipt or move any runtime gate.
- No persistent actor grant, live invocation, production evidence, Stage 18
  closure, FR-018 clearance, or physical validation occurred.
- The next software prerequisite is a canonical tenant-isolation runtime verifier;
  structural directory isolation and a cooperative fixture process are not
  sufficient customer-isolation evidence.

### 2026-07-15 - Governed managed-copy fixture runtime startup

Current posture: Phase 2 and Stage 18 remain open. Francis now has a dedicated
`managed_copies.runtime_start.execute` authority contract for one fixed,
repository-owned fixture runtime. A separate exact-action approval binds the
provision and isolation lineage, executable and argument fingerprints, bounded
environment and roots, runtime identity, endpoint, timeout, lease, nonce, and
trace before a no-shell launch.

Evidence:

- Focused runtime lifecycle, runtime-evidence integration, complete managed-copy
  API, route-contract, and mutation-authority tests pass in isolated data roots.
- Changed-path Ruff, format, targeted mypy, and repository diff checks pass.
- Fixture startup requires an identity-correlated handshake and current heartbeat;
  PID alone is not accepted. Exact cleanup revalidates process ownership and
  leaves no live fixture process.
- The runtime-evidence verifier independently loads the canonical startup receipt
  and current state. Fixture evidence remains `fixture_software_only` and cannot
  satisfy production runtime readiness.

Remaining truthful gap:

- No persistent actor received the startup scope, no live managed-copy runtime
  was started, and no production runtime evidence was recorded.
- The completion audit remains 1 of 8; fixture tests did not make a runtime
  requirement ready and did not create a Stage 18 closure claim.
- Automatic restart, resident supervision, production stop authority, containment,
  replacement, recovery, and decommission remain separate unimplemented
  authority boundaries.

### 2026-07-15 - Stage 18 runtime-evidence recorder software

Current posture: Phase 2 and Stage 18 remain open. The existing
`managed_copies.runtime_evidence.write` scope now guards an exact-schema,
immutable recorder for `copy_creation_runtime_proof`. The recorder independently
requires canonical source lineage, revalidates it under a cross-process write
lock, rejects conflicting replay and tampering, and persists no caller-supplied
evidence narrative.

Evidence:

- Focused recorder, complete managed-copy API, and mutation-authority tests pass.
- Changed-path Ruff, format, targeted mypy, and repository diff checks pass.
- Independent VERA acceptance review passed the immutable receipt, replay,
  tamper, completion-audit, and no-side-effect contract.
- Fixture-backed writes are labeled `fixture_software_only` and never satisfy
  runtime readiness.

Remaining truthful gap:

- No production startup receipt currently proves an operating managed copy.
  Production recording therefore fails closed with
  `stage18_copy_creation_runtime_startup_receipt_missing`.
- No persistent actor received the write scope, no live route invocation
  occurred, and no production runtime evidence was recorded.
- The runtime-evidence completion audit remains 1 of 8; tests did not make a
  runtime requirement ready and did not create a Stage 18 closure claim.

### 2026-07-15 - Isolated Lens runtime identity contract

- Lens overlay and tray runners now accept one bounded `RuntimeIdentity`, inherit
  the same validated value from `FRANCIS_RUNTIME_IDENTITY`, project visibly
  distinct window/tray labels, and preserve the existing operator labels when
  no identity is supplied.
- PowerShell and Python readbacks bind readiness to the expected isolated
  identity. A differently labeled runtime is reported as missing or mismatched
  rather than being accepted as the canonical proof-owned component.
- Canonical Orb identity readback distinguishes the default
  `francis.operator_orb` from a scoped `francis.proof_orb.<identity>` without
  granting process, desktop, input, or mutation authority.
- This closes the product-level namespacing mechanism required to retry CPJ-001
  D-02. It does not itself claim a successful resident proof stack or completed
  Category Proof Journey; those claims remain gated by terminal CI and isolated
  runtime evidence.
- PowerShell parser checks passed for `scripts/lens-overlay-window.ps1` and
  `scripts/lens-tray-presence.ps1`.
- Focused pytest validation passed 37 tests across the runtime-identity unit,
  overlay runner, tray runner, and host-manifest readback surfaces.

### 2026-07-15 - Stage 18 rogue-signal assessment promoted locally

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes a permission-gated, exact-schema assessment that can record one
immutable, redacted rogue-signal evidence receipt for a structurally verified
fixture copy. It does not declare the copy rogue or perform containment,
recovery, execution, network, or tenant-state mutation.

Evidence:

- Exact rebased candidate and promoted main head `224c9859` passed 7 focused
  rogue-assessment tests, the complete managed-copy card suite, changed-path
  Ruff and format checks, targeted mypy, and diff-check.
- SENTINEL and VERA passed the final affected delta after readback distinguished
  absent evidence from existing-but-drifted lineage without exposing or
  accepting invalid receipt content.
- Existing receipts are exact-schema validated, hash-bound, and checked against
  fresh tenant, provision, and structural-isolation lineage before projection.
- No live service, Orb process, production tenant, incident determination,
  containment action, recovery action, or authority grant occurred.

Remaining truthful gap:

- Real rogue determination and any containment/recovery action remain blocked on
  real operator facts, governed authority, and production evidence.
- Select the next executable Stage 18 prerequisite without extending a fixture
  preparation chain or fabricating production facts.
- Stage 18 closure, FR-018 clearance, and physical validation remain unclaimed.

### 2026-07-15 - Stage 18 export-artifact plan promoted locally

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes a permission-gated, exact-schema, deterministic no-write artifact plan
bound to one exact live-valid approved authorization decision. It grants no
export authority and performs no artifact, manifest, payload, receipt, network,
or tenant-state write.

Evidence:

- Exact candidate `2673cd5e` passed 3 focused artifact-plan tests, the complete
  94-test managed-copy card suite, changed-path Ruff, format, targeted mypy, and
  diff-check.
- SENTINEL, VERA, and HARBOR passed the final affected delta after exact built-in
  integer validation rejected Boolean, float, and string artifact counts.
- Post-promotion checks passed 3 focused artifact-plan tests and 4 route/mutation
  contract tests plus changed-path Ruff, format, and diff-check. No local full
  suite was run; exact-head GitHub CI is the broad repository gate.
- No live service, Orb process, production decision, artifact, network operation,
  or tenant mutation occurred.

Remaining truthful gap:

- Actual artifact materialization and export remain blocked on real operator
  facts and approval. Select the next executable roadmap prerequisite without
  fabricating those facts or extending the no-write preparation chain.
- Stage 18 closure, FR-018 clearance, and physical validation remain unclaimed.

### 2026-07-15 11:43Z - Stage 18 export-authorization decision promoted

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes separately scoped immutable approved/rejected decision receipts bound
to one exact live-valid pending export-authorization request. Fixture-backed
outcomes validate software only; no real approval or export occurred.

Evidence:

- Exact candidate `0a0cfd55` passed 6 focused decision tests, the complete
  91-test managed-copy card suite, changed-path Ruff, format, mypy, and
  diff-check.
- SENTINEL, VERA, and HARBOR passed the final affected delta after exact receipt
  schema validation blocked rehashed authority-field injection and live tenant
  lineage was bound through planning, final in-lock recording, and readback.
- The local `scripts/check.ps1` run passed branch-state, repository-wide Ruff,
  format, and mypy over 670 source files. Pytest was intentionally interrupted
  without a verdict after the validation policy changed to avoid duplicating
  exact-head remote CI; it is not represented as a pass or failure.
- Post-promotion validation on `D:\Francis` passed all 6 decision tests and both
  authority-matrix tests. No live service, Orb process, production decision,
  artifact, network operation, or tenant mutation occurred.

Remaining truthful gap:

- Implement a deterministic, dry-run-only export-artifact plan that consumes an
  independently validated approved decision but writes no plan, manifest,
  artifact, payload, or receipt and grants no export authority.
- Actual production approval, artifact creation, export, import, global learning,
  production tenant creation, Stage 18 closure, FR-018 clearance, and physical
  validation remain unclaimed.

### 2026-07-15 11:14Z - Stage 18 export-authorization request promoted

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes a separately scoped, immutable pending authorization-request receipt
bound to an exact freshly recomputed safe-delta export preflight and bounded
action classifications. Request creation does not approve or perform export.

Evidence:

- Exact candidate `44048d85` passed 6 focused request tests, the complete
  85-test managed-copy card suite, changed-path Ruff, format, mypy, and
  diff-check.
- SENTINEL, VERA, and HARBOR passed the final affected delta after the recorder
  moved its decisive live replan inside the write lock following guarded path
  resolution and required original, supplied, and final fingerprints to agree.
- Exact candidate `44048d85` passed `scripts/check.ps1` through repository-wide
  Ruff, format, mypy over 669 source files, and pytest at 100%, exit `0`.
- Post-promotion focused validation on `D:\Francis` exposed one Windows-long
  fixture root; test-only commit `f3cc8c7c` adopts the existing compact fixture
  pattern, after which all 6 request tests passed. No live service, Orb process,
  production request, approval, artifact, network operation, or tenant mutation
  occurred.

Remaining truthful gap:

- Implement a separately scoped approval/rejection decision receipt bound to
  one exact live-valid pending authorization request. Fixture-backed decisions
  validate software only and must never be represented as production approval.
- Actual approval, export, import, global learning, production tenant creation,
  Stage 18 closure, FR-018 clearance, and physical validation remain unclaimed.

### 2026-07-15 09:25Z - Stage 18 safe-delta export preflight promoted

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes a permission-gated, exact-schema, dry-run-only preflight that
revalidates one approved safe-delta review against live provision, isolation,
and tenant-policy lineage. It writes nothing and grants no export, execution,
or mutation authority.

Evidence:

- Exact candidate `287a27c8` passed 6 focused preflight tests, 2 authority-matrix
  tests, the complete 79-test managed-copy card suite, changed-path Ruff,
  format, mypy, and diff-check.
- SENTINEL, VERA, and HARBOR passed the affected remediation delta covering
  authoritative actor binding before lineage readback, exact schema and drift
  rejection, deterministic no-effect output, and dedicated scope reporting.
- Exact candidate `287a27c8` passed `scripts/check.ps1` through repository-wide
  Ruff, format, mypy over 668 source files, and pytest at 100%, exit `0`.
- Post-promotion validation on `D:\Francis` passed all 6 preflight tests and
  both authority-matrix tests. No live service, Orb process, production receipt,
  export artifact, network operation, or tenant mutation occurred.

Remaining truthful gap:

- Implement a separately scoped, immutable pending export-authorization request
  bound to a freshly recomputed preflight and exact action classification. The
  request must remain distinct from approval and export execution.
- Actual approval, export, import, global learning, production tenant creation,
  Stage 18 closure, FR-018 clearance, and physical validation remain unclaimed.

### 2026-07-15 07:37Z - Stage 18 safe-delta decision contract promoted

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes a separately scoped, immutable approval/rejection decision receipt
bound to the exact live candidate review, actor, provision, isolation, and
current tenant policy. Approval creates eligibility only for a future export
preflight; it does not export, import, learn, execute, use the network, or mutate
tenant state.

Evidence:

- Exact rebased candidate `e799c857` passed the complete managed-copy card suite,
  Ruff, format, mypy, diff-check, and `scripts/check.ps1` through 100% with exit
  `0`.
- SENTINEL and VERA passed the final affected delta after the write boundary was
  changed to replan against live sources and require the recomputed actor-bound
  fingerprint to match both the planned and supplied fingerprints.
- Local main source head `ff58d6d9` adds a compact tenant-local `receipts/sda`
  namespace after post-promotion validation exposed the longer path exceeding
  Windows `MAX_PATH`. The discriminating long-root regression, all 18 decision
  tests, and the complete 77-test card suite passed on `D:\Francis`.
- Production source-loaded readback remains empty. No production customer,
  tenant, approval decision, export artifact, or runtime action was created.

Remaining truthful gap:

- Implement a permission-gated, dry-run-only safe-delta export preflight that
  consumes only validated tenant-local review and approval receipts, revalidates
  current lineage/policy, writes nothing, and grants no export authority.
- Actual export, import, global learning, production tenant creation, Stage 18
  closure, FR-018 clearance, and physical validation remain unclaimed.

### 2026-07-15 05:19Z - Stage 18 safe-delta review and Lens v2 observation promoted

Current posture: Phase 2 and Stage 18 remain open. Managed-copy groundwork now
includes request, preflight, creation-plan, approval, provisioning, structural-
isolation verification, and hash-only safe-delta candidate-review receipts. The
safe-delta chain stops truthfully at a separate operator approval decision; no
export, import, learning, runtime execution, or production tenant fact exists.

Evidence:

- Main `414014e9` passed local `scripts/check.ps1`, focused post-promotion tests,
  GitHub CI run `29379568003`, and CodeQL run `29379568025`.
- Safe-delta candidate review is tenant-local, exact-schema validated, lineage-
  and policy-bound, collision resistant, and rejects path redirection. Readback
  leaves approval, export, import, learning, execution, memory, registry, and
  tenant-state mutation disabled.
- Main `7af273af` promotes the v2 local game-observer and situation-model
  contracts, direct teaching-recorder composition, stale authority-result
  rejection, and PID-correlated blocked worker terminal readback.
- Exact ARGUS card tests, affected API/Lens integration tests, Ruff, format,
  mypy, PowerShell parsing, and post-promotion tests passed. The final local CI-
  equivalent gate reached 100%; its sole stale v1 ready fixture was corrected
  test-only and the exact affected suite passed. Remote CI/CodeQL for
  `7af273af` are pending and are not claimed green here.

Remaining truthful gap:

- Record a separately scoped, immutable safe-delta approval or rejection receipt
  bound to the exact live candidate review and current lineage/policy. Approval
  must not itself export, import, learn, execute, or mutate tenant state.
- Production copy creation remains blocked on real operator-supplied tenant,
  identity, policy, isolation, support, and decommission declarations.
- No Stage 18 completion, FR-018 clearance, production action, or physical-
  validation claim is made.

### 2026-07-14 00:08Z - Stage 18 managed-copy request recording implemented

Current posture: Phase 2 and Stage 18 remain open. The first executable
copy-creation state-machine step is now implemented: a scoped actor can dry-run
a complete managed-copy request, receive a privacy-bounded fingerprint, and
record one durable redacted request receipt only by replaying the same request
with the matching fingerprint and explicit confirmation. Production readback
reports request recording enabled but zero requests. No customer copy, tenant
state, runtime, role authority, or execution authority has been created.

Evidence:

- `POST /managed-copies/copy-creation-request` checks
  `managed_copies.copy_creation.write`, Stage 17 receipt closure, actor and
  required request-field presence, a hash-bound dry-run fingerprint, and
  explicit `confirm_request_recording=true` before writing.
- Confirmed apply writes only
  `data/logs/managed_copies/copy_requests.jsonl`; receipts contain an opaque
  tenant key and request-field fingerprints, not the raw tenant identifier,
  identity, policy, isolation, lineage, support, safe-delta, or decommission
  payloads.
- `GET /managed-copies/copy-creation-requests` validates receipt structure and
  governance. Status and contract readbacks consume the latest valid receipt
  bound to the current Stage 17 closure, ignoring malformed or foreign rows.
- Duplicate confirmed requests are idempotent for the same request fingerprint
  and Stage 17 closure receipt. A request receipt does not create tenant state,
  launch a runtime, or satisfy the copy-creation runtime-evidence gate.
- The entire `tests/test_api_managed_copies.py` contract file passed after the
  implementation, including permission denial, prerequisite blocking,
  incomplete-request blocking, fingerprint mismatch, redaction, idempotency,
  stale-row alignment, and disabled-provisioning checks. Ruff, Ruff format,
  mypy, and diff checks passed for the touched Stage 18 path.
- Fresh source-loaded production GET readback returned
  `stage18_groundwork_open`, `copy_request_recording_enabled=true`,
  `copy_request_recorded=false`, `copy_creation_enabled=false`, zero request
  receipts, and `next_smallest_truthful_gap=stage18_copy_creation_request_recording`.

Remaining truthful gap:

- A real tenant identifier plus identity, policy, isolation, capability-lineage,
  safe-delta, support, and decommission declarations must come from the operator
  before a production request can be dry-run and confirmed. Francis will not
  invent those business and customer facts.
- Request recording is only the first copy-creation step. Governed preflight,
  approval, isolated provisioning, verification, and handoff remain disabled.
- No canonical Stage 18 deliverable, Stage 18 completion, FR-018 clearance, or
  physical-validation claim is made by this slice.

### 2026-07-13 23:40Z - Stage 17 Capability Economy governed closure

Current posture: Phase 2 continues. Stage 17 / Capability Economy is closed by
governed operator-delegation receipt after its six canonical software criteria
read ready with no blockers. Stage 18 / Managed Copies Platform now reads
`stage18_groundwork_open`; its first truthful gap is the actual
`stage18_copy_creation_process`. This closure does not start a Stage 18 runtime,
grant execution or mutation authority, promote or enable a capability, clear
FR-018, or change the separate FR-017 Forearm Cuffs package.

Evidence:

- Source-loaded `GET /plugins/capabilities/stage17/completion-review` returned
  `status=ready`, `stage17_completion_review_ready=true`, and six of six
  canonical criteria ready before the decision.
- `POST /plugins/capabilities/stage17/stage-closure-decision` recorded explicit
  decision `close_stage17` for actor `codex.builder` under Austin's active full
  operator delegation `opdel_2a7e1182b90a5c98bea67233661065ba`.
- Durable receipt `stage17_capability_economy_closure_afd0fa32f7d1` is stored in
  `data/logs/plugins/stage17_operator_stage_closure_decisions.jsonl`; readback
  validates receipt fingerprint
  `b934b89946672dc47750029e80e2168f592220083b2a392e36d9bbd320c263dc`.
- Post-decision `GET /plugins/capabilities/stage17/stage-closure-decisions`
  returned `status=closed`, `latest_receipt_valid=true`, and delegated-operator
  authority bound to the same delegation.
- Post-decision `GET /managed-copies/status` returned
  `status=stage18_groundwork_open`, `stage17_closed_by_receipt=true`, an empty
  Stage 17 blocker, and `next_smallest_truthful_gap=stage18_copy_creation_process`.
- Focused Stage 17 closure, Stage 18 prerequisite, catalog, Ruff, format, mypy,
  and diff checks passed for the implementation slices. CodeQL run
  `29293381242` passed at implementation head `cf8d1fb1`; full CI run
  `29293381261` was still in progress when the receipt was recorded and remains
  a final-head verification requirement.

Remaining truthful gap:

- Stage 18 has no implemented copy-creation runtime. Its copy creation,
  isolation, safe-delta, rogue-recovery, SLA, role-authority, decommission, and
  runtime-evidence write paths remain disabled until implemented and validated.
- No Stage 18 completion, FR-018 clearance, or physical-validation claim is made.
- The full local `scripts/check.ps1` gate was not run; focused local validation
  plus exact-head GitHub CI/CodeQL are the stated gates for this slice.

### 2026-07-13 22:45Z - Stage 17 naming collision removed from roadmap steering

Current posture: Phase 2 and Stage 17 remain open. The canonical Stage 17
Capability Economy criteria are software capability criteria; they do not
include FR-017 Forearm Cuffs or any other physical suit measurement gate. The
FR-017 package manifest itself records this as an excluded naming collision.
This checkpoint removes that unrelated package from roadmap steering without
claiming Stage 17 closure, writing a closure receipt, starting Stage 18, or
changing FR-017's separate physical-design posture.

Evidence:

- `docs/canonical/ROADMAP.md` section 25.20 defines Stage 17 solely through
  reusable packs, pack-carried governance, catalog coherence, and visible
  compounding leverage.
- `FR-017_Stage17_Package/FR-017-STAGE17-PACKAGE-MANIFEST.json` explicitly says
  repository Stage 17 Capability Economy records are not FR-017 forearm-cuff
  source material.
- Fresh source-loaded `/plugins/capabilities/catalog?limit=1` readback reports
  all six derived software criteria `ready`, 52 of 52 packs ready, 4,052 packed
  entries, and no catalog coherence blockers.
- GitHub CI run `29267102199` and CodeQL run `29267102194` passed at current
  committed head `53bbc74b7a3c58206a69c1320879faf1c757fe19`.

Remaining truthful gap:

- Stage 17 still needs an explicit governed operator closure-decision route and
  durable receipt backed by the current Capability Economy matrix. No such
  receipt is claimed by this checkpoint.
- Stage 18 remains blocked until that canonical Stage 17 closure receipt exists.
- FR-017 Forearm Cuffs remains a separate physical-design package and does not
  block the Francis software roadmap.

### 2026-07-13 00:41Z - Stage 17 software posture broad-validated at final head

Current posture: Phase 2 and Stage 17 remain open, but the Capability Economy
software closure posture is now broad-validated at exact code head
`52e69b323fa43336207b1344da3310fb85f9567c`. All six derived software criteria
remain ready with no blockers, and the full GitHub CI matrix plus CodeQL passed
for that head. This closes the final-head software-validation gap recorded by
the 2026-07-10 checkpoint. It does not supply FR-017 physical evidence, make the
final governed Stage 17 closure decision, start Stage 18, clear FR-018, or claim
that the currently running Orb process family is healthy.

Evidence:

- Fresh source-loaded `/plugins/capabilities/catalog?limit=1` readback from the
  exact head returned `stage17_closure_matrix.status=ready_for_closure_review`,
  `all_criteria_ready=true`, `closure_claimed=false`, and criteria 1 through 6
  each `ready` with no blockers.
- Pack readiness returned 52 of 52 packs ready, all 4,052 catalog entries packed,
  tested, and documented, and zero unpacked entries.
- Catalog coherence returned zero duplicate capabilities, duplicate proposals,
  lineage gaps, validation-lineage gaps, and quality gaps.
- Receipt-linked reuse proof remained ready across the mission-linked plugin and
  mission-linked tool-operation contexts for the same pack reuse key.
- GitHub CI run `29212950024` passed at the exact head across Ubuntu and Windows
  on Python 3.12 and 3.13. GitHub CodeQL run `29212950040` also passed.
- The code-bearing perception/input slices on this head passed their focused
  API, authority-matrix, Situation Model, worker, Ruff, format, mypy, and
  `git diff --check` gates before push.

Remaining truthful gap:

- FR-017 still requires the physically present operator evidence chain:
  accepted measurement/setup evidence, non-powered mockup and
  mannequin/interface work, pilot static-fit and movement evidence,
  quick-release/cable-snag evidence, professional engineering review, and the
  final human physical decision.
- Stage 17 remains open until that evidence and the final governed closure
  decision are recorded. Stage 18 and FR-018 remain blocked.
- Full local `scripts/check.ps1` was not run for this checkpoint; the focused
  local validation and exact-head remote CI/CodeQL results above are the stated
  software gates.
- Read-only live Orb identity inspection separately reports a missing resident
  supervisor process and missing tray runtime. No process was stopped, started,
  restarted, or modified while recording this checkpoint.

### 2026-07-12 20:04Z - Stage 1 Unreal Grounded Presence live acceptance

Current posture: the operator-selected Unreal Engine 5.8 project at
`apps/unreal_presence` is a live-validated governed renderer for Stage 1
Grounded Presence. Francis Core remains authoritative. This is cross-stage
hardening of a previously closed foundation stage; it does not close Phase 2,
close Stage 17, supply FR-017 physical evidence, start Stage 18, grant resident
Orb authority, or complete Francis.

What is materially true now:

- Versioned presence, selection, runtime, envelope, authenticated wrapper,
  signed ACK, delivery-attempt, delivery-journal, delivery-receipt, intent, and
  intent-receipt contracts are implemented and tested.
- Core-to-Unreal and Unreal-to-Core transport uses local-only Windows named
  pipes with HMAC-SHA256 process-environment keys, bounded framing/timeouts,
  signed correlation, cross-process writer locking, durable sequence state,
  replay rejection, and payload-free recovery metadata.
- The dedicated C++ runtime consumes the Core projection, renders a procedural
  state-reactive presence with the selected UE 5.8 stack, and emits only
  whitelisted request intents. Core receipts accepted intents without dispatch
  or mutation.
- `/continuity/presence`, `/continuity/presence/contracts`, and
  `/continuity/presence/unreal-runtime` expose live runtime truth; the operator
  UI and read-only Orb overlay consume the same bounded projection.
- The standard API launcher supplies the pinned operator selection through the
  explicit environment contract without inferring another project. The host
  uses a semantic digest plus bounded heartbeat, so timestamp-only refreshes do
  not race intent source correlation.
- Launch and stop scripts refuse PID drift, never persist the secret, restore
  the caller environment exactly, bound screenshots to the dedicated runtime
  directory, support a bounded test lifetime, and stop only the Unreal
  host/editor processes they own. The separately managed native Orb is not
  launched or granted residency by this project.

Validation actually run:

- Focused Python presence, host, selection, named-pipe, operator, and Orb suite:
  `175` tests passed.
- UI suite: `289` tests passed; Vite production build passed.
- Ruff, format, no-incremental mypy, all `11` Grounded Presence schemas,
  selection digest readback, PowerShell parser checks, bounded screenshot
  rejection, environment restoration, and `git diff --check` passed for the
  touched path.
- `FrancisPresenceEditor Win64 Development` and
  `FrancisPresence Win64 Development` both built successfully against Unreal
  Engine 5.8; the native C++ Orb renderer also built in compile-only mode.
- The runtime config enables the operator-selected stack and explicitly disables
  Nanite. MegaLights was not selected or claimed as validated. Enhanced Input
  initializes a real local-player mapping rather than remaining a linked-only
  dependency.
- Bounded live session `francis_unreal_stage1_acceptance_v7` reached
  `contracts_implemented_runtime_observed`, returned the presence projection in
  `0.806` seconds, wrote delivery receipt
  `gpd_e2ba69dd41a3da65314df581fbed0b84`, and captured the nonblank engine frame
  `data/runtime/unreal-presence/acceptance-v7.png`. The live projection
  truthfully remained `blocked` for the current receipt/evidence posture.
- The same session wrote five accepted request-only intent receipts. The
  auto-injected context refresh wrote `gpr_ef105c731c8c3e64bc3cef81fe736887`;
  focused Enhanced Input F6 wrote handback receipt
  `gpr_8e0c657389d776262c11b6f6d716f519`; and F7 wrote review receipt
  `gpr_ac78026fec935948d33479413fc870f0`. All reported no dispatch, mutation, or
  execution authority.
- Desktop inspection confirmed the rendered Orb plus Slate truth panel. The
  launcher restored all twelve environment entries, reported no persisted
  secret, and then stopped host PID `106240` plus Unreal PID `101908`. Final
  readback found no Unreal, host, native Orb, overlay, or test API process.

Remaining limits:

- Unreal presence residency is intentionally disabled; it is launched only for
  bounded tests until the operator accepts the version for normal use.
- The acceptance frame proves the selected visual runtime rendered, not that
  its art direction is permanently locked or that every device/driver profile
  has been qualified.
- The saved engine screenshot intentionally excludes Slate UI; the panel was
  verified through bounded desktop inspection. Repo-wide `npx tsc --noEmit`
  remains a separate baseline gap with `9,740` pre-existing diagnostics across
  `30` UI files; the production build and `289` UI tests are green.
- Phase 2, Stage 17 physical validation, the final governed Stage 17 closure
  decision, FR-018, Stage 18, and later roadmap work remain open.

### 2026-07-10 14:31Z - Stage 17 software criteria ready for closure review

Current posture: Phase 2 and Stage 17 remain open, but the Capability Economy
software closure matrix now reports all six criteria `ready` at exact code head
`5004ef2bd34db9e3dfa48d591a0dc8c08693e0b3`. The quality-remediation queue is
empty, every catalog pack is ready, catalog coherence has no reported gaps, and
receipt-linked cross-mission reuse proof remains ready. This closes the current
route/readback reconciliation gate. It does not supply FR-017 physical evidence,
make the final governed Stage 17 closure decision, start Stage 18, or clear
FR-018.

What changed:

- The quality-remediation GET and writer now use the same synchronized full-scan
  catalog truth, so readback no longer advertises reconstruction that the writer
  will reject.
- Quality dry runs plan from an in-memory catalog and leave registry/catalog
  bytes unchanged while reporting no write authority.
- Explicit legacy-pack migration budgets may exceed the default 500-member
  ceiling up to a hard 1,000-member cap, and the quality batch writer preserves
  every explicitly admitted member instead of truncating at 500.
- Governed metadata, candidate-reference, and reconstruction passes drained all
  17 blocked packs. Candidate test/doc references remain explicitly
  `candidate_reference_only_not_pack_specific_proof`; reconstruction receipts do
  not approve proposals, promote capabilities, enable capabilities, or execute
  them.

Evidence:

- Exact-head source-loaded readback returned
  `stage17_closure_matrix.status=ready_for_closure_review`,
  `all_criteria_ready=true`, and `closure_claimed=false`; criteria 1 through 6
  each report `status=ready` with no blockers.
- Pack/catalog readback returned 52 of 52 packs ready, 4,052 packed entries,
  4,052 tested and documented entries, zero unpacked entries, and zero duplicate,
  lineage, validation-lineage, or quality gaps.
- Quality readback returned `status=ready`, `remediation_queue_count=0`,
  `artifact_reconstruction_required_count=0`, and a synchronized full artifact
  scan. Migration readback returned `candidate_total=0`.
- Invocation audit returned `status=ready` and
  `proof_readiness.status=reuse_proof_ready` from two accepted receipt-linked
  mission operation shapes using the same pack reuse key.
- Seventeen metadata receipts under
  `data/artifacts/plugins/capability_packs/metadata_receipts/` bind 3,288 legacy
  generated capability members to versioned pack governance. The first and last
  receipts are
  `capability_pack_metadata_1783690993_legacy-generated-capabilitylineageplugin`
  and `capability_pack_metadata_1783693467_legacy-generated-opsplugin`.
- Ten reconstruction receipts under
  `data/artifacts/plugins/capability_packs/artifact_reconstructions/` close 208
  missing validation/proposal-lineage records. Receipt IDs are
  `stage17_artifact_reconstruction_batch_1783691376_1ab66038_receipt`,
  `stage17_artifact_reconstruction_batch_1783691643_250ccd50_receipt`,
  `stage17_artifact_reconstruction_batch_1783691859_7f1d47d4_receipt`,
  `stage17_artifact_reconstruction_batch_1783692395_4af1992a_receipt`,
  `stage17_artifact_reconstruction_batch_1783692588_e097dc61_receipt`,
  `stage17_artifact_reconstruction_batch_1783692776_69100f24_receipt`,
  `stage17_artifact_reconstruction_batch_1783692913_f53cab73_receipt`,
  `stage17_artifact_reconstruction_batch_1783693046_d247469a_receipt`,
  `stage17_artifact_reconstruction_batch_1783693177_f00e410e_receipt`, and
  `stage17_artifact_reconstruction_batch_1783693761_9d4f4a0c_receipt`.
- Bounded code commits `1ad1c55b`, `0a73a598`, `f8cd767f`, and `5004ef2b`
  passed focused plugin route/batch tests, Ruff lint, Ruff format, and diff checks
  before being pushed directly to `main`.

Remaining truthful gap:

- Final-head GitHub CI must pass before the software posture is treated as the
  broad validated head.
- FR-017 still requires the physically present operator evidence chain: accepted
  measurement/setup evidence, non-powered mockup and mannequin/interface work,
  pilot static-fit and movement evidence, quick-release/cable-snag evidence,
  professional engineering review, and the final human physical decision.
- Stage 17 remains open until that evidence and the final governed closure
  decision are recorded. Stage 18 and FR-018 remain blocked.
- The full local `scripts/check.ps1` gate was not run; focused local validation
  and final-head remote CI are the stated gates for this slice.

### 2026-07-10 12:34Z - Stage 6 Lens MVP acceptance closure

Current posture: Phase 2 continues, but Stage 6 Lens MVP is now ledger-closed
against the five done criteria in `docs/canonical/ROADMAP.md`. The exact-head
completion audit, canonical live runtime, rendered Lens/Chat surfaces, fresh
hotkey summon, and one-visible-loop effect proof agree at code commit
`c40cf6b965b4a262b45484a53d351b2f45e609e0`. Archived closure receipts remain
authoritative for Stages 7 through 16, making Stage 17 Capability Economy the
next open dependency. This does not complete Phase 2 or Francis, close Stage 17,
claim physical validation, or clear FR-018.

What changed:

- The Stage 6 completion audit can reuse a fresh hash-verified checkpoint only
  when its repository root and exact commit match, removing the prior audit
  timeout without weakening evidence integrity.
- Canonical Orb identity readback now correlates the supervised resident host,
  tray, hotkey, overlay, summon, voice, visual contract, and single native
  renderer against the same live instance.
- Browser evidence now proves the existing `/diagnostics` Lens and collaboration
  surfaces actually rendered with read-only authority, policy receipt visibility,
  and zero Lens blockers.
- The one-visible-loop proof now requires that render evidence and confirms an
  operator-approved app-targeted effect on a disposable safe target before it can
  pass.

Evidence:

- `data/logs/operations/stage6/lens_stage6_completion_audit_resumed_20260710_122358469.json`
  returned `ok=true`, `audit_status=complete`, `ready_to_close=true`,
  `can_close_stage6=true`, `transition_allowed=true`, no blocked criteria, and
  `closure_decision=stage6_ready_for_ledger_closure`. Its SHA256-verified
  checkpoint records the exact code head above.
- All five canonical acceptance criteria are `ready`: `summon_anywhere`,
  `helpful_not_noisy`, `mode_visibility`, `pilot_visibility_groundwork`, and
  `system_resident_presence`.
- Fresh canonical hotkey evidence records request
  `summon-global_hotkey-e4fdbba678554848a2a903fc7f4e4800`, summon receipt
  `lsum_1783686821_111205091a31`, and Orb-control receipt
  `orb-control-8dd7cf73431e441bae6672512b140562`.
- `data/logs/operations/one_visible_loop/francis_lens_ui_render_proof_20260710_123410048.json`
  validated as `render_verified` with zero blockers. Its Lens and Chat screenshots
  are SHA256-bound as `0120b69f994884f23860c8ca44e3c8257a7703aab356feea3f9a31c44defaae0`
  and `3442be07f3f7fc38d80e3d3702597e41b38870fc39d7489a12de3c761b8ce913`.
- `data/logs/operations/one_visible_loop/francis_one_visible_loop_proof_20260710_073428301.json`
  returned `status=passed`, `next_operator_decision=none`, actual Chat/Lens render
  verification, `desktop_effect_confirmed=true`, `target_state_changed=true`,
  `physical_input_performed=false`, `user_mouse_taken=false`, and confirmed the
  disposable target stopped.
- The live canonical process family remained supervisor `2608`, resident host
  `10108`, tray `1992`, hotkey `26076`, overlay `36728`, and native renderer
  `37312`; the process scan reported zero competing candidates.
- Safe-target authority used approval
  `9632c9ad-78f2-4d86-b054-b741e3092aaf`, delegation
  `opdel_7bee8173cc6d52e7adc4fdeaad80c2b2`, operator receipt
  `.francis/orb_operator/receipts/orb_operator_b4b65f66b7c3.json`, and desktop
  bridge receipt
  `.francis/orb_operator/desktop_bridge_receipts/orb_desktop_bridge_b377ac03ab68.json`.
- Focused tests, Ruff lint/format checks, PowerShell parser checks, and diff checks
  passed for the five bounded code slices from `4d8141b9` through `c40cf6b9`.
  CodeQL for `c40cf6b9` passed; the full GitHub CI matrix was still running its
  pytest jobs when this evidence was recorded.
- Existing stage-local closures remain receipt-backed from Stage 7 receipt
  `tel_stage7_closure_e4c216a895a6` through Stage 16 receipt
  `fedstage16close_f6c91d005446`; this Stage 6 closure does not reopen them.

Remaining blockers:

- Stage 17 remains open pending final-head CI/wiring trust, current capability
  route/readback reconciliation, the FR-017 operator/physical evidence chain,
  and a final governed closure decision. Stage 18 does not start before that.
- The full local `scripts/check.ps1` gate was not run for this live acceptance
  slice; final remote CI remains the broad gate.
- Later roadmap stages, Stage 17 physical validation, and FR-018 remain open.

### 2026-07-10 01:37Z - Stage 6 command-palette readback under large continuity ledger

Current posture: Phase 2 / Stage 6 Orb embodiment remains incomplete, but the
checkpoint no longer loses the command-palette shell bridge when the local
continuity ledger is large. The live checkpoint now advances past
`command_palette_shell_bridge_readback` and reports
`stage6_lens_completion_audit` as the next smallest truthful gap. This does not
close Stage 6, claim one-visible-loop completion, grant tray/hotkey/overlay
authority, or clear the full completion audit.

What changed:

- `francis.chat.continuity.ledger.tail()` now reads recent JSONL entries from
  the end of the ledger with bounded reverse line collection instead of reading
  the full historical ledger file before slicing.
- The continuity ledger tail cache is keyed by ledger path, requested limit,
  size, and mtime, so repeated status composition in one process reuses the
  same parsed recent entries while appends naturally invalidate the cache.
- `scripts/lens-stage6-completion-audit.ps1` now writes the already-computed
  summon-anywhere blockers proof to a cache file and passes it to
  `scripts/lens-summon-tray-presence-blocker-proof.ps1`, avoiding a duplicate
  child proof in the completion-audit chain.

Evidence:

- `python -m pytest tests/test_continuity_ledger.py -q` passed.
- `python -m pytest tests/test_lens_summon_tray_presence_blocker_proof_script.py::test_lens_summon_tray_presence_blocker_proof_is_readback_only tests/test_lens_stage6_completion_audit_script.py::test_lens_stage6_completion_audit_consumes_tray_presence_blocker_readback -q`
  passed.
- `python -m ruff check src\francis\chat\continuity\ledger.py tests\test_continuity_ledger.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_summon_tray_presence_blocker_proof_script.py`
  passed.
- `python -m ruff format --check src\francis\chat\continuity\ledger.py tests\test_continuity_ledger.py tests\test_lens_stage6_completion_audit_script.py tests\test_lens_summon_tray_presence_blocker_proof_script.py`
  passed.
- Direct local timing against the live `data\conversations\ledger\ledger.jsonl`
  returned `tail(1000)` in about `0.062` seconds for the current 88 MB ledger.
- `scripts\lens-command-palette.ps1 -Mode Status` returned `ok=true`,
  `status=blocked`, `readback_ready=true`, `command_total=24`,
  `summon_anywhere=true`, and only the expected
  `os_level_command_palette_missing` blocker.
- `scripts\lens-stage6-checkpoint.ps1 -Mode Status -StartupTimeoutSeconds 5 -HostLaunchRunSeconds 2 -ResidentSurfaceForegroundRunSeconds 5 -SupervisorRunSeconds 3 -LensStatusTimeoutSeconds 105 -ChildProofTimeoutSeconds 105`
  returned `ok=true`, `status=blocked`,
  `command_palette_shell_bridge.status=blocked`,
  `command_palette_shell_bridge.readback_ready=true`, `command_total=24`,
  and `next_smallest_truthful_gap=stage6_lens_completion_audit`.

Remaining blockers:

- `scripts\lens-stage6-completion-audit.ps1 -Mode Status -OverallTimeoutSeconds 300 -ChildProofTimeoutSeconds 120`
  still returned `ok=false`, `audit_status=checkpoint_timed_out`,
  `child_proof_timeouts=["stage6_checkpoint"]`, and
  `next_smallest_truthful_gap=stage6_completion_audit_checkpoint_timeout`.
- A standalone checkpoint with the audit's effective child settings completed
  in about `171.32` seconds, so the next bounded slice is to make the completion
  audit checkpoint wrapper/budget contract robust without hiding slow child
  proofs or claiming Stage 6 closure.

### 2026-07-09 21:44Z - Stage 6 resident-surface proof/readback boundary

Current posture: Phase 2 / Stage 6 Orb embodiment remains incomplete, but the
resident-surface proof/readback path no longer requires launching a competing
foreground runtime when the canonical supervised resident runtime is already
visible. The live checkpoint now advances past the resident-surface
runtime/readback blocker and reports `command_palette_shell_bridge_readback` as
the next smallest truthful gap. This does not close Stage 6, claim one-visible
loop completion, prove command-palette shell bridge behavior, or clear the full
completion audit.

What changed:

- `/lens/resident-surface` now uses a bounded fast readback snapshot for resident
  host, tray, hotkey, overlay, summon, resident-surface activation, and
  resident-claim authority-readiness state instead of depending on the full
  `/lens/status` aggregate.
- `scripts/lens-resident-surface-proof.ps1` consumes the canonical live
  resident runtime readback when present, skips the pre-resident foreground host
  and live-operator proof paths in that state, and keeps the next gate at
  `resident_surface_operator_experience_proof` without granting authority.
- The Stage 6 checkpoint test contract now accepts either bounded foreground
  proof before residency or direct supervised resident-runtime readback after
  residency.

Evidence:

- `python -m pytest tests/test_lens_resident_surface_proof_script.py tests/test_api_lens.py::test_lens_resident_surface_readback_mirrors_claim_authority_without_execution tests/test_api_lens.py::test_lens_api_observes_live_foreground_process_readback tests/test_lens_stage6_checkpoint_script.py tests/test_lens_stage6_completion_audit_script.py -q`
  passed with one skipped test.
- `python -m ruff check src\francis\lens\status.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  passed.
- `python -m ruff format --check src\francis\lens\status.py tests\test_lens_resident_surface_proof_script.py tests\test_lens_stage6_checkpoint_script.py`
  passed.
- `git diff --check -- scripts/lens-resident-surface-proof.ps1 src/francis/lens/status.py tests/test_lens_resident_surface_proof_script.py tests/test_lens_stage6_checkpoint_script.py`
  passed, with only the existing PowerShell line-ending normalization warning.
- `scripts\lens-resident-surface-proof.ps1 -Mode Status -DataDir D:\Francis\data`
  returned `status=proof_passed`,
  `resident_surface_resident_runtime_readback=true`,
  `resident_surface_foreground_runtime_readback=false`,
  `operator_experience_proof=false`, and
  `next_smallest_truthful_gap=resident_surface_operator_experience_proof`.
- `scripts\lens-stage6-checkpoint.ps1 -Mode Status` returned `ok=true`,
  `status=blocked`, `helpful_not_noisy=readback_ready`,
  `resident_surface_runtime_proof_observed=true`,
  `resident_surface_resident_runtime_proof_observed=true`, and
  `next_smallest_truthful_gap=command_palette_shell_bridge_readback`.

Remaining blockers:

- `scripts\lens-stage6-completion-audit.ps1 -Mode Status -OverallTimeoutSeconds 300 -ChildProofTimeoutSeconds 120`
  still returned `ok=false`, `audit_status=timed_out`,
  `child_exit_code=124`, and
  `next_smallest_truthful_gap=stage6_completion_audit_timeout`.
- The checkpoint's next functional gate is
  `command_palette_shell_bridge_readback`; Stage 6 still also requires actual
  operator-experience proof, summon acceptance, desktop effect evidence, voice
  replay proof, and one-visible-loop proof before any closure claim.

### 2026-07-09 02:34Z - Internal Compute Substrate API route

Current posture: Phase 2 / `P7_EXECUTION` remains partial, but the first
internal/local-dev Compute Substrate API route surface is now implemented and
validated at commit `3953ed26`. This does not close Phase 2, close
`P7_EXECUTION`, change the active Orb embodiment / Stage 6 workstream, expose a
production-grade public API, implement real adapters, add async/background
execution, add task recovery/resume, or add OS-level resource enforcement.

What changed:

- `POST /compute-substrate/submit` submits bounded direct compute requests
  through `ApiPermissionGate` and `ComputeSubstrateService`.
- `GET /compute-substrate/status/{task_id}` and
  `GET /compute-substrate/status/by-correlation/{correlation_id}` return bounded
  status readback through the service status surface.
- Route permissions use separate `compute:submit` and `compute:status:read`
  scopes; approval grants do not replace API actor authorization.
- The route reports bounded receipt/status/approval/cancellation/timeout truth
  without returning raw task payloads, raw execution outputs, secrets, raw
  approval notes, raw model prompts, broad filesystem paths, or tracebacks.

Evidence:

- Commit `3953ed2671ae3fe6bb8ff163abfae78940fbd4be`
  (`feat(api): expose internal compute substrate routes`) anchors this route
  slice.
- Commit-time validation passed for ruff check, ruff format check, mypy over the
  compute substrate and API route modules, API and substrate pytest suites, API
  mutation authority matrix tests, executor substrate API tests, and diff
  whitespace checks.

Remaining blockers:

- Production exposure, receipt readback routes, capability routes, admin routes,
  real adapters, durable adapter persistence, async/background execution,
  recovery/resume, cross-process approval reservation, distributed locking,
  local JSON multi-process coordination, retention/cleanup policy, OS-level
  CPU/memory enforcement, `LiveLearningEvent` persistence, long-term memory
  persistence, and model training remain future governed work.

### 2026-07-07 21:17Z - Stage 6 Orb ring/color identity readback

Current posture: Phase 2 / Stage 6 Orb embodiment still remains incomplete, but
the canonical Orb runtime identity readback now carries an explicit ring/color
contract for the locked visible Orb. This closes the
`orb_ring_color_contract_missing` blocker in the runtime identity readback. It
does not close Stage 6, prove one-visible-loop completion, resolve voice-provider
drift, grant new authority, modify the live Orb process, or claim FR-018
clearance.

What changed:

- `scripts/lens-overlay-window.ps1` now projects a read-only
  `lens.overlay.orb_ring_color_contract` sourced from
  `docs/operations/ORB_VISUAL_LOCK.md` and the existing WPF energy-orb renderer
  constants.
- `src/francis/lens/host_manifest.py` normalizes older live overlay status
  payloads at readback time when they already identify the canonical
  `chat_ui.orbGlyph.energy_reference` / `wpf_3d_animated_energy_orb` surface.
- The API-level canonical runtime identity now keeps missing ring/color as a
  blocker for arbitrary incomplete readback, but clears that blocker when the
  locked visual contract is present.

Evidence:

- `python -m py_compile src\francis\lens\host_manifest.py tests\test_api_lens.py tests\test_lens_host_manifest_process_readback.py tests\test_lens_overlay_window_script.py`
  passed.
- `python -m ruff check src/francis/lens/host_manifest.py tests/test_api_lens.py tests/test_lens_host_manifest_process_readback.py tests/test_lens_overlay_window_script.py`
  passed.
- `python -m pytest tests/test_api_lens.py::test_lens_orb_runtime_identity_reports_voice_and_visual_drift tests/test_api_lens.py::test_lens_orb_runtime_identity_accepts_locked_ring_color_contract tests/test_lens_host_manifest_process_readback.py::test_lens_host_manifest_normalizes_locked_orb_ring_color_contract tests/test_lens_overlay_window_script.py::test_lens_overlay_window_status_reports_missing_runtime tests/test_lens_overlay_window_script.py::test_lens_overlay_window_script_uses_atomic_state_and_owned_process_stop -q`
  passed, 5 tests.
- Live readback through `francis.lens.status.lens_orb_runtime_identity(limit=5,
  include_process_scan=True)` returned `status=identity_drift_detected`,
  `blockers=["orb_voice_provider_identity_drift"]`,
  `visual_identity.ring_color_contract_ready=true`, and
  `process_scan.status=single_canonical_runtime`.

Remaining blockers:

- `orb_voice_provider_identity_drift` still remains: overlay output is
  configured as ElevenLabs while input/runtime readback still reports
  WindowsSapi.
- Broader Stage 6 gates remain open: summon-anywhere acceptance, stable
  resident/supervision proof, desktop bridge effect proof, voice replay proof,
  and one-visible-loop proof.

### 2026-07-07 01:08Z - FR-017 setup updater classifies next handoff

Current posture: Phase 2 / FR-017 Stage 17 remains documentation-ready and evidence-container-ready, with physical validation still blocked at measurement intake. This is a Stage 17 / FR-017 setup-updater handoff correction for the first physical-input gate. It does not create durable pilot measurement evidence, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- `scripts/fr017-update-measurement-setup-record.ps1` now emits typed next-command metadata: `next_command_kind`, `next_command_contract`, and `next_status_command_template`.
- Valid pending-record status now reports `next_command_kind=update_setup_safety_brief` and points `next_command` at the setup/safety update command.
- Successful setup/safety writes now report `next_command_kind=rerun_measurement_intake` and point `next_command` back at read-only measurement intake status; failure paths return `next_command_kind=none`.
- The handoff contract explicitly states that these commands are operator handoffs only, not physical validation evidence, not a Stage 17 completion claim, and not FR-018 clearance.

Validation actually run:

- PowerShell parser validation passed for `scripts/fr017-update-measurement-setup-record.ps1`.
- `python -m py_compile tests\test_fr017_measurement_setup_record_update_script.py`: passed.
- `python -m ruff check tests/test_fr017_measurement_setup_record_update_script.py`: passed.
- `python -m ruff format --check tests/test_fr017_measurement_setup_record_update_script.py`: passed.
- `python -m pytest tests/test_fr017_measurement_setup_record_update_script.py -q`: passed, 5 tests.
- Direct temporary-record readback passed: status returned `next_command_kind=update_setup_safety_brief`, setup update returned `next_command_kind=rerun_measurement_intake`, both reported `physical_validation_complete=False`, and both reported `fr018_implementation_cleared=False`.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this slice.

### 2026-07-07 00:59Z - Completion model prefers active roadmap workstream

Current posture: Phase 2 / roadmap completion readback now keeps the declared active Orb embodiment / Stage 6 Lens runtime workstream as the continuation source when the ledger names an active workstream and current goal. This is a roadmap-steering correction. It does not close Stage 6, enable summon-anywhere, start resident supervision, claim a desktop effect, complete the one-visible-loop proof, close Stage 17, or clear FR-018.

What changed:

- `scripts/francis-completion-model.ps1` now reads the ledger's `Current active workstream` line and wrapped current-goal paragraph into a read-only `active_workstream` payload.
- `next_continue_decision` now selects `active_workstream_current_goal` before archived Stage 17 fallback gaps when that active workstream is present, while preserving `stage17_status` as a separate open readback.
- The selected-gap contract now exposes `selected_gap_is_active_workstream=True` for that path and continues to deny write, execution, mutation, promotion, and Stage 17 apply authority.

Validation actually run:

- PowerShell parser validation passed for `scripts/francis-completion-model.ps1`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-completion-model.ps1`: passed and returned `active_workstream.found=True`, `selected_gap_source=active_workstream_current_goal`, `active_workstream_preferred=True`, `stage17_gap_preferred=False`, `writes_repo=False`, and `grants_execution_authority=False`.
- `python -m py_compile tests\test_francis_completion_model_script.py`: passed.
- `python -m ruff check tests/test_francis_completion_model_script.py`: passed.
- `python -m ruff format --check tests/test_francis_completion_model_script.py`: passed.
- `python -m pytest tests/test_francis_completion_model_script.py -q`: passed, 6 tests.

Remaining blockers:

- Stage 6 Orb/Lens still requires the real summon prerequisites, Orb presence stability, confirmed desktop bridge effects, voice replay proof, and one-visible-loop proof before any completion claim.
- The config/runtime and live desktop state were not changed by this slice; no hotkey, resident-host, overlay, tray, bridge, or browser-render acceptance is claimed.
- Stage 17 remains open and physically unvalidated; FR-018 remains blocked and not cleared by this slice.

### 2026-07-07 00:14Z - FR-017 initializer summary uses full setup command

Current posture: Phase 2 / FR-017 Stage 17 remains documentation-ready and evidence-container-ready, with physical validation still blocked at measurement intake. This is a Stage 17 / FR-017 initializer-summary handoff correction for the first physical-input gate. It does not create a measurement record, record pilot dimensions, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- `scripts/fr017-new-measurement-record.ps1 -Mode Summary` now uses the full setup/safety create command as `next_create_command`, including `-EvidenceDate`, observer/pilot/tool/method/posture placeholders, safety-condition confirmations, and condition notes.
- The previous shorter output-path-only handoff is preserved separately as `next_create_path_command` so operators can still see the candidate file target without mistaking it for the complete create invocation.
- The summary remains read-only and still reports `wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.

Validation actually run:

- PowerShell parser validation passed for `scripts/fr017-new-measurement-record.ps1`.
- `python -m py_compile tests\test_fr017_measurement_record_initializer_script.py`: passed with `PYTHONPYCACHEPREFIX` redirected to a temp cache.
- `python -m ruff check tests/test_fr017_measurement_record_initializer_script.py`: passed.
- `python -m ruff format --check tests/test_fr017_measurement_record_initializer_script.py`: passed.
- `python -m pytest tests/test_fr017_measurement_record_initializer_script.py -q`: passed, 12 tests.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-new-measurement-record.ps1 -Mode Summary`: passed and returned a `next_create_command` containing `-EvidenceDate YYYY-MM-DD` and `-ConfirmStopConditionsBriefed`, plus `wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this slice.

### 2026-07-06 23:44Z - FR-017 summaries carry next capture command

Current posture: Phase 2 / FR-017 Stage 17 remains documentation-ready and evidence-container-ready, with physical validation still blocked at measurement intake. This is a Stage 17 / FR-017 readback-propagation slice for the first physical-input gate. It does not create a measurement record, record pilot dimensions, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- `scripts/fr017-measurement-session-brief.ps1 -Mode Status` and `-Mode Summary` now expose `measurement_capture_next_command_kind`, `measurement_capture_next_command_template`, and `measurement_capture_next_status_command_template` from the active measurement-intake state.
- `scripts/fr017-evidence-chain-status.ps1 -Mode Summary` now carries those fields upward as `first_blocking_capture_next_command_kind`, `first_blocking_capture_next_command_template`, and `first_blocking_capture_next_status_command_template`.
- Template/no-record readbacks still route the operator to a pending measurement-record create command using the suggested output path, then to a concrete measurement-intake rerun command; the fields are read-only handoffs, not evidence or validation completion.

Validation actually run:

- PowerShell parser validation passed for `scripts/fr017-measurement-session-brief.ps1` and `scripts/fr017-evidence-chain-status.ps1`.
- `python -m py_compile tests\test_fr017_measurement_session_brief_script.py tests\test_fr017_evidence_chain_status_script.py`: passed with `PYTHONPYCACHEPREFIX` redirected to a temp cache.
- `python -m ruff check tests/test_fr017_measurement_session_brief_script.py tests/test_fr017_evidence_chain_status_script.py`: passed.
- `python -m ruff format --check tests/test_fr017_measurement_session_brief_script.py tests/test_fr017_evidence_chain_status_script.py`: passed after formatting.
- `python -m pytest tests/test_fr017_measurement_session_brief_script.py tests/test_fr017_evidence_chain_status_script.py -q`: passed, 41 tests.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-measurement-session-brief.ps1 -Mode Summary`: passed and returned `measurement_capture_next_command_kind=create_pending_measurement_record`, a create command with the suggested pending record path, a concrete intake rerun command, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-evidence-chain-status.ps1 -Mode Summary`: passed and returned the same first-blocking capture next-command kind/template/status-command fields, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this slice.

### 2026-07-06 23:21Z - FR-017 measurement intake exposes next capture command

Current posture: Phase 2 / FR-017 Stage 17 remains documentation-ready and evidence-container-ready, with physical validation still blocked at measurement intake. This is a Stage 17 / FR-017 intake-readback slice for the first physical-input gate. It does not create a measurement record, record pilot dimensions, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- `scripts/fr017-measurement-intake.ps1 -Mode Status` now exposes read-only capture command templates for the five measurement-capture groups.
- The intake output now reports `measurement_capture_next_command_kind`, `measurement_capture_next_command_template`, and `measurement_capture_next_status_command_template` so the operator can move from the first blocking group to the correct updater path without guessing.
- Template/no-record status routes the next command to `fr017-new-measurement-record.ps1 -Mode Create` instead of suggesting mutation of `FR-017-MEASUREMENTS-INPUT-TEMPLATE.json`; existing working records route to the first blocking updater group, and ready records route only to the non-powered mockup readiness gate.

Validation actually run:

- PowerShell parser validation passed for `scripts/fr017-measurement-intake.ps1`.
- `python -m py_compile tests\test_fr017_measurement_intake_script.py`: passed with `PYTHONPYCACHEPREFIX` redirected to a temp cache.
- `python -m ruff check tests/test_fr017_measurement_intake_script.py`: passed.
- `python -m ruff format --check tests/test_fr017_measurement_intake_script.py`: passed after formatting.
- `python -m pytest tests/test_fr017_measurement_intake_script.py -q`: passed, 34 tests.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-measurement-intake.ps1 -Mode Status`: passed and returned `measurement_capture_next_command_kind=create_pending_measurement_record`, a create command with `<measurement-record.json>`, `measurement_capture_command_templates_not_evidence=True`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this slice.

### 2026-07-06 23:06Z - FR-017 initializer summary suggests output path

Current posture: Phase 2 / FR-017 Stage 17 remains documentation-ready and evidence-container-ready, with physical validation still blocked at measurement intake. This is a Stage 17 / FR-017 initializer-readback slice for the first physical-input gate. It does not create a measurement record, record pilot dimensions, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- `scripts/fr017-new-measurement-record.ps1 -Mode Status` and `-Mode Summary` now suggest the same default pending measurement-record path under `FR-017_Stage17_Package` when no `-OutputPath` is supplied.
- The initializer summary now reports `output_path_source=suggested_default`, `candidate_output_path_ready=True`, and concrete next create/intake commands using the suggested path.
- `-Mode Create` without `-OutputPath` still fails closed with `status=missing_output_path`, so the suggested readback does not silently create evidence.

Validation actually run:

- PowerShell parser validation passed for `scripts/fr017-new-measurement-record.ps1`.
- `python -m py_compile tests\test_fr017_measurement_record_initializer_script.py`: passed with `PYTHONPYCACHEPREFIX` redirected to a temp cache.
- `python -m ruff check tests/test_fr017_measurement_record_initializer_script.py`: passed.
- `python -m ruff format --check tests/test_fr017_measurement_record_initializer_script.py`: passed after formatting.
- `python -m pytest tests/test_fr017_measurement_record_initializer_script.py -q`: passed, 12 tests.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-new-measurement-record.ps1 -Mode Summary`: passed and returned `output_path_source=suggested_default`, the suggested path in `next_create_command`, `candidate_output_path_ready=True`, `output_exists=False`, `wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `Test-Path` for the suggested `FR-017-MEASUREMENTS-2026-07-06-PILOT-RECORD.json` path returned `False` after the read-only summary check.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-new-measurement-record.ps1 -Mode Create`: failed closed with `status=missing_output_path`, `output_path_source=missing`, `wrote_file=False`, `writes_data=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `git diff --check -- scripts\fr017-new-measurement-record.ps1 tests\test_fr017_measurement_record_initializer_script.py`: passed.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this slice.

### 2026-07-06 21:28Z - FR-017 first measurement handoff suggests record path

Current posture: Phase 2 / FR-017 Stage 17 remains documentation-ready and evidence-container-ready, with physical validation still blocked at measurement intake. This is a Stage 17 / FR-017 operator-readback slice for the first physical-input gate. It does not create a measurement record, record pilot dimensions, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- `scripts/fr017-measurement-session-brief.ps1` now generates a default suggested pending measurement-record path under `FR-017_Stage17_Package` when no `-CandidateMeasurementPath` is supplied.
- Measurement-session and evidence-chain summaries now preflight that suggested path in read-only mode and show the same path in the visible `fr017-new-measurement-record.ps1 -Mode Create -OutputPath "..."` handoff.
- The source of the active path is explicit: `candidate_measurement_path_source=suggested_default` for generated handoffs and `operator_supplied` when the caller provides a candidate path.

Validation actually run:

- PowerShell parser validation passed for `scripts/fr017-measurement-session-brief.ps1`.
- `python -m py_compile tests\test_fr017_measurement_session_brief_script.py tests\test_fr017_evidence_chain_status_script.py`: passed with `PYTHONPYCACHEPREFIX` redirected to a temp cache.
- `python -m ruff check tests/test_fr017_measurement_session_brief_script.py tests/test_fr017_evidence_chain_status_script.py`: passed.
- `python -m ruff format --check tests/test_fr017_measurement_session_brief_script.py tests/test_fr017_evidence_chain_status_script.py`: passed after formatting the evidence-chain test file.
- Focused pytest checks passed for the default suggested-path handoff and explicit operator-supplied candidate override across measurement-session and evidence-chain readbacks.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-measurement-session-brief.ps1 -Mode Summary`: passed and returned `candidate_measurement_path_source=suggested_default`, the suggested path inside `current_group_update_command_template`, `current_group_preflight_candidate_output_path_ready=True`, `current_group_preflight_output_exists=False`, `current_group_preflight_wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-evidence-chain-status.ps1 -Mode Summary`: passed and returned the same suggested path inside `first_blocking_update_command_template`, `first_blocking_preflight_candidate_output_path_ready=True`, `first_blocking_preflight_output_exists=False`, `first_blocking_preflight_wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `Test-Path` for the suggested `FR-017-MEASUREMENTS-2026-07-06-PILOT-RECORD.json` path returned `False` after the read-only summary checks.
- `git diff --check -- scripts\fr017-measurement-session-brief.ps1 tests\test_fr017_measurement_session_brief_script.py tests\test_fr017_evidence_chain_status_script.py`: passed with only the existing PowerShell line-ending normalization warning.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this slice.

### 2026-07-06 21:03Z - FR-017 validation stack integrated for main

Current posture: Phase 2 / FR-017 Stage 17 is documentation-ready and evidence-container-ready, with physical validation still blocked. This is a `main` integration receipt for the FR-017 validation-support stack after replaying the Stage 17 code/test commits onto current `origin/main`. It does not create a measurement record, record pilot dimensions, mark physical validation complete, close Stage 17, approve load-bearing use, clear powered or frame-coupled use, or clear FR-018.

What changed:

- The current `main` integration head now includes the FR-017 measurement-session brief, evidence-chain status readback, measurement/landmark/independence updater paths, downstream non-powered evidence-record initializers, completion-ledger handoff/update review gates, and their FR-017 tests.
- The latest candidate measurement path handoff is preserved on top of current `origin/main`: Summary readbacks preflight the candidate path in read-only mode and show the same path in the visible `fr017-new-measurement-record.ps1 -Mode Create -OutputPath "..."` command template.
- Old branch ledger history was not replayed over `main`; this entry is the fresh integration receipt for the mainline push.

Validation actually run:

- PowerShell parser validation passed for all `scripts/fr017*.ps1` files in the integration worktree.
- `python -m py_compile` passed for all `tests/test_fr017*.py` files with `PYTHONPYCACHEPREFIX` redirected to a temp cache.
- `python -m ruff check tests/test_fr017*.py`: passed.
- `python -m ruff format --check tests/test_fr017*.py`: passed, 28 files already formatted.
- `git diff --check origin/main..HEAD -- FR-017_Stage17_Package scripts/fr017* tests/test_fr017*`: passed.
- Focused candidate-path pytest checks passed: `test_fr017_measurement_session_brief_preflights_candidate_measurement_path`, `test_fr017_measurement_session_summary_reports_candidate_path_readiness`, `test_fr017_evidence_chain_status_preflights_candidate_measurement_path`, and `test_fr017_evidence_chain_summary_reports_candidate_measurement_path_readiness`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-measurement-session-brief.ps1 -Mode Summary -CandidateMeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-2099-01-06-PILOT-RECORD.json`: passed and returned the candidate path inside `current_group_update_command_template`, `current_group_preflight_candidate_output_path_ready=True`, `current_group_preflight_output_exists=False`, `current_group_preflight_wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fr017-evidence-chain-status.ps1 -Mode Summary -CandidateMeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-2099-01-06-PILOT-RECORD.json`: passed and returned the candidate path inside `first_blocking_update_command_template`, `first_blocking_preflight_candidate_output_path_ready=True`, `first_blocking_preflight_output_exists=False`, `first_blocking_preflight_wrote_file=False`, `physical_validation_complete=False`, and `fr018_implementation_cleared=False`.
- `Test-Path -LiteralPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-2099-01-06-PILOT-RECORD.json`: returned `False` after the read-only summary checks.
- A full `tests/test_fr017*.py` pytest family run was started and manually stopped after 69 passing tests with no failure output; it is not counted as a full-family pass in this receipt.

Remaining blockers:

- FR-017 still requires a real accepted measurement record with setup/safety brief values, left/right dimensions, marked zones, repeatability, independence, and symptom-screen evidence before mockup patterning can truthfully proceed.
- Downstream non-powered mockup, mannequin/interface, pilot static-fit, pilot movement, quick-release/cable-snag, professional engineering review, final human physical decision, and operator-reviewed completion-ledger update evidence remain required before any Stage 17 completion claim.
- FR-018 remains blocked and not cleared by this integration.

### 2026-07-03 18:18Z - Developer bridge unreadable output guard and ledger archive checkpoint

Current posture: Phase 2 / developer bridge operator trust blocks a known class
of unreadable local-model output before it reaches the operator channel. The
archive tooling for the completion ledger is present and safety-checked.

What changed:

- `OllamaParticipant` routes conservative symbol-heavy, non-wordlike replies
  through existing fallback machinery as `unreadable_rewritten`.
- The fallback keeps the `Francis1 output guard fallback:` prefix so existing
  collaboration, body-map, and driver consumers keep their current guard path.
- `_output_guard_rewrote()` treats unreadable rewrites as guard rewrites so
  drift-learning and receipt paths remain observable.
- `scripts/archive-completion-ledger.ps1` and archive files under
  `docs/operations/archive/` preserve old ledger history outside the bounded
  main ledger.

Validation:

- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k unreadable_model_output` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k output_guard` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\developer_bridge\ollama_participant.py tests\test_developer_bridge.py` passed.
- `scripts\archive-completion-ledger.ps1 -Apply` ran after commit `43120459`.

Remaining truthful gap:

- This guard prevents non-linguistic local-model output from being relayed as a
  normal operator reply, but it does not repair an unhealthy Ollama model,
  corrupt model blob, or GPU-offload issue. If Francis1/qwen2.5:7b continues
  returning unreadable output, run `scripts/ollama-doctor.ps1` and treat any
  continued gibberish as a local runtime/model-health issue before changing the
  Francis relay path again.
- Live Ollama replay after an Ollama doctor run has not been performed.

### 2026-07-03 18:40Z - Lens summon hotkey collision readback

Current posture: Phase 2 / Lens summon-anywhere prerequisites now avoid the
known local Claude Desktop `Ctrl+Alt+Space` collision by configuring the Francis
summon chord as `Ctrl+Alt+F`. The hotkey binding path records owned or blocked
Win32 `RegisterHotKey` failure as a visible `hotkey_already_owned` runtime
receipt instead of flattening it to generic missing-runtime behavior.

What changed:

- `config/runtime/lens/summon.json` declares `Ctrl+Alt+F` for the primary summon
  hotkey.
- Lens proof scripts, API tests, and UI Lens contract fixtures expect the
  configured `Ctrl+Alt+F` chord instead of `Ctrl+Alt+Space`.
- `scripts/lens-hotkey-binding.ps1` writes `status=hotkey_already_owned`,
  `error=hotkey_already_owned`, `blocker=hotkey_already_owned`, the requested
  chord, and the Win32 error into `data/runtime/lens-hotkey/status.json` when
  `RegisterHotKey` fails.
- PowerShell Status mode and Python preflight/readiness readbacks preserve that
  blocked runtime state and report `choose_unclaimed_global_hotkey` as the next
  gap.
- OS-binding execution receipts surface `hotkey_already_owned` instead of
  generic `global_hotkey_binding_failed` when the child runner reports the
  owned-chord blocker.

Validation:

- PowerShell parser validation for `scripts\lens-hotkey-binding.ps1` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_hotkey_binding_script.py -q` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_api_lens_os_binding_authority.py -q` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_summon_preflight_script.py tests\test_lens_command_palette_os_binding_proof_script.py tests\test_lens_summon_global_hotkey_binding_blocker_proof_script.py tests\test_lens_summon_authority_blocker_proof_script.py tests\test_lens_summon_anywhere_blockers_proof_script.py -q` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_api_lens.py::test_lens_status_projects_readonly_stage6_contract -q` passed.
- `node --test --experimental-strip-types src/lens/index.test.ts` passed from `apps/chat_ui`.
- `rg "Ctrl\+Alt\+Space" config scripts src tests apps/chat_ui/src/lens` returned no matches.
- `git diff --check` passed for the touched Lens hotkey/readback files, with only existing line-ending warnings.

Remaining truthful gap:

- This checkpoint does not prove `Ctrl+Alt+F` is unclaimed on every operator
  machine; it makes the collision outcome explicit and receipt-backed if the
  chord is owned.
- The summon binding is still governed by the existing authority and enablement
  gates. This does not claim full summon-anywhere readiness or Stage 6 closure.
- Full `scripts\check.ps1`, CI, and a live successful `RegisterHotKey` session
  were not run in this checkpoint.

### 2026-07-03 19:05Z - Orb presence overlay and virtual-pointer readback

Current posture: Phase 2 / Stage 6 Lens Orb presence has a validated overlay
checkpoint. The live Orb can occupy the full virtual-screen plane, including
over the Windows taskbar, while retaining a small Orb-core hit target and
receipt-backed virtual-pointer movement. This does not enable summon-anywhere
or default-on tray/hotkey authority.

What changed:

- `scripts/lens-overlay-window.ps1` now hosts the overlay as the virtual-screen
  coordinate plane and pins the WPF window topmost with Win32 `SetWindowPos`.
- Orb movement uses in-window offsets inside the full-screen overlay plane, so
  the Orb can reach screen edges while the click box stays limited to the Orb
  core.
- Ctrl+M one-shot placement now arms a transparent capture window and starts
  smootherstep render-frame travel before writing the final position receipt.
- Right-click Orb controls now expose a small receipted panel for wake listen,
  push-to-talk, LLM handoff, ambient motion, and bounded Orb chat handoff.
- Continuous voice chat readback now reports `push_to_talk_ctrl_v_required`
  with `continuous_voice_chat_free_run=false`.
- `src/francis/lens/status.py` surfaces `orb.move` as a command-palette action
  with `Ctrl+M` as a trigger that carries no authority by itself.
- Overlay and Orb contract tests were updated to lock the new full-screen plane,
  small hit-box, smooth travel, right-click controls, and virtual-pointer
  receipts.

Validation:

- PowerShell parser validation for `scripts\lens-overlay-window.ps1` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_overlay_window_script.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\lens\status.py tests\test_lens_overlay_window_script.py` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-overlay-runtime-proof.ps1 -Mode Status -SupervisorRunSeconds 3 -ResidentSurfaceForegroundRunSeconds 2` passed after its built-in resident-surface retry.
- A main-root overlay stop/start cycle returned `stop_status=stopped`,
  `start_status=started`, and final status `visible` with runtime process alive.
- Live status readback after restart showed `overlay_runtime.overlay_window_visible=true`,
  `overlay_runtime.always_on_top=true`, `overlay_position.full_screen_overlay_plane=true`,
  `overlay_position.overlay_includes_taskbar=true`,
  `overlay_position.topmost_pin_applied=true`,
  `overlay_position.hit_test_passthrough_outside_click_box_enabled=true`,
  `click_hit_box_size=72`, and `reach_mode=full_screen_overlay_orb_offset`.
- `.venv\Scripts\python.exe -m pytest tests\unit\test_orb_operator.py tests\test_orb_phase0_contracts.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\input_actuator\orb_operator.py tests\unit\test_orb_operator.py tests\test_orb_phase0_contracts.py` passed.
- Live Orb pointer probe ran with `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=0`:
  move/click/type and move/click/drag/right-click sequences returned complete,
  final overlay Orb center was `(620, 640)`, newest overlay virtual-pointer
  receipts were present, `physical_input_performed=false`, and
  `user_mouse_taken=false`.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\lens-tray-presence-api-execution-proof.ps1 -Mode Status` passed in an isolated data root, proving the governed API can start and stop real tray presence after fixture-granted resident/tray authority.

Remaining truthful gap:

- Production summon-anywhere is still blocked by governed enablement and
  authority gates. The live proof did not self-enable summon, default-on tray,
  or hotkey registration.
- `scripts\lens-summon-preflight.ps1 -Mode Status` still reports missing
  production prerequisites in the `required_before_enable` chain:
  resident host process, tray presence, overlay window, global hotkey binding,
  and summon binding.
- The tray proof used an isolated data root and fixture authority, then stopped
  tray and resident supervision before returning. It does not claim production
  tray is now running by default.
- The desktop bridge still has no post-action observer; `desktop_effect_confirmed`
  remains a Milestone 3 gap.

### 2026-07-03 19:12Z - Orb desktop bridge post-action observer

Current posture: Phase 2 / Stage 6 Orb desktop bridge still remains gated behind
`FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=1`, but the bridge no longer has to report
every posted-message action as unconfirmed. It now records redacted target-side
state before and after posting messages and sets `desktop_effect_confirmed=true`
only when observable target-side state changes.

What changed:

- `src/francis/input_actuator/orb_desktop_bridge.py` records redacted before/after
  target observations for the resolved target window/control.
- The observer polls briefly after posting Win32 messages and reports
  `confirmed_target_state_changed` only on an observed state delta.
- Receipts include observer status, poll count, target-state changed flag, and
  redacted observation metadata without storing raw typed text.
- The bridge keeps the existing default-off gate, visible-only disabled path,
  and no user-cursor/no physical-input claims.
- Target resolution now rejects empty-title shell targets, the Francis Lens
  Overlay, Claude-titled windows, and common desktop shell window classes.
- Orb operator governance now propagates `desktop_effect_confirmed=true` when
  the bridge returns a confirmed effect.

Validation:

- `.venv\Scripts\python.exe -m ruff check src\francis\input_actuator\orb_desktop_bridge.py tests\unit\test_orb_desktop_bridge.py tests\unit\test_orb_operator.py` passed.
- `.venv\Scripts\python.exe -m pytest tests\unit\test_orb_desktop_bridge.py tests\unit\test_orb_operator.py -q` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\orb-operator-dry-run.ps1 -X 410 -Y 360 -Text "Milestone 3 dry run proof"` passed.
- A live orb-pointer probe with `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=0` returned
  `status=complete`, last action `visible_only`, bridge status
  `blocked_bridge_disabled`, `desktop_action_sent=false`,
  `desktop_effect_performed=false`, and `desktop_effect_confirmed=false`.

Remaining truthful gap:

- The observer confirmation path is proven with a fake Win32 target in unit
  tests, not by enabling the production bridge against a live operator-approved
  app window.
- The bridge remains default-off. A live enabled bridge proof must use an
  explicit operator-approved safe target and must still exclude Francis Lens
  Overlay and Claude windows.
- This does not complete the final visible-loop acceptance test; that still
  needs hotkey summon, operator-approved safe target action, confirmed effect,
  receipt, trace, and Lens/chat visibility in one repeatable runner.

### 2026-07-03 19:32Z - Francis1 voice replay blocker after Ollama doctor

Current posture: Phase 2 / Orb embodiment Milestone 4 is blocked on local
Ollama model/runtime health, not on raw unreadable output leaking through the
developer bridge. The doctor now writes a bounded health report, and the
Francis1 reply lane still rewrites unreadable model output instead of relaying
symbol salad to the operator.

What changed:

- `scripts/ollama-doctor.ps1` now bounds external CLI probes with
  `CommandTimeoutSec` and returns timeout details instead of waiting forever.
- The doctor helper no longer uses a parameter named `Args`, avoiding collision
  with PowerShell's automatic `$args` variable when launching `ollama list`,
  `ollama ps`, and related probes.
- Doctor probe collections that are later counted are normalized to arrays under
  strict mode, and Event Log/process snapshots are best-effort so inaccessible
  local fields do not abort report export.
- `tests/test_ollama_doctor_script.py` locks the bounded command, strict-mode
  array, Event Log, process snapshot, and report-construction contracts.

Validation:

- PowerShell parser validation for `scripts\ollama-doctor.ps1` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_ollama_doctor_script.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_ollama_doctor_script.py` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\ollama-doctor.ps1 -Tag ollama_doctor_m4 -CommandTimeoutSec 5` completed and wrote:
  `data\logs\operations\ollama_doctor\ollama_doctor_m4_20260703_142950.log`,
  `.json`, and `_checks.csv`.
- The doctor check summary was 10 PASSED, 3 WARN, 2 SKIPPED, and 0 FAILED. API
  `/api/version` and `/api/tags` passed; `ollama list`, `ollama ps`, port 11434,
  process detection, model paths, model size scan, and `nvidia-smi` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k unreadable_model_output` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k output_guard` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\developer_bridge\ollama_participant.py tests\test_developer_bridge.py` passed.
- A live operator-scoped Francis1 status replay submitted prompt
  `collab-4d494e2aee18f190-ebb96481b08b` and received response
  `collab-52e42facbda0a874-4d30a811637e` with
  `output_guard_status=unreadable_rewritten`.

Remaining truthful gap:

- The Milestone 4 readable status reply requirement is not met. After a completed
  Ollama doctor run, the live Francis1/qwen2.5:7b lane still produced unreadable
  non-linguistic output.
- The forced-garbage fallback path is validated, and the live relay did not leak
  raw salad into the operator response. That is not equivalent to a healthy
  natural Francis1 reply.
- Treat the remaining blocker as local model blob/runtime/GPU-offload health
  until a new live operator-scoped status replay returns a readable reply. Do
  not proceed to the one-visible-loop acceptance proof on this evidence.

### 2026-07-03 19:47Z - Francis1 voice replay readability repair proof

Current posture: Phase 2 / Orb embodiment Milestone 4 now has a repeatable
Francis1/Ollama replay proof. The unhealthy primary local chat model is still
truthfully observed, but the developer bridge can recover a readable operator
reply through a same-provider fallback while preserving the unreadable-output
guard for forced garbage.

What changed:

- `src/francis/developer_bridge/ollama_participant.py` now performs a bounded
  readability repair after the primary Ollama response and before the output
  guard fallback.
- When primary output is unreadable, the participant retries same-provider local
  fallback models, defaulting to the already-installed `llama3.2:3b`.
- The execution trace records `readability_repair.status`, primary output
  quality metrics, fallback model attempts, and whether a readable fallback was
  used without storing raw unreadable primary output.
- Relay context explicitly states when same-provider readability repair was used.
- If all fallback attempts are still unreadable, the existing
  `unreadable_rewritten` output-guard fallback remains the operator-visible
  result.
- `scripts/francis1-ollama-replay-proof.ps1` now runs the repeatable Milestone 4
  proof: live operator-scoped status replay plus isolated forced-garbage
  injection.

Validation:

- Direct bounded Ollama probe showed `francis-chat`, `francis-chat:latest`, and
  `qwen2.5:7b-instruct` returned unreadable symbol-heavy output for a simple
  English prompt, while `llama3.2:3b` returned readable English.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k "unreadable_model_output or readable_same_provider_fallback"` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k output_guard` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\developer_bridge\ollama_participant.py tests\test_developer_bridge.py` passed.
- PowerShell parser validation for `scripts\francis1-ollama-replay-proof.ps1`
  passed.
- `.venv\Scripts\python.exe -m pytest tests\test_francis1_ollama_replay_proof_script.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_francis1_ollama_replay_proof_script.py` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\francis1-ollama-replay-proof.ps1 -Mode Status -TimeoutSeconds 180` passed and wrote
  `data\logs\operations\francis1_ollama_replay_proof\francis1_ollama_replay_proof_20260703_144349.json`.
- The live proof submitted prompt `collab-bcaaf1147e93045a-8a8bf44b1b27` and
  received response `collab-561e281a6cc4b49e-7aa0ec9c1ce4` with
  `readable_reply_observed=true`, `readability_repair_status=readable_fallback_used`,
  `fallback_model_used=llama3.2:3b`, and `output_guard_status=not_applicable`.
- The forced-garbage proof submitted prompt `collab-047eba3f1dafd02e-84b74b5bee49`
  and received response `collab-dde08072831020a1-dcc41782960b` with
  `fallback_rewritten_observed=true`, `output_guard_status=unreadable_rewritten`,
  and `raw_garbage_leaked=false`.

Remaining truthful gap:

- The primary `francis-chat` model still appears unhealthy in this local runtime.
  The live readable reply is recovered through same-provider fallback
  `llama3.2:3b`, not proof that the primary model blob/GPU-offload path is fixed.
- The proof does not grant execution, mutation, training, or memory-write
  authority. It closes the voice replay proof requirement only.
- The one-visible-loop acceptance proof remains unbuilt and unproven.

### 2026-07-03 20:01Z - One visible loop proof gate

Current posture: Phase 2 / Orb embodiment Milestone 5 now has a repeatable proof
gate and presentation-demo integration. This is not final acceptance: the proof
truthfully remains blocked until Austin approves the summon enable decision and a
live safe-target desktop bridge action.

What changed:

- `scripts/francis-one-visible-loop-proof.ps1` now runs the one-visible-loop
  status proof: summon preflight, overlay/orb presence readback, optional
  operator-approved fixture safe-target action, receipt/trace/status paths, and
  explicit governance fields.
- The proof treats summon as blocked unless the required-before-enable chain is
  clear and `-OperatorApprovedSummonDecision` is passed. It does not self-enable
  summon.
- The fixture safe-target path enables `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=1`
  only inside the proof process, uses a fake safe Win32 target, and proves the
  post-action observer path with `desktop_effect_confirmed=true`.
- `scripts/francis-presentation-demo.ps1` can include the proof with
  `-IncludeOneVisibleLoopProof` and now surfaces the proof path, operator
  receipt path, desktop bridge receipt path, desktop confirmation, observer
  status, and chat/Lens render flags.

Validation:

- PowerShell parser validation passed for
  `scripts\francis-one-visible-loop-proof.ps1`.
- PowerShell parser validation passed for `scripts\francis-presentation-demo.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py`
  passed.
- Default one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_145744326.json`
  with `status=blocked`, `overlay_window_visible=true`,
  `reach_mode=full_screen_overlay_orb_offset`, and action `status=blocked`.
- Fixture safe-target one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_150058037.json`
  with proof `status=blocked`, action `status=passed`,
  `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-200057.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`,
  action `status=passed`, `desktop_effect_confirmed=true`, and the desktop
  bridge receipt path
  `.francis\one-visible-loop\20260703_150058037\orb_operator\desktop_bridge_receipts\orb_desktop_bridge_cf1feb79dc4c.json`.

Remaining truthful gap:

- The final Milestone 5 acceptance loop is still not complete. The proof gate
  does not show a real global-hotkey summon from anywhere, does not enable
  summon, does not perform a live operator-approved safe-target desktop bridge
  action, and does not verify that receipt, trace, and status are actually
  rendered in the chat/Lens UI.
- The next operator decision is singular: approve the summon enable flip and a
  live safe-target desktop bridge proof, or leave the proof in blocked status.

### 2026-07-03 20:07Z - Summon preflight live overlay readback

Current posture: Phase 2 / Orb embodiment Milestone 5 still remains blocked, but
the summon prerequisite readback is now narrower and more truthful. The live
overlay window is no longer reported as missing when its runtime state proves a
visible topmost overlay.

What changed:

- `scripts/lens-summon-preflight.ps1` now reads live tray and overlay runtime
  state from `data\runtime\lens-tray\status.json` and
  `data\runtime\lens-overlay\status.json`.
- The `overlay_window` required-before-enable dependency now becomes ready only
  when a live `lens.overlay.runtime_state` process reports
  `overlay_running`, `overlay_window_visible=true`, and `always_on_top=true`.
- The `tray_presence` dependency now has the same runtime-readback contract used
  by `scripts\lens-tray-presence.ps1`: matching live PID, `tray_running`, and
  `tray_icon_visible=true`.
- The preflight preserves the existing missing/blocker names for absent
  prerequisites, but adds runtime readback details and source fields so the
  proof can distinguish ready, stale, and missing states.

Validation:

- PowerShell parser validation passed for `scripts\lens-summon-preflight.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_summon_preflight_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_lens_summon_preflight_script.py`
  passed.
- Live summon preflight now reports `overlay_ready=true`,
  `overlay_state=visible_topmost`, and missing prerequisites
  `resident_host_process,tray_presence,global_hotkey_binding,summon_binding`.
- Default one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_150706740.json`
  with summon missing
  `resident_host_process,tray_presence,global_hotkey_binding,summon_binding`,
  `overlay_window_visible=true`, and action `status=blocked`.
- Fixture safe-target one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_150715329.json`
  with action `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-200814.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`,
  action `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.

Remaining truthful gap:

- Milestone 5 is still not accepted. The remaining summon blockers are resident
  host process supervision, tray presence, global hotkey binding, and summon
  binding.
- Live runtime also shows stale/mismatched hotkey state: the persisted hotkey
  runtime status still reports `Ctrl+Alt+Space` while summon config now expects
  `Ctrl+Alt+F`. Do not treat summon-anywhere as ready until the runtime binding
  is refreshed and proven under the new chord.
- The final operator decision remains unchanged: Austin must approve the summon
  enable flip and a live safe-target desktop bridge proof.

### 2026-07-03 20:14Z - Summon stale hotkey chord readback

Current posture: Phase 2 / Orb embodiment Milestone 5 still remains blocked, but
the hotkey part of the summon prerequisite chain now exposes the exact stale
runtime chord mismatch inside both summon preflight and the one-visible-loop
proof artifact.

What changed:

- `scripts/lens-summon-preflight.ps1` now compares the runtime hotkey receipt's
  `global_hotkey` and `binding_scope` against the configured expected values.
- Stale or live mismatched hotkey state is reported as
  `global_hotkey_binding_stale_mismatched_chord` instead of only the generic
  `global_hotkey_binding_runtime_missing`.
- The hotkey readback now includes `global_hotkey_matches_expected` and
  `binding_scope_matches_expected` fields.
- `scripts/francis-one-visible-loop-proof.ps1` now carries the summon preflight
  hotkey, tray, and overlay runtime readbacks under its `summon` object so the
  acceptance artifact itself explains the current blockers.

Validation:

- PowerShell parser validation passed for `scripts\lens-summon-preflight.ps1`.
- PowerShell parser validation passed for
  `scripts\francis-one-visible-loop-proof.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_summon_preflight_script.py tests\test_francis_one_visible_loop_proof_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_lens_summon_preflight_script.py tests\test_francis_one_visible_loop_proof_script.py`
  passed.
- Live summon preflight reports `hotkey_state=stale_mismatched_hotkey`,
  `hotkey_blocker=global_hotkey_binding_stale_mismatched_chord`,
  `hotkey_actual=Ctrl+Alt+Space`, and `hotkey_expected=Ctrl+Alt+F`.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_151426754.json`
  with summon missing
  `resident_host_process,tray_presence,global_hotkey_binding,summon_binding`,
  `overlay_ready=true`, action `status=passed`,
  `desktop_effect_confirmed=true`, and the stale hotkey readback above.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-201426.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`, action
  `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.

Remaining truthful gap:

- Milestone 5 is still not accepted. The hotkey runtime must be refreshed and
  proven under `Ctrl+Alt+F` after the proper authority path; the current runtime
  receipt is stale and still names `Ctrl+Alt+Space`.
- The proof still does not show a real global-hotkey summon from anywhere,
  Austin's enable approval, a live safe-target bridge action, or chat/Lens UI
  receipt/trace/status render verification.

### 2026-07-03 20:43Z - Stage 6 completion audit watchdog receipt

Current posture: Phase 2 / Orb embodiment Milestone 5 remains blocked, but the
Stage 6 completion-audit handoff now has a bounded visible receipt instead of an
unbounded wait when nested proof review exceeds the caller's budget.

What changed:

- `scripts/lens-stage6-completion-audit.ps1` now wraps normal audit execution in
  an outer watchdog unless explicitly running as its watchdog child.
- The watchdog preserves normal audit JSON when the child finishes, and returns a
  structured blocked receipt with `audit_status=timed_out`,
  `stage6_completion_audit_timeout`, child stdout/stderr capture paths, and
  `none_new_stage6_completion_audit` authority when the budget expires.
- Timeout handling kills the child process tree and reports the non-mutating
  governance posture instead of leaving the operator with a silent hang.
- `tests/test_lens_stage6_completion_audit_script.py` now asserts the watchdog
  receipt contract and passes the computed full-audit budget into the opt-in
  full audit harness so that explicit full runs are not undercut by the default
  watchdog.

Validation:

- PowerShell parser validation passed for
  `scripts\lens-stage6-completion-audit.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  passed with the existing full live audit skipped unless explicitly enabled.
- `.venv\Scripts\python.exe -m ruff check tests\test_lens_stage6_completion_audit_script.py`
  passed.
- Live bounded audit proof
  `.\scripts\lens-stage6-completion-audit.ps1 -Mode Status -OverallTimeoutSeconds 5 -ChildProofTimeoutSeconds 30`
  returned a blocked timeout receipt in about five seconds with
  `audit_status=timed_out`, `recommended_next_slice=bound_stage6_completion_audit_child_proofs_before_replay`,
  and `watchdog_killed_child_process_tree=true`.
- No leftover `lens-stage6-completion-audit.ps1` child process was observed after
  the timeout proof.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_154255868.json`
  with overlay `visible/topmost`, action `status=passed`,
  `desktop_effect_confirmed=true`, and an honest blocked summon state.

Remaining truthful gap:

- Milestone 5 is still not accepted. The repeatable proof still lacks a real
  global-hotkey summon from anywhere, Austin's enable approval, a live
  safe-target bridge action, and chat/Lens UI receipt/trace/status render
  verification.
- The audit watchdog bounds operator feedback; it does not itself satisfy
  resident host, tray presence, refreshed `Ctrl+Alt+F` hotkey binding, summon
  binding, or the final enable authority.

### 2026-07-03 20:49Z - Live tray prerequisite restored

Current posture: Phase 2 / Orb embodiment Milestone 5 remains blocked, but the
live tray prerequisite is restored and the latest one-visible-loop artifact now
shows tray and overlay ready together.

What changed:

- Runtime-only recovery stopped the stale hotkey receipt and cleared the old
  `Ctrl+Alt+Space` runtime claim without registering the summon hotkey.
- Runtime-only recovery started the Lens tray presence process; summon remains
  disabled and no desktop bridge default was changed.
- The one-visible-loop fixture proof was refreshed so its summon readback now
  shows `tray_presence` ready and the remaining missing requirements narrowed to
  `resident_host_process`, `global_hotkey_binding`, and `summon_binding`.

Validation:

- `.\scripts\lens-hotkey-binding.ps1 -Mode Stop` returned `status=stopped`,
  `global_hotkey=Ctrl+Alt+F`, `launch_on_hotkey=false`, and no summon authority.
- `.\scripts\lens-tray-presence.ps1 -Mode Start -StartupTimeoutSeconds 10`
  returned `status=started`, `tray_presence=true`, `tray_icon_visible=true`,
  and live PID `4520`.
- `.\scripts\lens-summon-preflight.ps1 -Mode Status` reported
  `missing_required_before_enable=resident_host_process,global_hotkey_binding,summon_binding`,
  `tray_ready=true`, `overlay_ready=true`, and
  `hotkey_blocker=global_hotkey_binding_runtime_missing`.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_154928970.json`
  with tray `ready=true`, overlay `ready=true`, action `status=passed`,
  `desktop_effect_confirmed=true`, and an honest blocked summon state.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-205157.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`, action
  `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.
- `.\scripts\lens-host-supervisor.ps1 -Mode Status` still reports
  `resident_supervised_runtime=false`,
  `authority_required=process_supervision_authority`, and
  `authority_granted=false`.

Remaining truthful gap:

- Milestone 5 is still not accepted. Resident supervision still requires a
  process-supervision authority path, the global hotkey binding and summon
  binding remain disabled/missing pending authority, and final live acceptance
  still requires Austin's enable approval plus a live safe-target bridge proof
  and chat/Lens UI render verification.

### 2026-07-03 20:59Z - One visible loop operator decision queue

Current posture: Phase 2 / Orb embodiment Milestone 5 remains blocked, but the
repeatable one-visible-loop proof now surfaces the exact next Austin decision
instead of only a generic enable reminder.

What changed:

- `scripts/francis-one-visible-loop-proof.ps1` now reads live resident-host
  supervisor status and adds an `operator_decision_queue` object to the proof.
- The queue emits exactly one decision from the first live missing summon
  prerequisite. In the current environment that is
  `approve_resident_host_process_supervision_authority_request`.
- The queued decision names the required authority
  `process_supervision_authority`, the exact next request command, and explicit
  non-granting/non-executing flags.
- `scripts/francis-presentation-demo.ps1` now carries the one-visible-loop
  decision status, question, command, required authority, and self-grant state
  into the JSON summary and Markdown report.

Validation:

- PowerShell parser validation passed for
  `scripts\francis-one-visible-loop-proof.ps1` and
  `scripts\francis-presentation-demo.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py`
  passed.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_155647543.json`
  with `operator_decision_queue.status=operator_decision_required`,
  `queued_decision_count=1`,
  `authority_required=process_supervision_authority`,
  `script_would_execute=false`, `script_would_grant_authority=false`, and
  `self_granted=false`.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-205850.json`
  with the same operator decision question and command surfaced in the summary,
  while remaining honestly blocked by `one_visible_loop_proof_blocked`.

Remaining truthful gap:

- Milestone 5 is still not accepted. Austin has not approved the resident-host
  process-supervision authority path, the global hotkey binding and summon
  binding remain missing, and final live acceptance still requires Austin's
  enable approval, a live safe-target bridge proof, and chat/Lens UI render
  verification.

### 2026-07-03 21:06Z - One visible loop visibility contract readback

Current posture: Phase 2 / Orb embodiment Milestone 5 remains blocked, but the
proof no longer collapses artifact paths, UI contract surfacing, and live render
verification into one vague visibility claim.

What changed:

- `scripts/francis-one-visible-loop-proof.ps1` now emits
  `chat_lens_visibility.status=ui_contract_visible_render_unverified` when the
  proof artifact path, operator receipt path, desktop bridge receipt path,
  Lens status contract, Lens status tests, and presentation-demo summary fields
  are all present.
- The proof keeps `actual_chat_ui_render_verified=false` and
  `actual_lens_ui_render_verified=false` until a browser or live chat/Lens UI
  render proof is run.
- `scripts/francis-presentation-demo.ps1` now carries the visibility contract
  status, artifact-path presence, Lens contract flags, and render-validation
  requirement into the JSON summary and Markdown report.

Validation:

- PowerShell parser validation passed for
  `scripts\francis-one-visible-loop-proof.ps1` and
  `scripts\francis-presentation-demo.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py`
  passed.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_160616943.json`
  with `desktop_effect_confirmed=true`,
  `chat_lens_visibility.status=ui_contract_visible_render_unverified`,
  `receipt_trace_artifact_paths_present=true`,
  `lens_status_contract_verified=true`,
  `lens_status_test_contract_verified=true`,
  `presentation_demo_contract_verified=true`,
  and both actual render flags false.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-210623.json`
  with the same visibility contract fields while remaining honestly blocked by
  `one_visible_loop_proof_blocked`.

Remaining truthful gap:

- Milestone 5 is still not accepted. The proof now shows that receipt/trace
  artifacts and Lens/chat contracts are surfaced, but final acceptance still
  requires resident-host supervision authority, refreshed `Ctrl+Alt+F` hotkey
  binding, summon binding, Austin's enable approval, a live safe-target bridge
  proof, and browser/live chat/Lens render verification.

### 2026-07-09 14:51Z - Stage 6 summon checkpoint no-blocker audit handoff

Current posture: Phase 2 / Orb embodiment Milestone 5 remains blocked, but the
Stage 6 completion audit no longer treats a live ready summon-enable gate as a
missing blocked-handoff proof.

What changed:

- `scripts/lens-stage6-checkpoint.ps1` now emits a read-only
  `no_blocker_family_remaining` handoff when live `/lens/status` reports the
  summon enablement gate ready, `summon_anywhere=true`, operator-surface
  readback ready, and no blocker families, family handoffs, or blockers.
- `scripts/lens-stage6-completion-audit.ps1` now accepts that ready/no-blocker
  checkpoint shape and advances the audit to the next readback boundary instead
  of reopening `checkpoint_summon_enablement_gate_handoff`.
- Empty JSON list fields are normalized for both string arrays and handoff
  object arrays, so empty `blocked_families`, `blocked_family_handoffs`, and
  `blockers` are not misread as one empty object or `$null`.
- The slow persistent-supervision transition proof and checkpoint wrapper now
  have bounded child-proof budgets that let the audit return a complete receipt.

Validation:

- PowerShell parser validation passed for
  `scripts\lens-stage6-checkpoint.ps1` and
  `scripts\lens-stage6-completion-audit.ps1`.
- `.venv\Scripts\python.exe -m pytest` passed for the focused Stage 6
  checkpoint/audit tests covering the ready no-blocker handoff, empty-object
  normalization, checkpoint timeout budgeting, and transition-plan budgeting.
- `.venv\Scripts\python.exe -m ruff check` and
  `.venv\Scripts\python.exe -m ruff format --check` passed for the two touched
  Stage 6 test files.
- `git diff --check` passed for the touched Stage 6 scripts and tests, with
  only existing PowerShell line-ending warnings.
- Direct checkpoint readback returned `ok=true`, `handoff_status=ready_for_operator_review`,
  `no_blocker_family_handoff_observed=true`,
  `no_blocker_handoff_status=no_blocker_family_remaining`,
  zero blocker-family counts after JSON readback, and
  `handoff_next_gap=stage6_lens_completion_audit`.
- Full completion audit returned `ok=true`, `status=blocked`,
  `audit_status=complete`, `checkpoint_handoff=true`,
  `checkpoint_no_blocker_handoff=true`, `child_proof_timeouts=[]`,
  `resident_supervised_runtime=true`, supervisor PID `35400`, resident PID
  `37520`, and
  `next_smallest_truthful_gap=persistent_supervision_prerequisites_proof_readback`.

Remaining truthful gap:

- Milestone 5 is still not accepted. The completion audit is still blocked by
  missing `stage6_closure_readback`, `persistent_supervision_prerequisites_proof`,
  `summon_authority_blocker_proof`, and `summon_anywhere_family_chain_proof`.
  The current first reported gap is
  `persistent_supervision_prerequisites_proof_readback`.

## 5. Known truthful gaps

These still block any finished Orb embodiment claim:

- Summon: the final enable flip is not granted. Austin must explicitly approve
  the operator-authority decision before summon-anywhere can be enabled.
- Orb presence: overlay window, Ctrl+M one-shot placement, right-click controls,
  Ctrl+V gated voice readback, virtual pointer gestures, and host restart now
  have focused and live proof. Production summon/dismiss/tray integration still
  waits on governed resident, tray, hotkey, and summon authority.
- Desktop bridge: post-action observer support exists and can produce
  `desktop_effect_confirmed=true` when target-side state changes. The remaining
  gap is a live operator-approved safe-target proof with the bridge explicitly
  enabled; the bridge remains default-off.
- Voice: `scripts/ollama-doctor.ps1` now completes, forced-garbage injection
  rewrites to `unreadable_rewritten` without raw salad, and the live Francis1
  status replay now returns readable output through same-provider fallback
  `llama3.2:3b`. The primary `francis-chat` model remains unhealthy and should
  be repaired separately, but Milestone 4 replay proof is now present.
- One visible loop: a repeatable proof gate now exists and proves fixture
  safe-target desktop confirmation. The summon preflight now consumes live
  overlay readback and no longer reports `overlay_window` as missing while the
  overlay is visible/topmost. Final acceptance remains blocked by resident host,
  refreshed `Ctrl+Alt+F` hotkey binding, summon binding, Austin's approval for
  the resident-host supervision path, the enable flip/live safe-target action,
  and chat/Lens UI receipt/trace/status visibility.

## 6. Update rule

Update this ledger only when at least one of the following is true:

- a validated surface materially changed
- a plane posture changed in a way that is now directly inspectable
- a major blocker was removed
- the latest evidence set changed and should replace stale validation claims
