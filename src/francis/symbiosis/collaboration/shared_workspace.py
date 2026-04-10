from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["WorkspaceArtifact", "SharedWorkspace"]


@dataclass(frozen=True)
class WorkspaceArtifact:
    artifact_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SharedWorkspace:
    artifacts: list[WorkspaceArtifact] = field(default_factory=list)
