"""Aurora/Postgres chunk repository implementing the ChunkRepository port.

Chunks are keyed by a deterministic ``chunk_id`` so a reprocess can upsert only
the chunks that actually changed. Removed chunks are marked inactive instead of
being deleted immediately, which keeps citations from older answers readable
during their retention window. Every statement carries ``company_id`` so the
partitioned table is pruned to one tenant partition and RLS applies as a second
lock.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from finsight.core.types import ChunkId, CompanyId, DocumentId
from finsight.domain.entities.chunk import Chunk
from finsight.domain.ports.chunk_repository import ChunkRepository as ChunkRepositoryPort

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

_TABLE = 'document_chunks'
_ACTIVE_COLUMN = 'is_active'
_NEEDS_REVIEW_COLUMN = 'needs_review'

_RETURNING = (
    'chunk_id, company_id, document_id, version_id, content, context_header, '
    'content_hash, parent_chunk_id, page_number, structure_path, ordinal, '
    'is_parent, is_active, needs_review, token_count, embedding_model_version, '
    'metadata'
)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_value(value: object) -> object:
    """Normalise a Python value for a jsonb column."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _row_value(row: object, *names: str) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for name in names:
            try:
                if name in mapping:
                    return mapping[name]
            except TypeError:
                continue
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _row_to_chunk(row: object | None) -> Chunk | None:
    if row is None:
        return None
    structure_path = _row_value(row, 'structure_path') or ()
    if isinstance(structure_path, str):
        try:
            structure_path = json.loads(structure_path)
        except (TypeError, ValueError):
            structure_path = ()
    if not isinstance(structure_path, (list, tuple)):
        structure_path = ()
    metadata = _row_value(row, 'metadata') or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = {}
    is_active = _row_value(row, 'is_active')
    needs_review = _row_value(row, _NEEDS_REVIEW_COLUMN)
    return Chunk(
        chunk_id=ChunkId(str(_row_value(row, 'chunk_id', 'id') or '')),
        company_id=CompanyId(str(_row_value(row, 'company_id') or '')),
        document_id=DocumentId(str(_row_value(row, 'document_id') or '')),
        version_id=str(_row_value(row, 'version_id') or ''),
        text=str(_row_value(row, 'content', 'text') or ''),
        context_header=str(_row_value(row, 'context_header') or ''),
        parent_chunk_id=_optional_chunk_id(_row_value(row, 'parent_chunk_id', 'parent_id')),
        page_number=_optional_int(_row_value(row, 'page_number', 'page_from')),
        structure_path=tuple(str(part) for part in structure_path or ()),
        ordinal=_optional_int(_row_value(row, 'ordinal', 'chunk_index')) or 0,
        is_parent=bool(_row_value(row, 'is_parent')),
        is_active=True if is_active is None else bool(is_active),
        needs_review=bool(needs_review),
        token_count=_optional_int(_row_value(row, 'token_count')),
        embedding_model_version=_text(_row_value(row, 'embedding_model_version')),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _optional_chunk_id(value: object) -> ChunkId | None:
    text = _text(value)
    return ChunkId(text) if text is not None else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


class PostgresChunkRepository(ChunkRepositoryPort, BaseRepository):
    """Chunk repository with stable-id upserts and tenant-scoped lifecycle flags.

    When constructed without a session the adapter keeps state in memory. That
    mode exists for contract tests and the pilot composition path where no
    database is wired; it is never used while a session is present.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, Chunk]] = {}

    async def upsert_chunk(
        self,
        company_id: CompanyId,
        chunk: Chunk,
        **kwargs: object,
    ) -> Chunk:
        saved = await self.upsert_chunks(company_id, [chunk], **kwargs)
        return saved[0] if saved else chunk

    async def upsert_chunks(
        self,
        company_id: CompanyId,
        chunks: Sequence[Chunk],
        **kwargs: object,
    ) -> list[Chunk]:
        company_key = str(company_id)
        if self._session is None:
            return self._upsert_memory(company_key, chunks)
        await self._set_rls_context(company_id)
        embeddings = _embedding_map(kwargs, chunks)
        saved: list[Chunk] = []
        for chunk in chunks:
            row = _chunk_params(company_key, chunk, embeddings)
            result = await self._execute(_upsert_sql(row), row)
            saved.append(_row_to_chunk(await self._fetchone(result)) or chunk)
        return saved

    async def get_chunk(
        self,
        company_id: CompanyId,
        chunk_id: ChunkId,
        **kwargs: object,
    ) -> Chunk | None:
        if self._session is None:
            return self._memory.get(str(company_id), {}).get(str(chunk_id))
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'SELECT {_RETURNING} FROM {_TABLE} '
            'WHERE company_id = :company_id AND chunk_id = :chunk_id',
            {'company_id': str(company_id), 'chunk_id': str(chunk_id)},
        )
        return _row_to_chunk(await self._fetchone(result))

    async def list_chunks_by_version(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        include_inactive: bool = False,
        **kwargs: object,
    ) -> list[Chunk]:
        if self._session is None:
            rows = self._memory.get(str(company_id), {}).values()
            return [
                chunk
                for chunk in rows
                if chunk.version_id == str(version_id) and (include_inactive or chunk.is_active)
            ]
        await self._set_rls_context(company_id)
        sql = (
            f'SELECT {_RETURNING} FROM {_TABLE} '
            'WHERE company_id = :company_id AND version_id = :version_id'
        )
        if not include_inactive:
            sql += f' AND {_ACTIVE_COLUMN} = TRUE'
        result = await self._execute(
            sql + ' ORDER BY ordinal ASC',
            {'company_id': str(company_id), 'version_id': str(version_id)},
        )
        return _rows_to_chunks(await self._fetchall(result))

    async def list_chunks_by_document(
        self,
        company_id: CompanyId,
        document_id: DocumentId,
        *,
        version_id: str | None = None,
        include_inactive: bool = False,
        **kwargs: object,
    ) -> list[Chunk]:
        if self._session is None:
            rows = self._memory.get(str(company_id), {}).values()
            return [
                chunk
                for chunk in rows
                if chunk.document_id == str(document_id)
                and (version_id is None or chunk.version_id == str(version_id))
                and (include_inactive or chunk.is_active)
            ]
        await self._set_rls_context(company_id)
        params: dict[str, Any] = {
            'company_id': str(company_id),
            'document_id': str(document_id),
        }
        sql = (
            f'SELECT {_RETURNING} FROM {_TABLE} '
            'WHERE company_id = :company_id AND document_id = :document_id'
        )
        if version_id is not None:
            sql += ' AND version_id = :version_id'
            params['version_id'] = str(version_id)
        if not include_inactive:
            sql += f' AND {_ACTIVE_COLUMN} = TRUE'
        result = await self._execute(sql + ' ORDER BY ordinal ASC', params)
        return _rows_to_chunks(await self._fetchall(result))

    async def mark_chunks_inactive(
        self,
        company_id: CompanyId,
        chunk_ids: Sequence[ChunkId],
        **kwargs: object,
    ) -> int:
        ids = [str(chunk_id) for chunk_id in chunk_ids]
        if not ids:
            return 0
        if self._session is None:
            return self._mark_memory(str(company_id), ids)
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'UPDATE {_TABLE} SET {_ACTIVE_COLUMN} = FALSE, updated_at = now() '
            'WHERE company_id = :company_id AND chunk_id = ANY(:chunk_ids) '
            f'AND {_ACTIVE_COLUMN} = TRUE',
            {'company_id': str(company_id), 'chunk_ids': ids},
        )
        return _rowcount(result, len(ids))

    async def mark_version_chunks_inactive(
        self,
        company_id: CompanyId,
        version_id: str,
        *,
        exclude_chunk_ids: Sequence[ChunkId] = (),
        **kwargs: object,
    ) -> int:
        excluded = [str(chunk_id) for chunk_id in exclude_chunk_ids]
        if self._session is None:
            return self._mark_memory(
                str(company_id), None, version_id=str(version_id), exclude=excluded
            )
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'UPDATE {_TABLE} SET {_ACTIVE_COLUMN} = FALSE, updated_at = now() '
            'WHERE company_id = :company_id AND version_id = :version_id '
            f'AND {_ACTIVE_COLUMN} = TRUE '
            'AND (cardinality(:exclude_ids) = 0 OR NOT (chunk_id = ANY(:exclude_ids)))',
            {
                'company_id': str(company_id),
                'version_id': str(version_id),
                'exclude_ids': excluded,
            },
        )
        return _rowcount(result, 0)

    async def delete_chunks_by_version(
        self,
        company_id: CompanyId,
        version_id: str,
        **kwargs: object,
    ) -> int:
        if self._session is None:
            return self._delete_memory(str(company_id), str(version_id))
        await self._set_rls_context(company_id)
        result = await self._execute(
            f'DELETE FROM {_TABLE} WHERE company_id = :company_id AND version_id = :version_id',
            {'company_id': str(company_id), 'version_id': str(version_id)},
        )
        return _rowcount(result, 0)

    # ------------------------------------------------------------------
    # In-memory backend (no session wired).
    # ------------------------------------------------------------------

    def _upsert_memory(self, company_id: str, chunks: Sequence[Chunk]) -> list[Chunk]:
        store = self._memory.setdefault(company_id, {})
        saved: list[Chunk] = []
        for chunk in chunks:
            if str(chunk.company_id) != company_id:
                raise ValueError('chunk company_id must match the repository tenant')
            store[str(chunk.chunk_id)] = chunk
            saved.append(chunk)
        return saved

    def _mark_memory(
        self,
        company_id: str,
        chunk_ids: list[str] | None,
        *,
        version_id: str | None = None,
        exclude: list[str] | None = None,
    ) -> int:
        store = self._memory.get(company_id, {})
        excluded = set(exclude or ())
        changed = 0
        for chunk_id, chunk in store.items():
            if chunk_ids is not None and chunk_id not in chunk_ids:
                continue
            if version_id is not None and chunk.version_id != version_id:
                continue
            if chunk_id in excluded or not chunk.is_active:
                continue
            chunk.mark_inactive()
            changed += 1
        return changed

    def _delete_memory(self, company_id: str, version_id: str) -> int:
        store = self._memory.get(company_id, {})
        doomed = [key for key, chunk in store.items() if chunk.version_id == version_id]
        for key in doomed:
            del store[key]
        return len(doomed)


def _chunk_params(
    company_id: str,
    chunk: Chunk,
    embeddings: dict[str, object],
) -> dict[str, Any]:
    vector = embeddings.get(str(chunk.chunk_id)) or chunk.metadata.get('embedding')
    return {
        'company_id': company_id,
        'chunk_id': str(chunk.chunk_id),
        'document_id': str(chunk.document_id),
        'version_id': str(chunk.version_id),
        'parent_chunk_id': str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
        'content': chunk.text,
        'context_header': chunk.context_header,
        'content_hash': chunk.content_hash,
        'page_number': chunk.page_number,
        'structure_path': _json_value(list(chunk.structure_path)),
        'ordinal': chunk.ordinal,
        'is_parent': chunk.is_parent,
        'is_active': chunk.is_active,
        'needs_review': chunk.needs_review,
        'token_count': chunk.token_count,
        'embedding_model_version': chunk.embedding_model_version,
        'metadata': _json_value(chunk.metadata),
        'embedding': vector,
    }


def _upsert_sql(params: dict[str, Any]) -> str:
    columns = list(params)
    updates = []
    for column in columns:
        if column in {'company_id', 'chunk_id'}:
            continue
        if column in {'is_active', 'embedding'}:
            # The chunk repository owns text and lifecycle flags, not the
            # vector commit state: a reprocess must not reactivate staged rows
            # or wipe an embedding written by the vector adapter.
            continue
        updates.append(f'{column} = EXCLUDED.{column}')
    updates.append(
        'embedding = CASE WHEN EXCLUDED.embedding IS NULL '
        'THEN ' + _TABLE + '.embedding ELSE EXCLUDED.embedding END'
    )
    return (
        f'INSERT INTO {_TABLE} ({", ".join(columns)}) '
        f'VALUES ({", ".join(":" + column for column in columns)}) '
        'ON CONFLICT (company_id, chunk_id) DO UPDATE SET '
        + ', '.join(updates)
        + ', updated_at = now() RETURNING *'
    )


def _embedding_map(
    kwargs: dict[str, object],
    chunks: Sequence[Chunk],
) -> dict[str, object]:
    """Collect embeddings supplied with a batch, keyed by stable chunk id."""
    vectors = kwargs.get('vectors') or kwargs.get('embeddings')
    if isinstance(vectors, dict):
        return {str(key): value for key, value in vectors.items()}
    if isinstance(vectors, (list, tuple)):
        return {str(chunk.chunk_id): vector for chunk, vector in zip(chunks, vectors, strict=False)}
    return {}


def _rows_to_chunks(rows: object) -> list[Chunk]:
    chunks: list[Chunk] = []
    if not isinstance(rows, Iterable):
        return chunks
    for row in rows:
        chunk = _row_to_chunk(row)
        if chunk is not None:
            chunks.append(chunk)
    return chunks


def _rowcount(result: object, fallback: int) -> int:
    rowcount = getattr(result, 'rowcount', None)
    if rowcount is None:
        return fallback
    try:
        return int(rowcount)
    except (TypeError, ValueError):
        return fallback


# Naming variants used across the project/tests.
AuroraChunkRepository = PostgresChunkRepository
PostgresChunkRepo = PostgresChunkRepository
ChunkRepositoryAdapter = PostgresChunkRepository
RLSChunkRepository = PostgresChunkRepository
ChunkRepo = PostgresChunkRepository

__all__ = [
    'AuroraChunkRepository',
    'ChunkRepo',
    'ChunkRepositoryAdapter',
    'PostgresChunkRepo',
    'PostgresChunkRepository',
    'RLSChunkRepository',
]
