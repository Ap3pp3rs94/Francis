# FR-017 Stage 17 Package Index

FRANCIS status: Stage 17 documentation and evidence containers are packaged. Physical validation remains pending.

## Package Scope

This directory supports `FRANCIS_FR-017_Forearm_Cuffs_v1.0`.

It packages FR-017 Forearm Cuffs as a documentation-ready and test-record-ready stage without claiming fabrication, fit, mannequin, pilot, powered, load, or professional engineering validation.

## Current Stage Gate

- Documentation: COMPLETE.
- Evidence records: CREATED AS PENDING CONTAINERS.
- Physical validation: NOT COMPLETE.
- Powered/frame-coupled testing: NOT CLEARED.
- FR-018 implementation: NOT CLEARED.

## Read-Only Gate Commands

- `scripts/fr017-stage17-validation-gate.ps1 -Mode Status`: package and manifest structure.
- `scripts/fr017-measurement-intake.ps1 -Mode Status`: measurement intake status plus the read-only `measurement_capture_plan` for the first physical-input gate.
- `scripts/fr017-measurement-session-brief.ps1 -Mode Status`: full read-only operator brief for the current measurement session blocker; summarizes the next capture group, stop conditions, and no-fake-validation locks without writing evidence. Use `-Mode Summary` for the compact current-group handoff without the full contracts or operator sequence.
- `scripts/fr017-mockup-readiness-gate.ps1 -Mode Status`: mockup readiness status plus the read-only `mockup_capture_plan` for the non-powered cuff mockup gate.
- `scripts/fr017-mannequin-interface-gate.ps1 -Mode Status`: mannequin interface status plus the read-only `mannequin_capture_plan` for the non-powered future-interface clearance gate.
- `scripts/fr017-pilot-static-fit-gate.ps1 -Mode Status`: pilot static-fit status plus the read-only `static_fit_capture_plan` for the non-powered pilot static-fit gate.
- `scripts/fr017-pilot-movement-gate.ps1 -Mode Status`: pilot movement status plus the read-only `movement_capture_plan` for the non-powered pilot movement gate.
- `scripts/fr017-quick-release-cable-snag-gate.ps1 -Mode Status`: quick-release/cable-snag status plus the read-only `release_cable_capture_plan` for the non-powered release-access and cable-snag gate.
- `scripts/fr017-engineering-review-gate.ps1 -Mode Status`: professional review status plus the read-only `engineering_review_capture_plan` after quick-release/cable-snag evidence.
- `scripts/fr017-evidence-chain-status.ps1 -Mode Status`: full first-blocking FR-017 evidence gate payload, next required input, and current capture-plan details where applicable. Use `-Mode Summary` for a compact read-only operator handoff with the same blocked-clearance locks and no full `gate_results` payload.
- `scripts/fr017-final-physical-gate.ps1 -Mode Status`: final evidence-chain aggregate status plus the read-only `final_physical_decision_plan`; does not mark physical validation complete or clear FR-018 by itself.
- `scripts/fr017-final-decision-record-gate.ps1 -Mode Status`: human final decision record validation after final physical gate readiness; does not mark physical validation complete, permit a Stage 17 completion claim, or clear FR-018 by itself.
- `scripts/fr017-completion-ledger-gate.ps1 -Mode Status`: read-only candidate completion-ledger entry review after final decision readiness using `FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md`; use `scripts/fr017-new-completion-ledger-handoff.ps1 -Mode Create` only to create the candidate handoff file. Neither script writes the ledger, marks physical validation complete, permits a Stage 17 completion claim, or clears FR-018 by itself.
- `scripts/fr017-completion-ledger-update-gate.ps1 -Mode Status`: read-only review of an actual or proposed `docs/operations/COMPLETION_LEDGER.md` update after the candidate handoff is ready; verifies the matching FR-017 section preserves final-decision evidence references and no-clearance language. It does not write the ledger, mark physical validation complete, permit a Stage 17 completion claim, or clear FR-018 by itself.

## Files

