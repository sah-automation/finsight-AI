"""Immutable incoming dashboard layout payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .layout_chart import LayoutChart


@dataclass(frozen=True)
class LayoutDraft:
    """A caller's proposed layout before optimistic versioning is applied."""

    contract_version: int
    kpi_codes: tuple[str, ...]
    charts: tuple[LayoutChart, ...]
