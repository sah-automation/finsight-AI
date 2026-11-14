"""Auto-extracted helper for PostgresUnitOfWork.run_in_transaction."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _run_in_transaction(
    self: PostgresUnitOfWork, company_id: object = None, **kwargs: object
) -> object:
    func = kwargs.get('func') or kwargs.get('function') or kwargs.get('callback')
    if func is None:
        args_value: Any = kwargs.get('args', ()) or ()
        iterable: Any = args_value if isinstance(args_value, (tuple, list)) else ()
        for value in iterable:
            if callable(value):
                func = value
                break
    if company_id is not None:
        await self.begin(company_id)
    try:
        result = None
        if callable(func):
            result = func(self)
            result = await _await_maybe(result)
        await self.commit(self)
        return result
    except Exception:
        await self.rollback(self)
        raise