| File | Purpose | Current validation state |
| --- | --- | --- |
| `FR-017-MEASUREMENTS-LEFT-RIGHT_PENDING.md` | Left/right measurement capture record | REQUIRES MEASUREMENT |
| `FR-017-MEASUREMENTS-INPUT-TEMPLATE.json` | Structured measurement intake template | COMPLETE |
| `FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md` | First physical-input measurement capture sequence | COMPLETE RUNBOOK, NOT EVIDENCE |
| `FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json` | Structured non-powered mockup build template | COMPLETE |
| `FR-017-MAPS-AND-LAYOUTS.md` | Consolidated map and layout rollup | DOCUMENTED / PROVISIONALLY DEFINED |
| `FR-017-ADJUSTMENT-WORKSHEET_PENDING.md` | Strap, pad, release, and cable adjustment record | REQUIRES PILOT STATIC TEST |
| `FR-017-FIT-2026-06-23-LEFT_PENDING.md` | Left cuff fit and safety record | REQUIRES PILOT STATIC TEST / MOVEMENT TEST |
| `FR-017-FIT-2026-06-23-RIGHT_PENDING.md` | Right cuff fit and safety record | REQUIRES PILOT STATIC TEST / MOVEMENT TEST |
| `FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json` | Structured pilot static fit input template | COMPLETE |
| `FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json` | Structured pilot movement fit input template | COMPLETE |
| `FR-017-MANNEQUIN-INTERFACE-TEST_PENDING.md` | Mock frame/wrist/glove/armor interface check | REQUIRES MANNEQUIN TEST |
| `FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json` | Structured mannequin interface test input template | COMPLETE |
| `FR-017-QUICK-RELEASE-TEST_PENDING.md` | Release access and removal proof record | REQUIRES PILOT STATIC TEST / MANNEQUIN TEST |
| `FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json` | Structured quick-release and cable-snag input template | COMPLETE |
| `FR-017-ENGINEERING-REVIEW_PENDING.md` | Professional engineering review record | REQUIRES PROFESSIONAL ENGINEERING REVIEW |
| `FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json` | Structured engineering review input template | COMPLETE |
| `FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json` | Structured human final physical decision input template | COMPLETE, REQUIRES REAL RECORD REVIEW |
| `FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md` | Candidate completion-ledger handoff template | COMPLETE TEMPLATE, NOT EVIDENCE |
| `FR-017-VALIDATION-GATE-CHAIN.md` | Read-only gate order and no-fake-validation runbook | COMPLETE |
| `FR-017-INTERFACE-MATRIX.md` | Adjacent FR interface compatibility review | PROVISIONALLY DEFINED |
| `FR-017-COMPLETION-GATE-2026-06-23.md` | Stage 17 completion decision record | DOCUMENTED, PHYSICAL GATE BLOCKED |
| `FR-017-STAGE17-FINAL-AUDIT-2026-06-23.md` | Final Stage 17 closeout audit | COMPLETE, PHYSICAL GATE BLOCKED |
| `FR-017-STAGE17-PACKAGE-MANIFEST.json` | Machine-readable package manifest | COMPLETE |
| `FR-IMG-017_PROMPT.md` | Final technical image prompt | DOCUMENTED |

## Evidence Rule

Do not convert any `PENDING` record to `PASS` unless the record contains:

- date
- test article revision
- left/right side identifier
- observer name
- objective result
- fail-condition review
- photos or measurement references where applicable
- explicit remaining limitations

Any numbness, tingling, cold fingers, discoloration, hand weakness, wrist pain, sharp pressure, reduced finger motion, loss of grip strength, trapped glove/wrist assembly, or unreachable release is `FAILED / REQUIRES REDESIGN`.

## First Physical-Input Handoff

