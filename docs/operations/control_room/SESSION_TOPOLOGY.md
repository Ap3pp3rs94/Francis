# Francis Control Room Session Topology

Observed: 2026-07-14T11:25:00-05:00

A durable seat does not prove a live agent. `Controllable` means the current
ATLAS session successfully addressed or waited on the native agent handle during
this sync cycle.

| Seat | Durable seat | Live session | Controllable | Live state | Native session evidence | Current activity |
| --- | --- | --- | --- | --- | --- | --- |
| ATLAS | yes | yes | local manager | running | Codex session UUID unavailable; no material validation process remains | management, scope revision, and integration sequencing |
| FORGE | yes | no | resumable | completed/released | agent `019f6100-96ab-7631-98b0-5b92909186e0`; last verified commit `cd9cd504` | final cycle-two assignment prepared under `CR-DEC-0012` |
| ARGUS | yes | no | resumable | completed/released | agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`; last verified commit `683134a7` | parked on teaching-consumer scope blocker |
| LUMEN | yes | no | resumable | completed/released | agent `019f6100-9898-7353-9359-ed4727e2a4cb`; last verified commit `60070438` | parked on durable sequence/outcome ownership blocker |
| VERA | yes | no | resumable prior session | completed/released | prior agent `019f6100-9955-78f0-abda-5abd175b953a` | exact ARGUS/LUMEN/FORGE remediation reviews returned |
| SENTINEL | yes | no | resumable prior session | completed/released | prior agent `019f612d-46f2-78b1-bb84-2942081c86c1` | exact ARGUS/LUMEN reviews returned |
| HARBOR | yes | no | resumable prior session | completed/released | prior agent `019f6119-b5ef-7721-91c1-5c628ce3ec61` | exact ARGUS/LUMEN/FORGE reviews returned |
| CLAUDE | yes | unverified | no verified bridge | unreachable/unverified | none | do not simulate |
| MERIDIAN | yes | no | resumable prior session | completed/released | prior agent `019f613f-ae1a-7643-ba3d-b3793cc79233` | exact ARGUS/FORGE architecture reviews returned |
| ARCHIVIST | yes | no | prior session closed | completed/released | LUMEN review agent `019f616f-6063-7b13-b1aa-bfd5a3b3e192` | exact LUMEN receipt-truth review returned |
| ECHO | yes | no | no active handle | unstaffed | none | handoff review available when needed |

No worker is duplicated while its current native handle remains live. Completed
reviewer IDs identify prior controllable sessions, not currently running agents.
