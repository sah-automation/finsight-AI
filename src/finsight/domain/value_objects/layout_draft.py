"""Immutable incoming dashboard layout payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .layout_chart import LayoutChart


@dataclass(frozen=True)
class LayoutDraft:
    """A caller's proposed layout before optimistic versioning is applied."""

    contract_version: int
    kpi_codes: tuple[str, ...]
    charts: tuple[LayoutChart, ...]

    def to_mapping(self) -> dict[str, Any]:
        """Return the storage/wire shape of this proposed layout."""
        return {
            'contract_version': self.contract_version,
            'kpi_codes': list(self.kpi_codes),
            'charts': [chart.to_mapping() for chart in self.charts],
        }
