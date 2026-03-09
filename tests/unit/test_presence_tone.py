import pytest

from francis_presence.tone import compose_mode_briefing, normalize_mode


def test_compose_mode_briefing_preserves_receipt_language() -> None:
    briefing = compose_mode_briefing(
        objective="Verify the service foundation slice",
        mode="pilot",
    )

    assert "Pilot mode." in briefing
    assert "Objective: Verify the service foundation slice." in briefing
    assert "Claims remain tied to visible receipts and current scope." in briefing


def test_normalize_mode_rejects_unknown_modes() -> None:
    with pytest.raises(ValueError):
        normalize_mode("godmode")
