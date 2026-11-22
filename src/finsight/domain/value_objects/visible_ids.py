"""Immutable set of identifiers a caller may see in a dashboard layout."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisibleIds:
    """Role-filtered ids; the layout repository never widens this set."""

    kpi_codes: tuple[str, ...]
    chart_ids: tuple[str, ...]

    def to_mapping(self) -> dict[str, list[str]]:
        """Return the JSON shape expected by migration 0009's SQL functions."""
        return {'kpi_codes': list(self.kpi_codes), 'chart_ids': list(self.chart_ids)}
