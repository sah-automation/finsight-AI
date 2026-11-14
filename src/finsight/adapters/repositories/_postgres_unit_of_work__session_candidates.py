"""Auto-extracted helper for PostgresUnitOfWork._session_candidates."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


def _session_candidates(self: PostgresUnitOfWork, transaction: object = None) -> list[Any]:
    candidates: list[Any] = []
    if transaction is not None and transaction is not self:
        session = getattr(transaction, 'session', None)
        if session is None and hasattr(transaction, '_session'):
            session = getattr(transaction, '_session', None)
        if session is not None:
            candidates.append(session)
        if hasattr(transaction, 'commit') or hasattr(transaction, 'rollback'):
            candidates.append(transaction)
    if self._session is not None:
        candidates.append(self._session)
    out: list[Any] = []
    for candidate in candidates:
        if candidate is not None and candidate not in out:
            out.append(candidate)
    return out
