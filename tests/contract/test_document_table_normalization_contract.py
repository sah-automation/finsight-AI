"""Contract checks for normalising reader tables into the document-table shape.

Every reader must produce the same payload keys and value types so the save step
can persist one shape regardless of which adapter extracted the table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from finsight.adapters.readers.csv_reader import CsvReader
from finsight.adapters.readers.docx_reader import DocxReader
from finsight.adapters.readers.excel_reader import ExcelReader
from finsight.adapters.readers.pdf_plumber_reader import PdfPlumberReader
from finsight.adapters.readers.table_reader import TableReader
from finsight.adapters.readers.textract_reader import TextractReader
from finsight.core.types import CompanyId
from finsight.domain.services.document_table_normalizer import DocumentTableNormalizer

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
FIXTURES = Path(__file__).parent.parent / 'fixtures' / 'documents'

EXPECTED_PAYLOAD_KEYS = {
    'table_id',
    'index',
    'page',
    'headers',
    'rows',
    'row_count',
    'column_count',
    'needs_review',
    'html',
    'metadata',
}

_SAMPLES = [
    (CsvReader, 'csv__company-a__2025-FY__q4-ledger.csv'),
    (ExcelReader, 'xlsx__company-a__2025-FY__budget-vs-actual.xlsx'),
    (DocxReader, 'docx__company-a__2025-FY__board-notes.docx'),
    (TableReader, 'pdf__company-a__2025-FY__annual-report.pdf'),
]


def _raw_rows(table: Any) -> list[Any]:
    for key in ('rows', 'data', 'cells', 'table'):
        value = table.get(key)
        if isinstance(value, (list, tuple)):
            return [list(row) if isinstance(row, (list, tuple)) else row for row in value]
    return []


def _raw_headers(table: Any) -> list[Any]:
    for key in ('headers', 'header', 'column_headers'):
        value = table.get(key)
        if isinstance(value, (list, tuple)):
            return list(value)
    return []


@pytest.mark.parametrize(('reader_class', 'filename'), _SAMPLES)
async def test_every_reader_normalises_to_the_common_table_shape(
    reader_class: type, filename: str
) -> None:
    result = await reader_class().read(COMPANY, (FIXTURES / filename).read_bytes())

    assert result.tables, f'{reader_class.__name__} produced no tables to normalise'

    tables = DocumentTableNormalizer().normalize(
        result.tables,
        company_id=COMPANY,
        document_id='document-a',
        version_id='version-1',
    )

    assert len(tables) == len(result.tables)
    seen_ids: set[str] = set()
    for ordinal, (raw, table) in enumerate(zip(result.tables, tables, strict=True)):
        assert table.company_id == COMPANY
        assert table.document_id == 'document-a'
        assert table.version_id == 'version-1'
        assert isinstance(table.table_id, str) and table.table_id
        assert table.table_id not in seen_ids
        seen_ids.add(table.table_id)
        assert table.index == ordinal
        assert table.page is None or isinstance(table.page, int)
        assert isinstance(table.needs_review, bool)
        assert isinstance(table.payload, dict)
        assert set(table.payload) == EXPECTED_PAYLOAD_KEYS
        assert table.payload['table_id'] == table.table_id
        assert table.payload['index'] == ordinal
        assert table.payload['page'] == table.page
        assert table.payload['rows'] == _raw_rows(raw)
        assert table.payload['headers'] == _raw_headers(raw)
        assert table.payload['row_count'] == len(table.payload['rows'])
        assert isinstance(table.payload['column_count'], int)
        assert isinstance(table.payload['metadata'], dict)
        assert '<table' in table.html
        json.dumps(table.payload)


async def test_a_reader_with_no_extractable_tables_yields_no_document_tables() -> None:
    result = await PdfPlumberReader().read(
        COMPANY, (FIXTURES / 'pdf__company-a__2025-FY__annual-report.pdf').read_bytes()
    )

    assert result.tables == []
    assert DocumentTableNormalizer().normalize(result.tables) == []


def test_textract_reader_output_normalises_to_the_same_shape() -> None:
    response = {
        'DocumentMetadata': {'Pages': 1},
        'Blocks': [
            {
                'Id': 'table-1',
                'BlockType': 'TABLE',
                'Page': 7,
                'Confidence': 95.0,
                'Geometry': {'BoundingBox': {'Top': 0.1, 'Left': 0.2}},
                'Relationships': [{'Type': 'CHILD', 'Ids': ['cell-1', 'cell-2']}],
            },
            {
                'Id': 'cell-1',
                'BlockType': 'CELL',
                'RowIndex': 1,
                'ColumnIndex': 1,
                'Relationships': [{'Type': 'CHILD', 'Ids': ['word-1']}],
            },
            {'Id': 'word-1', 'BlockType': 'WORD', 'Text': 'Revenue'},
            {
                'Id': 'cell-2',
                'BlockType': 'CELL',
                'RowIndex': 1,
                'ColumnIndex': 2,
                'Relationships': [{'Type': 'CHILD', 'Ids': ['word-2']}],
            },
            {'Id': 'word-2', 'BlockType': 'WORD', 'Text': '100'},
        ],
    }

    result = TextractReader()._parse_response(response)
    tables = DocumentTableNormalizer().normalize(
        result.tables,
        company_id=COMPANY,
        document_id='document-a',
        version_id='version-1',
    )

    assert len(tables) == 1
    table = tables[0]
    payload = table.payload
    assert set(payload) == EXPECTED_PAYLOAD_KEYS
    assert payload['table_id'] == table.table_id
    assert payload['index'] == 0
    assert payload['page'] == 7
    assert payload['rows'] == [['Revenue', '100']]
    assert payload['row_count'] == 1
    assert payload['column_count'] == 2
    assert payload['metadata']['reader_index'] == 1
    assert payload['metadata']['confidence'] is not None
    json.dumps(payload)
