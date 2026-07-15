# Contributing to Francis

Francis is built as a governed, local-first operator layer. The repo workflow needs to reflect that discipline.

## Ownership and License

Francis is proprietary and all rights are reserved by Austin Peppers. Do not submit code, documentation, designs, issues, pull requests, assets, or other materials unless you have the right to submit them and agree that the submitted materials are assigned to Austin Peppers under the terms in [LICENSE](LICENSE).

Licensing questions and permission requests: peppera091@gmail.com

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

### Temporary worktree policy

- Normal bounded implementation is serialized in `D:\Francis` on `main`.
- Read-only reviewers may inspect the same exact head concurrently.
- Create a temporary worktree only for rollback isolation, conflicting mutation,
  or exact-head validation that cannot safely use the main checkout.
- Normally at most one mutating temporary worktree may exist. Record its owner,
  task, exact base, runtime lease, and removal condition before use.
- Place temporary worktrees under `D:\Francis-support\worktrees`; do not create
  permanent drive-root names such as `D:\fa`, `D:\fg`, or `D:\fv`.
- A promoted, rejected, superseded, or parked branch may retain an intentional
  Git ref, but its checkout must be removed in the same integration cycle after
  unique dirty state and untracked artifacts are preserved.
- For short-path validation, prefer a temporary reversible drive mapping backed
  by `D:\Francis-support\worktrees`, and remove the mapping after validation.
- Before removal, prove the worktree is clean or preserved, its unique commits
  are reachable from `main` or an intentional ref, no process or lease uses its
  path, and no required artifact exists only as an untracked file. Use
  `git worktree remove`; never force-remove uncertain work.

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

For exceptional isolated work only, create a named branch after syncing `main`
and add its checkout below `D:\Francis-support\worktrees`:

```powershell
git worktree add D:\Francis-support\worktrees\<slice-name> -b codex/<slice-name> main
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
