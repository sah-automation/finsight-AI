"""Auto-extracted helper for AuroraPgVectorWrite._existing."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from .aurora_pg_vector_write import (
    _RETURNING_COLUMNS,
    _TABLE,
    _rows_by_id,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


async def _existing(
    self: AuroraPgVectorWrite,
    company_id: str,
    chunk_ids: Sequence[str],
) -> dict[str, dict[str, object]]:
    if not chunk_ids:
        return {}
    if self._session is None:
        records = self._memory.get(company_id, {})
        return {chunk_id: dict(records[chunk_id]) for chunk_id in chunk_ids if chunk_id in records}
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'SELECT {_RETURNING_COLUMNS} FROM {_TABLE} '
        'WHERE company_id = :company_id AND chunk_id = ANY(:chunk_ids)',
        {'company_id': company_id, 'chunk_ids': list(chunk_ids)},
    )
    return _rows_by_id(await self._fetchall(result))
