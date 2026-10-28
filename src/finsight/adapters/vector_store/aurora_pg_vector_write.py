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
    from finsight.core.types import ChunkId, CompanyId
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

    async def upsert_chunks(
        self,
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
        if not company:
            raise ValueError('company_id is required for a vector write')
        if not version:
            raise ValueError('version_id is required for a vector write')
        vector_map = _vector_map(chunks, vectors)
        existing = await self._existing(company, [str(chunk.chunk_id) for chunk in chunks])
        model_override = kwargs.get('embedding_model_version')
        written = 0
        for chunk in chunks:
            vector = vector_map.get(_text(chunk.chunk_id))
            if vector is None or chunk.is_parent:
                continue
            model = _text(chunk.embedding_model_version or model_override)
            current = existing.get(_text(chunk.chunk_id))
            if only_changed and self._unchanged(chunk, current, model):
                await self._touch(company, version, chunk, current)
                continue
            await self._write(company, version, chunk, vector, model)
            written += 1
        return written

    async def mark_version_inactive(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        exclude_chunk_ids: Sequence[ChunkId] = (),
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        version = _text(version_id)
        excluded = {_text(chunk_id) for chunk_id in exclude_chunk_ids}
        if self._session is None:
            records = self._memory.get(company, {})
            changed = 0
            for chunk_id, record in records.items():
                if record.get('version_id') != version or chunk_id in excluded:
                    continue
                if record.get('is_active'):
                    record['is_active'] = False
                    changed += 1
            return changed
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'UPDATE {_TABLE} SET is_active = FALSE, updated_at = now() '
            'WHERE company_id = :company_id AND version_id = :version_id AND is_active = TRUE '
            'AND (cardinality(:exclude_ids) = 0 OR NOT (chunk_id = ANY(:exclude_ids)))',
            {
                'company_id': company,
                'version_id': version,
                'exclude_ids': list(excluded),
            },
        )
        return _rowcount(result)

    async def commit_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        version = _text(version_id)
        if self._session is None:
            records = self._memory.get(company, {})
            documents = {
                record.get('document_id')
                for record in records.values()
                if record.get('version_id') == version
            }
            for record in records.values():
                if record.get('document_id') not in documents:
                    continue
                if record.get('version_id') != version and record.get('is_active'):
                    record['is_active'] = False
            activated = 0
            for record in records.values():
                if record.get('version_id') != version or record.get('embedding') is None:
                    continue
                if not record.get('is_active'):
                    activated += 1
                record['is_active'] = True
            return activated
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'WITH target AS ('
            f'SELECT DISTINCT document_id FROM {_TABLE} '
            'WHERE company_id = :company_id AND version_id = :version_id), '
            f'deactivated AS ('
            f'UPDATE {_TABLE} SET is_active = FALSE, updated_at = now() '
            'WHERE company_id = :company_id AND is_active = TRUE '
            'AND document_id IN (SELECT document_id FROM target) '
            'AND version_id <> :version_id RETURNING 1) '
            f'UPDATE {_TABLE} SET is_active = TRUE, updated_at = now() '
            'WHERE company_id = :company_id AND version_id = :version_id '
            'AND embedding IS NOT NULL',
            {'company_id': company, 'version_id': version},
        )
        return _rowcount(result)

    async def delete_chunks(
        self,
        company_id: CompanyId,
        chunk_ids: Sequence[ChunkId],
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        ids = [_text(chunk_id) for chunk_id in chunk_ids]
        if not ids:
            return 0
        if self._session is None:
            records = self._memory.get(company, {})
            doomed = [chunk_id for chunk_id in ids if chunk_id in records]
            for chunk_id in doomed:
                del records[chunk_id]
            return len(doomed)
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND chunk_id = ANY(:chunk_ids)',
            {'company_id': company, 'chunk_ids': ids},
        )
        return _rowcount(result)

    async def delete_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        version = _text(version_id)
        if self._session is None:
            records = self._memory.get(company, {})
            doomed = [
                chunk_id
                for chunk_id, record in records.items()
                if record.get('version_id') == version
            ]
            for chunk_id in doomed:
                del records[chunk_id]
            return len(doomed)
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND version_id = :version_id',
            {'company_id': company, 'version_id': version},
        )
        return _rowcount(result)

    # ------------------------------------------------------------------
    # Flexible aliases used by the ingestion pipeline
    # ------------------------------------------------------------------

    async def upsert(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        """Alias that accepts either ``(company, version, chunks=..., vectors=...)``
        or ``(company, chunks, vectors)`` so callers can use either shape."""
        version_id = kwargs.pop('version_id', None)
        chunks = kwargs.get('chunks')
        vectors = kwargs.get('vectors', kwargs.get('embeddings'))
        rest = list(args)
        if rest and isinstance(rest[0], str) and version_id is None:
            version_id = rest.pop(0)
        if chunks is None and rest:
            chunks = rest.pop(0)
        if vectors is None and rest:
            vectors = rest.pop(0)
        if chunks is None:
            raise ValueError('chunks are required for a vector write')
        if version_id is None:
            version_id = getattr(chunks[0], 'version_id', None) if chunks else None
        return await self.upsert_chunks(
            company_id,
            _text(version_id),
            chunks=chunks,
            vectors=vectors,
            **kwargs,
        )

    async def upsert_vectors(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        return await self.upsert(company_id, *args, **kwargs)

    async def save_vectors(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        return await self.upsert(company_id, *args, **kwargs)

    async def save(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        return await self.upsert(company_id, *args, **kwargs)

    async def insert(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        return await self.upsert(company_id, *args, **kwargs)

    async def add(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        return await self.upsert(company_id, *args, **kwargs)

    async def delete_vectors(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> int:
        return await self.delete_chunks(company_id, *args, **kwargs)

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
        self,
        company_id: str,
        chunk_ids: Sequence[str],
    ) -> dict[str, dict[str, object]]:
        if not chunk_ids:
            return {}
        if self._session is None:
            records = self._memory.get(company_id, {})
            return {
                chunk_id: dict(records[chunk_id]) for chunk_id in chunk_ids if chunk_id in records
            }
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'SELECT {_RETURNING_COLUMNS} FROM {_TABLE} '
            'WHERE company_id = :company_id AND chunk_id = ANY(:chunk_ids)',
            {'company_id': company_id, 'chunk_ids': list(chunk_ids)},
        )
        return _rows_by_id(await self._fetchall(result))

    async def _touch(
        self,
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

    async def _write(
        self,
        company_id: str,
        version_id: str,
        chunk: Chunk,
        vector: object,
        model: str,
    ) -> None:
        if self._session is None:
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
            return
        await self._execute(
            f'INSERT INTO {_TABLE} '
            '(company_id, chunk_id, document_id, version_id, content_hash, '
            'embedding_model_version, embedding, is_active, updated_at) '
            'VALUES (:company_id, :chunk_id, :document_id, :version_id, :content_hash, '
            ':embedding_model_version, CAST(:embedding AS vector), FALSE, now()) '
            'ON CONFLICT (company_id, chunk_id) DO UPDATE SET '
            'document_id = EXCLUDED.document_id, '
            'version_id = EXCLUDED.version_id, '
            'content_hash = EXCLUDED.content_hash, '
            'embedding_model_version = EXCLUDED.embedding_model_version, '
            'embedding = EXCLUDED.embedding, '
            'is_active = FALSE, '
            'updated_at = now()',
            {
                'company_id': company_id,
                'chunk_id': _text(chunk.chunk_id),
                'document_id': _text(chunk.document_id),
                'version_id': version_id,
                'content_hash': chunk.content_hash,
                'embedding_model_version': model,
                'embedding': _vector_literal(vector),
            },
        )


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
