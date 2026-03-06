from tests.test_presence_state_grounding import (
    test_grounded_briefing_headline_changes_with_alerts,
    test_ledger_accumulates_presence_events,
    test_presence_state_returns_counts_and_ledger,
)


def test_presence_state_returns_counts_and_ledger_integration() -> None:
    test_presence_state_returns_counts_and_ledger()


def test_grounded_briefing_headline_changes_with_alerts_integration() -> None:
    test_grounded_briefing_headline_changes_with_alerts()


def test_ledger_accumulates_presence_events_integration() -> None:
    test_ledger_accumulates_presence_events()
