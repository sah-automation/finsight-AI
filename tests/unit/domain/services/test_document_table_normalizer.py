"""Unit tests for normalising raw reader tables into DocumentTable entities."""

from __future__ import annotations

from typing import ClassVar

from finsight.core.types import CompanyId
from finsight.domain.services.document_table_normalizer import (
    DocumentTableNormalizer,
    normalize_reader_tables,
)

COMPANY = CompanyId('company-a')


def _normalize(tables: object) -> list[object]:
    return DocumentTableNormalizer().normalize(
        tables,
        company_id=COMPANY,
        document_id='document-a',
        version_id='version-1',
    )


def _shape(raw: object) -> dict[str, object]:
    table = DocumentTableNormalizer().normalize_table(
        raw,
        company_id=COMPANY,
        document_id='document-a',
        version_id='version-1',
        ordinal=0,
    )
    return {
        'table_id': table.table_id,
        'index': table.index,
        'page': table.page,
        'payload': table.payload,
        'html': table.html,
        'needs_review': table.needs_review,
        'is_active': table.is_active,
    }


def test_normalizes_pdf_style_rows_and_metadata() -> None:
    values = _shape(
        {
            'page_number': 3,
            'rows': [['Metric', 'Value'], ['Revenue', '100']],
            'bbox': (1, 2, 3, 4),
        }
    )

    assert values['page'] == 3
    assert values['table_id'] == 'table-1'
    assert values['index'] == 0
    assert values['payload'] == {
        'table_id': values['table_id'],
        'index': 0,
        'page': 3,
        'headers': [],
        'rows': [['Metric', 'Value'], ['Revenue', '100']],
        'row_count': 2,
        'column_count': 2,
        'needs_review': False,
        'html': values['html'],
        'metadata': {'bbox': [1, 2, 3, 4]},
    }
    assert '<th>' not in values['html']
    assert '<td>Revenue</td>' in values['html']
    assert values['needs_review'] is False
    assert values['is_active'] is True


def test_normalizes_reader_style_headers_and_keeps_reader_index_in_metadata() -> None:
    values = _shape(
        {
            'index': 4,
            'table_id': 'table-4',
            'page': 2,
            'headers': ['Item', 'Total'],
            'rows': [['Revenue', 100]],
            'needs_review': True,
            'confidence': 0.42,
            'sheet': 'Budget',
        }
    )

    assert values['table_id'] == 'table-4'
    assert values['index'] == 0
    assert values['page'] == 2
    assert values['needs_review'] is True
    assert '<th>Item</th>' in values['html']
    assert '<td>Revenue</td>' in values['html']
    assert values['payload']['metadata']['sheet'] == 'Budget'
    assert values['payload']['metadata']['confidence'] == 0.42
    assert values['payload']['metadata']['reader_index'] == 4


def test_accepts_bare_rows_and_escapes_html() -> None:
    values = _shape([['Name', '<script>'], ['A & B', '2']])

    assert values['payload']['rows'] == [['Name', '<script>'], ['A & B', '2']]
    assert '&lt;script&gt;' in values['html']
    assert '<script>' not in values['html']
    assert 'A &amp; B' in values['html']


def test_empty_input_returns_no_tables() -> None:
    assert _normalize(None) == []
    assert _normalize([]) == []


def test_table_ids_are_deterministic_and_unique() -> None:
    tables = _normalize(
        [
            {'page': 1, 'rows': [['A']]},
            {'page': 1, 'rows': [['B']]},
            {'table_id': 'table-1', 'page': 2, 'rows': [['C']]},
        ]
    )

    assert [table.table_id for table in tables] == ['table-1', 'table-2', 'table-1-2']
    assert [table.index for table in tables] == [0, 1, 2]
    assert [table.payload['table_id'] for table in tables] == [
        'table-1',
        'table-2',
        'table-1-2',
    ]


def test_duplicate_reader_ids_are_suffixed_within_one_version() -> None:
    tables = _normalize(
        [
            {'table_id': 'table-1', 'page': 1, 'rows': [['A']]},
            {'table_id': 'table-1', 'page': 2, 'rows': [['B']]},
        ]
    )

    assert [table.table_id for table in tables] == ['table-1', 'table-1-2']


def test_normalizes_reader_result_collection() -> None:
    class _Result:
        tables: ClassVar[list[dict[str, object]]] = [
            {'page_number': 1, 'rows': [['Revenue', '10']]}
        ]

    tables = normalize_reader_tables(
        _Result(),
        company_id=COMPANY,
        document_id='document-a',
        version_id='version-1',
    )

    assert len(tables) == 1
    assert tables[0].payload['rows'] == [['Revenue', '10']]
