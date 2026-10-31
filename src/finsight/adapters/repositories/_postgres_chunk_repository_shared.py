"""Shared helpers for PostgresChunkRepository."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from finsight.core.types import ChunkId, CompanyId, DocumentId
from finsight.domain.entities.chunk import Chunk

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


def _parse_structure_path(row: object) -> tuple[str, ...]:
    structure_path = _row_value(row, 'structure_path') or ()
    if isinstance(structure_path, str):
        try:
            structure_path = json.loads(structure_path)
        except (TypeError, ValueError):
            structure_path = ()
    if not isinstance(structure_path, (list, tuple)):
        structure_path = ()
    return tuple(str(part) for part in structure_path or ())


def _parse_metadata(row: object) -> dict[str, object]:
    metadata = _row_value(row, 'metadata') or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = {}
    return dict(metadata) if isinstance(metadata, dict) else {}


def _row_to_chunk(row: object | None) -> Chunk | None:
    if row is None:
        return None
    structure_path = _parse_structure_path(row)
    metadata = _parse_metadata(row)
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
        structure_path=structure_path,
        ordinal=_optional_int(_row_value(row, 'ordinal', 'chunk_index')) or 0,
        is_parent=bool(_row_value(row, 'is_parent')),
        is_active=True if is_active is None else bool(is_active),
        needs_review=bool(needs_review),
        token_count=_optional_int(_row_value(row, 'token_count')),
        embedding_model_version=_text(_row_value(row, 'embedding_model_version')),
        metadata=metadata,
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
