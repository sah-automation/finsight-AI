"""SQL-only Postgres/Neon saved-layout repository implementing the layout port.

Reads and conditional saves call the ``dashboard_layout_get`` and
``dashboard_layout_save`` functions from migration 0009 with the company RLS
context set for the transaction. Caller visibility is intersected with the
config catalogue before binding SQL; no alternate store is used.
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
    LayoutDraft,
    LayoutRecord,
    VisibleIds,
)

from . import _dashboard_layout_repository_config as _config
from . import _dashboard_layout_repository_fields as _fields
from . import _dashboard_layout_repository_visibility as _visibility
from .base_repository import BaseRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
        _config.validate_config(config)
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
        self, company_id: Any, user_id: Any, visible: VisibleIds
    ) -> LayoutRecord:
        result = await self._raw_execute(
            _GET_SQL,
            {
                'company_id': str(company_id),
                'user_id': str(user_id),
                'visible_ids': json.dumps(visible.to_mapping()),
            },
        )
        rows = await self._fetchall(result)
        if not rows:
            return _config.default_record(self._config, visible)
        record = _fields.from_row(rows[0])
        if record.version == 0 and record.updated_at is None:
            return _config.default_record(self._config, visible)
        return _visibility.filter_record(record, visible)

    async def _save_record(
        self,
        company_id: Any,
        user_id: Any,
        layout: LayoutDraft,
        expected_version: int,
        visible: VisibleIds,
    ) -> LayoutRecord:
        fields = _visibility.visible_json_fields(_fields.json_fields(layout), visible)
        if not fields['kpi_codes'] and not fields['charts']:
            fields = _fields.json_fields(_config.default_record(self._config, visible))
        result = await self._raw_execute(
            _SAVE_SQL,
            {
                'company_id': str(company_id),
                'user_id': str(user_id),
                'expected_version': expected_version,
                'kpi_codes': json.dumps(fields['kpi_codes']),
                'charts': json.dumps(fields['charts']),
                'visible_ids': json.dumps(visible.to_mapping()),
            },
        )
        rows = await self._fetchall(result)
        if not rows:
            raise LayoutConflictError(await self._fetch_record(company_id, user_id, visible))
        return _visibility.filter_record(_fields.from_row(rows[0]), visible)

    async def get_layout(
        self,
        company_id: CompanyId,
        user_id: UserId,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        """Return the visible saved layout or current config default; never write."""
        visible = _config.effective_visible_ids(self._config, visible_ids)
        async with self._tenant_scope(company_id):
            return await self._fetch_record(company_id, user_id, visible)

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
        visible = _config.effective_visible_ids(self._config, visible_ids)
        async with self._tenant_scope(company_id):
            return await self._save_record(company_id, user_id, layout, expected_version, visible)

    async def delete_layout(self, company_id: CompanyId, user_id: UserId) -> None:
        """Remove the saved layout so a later read returns the config default."""
        async with self._tenant_scope(company_id):
            await self._raw_execute(
                _DELETE_SQL,
                {'company_id': str(company_id), 'user_id': str(user_id)},
            )
