"""Port for reading and writing a user's saved dashboard layout.

The public class keeps the ticket-facing ``DashboardLayoutRepositoryPort`` name;
the module path is fixed by issue #371. A layout holds only identifiers and
positions (ADR-0011). A miss returns the config-defined default at version 0 and
writes nothing. Saves are optimistic: the caller sends the loaded version, and a
mismatch raises LayoutConflictError carrying the current layout so the handler
can return HTTP 409.

``visible_ids`` is a required keyword extension to issue #371's shorthand
method signatures. Phase 2 spec §3.4 requires reads and saves to drop ids the
role may not see and skip ids unknown to config; migration 0009 expects the
caller to supply that role/config intersection. The repository never widens it.
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


class DashboardLayoutRepositoryPort(ABC):
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


# Backwards-compatible alias for callers that used the pre-review class name.
DashboardLayoutRepository = DashboardLayoutRepositoryPort

__all__ = [
    'DashboardLayoutRepository',
    'DashboardLayoutRepositoryPort',
    'LayoutChart',
    'LayoutConflictError',
    'LayoutDraft',
    'LayoutRecord',
    'VisibleIds',
]
