# Repository Guidelines

## Project Structure & Module Organization
`src/francis/` contains the Python runtime: API routes, governance, missions, memory, and observability. `tests/` holds the pytest suite, including focused API contract files such as `test_api_missions.py` plus broader folders like `unit/`, `integration/`, and `e2e/`. `apps/chat_ui/src/` contains the Vite/React operator UI. Canonical direction lives in `docs/canonical/`; shipped truth belongs in `docs/operations/COMPLETION_LEDGER.md`. Use `scripts/` for local entrypoints and validation.

## Build, Test, and Development Commands
```powershell
.\scripts\bootstrap.ps1
.\scripts\francis.ps1 api
.\scripts\check.ps1
cd apps\chat_ui; npm run dev
cd apps\chat_ui; npm run build
cd apps\chat_ui; npm run test
uv sync --frozen --extra core --extra web --extra dev
```
`bootstrap.ps1` prepares the local environment. `francis.ps1 api` runs the FastAPI service. `check.ps1` is the main gate: branch-state checks, Ruff lint, Ruff format check, mypy, and pytest. The UI uses Vite for local dev/build and Node’s test runner for TypeScript contract tests.

## Coding Style & Naming Conventions
Follow `.editorconfig`: 4 spaces for Python and PowerShell, 2 spaces for TypeScript, TSX, JSON, YAML, and CSS. Default to LF; PowerShell files use CRLF. Keep Python modules in `snake_case`; keep TypeScript tests and feature folders aligned with the existing `missions`, `operations`, and `settings` patterns. Prefer small, bounded diffs that preserve truthful UI behavior, governance checks, auditability, and shell-facing contracts.

## Testing Guidelines
Run the narrowest meaningful validation for the surface you touch, then run `.\scripts\check.ps1` before handoff when practical. Python tests use `pytest`; markers include `unit` and `smoke`. Name Python files `test_<surface>.py` and UI tests `*.test.ts`. If you change mission, governance, memory, or UI contract behavior, add or update direct tests for that exact path.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commit style with scopes, for example `feat(observability): surface watcher state age` and `fix(observability): pin francis observer to one session`. Current maintainer workflow is direct-on-`main`: sync `origin/main`, make a bounded change, validate, commit, and push `main`. Use temporary branches such as `codex/<slice-name>` or `hotfix/<slice-name>` only when isolated review or recovery safety is needed. PRs should state the roadmap area touched, summarize validation actually run, include screenshots for UI changes, and call out any policy, shell, orb, HUD, or memory-contract risk explicitly.

## Architecture & Governance Notes
Francis is currently in Phase 2. Work should reinforce the governed runtime spine: observability before autonomy, policy before power, and no fake progress signals. Inspect canonical docs before broad changes, keep operator-facing surfaces honest, and update the completion ledger only when repo truth materially changes.
