# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: active agent `019f6100-96ab-7631-98b0-5b92909186e0`
- Liveness: live/controllable in `CR-20260714-003`; interruption directive
  accepted and known pytest PIDs absent
- Current assignment: CR-FORGE-001 managed-copy safe-delta candidate review
- Current task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- Runtime lease: `LEASE-FORGE-001`; services and real Orb denied
- Contracts in play: `stage18_managed_copy_safe_delta_review_v1`, provisioning,
  structural isolation, tenant safe-delta policy, actor scope, drift readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: clean commit `90c4dbe0287c1f169cefad47debab85067dd4fd8`;
  `VAL-20260714-006` diff-check pass; `VAL-20260714-002` is
  `INTERRUPTED_KNOWN_REMEDIATION`; SENTINEL/MERIDIAN reviews archived
- Unresolved questions: exact envelope/lineage, per-lineage latest/invalidity,
  enum redaction, canonical nested path ownership, and stale receipt-path claim
- Current blocker: `MSG-20260714-012` and `MSG-20260714-015` require remediation
- Dependencies: committed card sync; HARBOR/VERA/ARCHIVIST after remediation;
  repeat MERIDIAN/SENTINEL only for materially affected questions
- Next action: execute remediation cycle one; report only a new focused-green
  commit or a path-owner contract blocker
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
