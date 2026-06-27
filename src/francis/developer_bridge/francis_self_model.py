"""Francis self-understanding readback (read-only, grants no authority).

Composes the existing governed surfaces into one coherent self-model the seated
intelligence reads to understand *itself and its needs* before completing the
build or expanding the roadmap:

  - identity: the intelligence seat and the tools it uses (intelligence_seat),
  - posture: phase and what is wired vs only visible (body map),
  - needs: open ORB coverage gaps and surfaces it can see but is not yet wired
    into, plus how many capabilities are actually granted,
  - roadmap: the canonical sources and the shape of what to build next.

Understanding itself is not authority to act on itself. This readback is derived
and read-only; capability still flows only through an operator grant receipt and
the trust ladder, with the operator at the gate.
"""

from __future__ import annotations

from francis.developer_bridge.body_map import read_francis_body_map
from francis.developer_bridge.capability_grants import read_francis_capability_grants
from francis.developer_bridge.intelligence_seat import read_intelligence_seat

_KIND = "developer_bridge.francis_self_model"
_SCHEMA_VERSION = "developer_bridge_francis_self_model_v1"
_MAX_NEEDS = 12


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _identity(seat: dict[str, object]) -> dict[str, object]:
    seat_lane = _dict(seat.get("seat_lane"))
    return {
        "seated_lane": seat.get("seated_lane"),
        "seat_role": seat_lane.get("role"),
        "seat_identity": seat_lane.get("identity"),
        "uses_tools": seat.get("seated_intelligence_uses_tools", True),
        "tools": [
            {
                "lane_id": _dict(tool).get("lane_id"),
                "role": _dict(tool).get("role"),
                "enabled": _dict(tool).get("enabled"),
            }
            for tool in _list(seat.get("tool_lanes"))
        ],
        "maintains_one_shared_experience": _dict(seat.get("shared_substrate")).get(
            "maintains_one_shared_experience", True
        ),
    }


def _posture(body: dict[str, object]) -> dict[str, object]:
    phase = _dict(body.get("phase"))
    summary = _dict(body.get("summary"))
    return {
        "phase": phase.get("current"),
        "phase_posture": phase.get("posture"),
        "priority": phase.get("priority"),
        "surface_count": summary.get("surface_count"),
        "connected_or_partial_count": summary.get("connected_or_partial_count"),
        "connected_to_local_model_count": summary.get("connected_to_local_model_count"),
        "full_body_visible": summary.get("full_body_visible"),
        "full_body_authority_granted": summary.get("full_body_authority_granted"),
        "open_orb_gap_count": summary.get("coverage_open_gap_count"),
    }


def _open_gaps(body: dict[str, object]) -> list[dict[str, object]]:
    coverage = _dict(body.get("coverage_review"))
    gaps: list[dict[str, object]] = []
    for raw in _list(coverage.get("items")):
        item = _dict(raw)
        remaining = _list(item.get("remaining_gaps"))
        if not remaining:
            continue
        gaps.append(
            {
                "plane_id": item.get("plane_id"),
                "posture": item.get("current_posture"),
                "risk_level": item.get("risk_level"),
                "need": str(remaining[0])[:160],
                "review_artifact": item.get("next_review_artifact"),
            }
        )
    return gaps[:_MAX_NEEDS]


def _surfaces_not_yet_wired(body: dict[str, object]) -> list[dict[str, object]]:
    surfaces: list[dict[str, object]] = []
    for raw in _list(body.get("surfaces")):
        surface = _dict(raw)
        exposure = _dict(surface.get("capability_exposure"))
        if exposure.get("connected_to_local_model") is False:
            surfaces.append(
                {
                    "surface_id": surface.get("id"),
                    "label": surface.get("label"),
                    "access_mode": surface.get("access_mode"),
                    "next_trust_gate": exposure.get("next_trust_gate"),
                }
            )
    return surfaces[:_MAX_NEEDS]


def read_francis_self_model() -> dict[str, object]:
    """Read Francis's coherent self-model without granting any authority."""

    body = read_francis_body_map()
    seat = read_intelligence_seat()
    grants = read_francis_capability_grants()
    grant_summary = _dict(grants.get("summary"))
    summary = _dict(body.get("summary"))

    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": _KIND,
        "identity": _identity(seat),
        "posture": _posture(body),
        "needs": {
            "summary": "What Francis must understand and close before completing the build.",
            "open_orb_gaps": _open_gaps(body),
            "open_orb_gap_count": summary.get("coverage_open_gap_count"),
            "surfaces_visible_but_not_yet_wired": _surfaces_not_yet_wired(body),
            "active_capability_grants": grant_summary.get("granted_count", 0),
        },
        "roadmap": {
            "complete_the_build": "Close each open ORB gap via its review_artifact, under operator-gated grants.",
            "expand_for_future_dev": "Once the ORB planes are closed and capability stays governed, extend beyond the current plane map.",
            "build_on_substrate": "Add operator-facing capability on the governed runtime spine, keeping policy before power.",
            "canonical_sources": [
                "docs/operations/COMPLETION_LEDGER.md",
                "docs/canonical/BUILD_MANIFEST.md",
            ],
        },
        "governance": {
            "read_only": True,
            "derived_from": [
                "developer_bridge.francis_body_map",
                "developer_bridge.intelligence_seat",
                "developer_bridge.capability_grants",
            ],
            "self_understanding_is_not_self_authority": True,
            "capability_requires_grant_receipt": True,
            "requires_codex_or_operator_review_before_capability_exposure": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }
