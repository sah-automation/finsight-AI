"""Postgres/Neon saved-layout repository implementing the layout port.

Reads and conditional saves go through the ``dashboard_layout_get`` and
``dashboard_layout_save`` functions from migration 0009 with the company RLS
context set for the transaction. With no wired session the adapter uses an
in-memory seam for the contract suite.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.dashboard_layout_repository import (
    DashboardLayoutRepository as DashboardLayoutRepositoryPort,
)
from finsight.domain.ports.dashboard_layout_repository import (
    LayoutConflictError,
    LayoutRecord,
    VisibleIds,
)

from . import _dashboard_layout_repository_layout as _layout
from . import _dashboard_layout_repository_memory as _memory
from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, UserId

_GET_SQL = 'SELECT * FROM dashboard_layout_get(:company_id, :user_id, CAST(:visible_ids AS jsonb))'
_SAVE_SQL = (
    'SELECT * FROM dashboard_layout_save('
    ':company_id, :user_id, :expected_version, '
    'CAST(:kpi_codes AS jsonb), CAST(:charts AS jsonb), CAST(:visible_ids AS jsonb))'
)
_DELETE_SQL = 'DELETE FROM dashboard_layouts WHERE company_id = :company_id AND user_id = :user_id'


class DashboardLayoutRepository(DashboardLayoutRepositoryPort, BaseRepository):
    """Tenant- and user-scoped layout store; SQL when wired, in-memory otherwise."""

    def __init__(self, config: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._memory: _memory.LayoutMemory = {}

    @staticmethod
    def _key(company_id: Any, user_id: Any) -> tuple[str, str]:
        return (str(company_id), str(user_id))

    async def _set_tenant(self, tenant: str) -> None:
        await self._raw_execute(
            "SELECT set_config('app.company_id', :company_id, true)",
            {'company_id': tenant},
        )

    async def _clear_tenant(self) -> None:
        await self._raw_execute("SELECT set_config('app.company_id', CAST(NULL AS text), true)")
        self._rls_company_id = None

    async def _fetch_record(self, company_id: Any, user_id: Any, context: Any) -> LayoutRecord:
        result = await self._raw_execute(
            _GET_SQL,
            {
                'company_id': str(company_id),
                'user_id': str(user_id),
                'visible_ids': json.dumps(context.visible),
            },
        )
        rows = await self._fetchall(result)
        if not rows:
            return _layout.default_record(self._config, context.visible)
        return _layout.row_to_record(rows[0])

    async def _save_record(
        self, company_id: Any, user_id: Any, layout: Any, expected_version: int, context: Any
    ) -> LayoutRecord:
        codes, charts = _layout.as_identifiers(layout)
        result = await self._raw_execute(
            _SAVE_SQL,
            {
                'company_id': str(company_id),
                'user_id': str(user_id),
                'expected_version': expected_version,
                'kpi_codes': json.dumps(codes),
                'charts': json.dumps(charts),
                'visible_ids': json.dumps(context.visible),
            },
        )
        rows = await self._fetchall(result)
        if not rows:
            raise LayoutConflictError(await self._fetch_record(company_id, user_id, context))
        return _layout.row_to_record(rows[0])

    async def get_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        *,
        visible_ids: VisibleIds | None = None,
        **kwargs: Any,
    ) -> LayoutRecord:
        context = _layout.context(self._config, visible_ids)
        if self._session is None:
            return _memory.stored_record(self._memory, self._key(company_id, user_id), context)
        await self._set_tenant(str(company_id))
        try:
            return await self._fetch_record(company_id, user_id, context)
        finally:
            await self._clear_tenant()

    async def save_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        layout: Any,
        expected_version: int,
        *,
        visible_ids: VisibleIds | None = None,
        **kwargs: Any,
    ) -> LayoutRecord:
        context = _layout.context(self._config, visible_ids)
        if self._session is None:
            return _memory.put_record(
                self._memory,
                self._key(company_id, user_id),
                layout,
                expected_version,
                context,
            )
        await self._set_tenant(str(company_id))
        try:
            return await self._save_record(company_id, user_id, layout, expected_version, context)
        finally:
            await self._clear_tenant()

    async def delete_layout(self, company_id: CompanyId, user_id: UserId, **kwargs: Any) -> None:
        if self._session is None:
            _memory.remove_record(self._memory, self._key(company_id, user_id))
            return
        await self._set_tenant(str(company_id))
        try:
            await self._raw_execute(
                _DELETE_SQL,
                {'company_id': str(company_id), 'user_id': str(user_id)},
            )
        finally:
            await self._clear_tenant()