Run `scripts/fr017-measurement-intake.ps1 -Mode Status` before entering pilot data, or run `scripts/fr017-measurement-session-brief.ps1 -Mode Status` when the operator needs the current first blocking capture group and stop-condition summary. Then use `scripts/fr017-new-measurement-record.ps1 -Mode Status`, or `scripts/fr017-new-measurement-record.ps1 -Mode Summary` for compact path-readiness and next-create-command readback, as a read-only initializer preflight before `scripts/fr017-new-measurement-record.ps1 -Mode Create` and `FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md` with `FR-017-MEASUREMENTS-INPUT-TEMPLATE.json` for the real left/right measurement record. The initializer can also capture explicitly supplied setup/safety-brief fields, but those fields can only make `setup_and_safety_brief` ready; they do not replace left/right measurements, marked zones, repeatability, independence checks, or symptom screening. Use `scripts/fr017-update-measurement-setup-record.ps1 -Mode UpdateSetup` only to write real operator-supplied setup and safety-brief fields, `scripts/fr017-update-measurement-record.ps1 -Mode UpdateSide` only to write real operator-supplied left/right numeric measurement passes, `scripts/fr017-update-landmark-record.ps1 -Mode UpdateLandmarks` only to write real marked-zone references and landmark confirmations, and `scripts/fr017-update-independence-safety-record.ps1 -Mode UpdateIndependenceSafety` only to write real left/right independence confirmations and safety-screen values into that working record. The intake gate remains the authority for readiness and rejects unsafe, copied, incomplete, or ambiguous values. The returned `measurement_capture_plan` is the operator-facing capture order for the first FR-017 physical-input gate, `measurement_capture_plan_status` reports which capture groups are still pending, invalid, or blocked for the supplied record, and `measurement_capture_first_blocking_group_id` identifies the next group requiring work. These fields, the measurement-session brief, initializer, updaters, and runbook are not completion evidence; they cannot mark physical validation complete, clear powered or frame-coupled testing, or clear FR-018.

After measurement intake reports `ready_for_non_powered_mockup_patterning`, run `scripts/fr017-mockup-readiness-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json>` before building or recording the non-powered mockup. Use `scripts/fr017-new-mockup-record.ps1 -Mode Create` only to create a real operator-supplied non-powered mockup working record linked to the same completed measurement record. The returned `mockup_capture_plan` groups the mockup evidence, material stack, global safety constraints, and left/right side checks; `mockup_capture_first_blocking_group_id` identifies the next mockup capture group requiring work. These fields, the mockup template, and the mockup initializer are operator input tooling only and are not physical validation completion, mannequin test completion, pilot testing clearance, powered testing clearance, frame-coupled testing clearance, or FR-018 clearance.

After mockup readiness reports `ready_for_mannequin_interface_test`, run `scripts/fr017-mannequin-interface-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json>` before performing or recording the non-powered mannequin or arm-form interface check. Use `scripts/fr017-new-mannequin-interface-record.ps1 -Mode Create` only to create a real operator-supplied non-powered mannequin or arm-form interface working record linked to the same completed mockup record. The returned `mannequin_capture_plan` groups evidence linkage, test article identity, future-interface clearance, cable/sensor/release checks, and fail observations; `mannequin_capture_first_blocking_group_id` identifies the next mannequin evidence group requiring work. These fields, the mannequin template, and the mannequin initializer are operator input tooling only and are not physical validation completion, pilot fit validation, powered testing clearance, frame-coupled testing clearance, professional engineering approval, or FR-018 clearance.

After mannequin interface reports `ready_for_pilot_static_fit_planning`, run `scripts/fr017-pilot-static-fit-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json>` before performing or recording a non-powered pilot static-fit session. Use `scripts/fr017-new-pilot-static-fit-record.ps1 -Mode Create` only to create a real operator-supplied non-powered pilot static-fit working record linked to the same completed measurement, mockup, and mannequin records. The returned `static_fit_capture_plan` groups evidence linkage, safety preconditions, left/right baseline and clearance checks, and left/right post-doff symptom screens; `static_fit_capture_first_blocking_group_id` identifies the next static-fit evidence group requiring work. These fields, the static-fit template, and the static-fit initializer are operator input tooling only and are not physical validation completion, movement-test clearance, powered testing clearance, frame-coupled testing clearance, professional engineering approval, or FR-018 clearance.

