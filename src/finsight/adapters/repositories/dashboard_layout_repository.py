"""SQL-only Postgres/Neon saved-layout repository implementing the layout port.

Reads and conditional saves call the ``dashboard_layout_get`` and
``dashboard_layout_save`` functions from migration 0009 with the company RLS
context set for the transaction. The caller supplies the role-filtered visible
id set; this adapter never substitutes an alternate store when no session is
wired.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.dashboard_layout_repository import (
    DashboardLayoutRepository as DashboardLayoutRepositoryPort,
)
from finsight.domain.ports.dashboard_layout_repository import (
    LayoutConflictError,
    LayoutRecord,
    VisibleIds,
)

from . import _dashboard_layout_repository_records as _records
from .base_repository import BaseRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from finsight.core.types import CompanyId, UserId

_GET_SQL = 'SELECT * FROM dashboard_layout_get(:company_id, :user_id, CAST(:visible_ids AS jsonb))'
_SAVE_SQL = (
    'SELECT * FROM dashboard_layout_save('
    ':company_id, :user_id, :expected_version, '
    'CAST(:kpi_codes AS jsonb), CAST(:charts AS jsonb), CAST(:visible_ids AS jsonb))'
)
_DELETE_SQL = 'DELETE FROM dashboard_layouts WHERE company_id = :company_id AND user_id = :user_id'


class DashboardLayoutRepository(DashboardLayoutRepositoryPort, BaseRepository):
    """Tenant- and user-scoped layout store backed only by the relational table."""

    def __init__(self, config: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        _records.validate_config(config)
        self._config = config

    async def _set_tenant(self, tenant: str) -> None:
        await self._raw_execute(
            "SELECT set_config('app.company_id', :company_id, true)",
            {'company_id': tenant},
        )

    async def _clear_tenant(self) -> None:
        await self._raw_execute("SELECT set_config('app.company_id', CAST(NULL AS text), true)")
        self._rls_company_id = None

    @asynccontextmanager
    async def _tenant_scope(self, company_id: Any) -> AsyncIterator[None]:
        await self._set_tenant(str(company_id))
        try:
            yield
        finally:
            await self._clear_tenant()

    async def _fetch_record(
        self, company_id: Any, user_id: Any, visible_ids: VisibleIds
    ) -> LayoutRecord:
        result = await self._raw_execute(
            _GET_SQL,
            {
                'company_id': str(company_id),
                'user_id': str(user_id),
                'visible_ids': json.dumps(visible_ids.to_mapping()),
            },
        )
        rows = await self._fetchall(result)
        if not rows:
            return _records.default_record(self._config, visible_ids)
        return _records.from_row(rows[0])

    async def _save_record(
        self,
        company_id: Any,
        user_id: Any,
        layout: Mapping[str, Any] | LayoutRecord,
        expected_version: int,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        payload = _records.json_fields(layout)
        result = await self._raw_execute(
            _SAVE_SQL,
            {
                'company_id': str(company_id),
                'user_id': str(user_id),
                'expected_version': expected_version,
                'kpi_codes': json.dumps(payload['kpi_codes']),
                'charts': json.dumps(payload['charts']),
                'visible_ids': json.dumps(visible_ids.to_mapping()),
            },
        )
        rows = await self._fetchall(result)
        if not rows:
            raise LayoutConflictError(await self._fetch_record(company_id, user_id, visible_ids))
        return _records.from_row(rows[0])

    async def get_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        """Return the visible saved layout or config default; never write."""
        async with self._tenant_scope(company_id):
            return await self._fetch_record(company_id, user_id, visible_ids)

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
        async with self._tenant_scope(company_id):
            return await self._save_record(
                company_id, user_id, layout, expected_version, visible_ids
            )

    async def delete_layout(self, company_id: CompanyId, user_id: UserId) -> None:
        """Remove the saved layout so a later read returns the config default."""
        async with self._tenant_scope(company_id):
            await self._raw_execute(
                _DELETE_SQL,
                {'company_id': str(company_id), 'user_id': str(user_id)},
            )
