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
- `scripts/fr017-mockup-readiness-gate.ps1 -Mode Status`: mockup readiness status plus the read-only `mockup_capture_plan` for the non-powered cuff mockup gate.
- `scripts/fr017-mannequin-interface-gate.ps1 -Mode Status`: mannequin interface status plus the read-only `mannequin_capture_plan` for the non-powered future-interface clearance gate.
- `scripts/fr017-evidence-chain-status.ps1 -Mode Status`: first blocking FR-017 evidence gate, next required input, and the current measurement/mockup/mannequin capture summary where applicable.
- `scripts/fr017-engineering-review-gate.ps1 -Mode Status`: professional review evidence after quick-release/cable-snag evidence.
- `scripts/fr017-final-physical-gate.ps1 -Mode Status`: final aggregate gate; does not mark physical validation complete or clear FR-018 by itself.

## Files

| File | Purpose | Current validation state |
| --- | --- | --- |
| `FR-017-MEASUREMENTS-LEFT-RIGHT_PENDING.md` | Left/right measurement capture record | REQUIRES MEASUREMENT |
| `FR-017-MEASUREMENTS-INPUT-TEMPLATE.json` | Structured measurement intake template | COMPLETE |
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

Run `scripts/fr017-measurement-intake.ps1 -Mode Status` before entering pilot data. The returned `measurement_capture_plan` is the operator-facing capture order for the first FR-017 physical-input gate, `measurement_capture_plan_status` reports which capture groups are still pending, invalid, or blocked for the supplied record, and `measurement_capture_first_blocking_group_id` identifies the next group requiring work. These fields are not completion evidence; they cannot mark physical validation complete, clear powered or frame-coupled testing, or clear FR-018.

After measurement intake reports `ready_for_non_powered_mockup_patterning`, run `scripts/fr017-mockup-readiness-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json>` before building or recording the non-powered mockup. The returned `mockup_capture_plan` groups the mockup evidence, material stack, global safety constraints, and left/right side checks; `mockup_capture_first_blocking_group_id` identifies the next mockup capture group requiring work. These fields are read-only operator guidance and are not mannequin, pilot, powered, frame-coupled, or FR-018 clearance.

After mockup readiness reports `ready_for_mannequin_interface_test`, run `scripts/fr017-mannequin-interface-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json>` before performing or recording the non-powered mannequin or arm-form interface check. The returned `mannequin_capture_plan` groups evidence linkage, test article identity, future-interface clearance, cable/sensor/release checks, and fail observations; `mannequin_capture_first_blocking_group_id` identifies the next mannequin evidence group requiring work. These fields are read-only operator guidance and are not pilot fit validation, powered testing clearance, frame-coupled testing clearance, professional engineering approval, or FR-018 clearance.
