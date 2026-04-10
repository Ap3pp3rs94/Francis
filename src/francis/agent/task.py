from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

__all__ = ["TaskStatus", "Task", "create_task", "update_task", "mark_task_completed"]


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    description: str
    priority: int = 5
    status: str = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(UTC).replace(microsecond=0).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).replace(microsecond=0).isoformat())
    meta: dict[str, str] = field(default_factory=dict)

    def mark_completed(self) -> None:
        self.status = TaskStatus.COMPLETED
        self.updated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        logger.info("Task %s marked completed", self.task_id)


def _clamp_priority(priority: int) -> int:
    return max(1, min(int(priority), 9))


def create_task(task_id: str, description: str, priority: int = 5) -> Task:
    try:
        return Task(task_id=task_id, description=description, priority=_clamp_priority(priority))
    except Exception as exc:
        logger.error("Failed to create task: %s", exc)
        raise


def update_task(task: Task, *, description: str | None = None, priority: int | None = None) -> Task:
    try:
        if description is not None:
            task.description = description
        if priority is not None:
            task.priority = _clamp_priority(priority)
        task.updated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        logger.info("Task %s updated", task.task_id)
        return task
    except Exception as exc:
        logger.error("Failed to update task: %s", exc)
        raise


def mark_task_completed(task: Task) -> Task:
    task.mark_completed()
    return task
