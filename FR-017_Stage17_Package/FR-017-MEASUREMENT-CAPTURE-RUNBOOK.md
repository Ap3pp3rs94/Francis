# FR-017 Measurement Capture Runbook

Status: COMPLETE OPERATOR RUNBOOK, NOT EVIDENCE
Component: FR-017 Forearm Cuffs
Gate: measurement_intake

## Purpose

This runbook converts the read-only `measurement_capture_plan` from `scripts/fr017-measurement-intake.ps1 -Mode Status` into an operator capture sequence for the first FR-017 physical-input gate.

This runbook is not physical validation evidence. It does not replace `FR-017-MEASUREMENTS-INPUT-TEMPLATE.json`, does not record Pilot measurements, does not approve fabrication, does not approve load-bearing use, and does not clear powered or frame-coupled testing.

Required lock flags:

- `physical_validation_complete: false`
- `stage17_completion_claim_allowed: false`
- `fr018_implementation_cleared: false`

## Source Template

Create a dated working record from `FR-017-MEASUREMENTS-INPUT-TEMPLATE.json` before entering measurements. Do not overwrite the template.

Suggested record name:

`FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json`

Run the gate before and after editing the working record:

```powershell
.\scripts\fr017-measurement-intake.ps1 -Mode Status
.\scripts\fr017-new-measurement-record.ps1 -Mode Create -OutputPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json
.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json
```

The initializer creates only a pending working record. It refuses to overwrite an existing file or target the template itself. The generated record still requires real left/right measurements, landmark references, repeatability checks, and symptom-screen entries before the intake gate can advance.

If the setup and safety brief has actually been completed, the initializer can also record those first-gate fields:

```powershell
.\scripts\fr017-new-measurement-record.ps1 -Mode Create `
  -OutputPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json `
  -EvidenceDate YYYY-MM-DD `
  -Observer "<observer>" `
  -PilotId "<pilot-reference>" `
  -MeasurementTool "flexible metric tape" `
  -ConfirmNoTissueCompressionUsed `
  -ConfirmNoWristBoneCompressionUsed `
  -ConfirmMetricToolUsed `
  -ConfirmArmRelaxedPalmNeutralOrExceptionRecorded `
  -ConfirmStopConditionsBriefed `
  -ConditionNotes "No tissue compression, no wrist-bone compression, metric tool, and stop briefing confirmed."
```

These setup-brief fields are still not physical validation evidence. They can make only `setup_and_safety_brief` ready when real values are provided. Left/right measurements, marked zones, repeatability, left/right independence, and symptom screen entries remain separate required evidence.

If a pending record already exists without setup/safety-brief fields, update that first capture group with real operator-supplied values instead of editing JSON by hand:

```powershell
.\scripts\fr017-update-measurement-setup-record.ps1 -Mode UpdateSetup `
  -MeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json `
  -EvidenceDate YYYY-MM-DD `
  -Observer "<observer>" `
  -PilotId "<pilot-reference>" `
  -MeasurementTool "flexible metric tape" `
  -Method "flexible tape, no tissue compression" `
  -Posture "arm relaxed, palm neutral" `
  -ConfirmNoTissueCompressionUsed `
  -ConfirmNoWristBoneCompressionUsed `
  -ConfirmMetricToolUsed `
  -ConfirmArmRelaxedPalmNeutralOrExceptionRecorded `
  -ConfirmStopConditionsBriefed `
  -ConditionNotes "No tissue compression, no wrist-bone compression, metric tool, and stop briefing confirmed."
```

This command writes operator-supplied setup and measurement-condition input only. It refuses to update the template and refuses to overwrite populated fields unless `-AllowOverwrite` is explicitly supplied. The measurement-intake gate remains the authority for readiness.

## Capture Order

The capture groups below must remain in the same order as the gate status output.

### 1. setup_and_safety_brief

Capture:

- `evidence.date`
- `evidence.observer`
- `evidence.pilot_id`
- `evidence.measurement_tool`
- `evidence.method`
- `evidence.posture`
- `measurement_conditions.no_tissue_compression_used`
- `measurement_conditions.no_wrist_bone_compression_used`
- `measurement_conditions.metric_tool_used`
- `measurement_conditions.arm_relaxed_palm_neutral_or_exception_recorded`
- `measurement_conditions.stop_conditions_briefed`
- `measurement_conditions.condition_notes`

Stop if the tool is not metric or millimeter-capable, if measurement requires tissue or wrist-bone compression, or if the Pilot reports pain, tingling, numbness, cold fingers, discoloration, weakness, wrist pain, sharp pressure, reduced finger motion, or loss of grip strength.

### 2. left_arm_numeric_measurement_passes

Capture the left arm as its own side-labeled record:

