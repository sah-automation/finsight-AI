from __future__ import annotations

import pytest

from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities import Chunk
from finsight.domain.services import DeltaDiffer, DeltaResult


def _chunk(  # noqa: PLR0913 - test helper mirrors the chunk factory
    *,
    document_id: str = 'doc-1',
    version_id: str = 'version-1',
    text: str = 'Revenue was 10 million.',
    context_header: str = '',
    structure_path: tuple[str, ...] = ('Income statement',),
    occurrence: int = 0,
    is_parent: bool = False,
) -> Chunk:
    return Chunk.create(
        company_id=CompanyId('company-a'),
        document_id=DocumentId(document_id),
        version_id=version_id,
        text=text,
        context_header=context_header,
        structure_path=structure_path,
        occurrence=occurrence,
        is_parent=is_parent,
    )


def test_equal_page_hashes_are_unchanged() -> None:
    result = DeltaDiffer().diff_pages({1: 'a', 2: 'b'}, {1: 'a', 2: 'b'})

    assert result.unchanged == (1, 2)
    assert result.added == ()
    assert result.changed == ()
    assert result.removed == ()
    assert result.has_changes is False


def test_pages_report_added_changed_and_removed_deterministically() -> None:
    previous = {1: 'a', 2: 'b', 3: 'c'}
    current = {2: 'b', 3: 'changed', 4: 'd', 10: 'j'}

    result = DeltaDiffer().diff_pages(previous, current)

    assert result.unchanged == (2,)
    assert result.changed == (3,)
    assert result.added == (4, 10)
    assert result.removed == (1,)
    assert result.has_changes is True
    assert result.to_process == (4, 10, 3)


def test_empty_page_sets_diff_to_empty_result() -> None:
    result = DeltaDiffer().diff_pages({}, {})

    assert result == DeltaResult()
    assert result.has_changes is False


def test_all_pages_added_when_previous_version_is_empty() -> None:
    result = DeltaDiffer().diff_pages({}, {1: 'a', 2: 'b'})

    assert result.added == (1, 2)
    assert result.removed == ()
    assert result.to_process == (1, 2)


def test_all_pages_removed_when_current_version_is_empty() -> None:
    result = DeltaDiffer().diff_pages({1: 'a'}, {})

    assert result.removed == (1,)
    assert result.added == ()
    assert result.has_changes is True


def test_chunks_diff_by_stable_id_and_content_hash() -> None:
    unchanged = _chunk()
    changed_previous = _chunk(text='Profit was 2 million.', context_header='Period: 2025-Q1')
    changed_current = _chunk(text='Profit was 2 million.', context_header='Period: 2025-Q2')
    removed = _chunk(text='Old removed paragraph', structure_path=('Income statement', 'Note 2'))
    added = _chunk(text='New added paragraph', structure_path=('Income statement', 'Note 3'))

    assert changed_previous.chunk_id == changed_current.chunk_id
    assert changed_previous.content_hash != changed_current.content_hash

    result = DeltaDiffer().diff_chunks(
        [unchanged, changed_previous, removed],
        [unchanged, changed_current, added],
    )

    assert result.unchanged == (unchanged.chunk_id,)
    assert result.changed == (changed_current.chunk_id,)
    assert result.removed == (removed.chunk_id,)
    assert result.added == (added.chunk_id,)
    assert result.to_process == (added.chunk_id, changed_current.chunk_id)


def test_edited_text_appears_as_removed_and_added() -> None:
    previous = _chunk(text='Revenue was 10 million.')
    current = _chunk(text='Revenue was 12 million.')

    result = DeltaDiffer().diff_chunks([previous], [current])

    assert result.removed == (previous.chunk_id,)
    assert result.added == (current.chunk_id,)
    assert result.changed == ()
    assert result.unchanged == ()


def test_chunk_diff_ignores_inactive_previous_chunks() -> None:
    chunk = _chunk()
    inactive = _chunk(text='Removed paragraph', structure_path=('Income statement', 'Note 2'))
    inactive.mark_inactive()

    result = DeltaDiffer().diff_chunks([chunk, inactive], [chunk])

    assert result.unchanged == (chunk.chunk_id,)
    assert result.removed == ()


def test_chunk_diff_rejects_duplicate_ids() -> None:
    chunk = _chunk()

    with pytest.raises(ValueError, match='Duplicate chunk_id'):
        DeltaDiffer().diff_chunks([chunk, chunk], [chunk])
