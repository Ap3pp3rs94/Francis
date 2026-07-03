# FR-017-VALIDATION-GATE-CHAIN

FRANCIS status: Stage 17 validation gate chain documented. Physical validation remains blocked.

## Purpose

This runbook defines the read-only FR-017 gate sequence for moving from documentation containers toward a final physical completion decision.

It does not perform physical testing, approve load-bearing use, clear powered or frame-coupled testing, or clear FR-018 implementation.

## Gate Order

Run `scripts/fr017-evidence-chain-status.ps1 -Mode Status` at any point to identify the first blocking evidence gate and the next required input without writing data or claiming physical validation.

| Order | Gate | Command | Required input state | Output state that permits next gate |
| --- | --- | --- | --- | --- |
| 1 | Package structure gate | `scripts/fr017-stage17-validation-gate.ps1 -Mode Status` | Manifest and package records present | `blocked_physical_validation` with no failed structural checks |
| 2 | Measurement intake gate | `scripts/fr017-measurement-intake.ps1 -Mode Status -MeasurementPath <measurement-record.json>` | Real left/right forearm measurements entered; safety-critical landmark confirmation complete; second-pass repeatability evidence complete; broad sanity bounds and derived consistency checks passed | `ready_for_non_powered_mockup_patterning` |
| 3 | Mockup readiness gate | `scripts/fr017-mockup-readiness-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json>` after creating a bounded working record with `scripts/fr017-new-mockup-record.ps1 -Mode Create` | Non-powered soft/semi-rigid cuff mockup evidence linked to the same completed measurement record | `ready_for_mannequin_interface_test` |
| 4 | Mannequin interface gate | `scripts/fr017-mannequin-interface-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json>` after creating a bounded working record with `scripts/fr017-new-mannequin-interface-record.ps1 -Mode Create` | Arm form, future interface mock geometry, and cable-sleeve mock evidence linked to the same non-powered mockup record | `ready_for_pilot_static_fit_planning` |
| 5 | Pilot static fit gate | `scripts/fr017-pilot-static-fit-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json>` | Pilot static fit evidence linked to the same measurement, mockup, and mannequin records, with circulation, nerve, pressure, release, glove, and wrist-removal checks | `ready_for_pilot_movement_test_planning` |
| 6 | Pilot movement gate | `scripts/fr017-pilot-movement-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json>` | Pilot movement evidence linked to the same static-fit record, with elbow, wrist, grip, glove removal, release access, and cable routing checks | `ready_for_quick_release_and_cable_snag_test_planning` |
| 7 | Quick-release/cable-snag gate | `scripts/fr017-quick-release-cable-snag-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json>` | Non-powered quick-release and cable-snag evidence linked to the same movement record | `ready_for_engineering_review_or_final_physical_gate_audit` |
| 8 | Professional engineering review gate | `scripts/fr017-engineering-review-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json>` | Professional review of the complete non-powered evidence chain, with the review record linked to the same quick-release/cable-snag record passed into this gate | `ready_for_final_stage17_physical_gate_audit` |
| 9 | Final physical gate audit | `scripts/fr017-final-physical-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json>` | Complete evidence chain, package gate pass, non-regressing evidence chronology, and one pilot identity across all pilot-linked records | `ready_for_stage17_final_physical_completion_decision` |
| 10 | Human final decision record | `scripts/fr017-final-decision-record-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json>` | Final physical gate output saved, real records reviewed by a human decision reviewer, populated decision record, and no-clearance locks preserved | `ready_for_completion_ledger_review` |
| 11 | Completion ledger handoff gate | `scripts/fr017-completion-ledger-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-record.json> -StaticFitPath <static-fit-record.json> -MovementPath <movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json> -LedgerEntryPath <candidate-ledger-entry.md>` | Candidate ledger entry is copied from `FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md`, has all `PENDING` placeholders replaced, references the final decision record, and preserves explicit no-clearance language for physical completion, Stage 17 claim authority, powered/frame-coupled/load-bearing use, and FR-018 | `ready_for_operator_completion_ledger_update` |

## No-Fake-Validation Lock

The final physical gate audit is a decision-readiness gate only.

`FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json` is a record-capture
template only. A blank or `PENDING` copy is not physical validation evidence,
does not certify FR-017, and does not clear FR-018.

The final decision record gate can report `ready_for_completion_ledger_review`.
That state is a ledger-review handoff only; it still does not mark Stage 17
complete or clear FR-018.

The completion ledger handoff gate can report
`ready_for_operator_completion_ledger_update`. That state means the candidate
entry is structurally safe for operator review and still does not write the
ledger, mark Stage 17 complete, mark physical validation complete, or clear
FR-018.

`FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md` is an operator input template
only. A copy containing any `PENDING` placeholder remains pending and cannot
reach `ready_for_operator_completion_ledger_update`.

It must keep these values false unless a separate human-reviewed, ledger-backed completion decision updates the package:

- `physical_validation_complete`
- `stage17_completion_claim_allowed`
- `powered_or_frame_coupled_testing_cleared`
- `fr018_implementation_cleared`

## Evidence Chronology Lock

Early gate scripts enforce local evidence chronology where enough upstream
evidence is available:

- Mockup evidence must be dated the same day as or after the linked measurement
  evidence.
- Mannequin interface evidence must be dated the same day as or after the
  linked mockup evidence.
- Pilot static-fit evidence must be dated the same day as or after the linked
  measurement, mockup, and mannequin evidence.
- Pilot movement evidence must be dated the same day as or after the linked
  pilot static-fit evidence.
- Quick-release/cable-snag evidence must be dated the same day as or after the
  linked pilot movement evidence.
- Engineering-review evidence must be dated the same day as or after the linked
  quick-release/cable-snag evidence.

The final physical gate also checks the full linked evidence dates in gate
order:

1. measurement
2. mockup
3. mannequin
4. pilot static fit
5. pilot movement
6. quick-release/cable-snag
7. engineering review

Dates must use ISO `YYYY-MM-DD` and must not move backward across the chain.
Same-day records are allowed when the evidence documents same-day work. A
backward date blocks final decision readiness and does not mark physical
validation complete.

## Pilot Identity Continuity Lock

The final physical gate also checks pilot-linked evidence identity continuity
across:

1. measurement
2. any mockup record that includes `evidence.pilot_id`
3. pilot static fit
4. pilot movement
5. quick-release/cable-snag
6. engineering review

The final gate exposes redacted identity fingerprints only. Missing required
pilot IDs or mismatched identities block final decision readiness and do not
mark physical validation complete.

## Stop Conditions

Stop FR-017 progression and mark the affected physical record `FAILED / REQUIRES REDESIGN` if any of these are observed:

- numbness
- tingling
- cold fingers
- discoloration
- hand weakness
- wrist pain
- sharp pressure
- reduced finger motion
- loss of grip strength
- unconfirmed landmark boundaries
- unreachable release
- trapped glove or wrist assembly
- cable crossing palm, grip path, wrist bones, or inner elbow

## Current Package State

Current package state is documentation-complete and evidence-container-complete.

Current physical validation state is NOT COMPLETE.

FR-018 implementation is NOT CLEARED.