- `sides.left.forearm_circumference_25mm_below_elbow_crease`
- `sides.left.forearm_circumference_mid_forearm`
- `sides.left.forearm_circumference_40mm_above_wrist_crease`
- `sides.left.forearm_length_elbow_crease_to_wrist_crease`
- `sides.left.outer_forearm_usable_panel_length`
- `sides.left.upper_strap_allowed_band_width`
- `sides.left.lower_strap_allowed_band_width`
- `sides.left.bone_ridge_relief_length`
- `sides.left.inner_forearm_no_pressure_zone_width`
- `sides.left.wrist_clearance_gap`
- `repeatability.left.second_pass_completed`
- `repeatability.left.max_delta_mm`
- `repeatability.left.all_required_measurements_within_5mm`

Stop if the left side label is not visible, if the second pass is not complete, if repeatability exceeds 5 mm, or if any safety-screen symptom appears.

Optional guarded update command for real left-side values:

```powershell
.\scripts\fr017-update-measurement-record.ps1 -Mode UpdateSide `
  -MeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json `
  -Side left `
  -ForearmCircumference25mmBelowElbowCrease <mm> `
  -ForearmCircumferenceMidForearm <mm> `
  -ForearmCircumference40mmAboveWristCrease <mm> `
  -ForearmLengthElbowCreaseToWristCrease <mm> `
  -OuterForearmUsablePanelLength <mm> `
  -UpperStrapAllowedBandWidth <mm> `
  -LowerStrapAllowedBandWidth <mm> `
  -BoneRidgeReliefLength <mm> `
  -InnerForearmNoPressureZoneWidth <mm> `
  -WristClearanceGap <mm> `
  -ConfirmSecondPassCompleted `
  -MaxDeltaMm <0-5> `
  -ConfirmAllRequiredMeasurementsWithin5mm
```

This command writes operator-supplied numeric input only. It refuses to update the template and refuses to overwrite populated fields unless `-AllowOverwrite` is explicitly supplied. The measurement-intake gate remains the authority for readiness.

### 3. right_arm_numeric_measurement_passes

Capture the right arm as its own side-labeled record:

- `sides.right.forearm_circumference_25mm_below_elbow_crease`
- `sides.right.forearm_circumference_mid_forearm`
- `sides.right.forearm_circumference_40mm_above_wrist_crease`
- `sides.right.forearm_length_elbow_crease_to_wrist_crease`
- `sides.right.outer_forearm_usable_panel_length`
- `sides.right.upper_strap_allowed_band_width`
- `sides.right.lower_strap_allowed_band_width`
- `sides.right.bone_ridge_relief_length`
- `sides.right.inner_forearm_no_pressure_zone_width`
- `sides.right.wrist_clearance_gap`
- `repeatability.right.second_pass_completed`
- `repeatability.right.max_delta_mm`
- `repeatability.right.all_required_measurements_within_5mm`

Stop if the right side label is not visible, if the second pass is not complete, if repeatability exceeds 5 mm, or if any safety-screen symptom appears.

Use the same guarded update command for right-side values with `-Side right`. Do not copy left values to the right side. The intake gate rejects copied left/right values and repeated evidence references.

### 4. safety_critical_landmark_and_zone_references

Capture side-specific marked-zone references:

- `marked_zones.left.inner_elbow_crease_boundary`
- `marked_zones.left.wrist_bone_boundary`
- `marked_zones.left.radius_ridge_relief`
- `marked_zones.left.ulna_ridge_relief`
- `marked_zones.left.outer_forearm_cable_route`
- `marked_zones.left.quick_release_reach_zone`
- `marked_zones.left.glove_removal_path`
- `marked_zones.right.inner_elbow_crease_boundary`
- `marked_zones.right.wrist_bone_boundary`
- `marked_zones.right.radius_ridge_relief`
- `marked_zones.right.ulna_ridge_relief`
- `marked_zones.right.outer_forearm_cable_route`
- `marked_zones.right.quick_release_reach_zone`
- `marked_zones.right.glove_removal_path`
- `landmark_confirmation.inner_elbow_crease_boundary_confirmed`
- `landmark_confirmation.wrist_bone_boundary_confirmed`
- `landmark_confirmation.radius_ulna_relief_paths_confirmed`
- `landmark_confirmation.outer_forearm_cable_route_confirmed`
- `landmark_confirmation.quick_release_reach_zone_confirmed`
- `landmark_confirmation.glove_removal_path_confirmed`
- `landmark_confirmation.skin_safe_marking_used`
- `landmark_confirmation.landmark_notes`

Stop if the inner elbow boundary, wrist-bone boundary, radius or ulna relief path, quick-release reach zone, or glove-removal path is unmarked or ambiguous.

Optional guarded update command for real marked-zone references:

```powershell
.\scripts\fr017-update-landmark-record.ps1 -Mode UpdateLandmarks `
  -MeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json `
  -LeftInnerElbowCreaseBoundary "<left labeled reference>" `
  -LeftWristBoneBoundary "<left labeled reference>" `
  -LeftRadiusRidgeRelief "<left labeled reference>" `
  -LeftUlnaRidgeRelief "<left labeled reference>" `
  -LeftOuterForearmCableRoute "<left labeled reference>" `
  -LeftQuickReleaseReachZone "<left labeled reference>" `
  -LeftGloveRemovalPath "<left labeled reference>" `
  -RightInnerElbowCreaseBoundary "<right labeled reference>" `
  -RightWristBoneBoundary "<right labeled reference>" `
  -RightRadiusRidgeRelief "<right labeled reference>" `
  -RightUlnaRidgeRelief "<right labeled reference>" `
  -RightOuterForearmCableRoute "<right labeled reference>" `
  -RightQuickReleaseReachZone "<right labeled reference>" `
  -RightGloveRemovalPath "<right labeled reference>" `
  -ConfirmInnerElbowCreaseBoundary `
  -ConfirmWristBoneBoundary `
  -ConfirmRadiusUlnaReliefPaths `
  -ConfirmOuterForearmCableRoute `
  -ConfirmQuickReleaseReachZone `
  -ConfirmGloveRemovalPath `
  -ConfirmSkinSafeMarkingUsed `
  -LandmarkNotes "Skin-safe marks identify inner elbow, wrist, radius, ulna, cable route, quick release, glove path, and side labels."
```

