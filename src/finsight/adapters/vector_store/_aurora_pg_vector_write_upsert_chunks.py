"""Auto-extracted helper for AuroraPgVectorWrite.upsert_chunks."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from .aurora_pg_vector_write import (
    _text,
    _vector_map,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.core.types import CompanyId
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite


def _validate_write_ids(company: str, version: str) -> None:
    if not company:
        raise ValueError('company_id is required for a vector write')
    if not version:
        raise ValueError('version_id is required for a vector write')


async def _upsert_one(
    self: AuroraPgVectorWrite,
    company: str,
    version: str,
    chunk: Chunk,
    vector_map: dict[str, Any],
    existing: dict[str, Any],
    model_override: object,
    only_changed: bool,
) -> int:
    vector = vector_map.get(_text(chunk.chunk_id))
    if vector is None or chunk.is_parent:
        return 0
    model = _text(chunk.embedding_model_version or model_override)
    current = existing.get(_text(chunk.chunk_id))
    if only_changed and self._unchanged(chunk, current, model):
        await self._touch(company, version, chunk, current)
        return 0
    await self._write(company, version, chunk, vector, model)
    return 1


async def _upsert_chunks(
    self: AuroraPgVectorWrite,
    company_id: CompanyId,
    version_id: str,
    *,
    chunks: Sequence[Chunk],
    vectors: object,
    only_changed: bool = True,
    **kwargs: object,
) -> int:
    company = _text(company_id)
    version = _text(version_id)
    _validate_write_ids(company, version)
    vector_map = _vector_map(chunks, vectors)
    existing = await self._existing(company, [str(chunk.chunk_id) for chunk in chunks])
    model_override = kwargs.get('embedding_model_version')
    written = 0
    for chunk in chunks:
        written += await _upsert_one(
            self, company, version, chunk, vector_map, existing, model_override, only_changed
        )
    return written
