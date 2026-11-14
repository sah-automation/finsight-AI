"""Auto-extracted helper for PostgresUnitOfWork._call_best_effort."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_unit_of_work_shared import _await_maybe

if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _call_best_effort(
    self: PostgresUnitOfWork, obj: object, method_name: str, *args: Any, **kwargs: Any
) -> object:
    method = getattr(obj, method_name, None)
    if not callable(method):
        return None
    try:
        result = method(*args, **kwargs)
        return await _await_maybe(result)
    except TypeError:
        try:
            result = method()
            return await _await_maybe(result)
        except Exception:
            return None
    except Exception:
        return None
