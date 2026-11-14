"""Auto-extracted helper for AuroraPgVectorWrite.delete_vectors."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


async def _delete_vectors(
    self: AuroraPgVectorWrite, company_id: CompanyId, *args: Any, **kwargs: Any
) -> int:
    return await self.delete_chunks(company_id, *args, **kwargs)
