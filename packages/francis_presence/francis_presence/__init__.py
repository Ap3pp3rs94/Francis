from .briefing import compose_briefing
from .narrator import build_presence_grounding, build_presence_headline, build_presence_lines, compose_operator_presence
from .notifications import build_notification_digest
from .rituals import build_handback_ritual, build_shift_report
from .state import PresenceState, compute_state
from .tone import MODE_OPENERS, compose_mode_briefing, normalize_mode
from .triggers import detect_presence_triggers

__all__ = [
    "MODE_OPENERS",
    "PresenceState",
    "build_handback_ritual",
    "build_notification_digest",
    "build_presence_grounding",
    "build_presence_headline",
    "build_presence_lines",
    "build_shift_report",
    "compose_briefing",
    "compose_mode_briefing",
    "compose_operator_presence",
    "compute_state",
    "detect_presence_triggers",
    "normalize_mode",
]
