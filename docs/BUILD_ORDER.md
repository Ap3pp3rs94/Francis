# FRANCIS - Canonical Build Order

This file translates the ORB model into the practical sequence for building Francis.

The authoritative architectural sources are:

- `docs/PLANES.md`
- `meta/plane_map.yaml`
- `BUILD_MANIFEST.md`

## 1. Rule

Build Francis by completing planes and enforcing transitions, not by filling folders
or shipping isolated UI features.

The ORB is canonical. If a roadmap decision conflicts with plane boundaries, the
plane model wins.

## 2. Runtime flow vs build order

The runtime flow of a request is:

`P1_INTERFACE -> P4_COGNITION -> P3_GOVERNANCE -> P2_IDENTITY -> P7_EXECUTION -> P9_OBSERVABILITY -> P8_MEMORY`

Optional paths:

- `P4_COGNITION -> P5_EVIDENCE -> P4_COGNITION`
- `P4_COGNITION -> P6_SIMULATION -> P4_COGNITION`
- `P8_MEMORY <-> P10_FEDERATION`

The build order is different because the control spine must exist before the product
surface is trusted:

1. `P0_FOUNDATION`
2. `P9_OBSERVABILITY`
3. `P3_GOVERNANCE`
4. `P2_IDENTITY`
5. `P4_COGNITION`
6. `P7_EXECUTION`
7. `P8_MEMORY`
8. `P1_INTERFACE`
9. `P5_EVIDENCE`
10. `P6_SIMULATION`
11. `P10_FEDERATION`

## 3. What "functional" means

Francis is functionally real when a primary operator request can move end to end
through the ORB:

- request captured in `P1_INTERFACE`
- plan produced in `P4_COGNITION`
- gate evaluated in `P3_GOVERNANCE`
- identity and scope confirmed in `P2_IDENTITY`
- authorized action performed in `P7_EXECUTION`
- trace recorded in `P9_OBSERVABILITY`
- continuity updated in `P8_MEMORY`

Anything less is still partial runtime infrastructure.

## 4. What "user-friendly" means

Francis is user-friendly when the operator can understand the ORB without reading
source code.

Required UX outcomes:

- current plane is visible
- blocked work names the missing approval, policy, or trust gate
- approvals are tied to concrete actions
- traces and artifacts are easy to inspect
- backlog and continuity state are trustworthy
- errors are actionable

The ORB should be the visible product shape, not hidden implementation detail.

## 5. Current priority

Near-term work should stay in this order:

1. close server-side governance and identity gaps
2. finish the end-to-end plan -> gate -> execute -> trace -> memory loop
3. expose that loop clearly in the chat UI
4. only then expand evidence, simulation, and federation surfaces

## 6. Local run commands

1. Optional services:
   `docker compose -f infra/docker/compose.yaml up -d`

2. Python:
   `uv venv`
   `uv pip install -e .`
   `python -m francis api`
   `python -m francis daemon`

3. UI:
   `cd apps/chat_ui`
   `npm install`
   `npm run dev`
