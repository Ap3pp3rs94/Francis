from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["MultiDomainPlan", "MultiDomainPlanner"]


@dataclass(frozen=True)
class MultiDomainPlan:
    domains: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MultiDomainPlanner:
    def plan(self, domains: list[str]) -> MultiDomainPlan:
        if not isinstance(domains, list) or not domains:
            logger.warning("plan expected list of domains")
            return MultiDomainPlan(domains=[], steps=[])
        steps = [f"coordinate {domain}" for domain in domains]
        return MultiDomainPlan(domains=list(domains), steps=steps)
