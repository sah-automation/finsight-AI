"""Chunk entity with stable ids and content hashes (pure domain)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from finsight.core.types import ChunkId, CompanyId, DocumentId

if TYPE_CHECKING:
    from collections.abc import Iterable

_CONTEXT_SEPARATOR = '\x1f'


def _require_text(value: object, name: str) -> str:
    text = '' if value is None else str(value).strip()
    if not text:
        raise ValueError(f'{name} is required for a chunk')
    return text


def compute_chunk_hash(text: str, *, context_header: str = '') -> str:
    """Hash the embedded content (optional context header plus text).

    Platform line endings are normalised so the same logical text hashes the
    same on every machine. The hash changes when a rule-built context header
    changes, even though the chunk's stable id stays the same.
    """
    normalized_text = text.replace('\r\n', '\n').replace('\r', '\n')
    payload = f'{context_header}{_CONTEXT_SEPARATOR}{normalized_text}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def build_stable_chunk_id(*args: Any, **kwargs: Any) -> Any:
    return _build_stable_chunk_id_impl(*args, **kwargs)


def _build_stable_chunk_id_impl(  # noqa: PLR0913 - identity inputs are explicit policy inputs
    company_id: CompanyId,
    document_id: DocumentId,
    *,
    text: str,
    structure_path: Iterable[str] = (),
    occurrence: int = 0,
    is_parent: bool = False,
) -> ChunkId:
    """Derive a deterministic id from document, section path and text hash.

    This follows the binding chunking policy. ``company_id`` is added as a
    tenant salt so identical document/section/text never collides across
    companies. ``occurrence`` disambiguates identical paragraphs repeated in
    the same section; it is only non-zero for those duplicates, so inserting a
    different paragraph never re-keys its neighbours.
    """
    company_key = _require_text(company_id, 'company_id')
    document_key = _require_text(document_id, 'document_id')
    if occurrence < 0:
        raise ValueError('occurrence must not be negative')
    payload = {
        'company_id': company_key,
        'document_id': document_key,
        'kind': 'parent' if is_parent else 'child',
        'structure_path': [str(part) for part in structure_path],
        'text_hash': compute_chunk_hash(text),
        'occurrence': occurrence,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return ChunkId(hashlib.sha256(encoded).hexdigest())


@dataclass
class Chunk:
    """A parent or child text chunk belonging to a document version."""

    chunk_id: ChunkId
    company_id: CompanyId
    document_id: DocumentId
    version_id: str
    text: str
    context_header: str = ''
    parent_chunk_id: ChunkId | None = None
    page_number: int | None = None
    structure_path: tuple[str, ...] = ()
    ordinal: int = 0
    is_parent: bool = False
    is_active: bool = True
    needs_review: bool = False
    token_count: int | None = None
    embedding_model_version: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Hash of the embedded content, derived from text and context header."""
        return compute_chunk_hash(self.text, context_header=self.context_header)

    @classmethod
    def create(  # noqa: PLR0913 - a chunk is a data record; every field is optional data
        cls,
        *,
        company_id: CompanyId,
        document_id: DocumentId,
        version_id: str,
        text: str,
        context_header: str = '',
        structure_path: Iterable[str] = (),
        ordinal: int = 0,
        occurrence: int = 0,
        is_parent: bool = False,
        parent_chunk_id: ChunkId | None = None,
        page_number: int | None = None,
        token_count: int | None = None,
        embedding_model_version: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Chunk:
        """Create a chunk, deriving its stable id; ``content_hash`` is computed."""
        company_key = _require_text(company_id, 'company_id')
        document_key = _require_text(document_id, 'document_id')
        version_key = _require_text(version_id, 'version_id')
        path = tuple(str(part) for part in structure_path)
        _validate_chunk_content(text, ordinal, page_number)
        return cls(
            chunk_id=build_stable_chunk_id(
                CompanyId(company_key),
                DocumentId(document_key),
                text=text,
                structure_path=path,
                occurrence=occurrence,
                is_parent=is_parent,
            ),
            company_id=CompanyId(company_key),
            document_id=DocumentId(document_key),
            version_id=version_key,
            text=text,
            context_header=context_header,
            parent_chunk_id=parent_chunk_id,
            page_number=page_number,
            structure_path=path,
            ordinal=ordinal,
            is_parent=is_parent,
            token_count=token_count,
            embedding_model_version=embedding_model_version,
            metadata=dict(metadata or {}),
        )

    def mark_inactive(self) -> Chunk:
        """Mark the chunk unavailable to retrieval while keeping it for audit."""
        self.is_active = False
        return self

    def flag_needs_review(self) -> Chunk:
        """Flag a low-confidence chunk so it is excluded from numbers/citations."""
        self.needs_review = True
        return self


def _validate_chunk_content(text: str, ordinal: int, page_number: int | None) -> None:
    if not text.strip():
        raise ValueError('text is required for a chunk')
    if ordinal < 0:
        raise ValueError('ordinal must not be negative')
    if page_number is not None and page_number < 1:
        raise ValueError('page_number must be 1 or greater')


__all__ = ['Chunk', 'build_stable_chunk_id', 'compute_chunk_hash']
