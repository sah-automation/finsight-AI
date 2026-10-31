"""Auto-extracted helper for PostgresUnitOfWork.commit."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _commit(self: PostgresUnitOfWork, transaction: object = None, **kwargs: object) -> None:
    for session in self._session_candidates(transaction):
        if hasattr(session, 'commit') and callable(getattr(session, 'commit', None)):
            result = session.commit()
            await _await_maybe(result)
    self._committed_count += 1
    self.committed = True
