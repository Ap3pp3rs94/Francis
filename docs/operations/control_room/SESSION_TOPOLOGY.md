# Francis Control Room Session Topology

Observed: 2026-07-14T16:29:41-05:00

A durable seat does not prove a live agent. `Controllable` means the current
ATLAS session successfully addressed or waited on the native agent handle during
this sync cycle.

| Seat | Durable seat | Live session | Controllable | Live state | Native session evidence | Current activity |
| --- | --- | --- | --- | --- | --- | --- |
| ATLAS | yes | yes | local manager | running | Codex session UUID unavailable; `VAL-20260714-028` exit `0` on exact `cdfc4a23` | CR-005 commit, rebase, and promotion sequencing |
| FORGE | yes | no | no | completed/released | correction-session evidence archived; worker `24658090`; integration `cdfc4a23`; `VAL-028` pass | ready for exact post-CR-005 rebase proof |
| ARGUS | yes | no | no | unavailable / `not_found` | prior agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`; last verified commit `683134a7` | parked on teaching-consumer scope blocker |
| LUMEN | yes | no | no | unavailable / `not_found` | prior agent `019f6100-9898-7353-9359-ed4727e2a4cb`; last verified commit `60070438` | parked on durable sequence/outcome ownership blocker |
| VERA | yes | no | no | unavailable / `not_found` | prior agent `019f6100-9955-78f0-abda-5abd175b953a` | final FORGE review archived |
| SENTINEL | yes | no | no | unavailable / `not_found` | prior agent `019f612d-46f2-78b1-bb84-2942081c86c1` | final FORGE review archived |
| HARBOR | yes | no | no | completed/released | handle `019f623e-597e-7040-be36-f6d93164407d`; review archived | `cdfc4a23` affected-delta review passed |
| CLAUDE | yes | unverified | no verified bridge | unreachable/unverified | none | do not simulate |
| MERIDIAN | yes | no | no | unavailable / `not_found` | prior agent `019f613f-ae1a-7643-ba3d-b3793cc79233` | final FORGE architecture review archived |
| ARCHIVIST | yes | no | no | completed/released | handle `019f623d-ae53-79c0-9645-abbfb6051d02` completed this cycle | CR-005 stale-record reconciliation completed |
| ECHO | yes | no | no active handle | unstaffed | none | handoff review available when needed |

Native wait returned `not_found` for every listed prior worker/reviewer handle.
Their IDs preserve provenance only and are not evidence of current reachability.
