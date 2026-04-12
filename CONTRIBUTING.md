# Contributing to Francis

Francis is built as a governed, local-first operator layer. The repo workflow needs to reflect that discipline.

## Branch Management

- `main` is the canonical branch. Keep it releasable and reflective of the current repo state on GitHub.
- Do implementation work on a named working branch, not on `main`.
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
git switch -c codex/<slice-name>
```

Work, validate, commit, and push the working branch:

```powershell
.\scripts\check.ps1
git push -u origin codex/<slice-name>
```

After the slice is validated and ready to become canonical:

```powershell
git switch main
git merge --ff-only codex/<slice-name>
git push origin main
git switch codex/<slice-name>
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
- clearly named working branches
- checkpoint branches that explain themselves
- no ambiguous branch drift
- no confusion about which branch is the source of truth