This command writes operator-supplied landmark references only. It refuses to update the template, refuses copied left/right references, and refuses to overwrite populated fields unless `-AllowOverwrite` is explicitly supplied. The measurement-intake gate remains the authority for readiness.

### 5. left_right_independence_and_safety_screen

Capture:

- `left_right_independence.left_arm_measured_separately`
- `left_right_independence.right_arm_measured_separately`
- `left_right_independence.side_labels_verified`
- `left_right_independence.values_not_copied_between_sides`
- `left_right_independence.left_measurement_reference`
- `left_right_independence.right_measurement_reference`
- `left_right_independence.independence_notes`
- `safety_screen.pain`
- `safety_screen.tingling`
- `safety_screen.numbness`
- `safety_screen.cold_fingers`
- `safety_screen.discoloration`
- `safety_screen.hand_weakness`
- `safety_screen.wrist_pain`
- `safety_screen.sharp_pressure`
- `safety_screen.reduced_finger_motion`
- `safety_screen.loss_of_grip_strength`

Stop if left and right values were copied, if left and right evidence references are not distinct, if the complete left/right numeric profiles are identical without recheck, or if any symptom is true.

Optional guarded update command for left/right independence and symptom screening:

```powershell
.\scripts\fr017-update-independence-safety-record.ps1 -Mode UpdateIndependenceSafety `
  -MeasurementPath .\FR-017_Stage17_Package\FR-017-MEASUREMENTS-YYYY-MM-DD-PILOT-RECORD.json `
  -ConfirmLeftArmMeasuredSeparately `
  -ConfirmRightArmMeasuredSeparately `
  -ConfirmSideLabelsVerified `
  -ConfirmValuesNotCopiedBetweenSides `
  -LeftMeasurementReference "<left independent evidence reference>" `
  -RightMeasurementReference "<right independent evidence reference>" `
  -IndependenceNotes "Left and right measurement passes were separate with side label verification." `
  -ConfirmNoPain `
  -ConfirmNoTingling `
  -ConfirmNoNumbness `
  -ConfirmNoColdFingers `
  -ConfirmNoDiscoloration `
  -ConfirmNoHandWeakness `
  -ConfirmNoWristPain `
  -ConfirmNoSharpPressure `
  -ConfirmNoReducedFingerMotion `
  -ConfirmNoLossOfGripStrength
```

If a symptom is observed, record the corresponding `-PainObserved`, `-TinglingObserved`, `-NumbnessObserved`, `-ColdFingersObserved`, `-DiscolorationObserved`, `-HandWeaknessObserved`, `-WristPainObserved`, `-SharpPressureObserved`, `-ReducedFingerMotionObserved`, or `-LossOfGripStrengthObserved` flag instead of the matching no-symptom confirmation. Any observed symptom is a failed fit condition and blocks FR-017 progression until appropriate review.

This command writes operator-supplied independence and safety-screen values only. It refuses to update the template and refuses to overwrite populated fields unless `-AllowOverwrite` is explicitly supplied. `ready_for_non_powered_mockup_patterning` remains measurement-intake readiness only; it is not physical validation completion, fit approval, powered testing clearance, or FR-018 clearance.

## Gate Interpretation

`ready_for_non_powered_mockup_patterning` means only that the measurement record passed the intake gate. It is not fit approval, fabrication approval, load approval, powered testing approval, frame-coupled testing approval, Stage 17 completion, or FR-018 clearance.

If the gate returns `pending_measurements`, complete the first blocking group reported by `measurement_capture_first_blocking_group_id`.

If the gate returns `invalid_measurement_record`, correct the listed invalid fields or blockers before re-running the gate.

If the gate returns `failed_requires_redesign_or_medical_review`, stop FR-017 progression and do not continue until the failure is resolved by appropriate review.
