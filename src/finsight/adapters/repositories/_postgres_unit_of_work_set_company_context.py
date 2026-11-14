"""Auto-extracted helper for PostgresUnitOfWork.set_company_context."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _set_company_context(self: PostgresUnitOfWork, company_id: object) -> None:
    self.company_id = company_id
    if self._session is not None:
        try:
            session_any: Any = self._session
            session_any.company_id = company_id
        except Exception:
            pass
    await self._set_company_context()
