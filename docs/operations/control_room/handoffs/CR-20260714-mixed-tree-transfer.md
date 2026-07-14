# Mixed-Tree Transfer Handoff - CR-20260714

Archive root: `D:\Francis-archives\control-room-activation-20260714-091739`

ATLAS verified each archived file was readable, applied each patch to its named
worktree, reproduced the same patch hash from that worktree, and restored the
shared tracked path only after equality. Unknown untracked paths were untouched.

| Front | Archive file | Bytes | SHA256 |
| --- | --- | ---: | --- |
| ARGUS | `argus-game-observer.patch` | 44070 | `25652a348fab7e974713b3dd2169a9e567df0131f6d0fd216e342f193e578940` |
| ATLAS | `atlas-control-room.patch` | 41749 | `f32d859ae192721f49dc390f763915047e0b78228250cdffd9e032b43a8585d9` |
| FORGE | `forge-managed-copy-safe-delta.patch` | 27305 | `a085f924138c1900b0030b348a1f37d633c32146a50f1d769daa10886aad8877` |
| LUMEN | `lumen-orb-choreography.patch` | 26604 | `8e8bb1f73430840f970aa17577a067694042760f21f11e5b054ffd37045f3961` |
| FORGE untracked source | `managed_copy_safe_delta.py` | 26091 | `92505592e84f0cbd268b0d42092c4a12f1a7e52025854748b81319a77e27f5b2` |

Worktree destinations:

- FORGE: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- ARGUS: `D:\Francis-worktrees\argus-game-observer`
- LUMEN: `D:\Francis-worktrees\lumen-orb-choreography`

The archive is preservation evidence, not acceptance evidence. Every front
still requires a worker commit, review, exact-head validation, and promotion.
