# Francis Control Room Session Topology

Observed: 2026-07-14T10:55:59-05:00

A durable seat does not prove a live agent. `Controllable` means the current
ATLAS session successfully addressed or waited on the native agent handle during
this sync cycle.

| Seat | Durable seat | Live session | Controllable | Live state | Native session evidence | Current activity |
| --- | --- | --- | --- | --- | --- | --- |
| ATLAS | yes | yes | local manager | running | Codex session UUID unavailable; terminal session `41434` is only the exact-head pytest handle | management, review, and exact-head validation |
| FORGE | yes | yes | yes | running | agent `019f6100-96ab-7631-98b0-5b92909186e0`; interrupt submission `019f6157-02a8-7882-93dc-fabc3b3839b7`; known pytest PIDs absent | remediation cycle one at `90c4dbe0` |
| ARGUS | yes | yes | yes | running | agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`; interrupt submission `019f6157-1cbb-7303-81dc-cb9627297212`; known pytest PIDs absent | remediation cycle one at `2e454ba5`; first integration priority |
| LUMEN | yes | yes | yes | running | agent `019f6100-9898-7353-9359-ed4727e2a4cb`; interrupt submission `019f6157-3cd3-78f2-a6ad-1262f535e849`; known pytest PIDs absent | remediation cycle one at `a1b2c60b` |
| VERA | yes | no | resumable prior session | completed/released | prior agent `019f6100-9955-78f0-abda-5abd175b953a` | preflight archived; exact candidates not yet eligible |
| SENTINEL | yes | no | resumable prior session | completed/released | prior agent `019f612d-46f2-78b1-bb84-2942081c86c1` | FORGE preflight archived; remediation required |
| HARBOR | yes | no | resumable prior session | completed/released | prior agent `019f6119-b5ef-7721-91c1-5c628ce3ec61` | environment and LUMEN reviews archived |
| CLAUDE | yes | unverified | no verified bridge | unreachable/unverified | none | do not simulate |
| MERIDIAN | yes | no | resumable prior session | completed/released | prior agent `019f613f-ae1a-7643-ba3d-b3793cc79233` | FORGE architecture review archived |
| ARCHIVIST | yes | no | resumable prior session | completed/released | prior agent `019f6144-d5f2-7923-80c9-ae0b3f2bfce4` | CR-003 precommit audit archived; corrections required |
| ECHO | yes | no | no active handle | unstaffed | none | handoff review available when needed |

No worker is duplicated while its current native handle remains live. Completed
reviewer IDs identify prior controllable sessions, not currently running agents.
