"""Auto-extracted helper for PostgresUnitOfWork.rollback."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _rollback(self: PostgresUnitOfWork, transaction: object = None, **kwargs: object) -> None:
    for session in self._session_candidates(transaction):
        if hasattr(session, 'rollback') and callable(getattr(session, 'rollback', None)):
            result = session.rollback()
            await _await_maybe(result)
    self._rollback_count += 1
    self.rolled_back = True
