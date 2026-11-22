"""Port for reading and writing a user's saved dashboard layout.

A layout holds only identifiers and positions (ADR-0011). A miss returns the
config-defined default at version 0 and writes nothing. Saves are optimistic:
the caller sends the loaded version, and a mismatch raises LayoutConflictError
carrying the current layout so the handler can return HTTP 409.

``visible_ids`` is mandatory. It is the caller's role-filtered id set; the
repository intersects it with the config catalogue and never widens it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from finsight.core.errors import LayoutConflictError
from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_draft import LayoutDraft
from finsight.domain.value_objects.layout_record import LayoutRecord
from finsight.domain.value_objects.visible_ids import VisibleIds

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, UserId


class DashboardLayoutRepository(ABC):
    """Tenant- and user-scoped saved-layout store."""

    @abstractmethod
    async def get_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        """Return the visible saved layout or config default; never write."""
        raise NotImplementedError

    @abstractmethod
    async def save_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        layout: LayoutDraft,
        expected_version: int,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        """Conditionally save the draft, incrementing its version on success."""
        raise NotImplementedError

    @abstractmethod
    async def delete_layout(self, company_id: CompanyId, user_id: UserId) -> None:
        """Remove the saved layout so a later read returns the config default."""
        raise NotImplementedError


# Ticket-facing alias; the concrete class name follows the repo's file/class rule.
DashboardLayoutRepositoryPort = DashboardLayoutRepository

__all__ = [
    'DashboardLayoutRepository',
    'DashboardLayoutRepositoryPort',
    'LayoutChart',
    'LayoutConflictError',
    'LayoutDraft',
    'LayoutRecord',
    'VisibleIds',
]
