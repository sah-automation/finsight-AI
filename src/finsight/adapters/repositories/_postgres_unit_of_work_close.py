"""Auto-extracted helper for PostgresUnitOfWork.close."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _close(self: PostgresUnitOfWork, transaction: object = None, **kwargs: object) -> None:
    for session in self._session_candidates(transaction):
        await self._call_best_effort(session, 'close')
    self._closed = True
