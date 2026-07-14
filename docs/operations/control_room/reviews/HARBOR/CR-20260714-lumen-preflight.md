# HARBOR Review: CR-LUMEN-001 Preflight

Review ID: `REVIEW-HARBOR-20260714-002`

- Reviewer seat: HARBOR
- Agent session: `019f6119-b5ef-7721-91c1-5c628ce3ec61`
- Candidate: `a1b2c60bced10506cfd53bdfb97aa8b491656cea`
- Base: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`
- Mode: read-only Windows publication, queue-bound, portability, and visual-lock
  contract review
- Disposition: `REMEDIATION_REQUIRED`

## Blocking Findings

1. Native publication uses `MOVEFILE_REPLACE_EXISTING`; a destination created
   during the publication race can be overwritten.
2. Overlay drain iterates every discovered request. Entries beyond the declared
   32-request bound are marked failed and deleted, and the existing 34-request
   test enshrines that behavior.
3. One physical gesture may publish more than once because button-down,
   non-client button-down, and context-menu messages all publish after debounce
   removal.
4. Discovery parses every matching JSON file before selection, and selected files
   are read again. Per-cycle work remains unbounded without count and byte limits.
5. The C++ producer emits an unsigned 64-bit sequence while PowerShell accepts a
   signed 64-bit sequence. Restart/clock behavior also cannot rely on FILETIME as
   the ordering identity.

## Static Pass

The main streamer-ring count is `8` in native source, PowerShell, host manifest,
visual-lock documentation, and direct assertions. This is static alignment, not
live visual proof.

## Required Remediation

- Publish a flushed same-directory temporary file without replace semantics and
  retry occupied destinations a bounded number of times.
- Make one drain attempt at most 32 requests; defer untouched backlog and report
  discovered/attempted/deferred/remaining truthfully.
- Bound discovery count, file bytes, and projected marker fields before parsing.
- Preserve one-publication-per-gesture semantics without suppressing separate
  rapid gestures.

## Evidence And Limits

- Worktree was clean at the exact candidate; parent/base relationship verified.
- All seven changed files and the native build entrypoint were inspected.
- `git diff --check d5516a54..a1b2c60b` exited `0`.
- HARBOR ran no build, pytest, PowerShell execution, renderer, or live process.

Live renderer activation remains operator-gated and was not attempted.