After pilot static fit reports `ready_for_pilot_movement_test_planning`, run `scripts/fr017-pilot-movement-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json>` before performing or recording a non-powered pilot movement session. Use `scripts/fr017-new-pilot-movement-record.ps1 -Mode Create` only to create a real operator-supplied non-powered pilot movement working record linked to the same completed static-fit record. The returned `movement_capture_plan` groups evidence linkage, safety preconditions, left/right motion clearance checks, and left/right post-motion symptom screens; `movement_capture_first_blocking_group_id` identifies the next movement evidence group requiring work. These fields, the movement template, and the movement initializer are operator input tooling only and are not physical validation completion, quick-release/cable-snag clearance, powered testing clearance, frame-coupled testing clearance, professional engineering approval, or FR-018 clearance.

After pilot movement reports `ready_for_quick_release_and_cable_snag_test_planning`, run `scripts/fr017-quick-release-cable-snag-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json>` before performing or recording a non-powered quick-release/cable-snag session. Use `scripts/fr017-new-release-cable-record.ps1 -Mode Create` only to create a real operator-supplied non-powered quick-release/cable-snag working record linked to the same completed movement record. The returned `release_cable_capture_plan` groups evidence linkage, safety preconditions, left/right release access, and left/right cable route plus fail observations; `release_cable_capture_first_blocking_group_id` identifies the next release/cable evidence group requiring work. These fields, the release/cable template, and the release/cable initializer are operator input tooling only and are not professional engineering approval, physical validation completion, powered testing clearance, frame-coupled testing clearance, or FR-018 clearance.

After quick-release/cable-snag reports `ready_for_engineering_review_or_final_physical_gate_audit`, run `scripts/fr017-engineering-review-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json>` before obtaining or recording professional engineering review. Use `scripts/fr017-new-engineering-review-record.ps1 -Mode Create` only to create a real operator-supplied professional engineering review working record linked to the same completed quick-release/cable-snag record. The returned `engineering_review_capture_plan` groups evidence linkage, review constraints, safety review, and review decision limits; `engineering_review_capture_first_blocking_group_id` identifies the next engineering-review evidence group requiring work. These fields, the engineering-review template, and the engineering-review initializer are operator input tooling only and are not final physical gate completion, powered testing clearance, frame-coupled testing clearance, load-bearing approval, or FR-018 clearance.

After engineering review reports `ready_for_final_stage17_physical_gate_audit`, run `scripts/fr017-final-physical-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json>` before any Stage 17 completion claim. The returned `final_physical_decision_plan` groups package/manifest lock, engineering-review gate lock, evidence chronology, pilot identity continuity, and human final decision/no-clearance locks; `final_physical_decision_first_blocking_group_id` identifies the next final-decision evidence group requiring work. If the gate reports `ready_for_stage17_final_physical_completion_decision`, use `scripts/fr017-new-final-decision-record.ps1 -Mode Create` only to save that final physical gate output and create a real operator-supplied human final decision working record from `FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json`, then run `scripts/fr017-final-decision-record-gate.ps1 -Mode Status -FinalDecisionPath <final-decision-record.json>` with the same evidence paths before any ledger-backed completion claim. After that reports `ready_for_completion_ledger_review`, use `scripts/fr017-new-completion-ledger-handoff.ps1 -Mode Create` only to create a candidate operator-reviewed ledger handoff from `FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md`, then run `scripts/fr017-completion-ledger-gate.ps1 -Mode Status -FinalDecisionPath <final-decision-record.json> -LedgerEntryPath <candidate-ledger-entry.md>` with the same evidence paths. After that reports `ready_for_operator_completion_ledger_update`, update or provide a proposed completion ledger file containing the reviewed candidate entry, then run `scripts/fr017-completion-ledger-update-gate.ps1 -Mode Status -FinalDecisionPath <final-decision-record.json> -LedgerEntryPath <candidate-ledger-entry.md> -CompletionLedgerPath <completion-ledger-or-proposal.md>` with the same evidence paths before treating the ledger update as reviewed. These fields, templates, and initializers are operator input tooling until populated with real accepted records; they are not physical validation completion, Stage 17 closure, powered testing clearance, frame-coupled testing clearance, load-bearing approval, or FR-018 clearance.
