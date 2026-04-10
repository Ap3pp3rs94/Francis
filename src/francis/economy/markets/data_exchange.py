from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["DataOffer", "DataExchange"]


@dataclass(frozen=True)
class DataOffer:
    dataset: str
    price: float
    metadata: dict[str, Any] = field(default_factory=dict)


class DataExchange:
    def __init__(self) -> None:
        self._offers: list[DataOffer] = []

    def offer(self, offer: DataOffer) -> None:
        if not isinstance(offer, DataOffer):
            logger.warning("offer expected DataOffer")
            return
        self._offers.append(offer)

    def list_offers(self) -> list[DataOffer]:
        return list(self._offers)
