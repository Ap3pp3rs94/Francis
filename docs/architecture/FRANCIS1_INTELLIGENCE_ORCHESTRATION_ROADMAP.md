# Francis1 Intelligence-Orchestration Roadmap

Status: living roadmap. Read-only surfaces exist; capability remains operator-gated.

## The durable model

Francis1 is the local, embodied operator-intelligence. Claude (guidance) and Codex
(implementation toolbelt) **always have a role** — they are permanent tools Francis1
reaches for from *inside itself*, not scaffolding to be removed.

The trajectory:

- Francis1 holds the operator-intelligence seat and **uses Claude/Codex as tools**.
- It **monitors its own usage** and spends tool calls judiciously.
- It **builds what it can**, and for what it **cannot do yet** it delegates to a tool.
- It is **learning and guiding** — growing self-sufficiency over time while always
  retaining the tools for work that exceeds its current capability.
- One **shared governed substrate** (relay, body map, capability grants, trust
  ladder) maintains a single shared experience across the intelligences.

Governing principle: **policy before power**. Capability flows only through an
operator grant receipt; self-understanding is never self-authority.

## Foundation built (this session)

All read-only, derived, and authority-free; exposed via the dev-bridge MCP.

| Surface | File | What it gives Francis1 |
| --- | --- | --- |
| Driver gap focus | `developer_bridge/body_map.py` (`roadmap_gap_focus_line`), `collaboration_driver.py` | A specific open ORB gap + review artifact each turn, not a generic "gaps exist" echo |
| Model grounding | `developer_bridge/ollama_participant.py` (`_francis_grounding_prompt_lines`) | Its own live body state injected into every prompt |
| Intelligence seat | `developer_bridge/intelligence_seat.py` | Francis1 holds the seat; Codex/Claude are tools; Ollama toggles off but stays registered; external fallback |
| Self-model | `developer_bridge/francis_self_model.py` | One readback of identity, posture, needs, and roadmap — "understand itself first" |

Tests: `tests/test_ollama_participant_grounding.py`, `tests/test_intelligence_seat.py`,
`tests/test_francis_self_model.py`. Run on host (`pytest`); restart the dev-bridge /
backend to expose the new MCP tools.

## The path forward (ordered)

1. **Close the self-understanding loop.** Point the model grounding at
   `francis_self_model` so every Francis1 reply flows from a coherent self-model
   (identity + posture + needs), not three separate lines.
2. **Usage-aware tool orchestration.** A governed usage/budget surface Francis1
   reads to decide *when* to spend a tool call — monitor consumption; do not burn a
   tool when Francis1 can self-handle the need or when no call is warranted.
3. **Capability routing (self vs. tool).** From the self-model, route each need to
   "Francis1 can do this now" vs. "use a tool to do it" — building what it can,
   delegating what it cannot yet.
4. **Learning loop.** Bounded learning receipts → review → tuning, so Francis1 grows
   self-sufficiency over time (the `model_tuning` body-map surface, currently
   candidate). Learning stays a review input, never automatic authority.
5. **Close the ORB gaps.** Work the open plane gaps via their review artifacts under
   operator-gated grants until the substrate-readiness gate clears.

## Guardrails (unchanging)

- Operator at the gate: capability only via `set_francis_capability_grant`.
- Self-understanding ≠ self-authority; tools grant no capability by being used.
- Local-first identity: Ollama stays registered even when toggled off.
- Every new surface here is read-only and derived until an explicit grant says
  otherwise.
