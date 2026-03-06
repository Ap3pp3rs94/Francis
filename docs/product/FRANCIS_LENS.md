# Francis Lens

## What It Is
Francis Lens is the 4th-wall overlay and operator HUD for the PC. It is the in-context surface where Francis shows what it understands, what it recommends, and what it is doing right now.

## What It Shows
- Mission intent and active objective stack.
- Current context: repo/app/session focus.
- Blockers and risks with evidence links.
- Action chips for safe next operations (observe, assist, pilot, away actions).
- Control mode visibility (Observe/Assist/Pilot/Away) and current scope.

## 4th-Wall Experience
Breaking the 4th wall means Francis feels present in the work itself, not hidden behind chat tabs. The user sees intent, evidence, and options in real time while staying in control.

## What It Is Not
- Not constant screen recording.
- Not spyware.
- Not hidden background authority.
- Not a health-only dashboard.

## Acceptance Criteria
- Overlay always shows current mode, scope, and intent.
- Overlay prioritizes mission/blocker/action context over raw system vitals.
- Pilot Mode state is visibly active and instantly revocable.
- Lens claims map to receipts (`run_id`, logs, diffs, journals).
- Lens never presents out-of-scope actions as executable.
