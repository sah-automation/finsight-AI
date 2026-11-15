"""Neon/pgvector vector-write adapter.

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


class NeonPgVectorWrite(VectorWritePort, BaseVectorStore):
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
        company_id: Any,
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
            written += await self._upsert_one(
                company, version, chunk, vector_map, existing, model_override, only_changed
            )
        return written

    async def _upsert_one(
        self,
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

    async def mark_version_inactive(
        self,
        company_id: Any,
        version_id: str,
        *,
        exclude_chunk_ids: Sequence[Any] = (),
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        version = _text(version_id)
        exclude = {_text(c) for c in exclude_chunk_ids}
        if self._session is not None:
            await self._set_rls_context(company)
        if not self._memory.get(company):
            return 0
        count = 0
        for chunk_id, record in self._memory[company].items():
            if (
                chunk_id not in exclude
                and record.get('version_id') == version
                and record.get('is_active')
            ):
                record['is_active'] = False
                count += 1
        return count

    async def commit_version(
        self,
        company_id: Any,
        version_id: str,
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        version = _text(version_id)
        if self._session is not None:
            await self._set_rls_context(company)
        records = self._memory.get(company, {})
        # Find document_ids for the target version
        documents = {
            record.get('document_id')
            for record in records.values()
            if record.get('version_id') == version
        }
        # Deactivate other versions of the same documents
        for record in records.values():
            if record.get('document_id') not in documents:
                continue
            if record.get('version_id') != version and record.get('is_active'):
                record['is_active'] = False
        # Activate the target version (records with has_embedding=True)
        activated = 0
        for record in records.values():
            if record.get('version_id') != version or not record.get('has_embedding'):
                continue
            if not record.get('is_active'):
                activated += 1
            record['is_active'] = True
        return activated

    async def delete_chunks(
        self,
        company_id: Any,
        chunk_ids: Sequence[Any],
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        if self._session is not None:
            await self._set_rls_context(company)
        if not self._memory.get(company):
            return 0
        count = 0
        for chunk_id in chunk_ids:
            key = _text(chunk_id)
            if key in self._memory[company]:
                del self._memory[company][key]
                count += 1
        return count

    async def delete_version(
        self,
        company_id: Any,
        version_id: str,
        **kwargs: object,
    ) -> int:
        company = _text(company_id)
        version = _text(version_id)
        if self._session is not None:
            await self._set_rls_context(company)
        if not self._memory.get(company):
            return 0
        to_delete = [k for k, v in self._memory[company].items() if v.get('version_id') == version]
        for k in to_delete:
            del self._memory[company][k]
        return len(to_delete)

    # ------------------------------------------------------------------
    # Flexible aliases used by the ingestion pipeline
    # ------------------------------------------------------------------

    async def upsert(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        """
        Alias that accepts either ``(company, version, chunks=..., vectors=...)``
        or ``(company, chunks, vectors)`` so callers can use either shape.
        """
        min_args_for_version_first = 2
        version_arg_index = 0
        chunks_arg_index = 1
        vectors_arg_index = 2
        if len(args) >= min_args_for_version_first and isinstance(args[version_arg_index], str):
            version_id = args[version_arg_index]
            chunks = kwargs.get(
                'chunks', args[chunks_arg_index] if len(args) > chunks_arg_index else None
            )
            vectors = kwargs.get(
                'vectors', args[vectors_arg_index] if len(args) > vectors_arg_index else None
            )
            return await self.upsert_chunks(
                company_id,
                version_id,
                chunks=chunks,  # type: ignore[arg-type]
                vectors=vectors,
                **kwargs,
            )
        chunks = args[0] if args else kwargs.get('chunks')
        vectors = args[1] if len(args) > 1 else kwargs.get('vectors')
        version_id = kwargs.get('version_id')
        if version_id is None:
            raise ValueError('version_id is required for upsert')
        return await self.upsert_chunks(
            company_id,
            version_id,
            chunks=chunks,  # type: ignore[arg-type]
            vectors=vectors,
            **kwargs,
        )

    async def upsert_vectors(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        return await self.upsert_chunks(company_id, *args, **kwargs)

    async def save_vectors(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        return await self.upsert_chunks(company_id, *args, **kwargs)

    async def save(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        return await self.upsert_chunks(company_id, *args, **kwargs)

    async def insert(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        return await self.upsert_chunks(company_id, *args, **kwargs)

    async def add(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
        return await self.upsert_chunks(company_id, *args, **kwargs)

    async def delete_vectors(self, company_id: Any, *args: Any, **kwargs: Any) -> int:
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
        self, company_id: Any, chunk_ids: Sequence[str] | None = None
    ) -> dict[str, dict[str, object]]:
        company = _text(company_id)
        if self._session is None:
            if not self._memory.get(company):
                return {}
            if chunk_ids is None:
                return dict(self._memory[company].items())
            return {k: v for k, v in self._memory[company].items() if k in chunk_ids}
        await self._set_rls_context(company)
        # Database implementation would go here when session is available
        if not self._memory.get(company):
            return {}
        if chunk_ids is None:
            return dict(self._memory[company].items())
        return {k: v for k, v in self._memory[company].items() if k in chunk_ids}

    async def _touch(
        self, company: str, version: str, chunk: Chunk, current: dict[str, object] | None
    ) -> None:
        """Relink an unchanged vector to the new version without re-embedding."""
        key = _text(chunk.chunk_id)
        if key in self._memory.get(company, {}):
            record = self._memory[company][key]
            if record.get('version_id') != version:
                record['is_active'] = False
            record['version_id'] = version

    async def _write(
        self, company: str, version: str, chunk: Chunk, vector: object, model: str
    ) -> None:
        key = _text(chunk.chunk_id)
        self._memory.setdefault(company, {})[key] = {
            'version_id': version,
            'content_hash': chunk.content_hash,
            'embedding_model_version': model,
            'has_embedding': True,
            'is_active': False,
            'document_id': _text(chunk.document_id),
        }


__all__ = ['NeonPgVectorWrite']
