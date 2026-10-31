"""Auto-extracted helper for PostgresUnitOfWork.execute."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _execute(self: PostgresUnitOfWork, company_id: object = None, **kwargs: object) -> object:
    if company_id is not None:
        await self.begin(company_id)
    session = self._session
    sql = kwargs.get('sql') or kwargs.get('statement')
    params = kwargs.get('params') or {}
    if session is not None and hasattr(session, 'execute'):
        try:
            result = session.execute(sql, params)
            return await _await_maybe(result)
        except Exception:
            return None
    return None
