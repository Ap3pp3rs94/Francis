from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["DomainVersion", "DomainVersionManager"]


@dataclass(frozen=True)
class DomainVersion:
    domain: str
    version: str


class DomainVersionManager:
    def __init__(self) -> None:
        self._versions: dict[str, DomainVersion] = {}

    def set_version(self, domain: str, version: str) -> DomainVersion | None:
        if not domain or not version:
            logger.warning("set_version expected domain and version")
            return None
        dv = DomainVersion(domain=domain, version=version)
        self._versions[domain] = dv
        return dv

    def get_version(self, domain: str) -> DomainVersion | None:
        return self._versions.get(domain)
