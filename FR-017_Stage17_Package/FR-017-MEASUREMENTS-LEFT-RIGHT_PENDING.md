# FR-017-MEASUREMENTS-LEFT-RIGHT_PENDING

FRANCIS status: Measurement record created. No measurements have been entered.

## Validation State

REQUIRES MEASUREMENT

## Pilot Constants

- Pilot reference height: 5'5".
- Maximum external suit height: 5'7".
- FR-017 scope: forearm cuff interface only; not armor, not powered joint, not load-bearing frame.

## Measurement Rules

- Measure left and right arms separately.
- Do not assume symmetry.
- Use a flexible tape without compressing tissue.
- Record a project-local pilot identifier and the measurement tool used.
- Record measurement posture.
- Stop if any measurement position produces pain, tingling, numbness, or discoloration.
- In JSON intake records, enter measurement fields as unquoted JSON numbers in millimeters. Quoted numeric strings are invalid.
- In JSON intake records, enter safety-screen fields as unquoted JSON `false` only when the symptom is absent and unquoted JSON `true` only when the symptom is observed; any `true` symptom blocks FR-017 progression.
- In JSON intake records, enter measurement-condition fields as unquoted JSON `true` only after confirming no tissue compression, no wrist-bone compression, metric tool use, neutral posture or recorded exception, and stop-condition briefing.
- In JSON intake records, enter landmark-confirmation fields as unquoted JSON `true` only after the safety-critical landmarks are visibly marked with a skin-safe method.
- Measurement intake applies broad human-scale sanity bounds to reject clearly impossible entries. Passing those bounds is not fit approval, fabrication approval, load-bearing approval, powered-test clearance, or FR-018 clearance.
- Measurement intake also rejects contradictory dimensions, including panel length, bone-relief length, strap-band width, or wrist-clearance gap greater than the measured forearm length, and inner no-pressure width greater than the mid-forearm circumference.
- Measure every required left/right field twice. The measurement-intake JSON requires second-pass confirmation and a maximum repeatability delta of 5 mm or less for each side.
- Marked-zone evidence references must be side-specific. Do not reuse the same reference text for left and right on a zone unless the reference itself names distinct left and right labels or anchors.
- The measurement-intake JSON requires explicit left/right independence evidence: left arm measured separately, right arm measured separately, side labels verified, values not copied between sides, and distinct left/right measurement references.
- If every required left/right numeric measurement is exactly identical, the intake gate treats the record as requiring a left/right recheck before progression.
- Before entering real pilot data, run `scripts/fr017-measurement-intake.ps1 -Mode Status` and follow the returned `measurement_capture_plan`. The capture plan is read-only guidance for the first physical-input gate and is not physical validation evidence.

## Required Measurements

| Field | Left value | Right value | Units | Method note |
| --- | --- | --- | --- | --- |
| Forearm circumference 25 mm below elbow crease | PENDING | PENDING | mm | Arm relaxed, palm neutral |
| Forearm circumference at mid-forearm | PENDING | PENDING | mm | Mark midpoint between elbow and wrist creases |
| Forearm circumference 40 mm above wrist crease | PENDING | PENDING | mm | Avoid wrist bone compression |
| Forearm length, elbow crease to wrist crease | PENDING | PENDING | mm | Straight line along outer forearm |
| Outer forearm usable panel length | PENDING | PENDING | mm | Excludes elbow and wrist clearance |
| Upper strap allowed band width | PENDING | PENDING | mm | Must stay below elbow crease |
| Lower strap allowed band width | PENDING | PENDING | mm | Must stay above wrist bones |
| Bone ridge relief length | PENDING | PENDING | mm | Mark radius/ulna pressure-sensitive paths |
| Inner forearm no-pressure zone width | PENDING | PENDING | mm | Soft zone only |
| Wrist clearance gap | PENDING | PENDING | mm | Must preserve wrist movement and removal path |

## Marked Zones

| Zone | Left status | Right status | Evidence reference |
| --- | --- | --- | --- |
| Inner elbow crease boundary | PENDING | PENDING | PENDING |
| Wrist bone boundary | PENDING | PENDING | PENDING |
| Radius ridge relief | PENDING | PENDING | PENDING |
| Ulna ridge relief | PENDING | PENDING | PENDING |
| Outer forearm cable route | PENDING | PENDING | PENDING |
| Quick-release reach zone | PENDING | PENDING | PENDING |
| Glove removal path | PENDING | PENDING | PENDING |

## Repeatability Check

| Check | Left status | Right status | Required evidence |
| --- | --- | --- | --- |
| Second measurement pass completed | PENDING | PENDING | Boolean true only after second pass |
| Maximum delta between passes | PENDING | PENDING | Unquoted JSON number, 0-5 mm inclusive |
| All required measurements within 5 mm | PENDING | PENDING | Boolean true only when every required field meets the limit |

## Measurement Conditions

| Check | Status | Required evidence |
| --- | --- | --- |
| No tissue compression used | PENDING | Boolean true only when the tape did not compress tissue |
| No wrist-bone compression used | PENDING | Boolean true only when wrist-bone landmarks were not pressed |
| Metric tool used | PENDING | Boolean true only when measurement tool is metric or values are directly recorded in mm |
| Neutral posture or recorded exception | PENDING | Boolean true only when arm posture was neutral or exception is documented |
| Stop conditions briefed | PENDING | Boolean true only after symptom stop conditions are briefed |
| Condition notes | PENDING | Short note naming method, posture, and any exception |

## Landmark Confirmation

| Check | Status | Required evidence |
| --- | --- | --- |
| Inner elbow crease boundary confirmed | PENDING | Boolean true only after the no-strap crease boundary is visibly marked |
| Wrist-bone boundary confirmed | PENDING | Boolean true only after wrist-bone no-pressure clearance is visibly marked |
| Radius/ulna relief paths confirmed | PENDING | Boolean true only after both bone-ridge relief paths are visibly marked |
| Outer forearm cable route confirmed | PENDING | Boolean true only after the outer/lateral cable path is visibly marked |
| Quick-release reach zone confirmed | PENDING | Boolean true only after the release reach zone is visibly marked |
| Glove-removal path confirmed | PENDING | Boolean true only after the glove-removal path is visibly marked |
| Skin-safe marking used | PENDING | Boolean true only after the marking method is confirmed skin-safe and removable |
| Landmark notes | PENDING | Short note naming marking method, side labels, and evidence reference |

## Left/Right Independence Check

| Check | Status | Required evidence |
| --- | --- | --- |
| Left arm measured separately | PENDING | Boolean true only after the left arm is measured as its own pass |
| Right arm measured separately | PENDING | Boolean true only after the right arm is measured as its own pass |
| Side labels verified | PENDING | Boolean true only after left/right labels are checked against the pilot |
| Values not copied between sides | PENDING | Boolean true only when left/right entries came from separate observations |
| Left measurement reference | PENDING | Distinct local note/photo/sheet reference |
| Right measurement reference | PENDING | Distinct local note/photo/sheet reference |
| Independence notes | PENDING | Short note describing how left/right separation was preserved |
| Identical complete numeric profile rechecked | PENDING | Required when every left/right numeric value is exactly identical |

## Decision

No fabrication dimensions are approved from this record until all required fields are entered and reviewed.
