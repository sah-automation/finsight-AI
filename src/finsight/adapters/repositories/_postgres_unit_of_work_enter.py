"""Auto-extracted helper for PostgresUnitOfWork.enter."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)

if TYPE_CHECKING:
    from .postgres_unit_of_work import (
        PostgresUnitOfWork,
    )


if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _enter(
    self: PostgresUnitOfWork, company_id: object = None, **kwargs: object
) -> PostgresUnitOfWork:
    return await self.begin(company_id, **kwargs)
