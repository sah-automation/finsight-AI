"""Port for reading and writing a user's saved dashboard layout.

A layout holds only identifiers and positions (ADR-0011). A miss returns the
config-defined default at version 0 and writes nothing. Saves are optimistic:
the caller sends the loaded version, and a mismatch raises LayoutConflictError
carrying the current layout so the handler can return HTTP 409.

``visible_ids`` is mandatory. It is the caller's already role-filtered id set
(the intersection of permissions and the config catalogue); the repository
never widens it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from finsight.core.errors import ConflictError
from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_record import LayoutRecord
from finsight.domain.value_objects.visible_ids import VisibleIds

if TYPE_CHECKING:
    from collections.abc import Mapping

    from finsight.core.types import CompanyId, UserId


class LayoutConflictError(ConflictError):
    """A save lost the optimistic-version race; carries the current layout."""

    def __init__(self, current_layout: LayoutRecord) -> None:
        super().__init__('layout changed elsewhere', code='layout_changed')
        self.current_layout = current_layout


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
        """Return the visible saved layout or the config default; never write."""
        raise NotImplementedError

    @abstractmethod
    async def save_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        layout: Mapping[str, Any] | LayoutRecord,
        expected_version: int,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        """Conditionally save the layout, incrementing its version on success."""
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
    'LayoutRecord',
    'VisibleIds',
]
