"""Immutable chart entry in a saved dashboard layout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LayoutChart:
    """A config-defined chart id and its span hint."""

    chart_id: str
    span: str

    def to_mapping(self) -> dict[str, Any]:
        """Return the JSON shape stored in ``dashboard_layouts.charts``."""
        return {'chart_id': self.chart_id, 'span': self.span}
