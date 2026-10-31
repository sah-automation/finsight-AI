"""Auto-extracted helper for PostgresUnitOfWork.set_tenant_context."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_unit_of_work import PostgresUnitOfWork


async def _set_tenant_context(self: PostgresUnitOfWork, company_id: object) -> None:
    await self.set_company_context(company_id)
