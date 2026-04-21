# Contributing to Francis

Francis is built as a governed, local-first operator layer. The repo workflow needs to reflect that discipline.

## Branch Management

- `main` is the canonical branch. Keep it releasable and reflective of the current repo state on GitHub.
- Current maintainer workflow is direct-on-`main`: sync first, make a bounded change, validate, commit, and push `main`.
- Use a named working branch only when a change needs isolated review, experimental protection, or recovery safety.
- Preferred working branch prefixes:
  - `codex/` for implementation slices
  - `backup/` for preserved checkpoints
  - `release/` for release preparation
  - `hotfix/` for urgent repairs
- Base working branches from current `origin/main`.
- Set an upstream for every shared branch so local and remote state stay aligned.
- Keep working branches current with `origin/main`. Do not let long-lived branches drift behind the canonical line.
- Promote validated work back to `main` with a fast-forward merge. Do not create avoidable merge bubbles for routine slices.
- Do not force-push shared branches unless there is an explicit recovery reason and everyone involved understands the history rewrite.

## Expected Local Flow

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
```

Work, validate, commit, and push `main`:

```powershell
.\scripts\check.ps1
git push origin main
```

For isolated work only, create a named branch after syncing `main`:

```powershell
git switch -c codex/<slice-name>
```

## Repo Checks

- `.\scripts\check.ps1` includes a branch-state check before lint, type, and test validation.
- The branch-state check is intended to catch workflow drift early:
  - detached HEAD work
  - unsupported branch naming
  - missing upstream tracking
  - feature branches that have fallen behind `origin/main`

## Practical Standard

If someone opens the repository and inspects the branch graph, they should be able to see:

- a clean canonical `main`
- no unnecessary working branches
- clearly named temporary branches when isolation is actually needed
- no ambiguous branch drift
- no confusion about which branch is the source of truth
