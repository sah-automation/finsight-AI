"""Immutable saved dashboard layout record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from .layout_chart import LayoutChart


@dataclass(frozen=True)
class LayoutRecord:
    """A complete layout: identifiers, positions, version and timestamp."""

    contract_version: int
    kpi_codes: tuple[str, ...]
    charts: tuple[LayoutChart, ...]
    version: int
    updated_at: datetime | None = None

    def to_mapping(self) -> dict[str, Any]:
        """Return the wire/storage shape of this layout."""
        return {
            'contract_version': self.contract_version,
            'kpi_codes': list(self.kpi_codes),
            'charts': [chart.to_mapping() for chart in self.charts],
            'version': self.version,
            'updated_at': self.updated_at,
        }
