"""Immutable saved dashboard layout record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
