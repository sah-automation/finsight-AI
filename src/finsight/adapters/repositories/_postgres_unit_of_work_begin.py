"""Auto-extracted helper for PostgresUnitOfWork.begin."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _begin(
    self: PostgresUnitOfWork, company_id: object = None, **kwargs: object
) -> PostgresUnitOfWork:
    if company_id is not None:
        self.company_id = company_id
    if self._session is None and self._session_factory is not None:
        try:
            factory = self._session_factory
            result = factory() if callable(factory) else None
            self._session = await _await_maybe(result)
        except Exception:
            self._session = None
    if self.company_id is None:
        self.company_id = kwargs.get('company') or kwargs.get('tenant_id') or kwargs.get('tenant')
    session = self._session
    if session is not None:
        await self._call_best_effort(session, 'begin')
    await self._set_company_context()
    self._started = True
    self.started = True
    return self
