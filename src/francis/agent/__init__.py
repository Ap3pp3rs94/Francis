from __future__ import annotations

import logging

from .delegation import DelegationDecision, DelegationPolicy, DelegationRouter
from .executor import Executor, ExecutionResult
from .outcomes import Outcome, OutcomeLog
from .task import Task, TaskStatus
from .tool_selector import ToolSelection, ToolSelector

logger = logging.getLogger(__name__)

__all__ = [
    "DelegationDecision",
    "DelegationPolicy",
    "DelegationRouter",
    "Executor",
    "ExecutionResult",
    "Outcome",
    "OutcomeLog",
    "Task",
    "TaskStatus",
    "ToolSelection",
    "ToolSelector",
    "get_version",
    "initialize_agent",
]


def get_version() -> str:
    return "0.1.0"


def initialize_agent() -> None:
    try:
        logger.info("Initializing agent...")
        logger.info("Agent initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize agent: %s", e)
