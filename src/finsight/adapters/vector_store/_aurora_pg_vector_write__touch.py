"""Auto-extracted helper for AuroraPgVectorWrite._touch."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from .aurora_pg_vector_write import (
    _TABLE,
    _text,
)

if TYPE_CHECKING:
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


async def _touch(
    self: AuroraPgVectorWrite,
    company_id: str,
    version_id: str,
    chunk: Chunk,
    current: dict[str, object] | None,
) -> None:
    """Relink an unchanged vector to the new version without re-embedding."""
    if self._session is None:
        record = self._memory.setdefault(company_id, {}).get(_text(chunk.chunk_id))
        if record is None:
            return
        if record.get('version_id') != version_id:
            record['is_active'] = False
        record['version_id'] = version_id
        return
    await self._execute(
        f'UPDATE {_TABLE} SET '
        'is_active = CASE WHEN version_id = :version_id THEN is_active ELSE FALSE END, '
        'version_id = :version_id, updated_at = now() '
        'WHERE company_id = :company_id AND chunk_id = :chunk_id',
        {
            'company_id': company_id,
            'version_id': version_id,
            'chunk_id': _text(chunk.chunk_id),
        },
    )
