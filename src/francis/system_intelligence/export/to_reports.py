from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ReportExport", "ReportExporter"]


@dataclass(frozen=True)
class ReportExport:
    title: str
    sections: dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.utcnow)


class ReportExporter:
    def export(self, title: str, sections: dict[str, Any]) -> ReportExport | None:
        if not isinstance(title, str) or not title.strip():
            logger.warning("export expected title")
            return None
        if not isinstance(sections, dict):
            sections = {}
        return ReportExport(title=title.strip(), sections=dict(sections))
