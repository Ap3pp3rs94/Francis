"""Tests for the Francis self-understanding readback.

The self-model is the keystone: the seated intelligence reads it to understand
itself and its needs (identity, posture, open gaps, surfaces not yet wired,
roadmap) before completing the build -- without that understanding granting any
authority to act on itself.
"""

from __future__ import annotations

from francis.developer_bridge.francis_self_model import read_francis_self_model

_AUTHORITY_FLAGS = (
    "grants_execution_authority",
    "grants_mutation_authority",
    "grants_approval_authority",
    "grants_memory_write_authority",
    "grants_training_authority",
)


def test_self_model_has_the_four_understanding_facets() -> None:
    model = read_francis_self_model()
    assert model["ok"] is True
    assert model["mode"] == "read_only"
    for facet in ("identity", "posture", "needs", "roadmap"):
        assert facet in model
        assert isinstance(model[facet], dict)


def test_self_model_identity_is_seat_using_tools() -> None:
    identity = read_francis_self_model()["identity"]
    assert identity["uses_tools"] is True
    assert identity["maintains_one_shared_experience"] is True
    assert isinstance(identity["tools"], list)


def test_self_model_needs_are_structured() -> None:
    needs = read_francis_self_model()["needs"]
    assert isinstance(needs["open_orb_gaps"], list)
    assert isinstance(needs["surfaces_visible_but_not_yet_wired"], list)
    # Each named gap carries a concrete review artifact to act on.
    for gap in needs["open_orb_gaps"]:
        assert gap.get("plane_id")
        assert "review_artifact" in gap


def test_self_understanding_grants_no_authority() -> None:
    gov = read_francis_self_model()["governance"]
    assert gov["read_only"] is True
    assert gov["self_understanding_is_not_self_authority"] is True
    assert gov["capability_requires_grant_receipt"] is True
    for flag in _AUTHORITY_FLAGS:
        assert gov[flag] is False
