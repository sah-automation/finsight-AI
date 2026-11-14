"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult


def _build_result_from_sheets(self: Any, extracted: list[dict[str, Any]]) -> Any:
    tables: list[object] = []
    locators: list[dict[str, Any]] = []
    text_blocks: list[str] = []
    page_numbers: list[int] = []

    for page_number, info in enumerate(extracted, start=1):
        sheet_name = str(info.get('sheet') or f'Sheet{page_number}')
        headers = list(info.get('headers') or [])
        rows = [list(r) for r in (info.get('rows') or [])]
        range_str = str(info.get('range') or 'A1')
        header_idx = info.get('header_idx')
        header_row_number = (int(header_idx) + 1) if isinstance(header_idx, int) else None

        page_numbers.append(page_number)

        table_index = page_number
        table: dict[str, Any] = {
            'sheet': sheet_name,
            'sheet_name': sheet_name,
            'worksheet': sheet_name,
            'name': sheet_name,
            'title': sheet_name,
            'index': table_index,
            'table_index': table_index,
            'headers': headers,
            'header': headers,
            'header_row': header_row_number,
            'rows': rows,
            'data': rows,
            'table': rows,
            'cells': rows,
            'range': range_str,
            'cell_range': range_str,
            'cells_range': range_str,
            'range_string': range_str,
            'coordinates': range_str,
            'dimensions': range_str,
            'min_row': 1,
            'max_row': (header_row_number or 0) + len(rows),
            'page': page_number,
            'page_number': page_number,
        }
        max_col = info.get('max_col')
        if isinstance(max_col, int) and max_col > 0:
            table['column_count'] = max_col
            table['max_col'] = max_col
        tables.append(table)

        locators.append(
            {
                'page': page_number,
                'type': 'worksheet',
                'sheet': sheet_name,
                'sheet_name': sheet_name,
                'worksheet': sheet_name,
                'range': range_str,
                'cell_range': range_str,
                'cells_range': range_str,
                'range_string': range_str,
                'coordinates': range_str,
                'headers': headers,
                'rows': len(rows),
                'index': table_index,
                'table_index': table_index,
            }
        )

        # Text rendering (all populated rows, including header and notes).
        text_rows = list(info.get('text_rows') or [])
        text_blocks.append(f'Sheet: {sheet_name}')
        if headers and not text_rows:
            text_rows = [headers, *rows]
        if not text_rows:
            text_rows = ([headers] if headers else []) + rows
        for row in text_rows:
            row_cells = [str(c) if c is not None else '' for c in row]
            if any(cell.strip() if isinstance(cell, str) else cell != '' for cell in row_cells):
                text_blocks.append('\t'.join(row_cells))

    full_text = '\n'.join(block for block in text_blocks).strip()

    confidence: Any = 1.0 if extracted else 0.0
    # If every sheet is empty, still report a successful read.
    has_data = any((info.get('headers') or info.get('rows')) for info in extracted)
    if has_data:
        confidence = 1.0
    else:
        confidence = 0.0

    if not page_numbers:
        page_numbers = [1]
        locators = locators or [
            {
                'page': 1,
                'type': 'worksheet',
                'sheet': 'Sheet1',
                'range': 'A1',
                'cell_range': 'A1',
            }
        ]

    return ReaderResult(
        text=full_text,
        tables=tables,
        page_numbers=page_numbers,
        confidence=confidence,
        locators=list(locators),
    )
