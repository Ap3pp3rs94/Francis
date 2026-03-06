# Work Telemetry

## High-Signal Streams
Francis should prefer structured, high-signal telemetry over raw visual scraping:
- File and git events (changed files, branch state, diff stats).
- Terminal command output and exit codes.
- Build/test logs and CI-style diagnostics.
- Dev server/runtime logs.
- IDE diagnostics (errors, warnings, unresolved symbols).
- Optional browser console/network errors for web workflows.

## Opt-In Design
- Telemetry sources are explicitly enabled by the user.
- Each source has visible scope and retention boundaries.
- Disable/enable controls are immediate and reversible.

## Privacy Boundaries
- Collect minimum required signal for active missions.
- Do not ingest unrelated personal content by default.
- No constant full-screen recording requirement.
- Redaction and scope policies apply before storage and actioning.

## Why This Beats Raw Screen Watching
- Better precision: structured errors/events are more actionable.
- Better safety: easier scope and policy enforcement.
- Better privacy: lower collateral data collection.
- Better reliability: deterministic receipts tied to artifacts.

## Acceptance Criteria
- Telemetry is opt-in per connector/source.
- Francis never processes signals outside declared scope.
- Every telemetry-driven action links to evidence and `run_id`.
- Users can pause telemetry instantly.
- High-signal streams drive decisions; screen capture is optional, not default.
