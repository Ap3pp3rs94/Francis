from __future__ import annotations

from francis.lens.runtime_identity import canonical_orb_identity_id, runtime_identity, scoped_runtime_label


def test_runtime_identity_defaults_to_operator_identity(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_RUNTIME_IDENTITY", raising=False)

    assert runtime_identity() == ""
    assert scoped_runtime_label("Francis Lens") == "Francis Lens"
    assert canonical_orb_identity_id() == "francis.operator_orb"


def test_runtime_identity_scopes_proof_labels(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_RUNTIME_IDENTITY", "CPJ-001")

    assert runtime_identity() == "CPJ-001"
    assert scoped_runtime_label("Francis Lens") == "Francis Lens [CPJ-001]"
    assert canonical_orb_identity_id() == "francis.proof_orb.CPJ-001"


def test_runtime_identity_rejects_unsafe_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_RUNTIME_IDENTITY", "CPJ 001; unsafe")

    assert runtime_identity() == ""
    assert scoped_runtime_label("Francis Lens") == "Francis Lens"
