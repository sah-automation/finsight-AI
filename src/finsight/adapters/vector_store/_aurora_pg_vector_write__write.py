"""Auto-extracted helper for AuroraPgVectorWrite._write."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from .aurora_pg_vector_write import (
    _TABLE,
    _text,
    _vector_literal,
)

if TYPE_CHECKING:
    from finsight.domain.entities.chunk import Chunk


if TYPE_CHECKING:
    from .aurora_pg_vector_write import AuroraPgVectorWrite

_UPSERT_CHUNK_SQL = (
    f'INSERT INTO {_TABLE} '
    '(company_id, chunk_id, document_id, version_id, chunk_index, content_hash, '
    'embedding_model_version, embedding, is_active, updated_at) '
    'VALUES (:company_id, :chunk_id, :document_id, :version_id, :chunk_index, :content_hash, '
    ':embedding_model_version, CAST(:embedding AS vector), FALSE, now()) '
    'ON CONFLICT (company_id, chunk_id) DO UPDATE SET '
    'document_id = EXCLUDED.document_id, '
    'version_id = EXCLUDED.version_id, '
    'chunk_index = EXCLUDED.chunk_index, '
    'content_hash = EXCLUDED.content_hash, '
    'embedding_model_version = EXCLUDED.embedding_model_version, '
    'embedding = EXCLUDED.embedding, '
    'is_active = FALSE, '
    'updated_at = now()'
)


def _write_memory(
    self: AuroraPgVectorWrite,
    company_id: str,
    version_id: str,
    chunk: Chunk,
    vector: object,
    model: str,
) -> None:
    records = self._memory.setdefault(company_id, {})
    records[_text(chunk.chunk_id)] = {
        'chunk_id': _text(chunk.chunk_id),
        'document_id': _text(chunk.document_id),
        'version_id': version_id,
        'content_hash': chunk.content_hash,
        'embedding_model_version': model,
        'embedding': vector,
        'has_embedding': vector is not None,
        'is_active': False,
    }


def _write_params(
    company_id: str,
    version_id: str,
    chunk: Chunk,
    vector: object,
    model: str,
) -> dict[str, object]:
    return {
        'company_id': company_id,
        'chunk_id': _text(chunk.chunk_id),
        'document_id': _text(chunk.document_id),
        'version_id': version_id,
        'chunk_index': chunk.ordinal,
        'content_hash': chunk.content_hash,
        'embedding_model_version': model,
        'embedding': _vector_literal(vector),
    }


async def _write(
    self: AuroraPgVectorWrite,
    company_id: str,
    version_id: str,
    chunk: Chunk,
    vector: object,
    model: str,
) -> None:
    if self._session is None:
        _write_memory(self, company_id, version_id, chunk, vector, model)
        return
    await self._execute(
        _UPSERT_CHUNK_SQL, _write_params(company_id, version_id, chunk, vector, model)
    )
