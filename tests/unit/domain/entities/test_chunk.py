from __future__ import annotations

import pytest

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities import Chunk

SHA256_HEX_LENGTH = 64


def _chunk(**overrides: object) -> Chunk:
    values: dict[str, object] = {
        'company_id': CompanyId('company-a'),
        'document_id': DocumentId('doc-1'),
        'version_id': 'version-1',
        'text': 'Revenue was 10 million.',
        'structure_path': ('Income statement',),
        'ordinal': 0,
    }
    values.update(overrides)
    return Chunk.create(**values)  # type: ignore[arg-type]


def test_create_computes_stable_id_and_content_hash() -> None:
    first = _chunk()
    second = _chunk()

    assert first.chunk_id == second.chunk_id
    assert first.content_hash == second.content_hash
    assert len(first.chunk_id) == SHA256_HEX_LENGTH
    assert len(first.content_hash) == SHA256_HEX_LENGTH
    assert first.is_active is True
    assert first.needs_review is False


def test_stable_id_ignores_version_and_position() -> None:
    original = _chunk()
    next_version = _chunk(version_id='version-2')
    moved = _chunk(ordinal=7)

    assert original.chunk_id == next_version.chunk_id
    assert original.chunk_id == moved.chunk_id


def test_stable_id_follows_document_section_path_and_text_hash() -> None:
    base = _chunk()

    assert base.chunk_id != _chunk(text='Revenue was 12 million.').chunk_id
    assert base.chunk_id != _chunk(structure_path=('Balance sheet',)).chunk_id
    assert base.chunk_id != _chunk(is_parent=True).chunk_id
    assert base.chunk_id != _chunk(company_id=CompanyId('company-b')).chunk_id
    assert base.chunk_id != _chunk(document_id=DocumentId('doc-2')).chunk_id


def test_occurrence_disambiguates_identical_paragraphs_only() -> None:
    first = _chunk()
    duplicate = _chunk(occurrence=1)

    assert first.chunk_id != duplicate.chunk_id
    assert first.content_hash == duplicate.content_hash


def test_context_header_changes_content_hash_but_not_stable_id() -> None:
    base = _chunk(context_header='Company: A | Period: 2025-Q1')
    reheaded = _chunk(context_header='Company: A | Period: 2025-Q2')

    assert base.chunk_id == reheaded.chunk_id
    assert base.content_hash != reheaded.content_hash


def test_content_hash_normalises_line_endings() -> None:
    unix = _chunk(text='line one\nline two')
    windows = _chunk(text='line one\r\nline two')

    assert unix.content_hash == windows.content_hash


def test_child_chunk_carries_parent_id() -> None:
    parent = _chunk(is_parent=True)
    child = _chunk(parent_chunk_id=parent.chunk_id)

    assert parent.parent_chunk_id is None
    assert child.parent_chunk_id == parent.chunk_id


def test_lifecycle_flags_are_explicit() -> None:
    chunk = _chunk()

    assert chunk.mark_inactive() is chunk
    assert chunk.is_active is False

    assert chunk.flag_needs_review() is chunk
    assert chunk.needs_review is True


def test_missing_company_document_or_text_fails_loudly() -> None:
    with pytest.raises(ValueError, match='company_id'):
        _chunk(company_id=CompanyId(''))
    with pytest.raises(ValueError, match='document_id'):
        _chunk(document_id=DocumentId(''))
    with pytest.raises(ValueError, match='text'):
        _chunk(text='   ')


def test_invalid_location_values_fail_loudly() -> None:
    with pytest.raises(ValueError, match='ordinal'):
        _chunk(ordinal=-1)
    with pytest.raises(ValueError, match='page_number'):
        _chunk(page_number=0)
