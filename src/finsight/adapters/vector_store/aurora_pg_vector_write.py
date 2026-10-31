"""Aurora/pgvector vector-write adapter.

The adapter writes only chunks whose content hash or embedding model version
changed. A reprocess writes the new version inactive, then :meth:`commit_version`
flips the whole version in one statement, so search never mixes the old and new
vectors of the same document.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.vector_write import VectorWrite as VectorWritePort

from .base_vector_store import BaseVectorStore

if TYPE_CHECKING:
    from finsight.domain.entities.chunk import Chunk

_TABLE = 'document_chunks'
_RETURNING_COLUMNS = (
    'chunk_id, version_id, content_hash, embedding_model_version, '
    '(embedding IS NOT NULL) AS has_embedding, is_active'
)


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _vector_literal(vector: object) -> str | None:
    if vector is None:
        return None
    if isinstance(vector, str):
        return vector
    if not isinstance(vector, Iterable):
        return None
    try:
        return json.dumps([float(value) for value in vector])
    except (TypeError, ValueError):
        return None


def _vector_map(chunks: Sequence[Chunk], vectors: object) -> dict[str, object]:
    if isinstance(vectors, dict):
        return {_text(key): value for key, value in vectors.items()}
    if vectors is None:
        return {
            _text(chunk.chunk_id): chunk.metadata.get('embedding')
            for chunk in chunks
            if chunk.metadata.get('embedding') is not None
        }
    if isinstance(vectors, (list, tuple)):
        return {
            _text(chunk.chunk_id): vector for chunk, vector in zip(chunks, vectors, strict=False)
        }
    return {}


def _row_value(row: object, name: str) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        try:
            return mapping[name]
        except (KeyError, TypeError):
            return None
    return getattr(row, name, None)


def _rows_by_id(rows: object) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    if not isinstance(rows, Iterable):
        return records
    for row in rows:
        chunk_id = _text(_row_value(row, 'chunk_id'))
        if not chunk_id:
            continue
        records[chunk_id] = {
            'version_id': _text(_row_value(row, 'version_id')),
            'content_hash': _text(_row_value(row, 'content_hash')),
            'embedding_model_version': _text(_row_value(row, 'embedding_model_version')),
            'has_embedding': bool(_row_value(row, 'has_embedding')),
            'is_active': bool(_row_value(row, 'is_active')),
        }
    return records


def _rowcount(result: object, fallback: int = 0) -> int:
    rowcount = getattr(result, 'rowcount', None)
    if rowcount is None:
        return fallback
    try:
        return int(rowcount)
    except (TypeError, ValueError):
        return fallback


class AuroraPgVectorWrite(VectorWritePort, BaseVectorStore):
    """Version-safe pgvector writes over the company's chunk partition.

    Without a session the adapter keeps vectors in memory for contract tests and
    the pilot composition path. With a session it uses ``document_chunks``,
    where the schema keeps the chunk text and its embedding together.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, dict[str, Any]]] = {}

    async def upsert_chunks(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_upsert_chunks import _upsert_chunks as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def mark_version_inactive(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_mark_version_inactive import (
            _mark_version_inactive as _adapter_method,
        )

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def commit_version(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_commit_version import _commit_version as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def delete_chunks(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_delete_chunks import _delete_chunks as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def delete_version(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_delete_version import _delete_version as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    # ------------------------------------------------------------------
    # Flexible aliases used by the ingestion pipeline
    # ------------------------------------------------------------------

    async def upsert(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_upsert import _upsert as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def upsert_vectors(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_upsert_vectors import _upsert_vectors as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def save_vectors(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_save_vectors import _save_vectors as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def save(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_save import _save as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def insert(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_insert import _insert as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def add(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_add import _add as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def delete_vectors(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        from ._aurora_pg_vector_write_delete_vectors import _delete_vectors as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unchanged(
        chunk: Chunk,
        current: dict[str, object] | None,
        model: str,
    ) -> bool:
        if current is None or not current.get('has_embedding'):
            return False
        if current.get('content_hash') != chunk.content_hash:
            return False
        return _text(current.get('embedding_model_version')) == model

    async def _existing(
        self, company_id: Any, *args: Any, **kwargs: Any
    ) -> dict[str, dict[str, object]]:
        from ._aurora_pg_vector_write__existing import _existing as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def _touch(self, company_id: Any, *args: Any, **kwargs: Any) -> None:
        from ._aurora_pg_vector_write__touch import _touch as _adapter_method

        await _adapter_method(self, company_id, *args, **kwargs)

    async def _write(self, company_id: Any, *args: Any, **kwargs: Any) -> None:
        from ._aurora_pg_vector_write__write import _write as _adapter_method

        await _adapter_method(self, company_id, *args, **kwargs)


# Naming variants used across the project/tests.
PostgresVectorWrite = AuroraPgVectorWrite
PgVectorWrite = AuroraPgVectorWrite
AuroraVectorWrite = AuroraPgVectorWrite
AuroraPgvectorWrite = AuroraPgVectorWrite
VectorWriteAdapter = AuroraPgVectorWrite
VectorStoreWrite = AuroraPgVectorWrite

__all__ = [
    'AuroraPgVectorWrite',
    'AuroraPgvectorWrite',
    'AuroraVectorWrite',
    'PgVectorWrite',
    'PostgresVectorWrite',
    'VectorStoreWrite',
    'VectorWriteAdapter',
]
