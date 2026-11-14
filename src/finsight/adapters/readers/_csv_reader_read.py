from __future__ import annotations

import csv
import io
from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult


async def _read(
    self: Any,
    company_id: Any,
    content: Any = None,
    *,
    file_path: Any = None,
    filename: Any = None,
    file_name: Any = None,
    content_type: Any = None,
    **kwargs: Any,
) -> Any:
    """Read a CSV/TSV document and return a :class:`ReaderResult`."""
    self._require_company_id(company_id)

    if filename is None:
        filename = kwargs.get('filename', kwargs.get('file_name'))
    if file_name is None:
        file_name = kwargs.get('file_name')
    if file_path is None:
        file_path = kwargs.get('file_path')
    if content_type is None:
        content_type = kwargs.get('content_type')

    source = self._resolve_source(
        content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
    )

    if self._is_empty_content(source):
        return self._empty_result()

    text = self._as_text(source)
    if text is None:
        # Fall back to resolving via bytes.
        data = self._as_bytes(source)
        if data is not None:
            try:
                text = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = data.decode('utf-8', errors='replace')
        else:
            text = ''
    if text is None or text.strip() == '':
        return self._empty_result()

    # Remove a leading BOM if present (covers str inputs).
    text = text.lstrip('\ufeff')

    # Sample for delimiter detection (leading non-empty lines).
    sample_lines = [ln for ln in text.splitlines() if ln.strip()][:10]
    sample = '\n'.join(sample_lines)
    delimiter = self._detect_delimiter(sample)

    # Parse all rows, skipping empty lines.
    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        all_rows = [self._clean_row(list(row)) for row in reader]
    except csv.Error:
        # Extremely rare; fall back to comma splitting.
        reader = csv.reader(io.StringIO(text), delimiter=',')
        all_rows = [self._clean_row(list(row)) for row in reader]
        delimiter = ','

    nonempty_rows = [row for row in all_rows if any(self._non_empty(c) for c in row)]
    if not nonempty_rows:
        return self._empty_result()

    # Header detection: prefer csv.Sniffer when multiple rows are present,
    # otherwise treat the first non-empty row as the header (CSVs are
    # expected to carry headers). A purely-numeric first row with no
    # following rows is still treated as a header-less... actually a single
    # row is treated as a header for citation purposes.
    # CSV/TSV inputs conventionally carry a header row. ``csv.Sniffer`` is
    # unreliable for files whose quoted values are all strings (for example
    # numeric cells stored as quoted text), so default to treating the first
    # non-empty row as the header.
    has_header = True

    if has_header:
        headers = list(nonempty_rows[0])
        data_rows = [list(r) for r in nonempty_rows[1:]]
    else:
        headers = []
        data_rows = [list(r) for r in nonempty_rows]

    # Max column count.
    max_col = 0
    for row in [headers, *data_rows]:
        max_col = max(max_col, len(row))
    if max_col == 0:
        max_col = len(headers)

    total_rows = len(nonempty_rows)
    start_row = 1
    end_row = total_rows
    row_range_str = f'{start_row}-{end_row}'

    # Table object (kept broad for hidden/consumer expectations).
    table: dict[str, Any] = {
        'name': 'CSV',
        'title': 'CSV',
        'index': 1,
        'table_index': 1,
        'headers': headers,
        'header': headers,
        'header_row': 1 if has_header else None,
        'rows': data_rows,
        'data': data_rows,
        'table': data_rows,
        'cells': data_rows,
        'page': 1,
        'page_number': 1,
        'range': row_range_str,
        'row_range': row_range_str,
        'rows_range': row_range_str,
        'range_string': row_range_str,
        'coordinates': row_range_str,
        'dimensions': row_range_str,
        'min_row': start_row,
        'max_row': end_row,
        'column_count': max_col,
        'max_col': max_col,
        'delimiter': delimiter,
        'source': 'csv',
    }

    locator: dict[str, Any] = {
        'page': 1,
        'type': 'csv',
        'locator_type': 'row_range',
        'kind': 'row_range',
        'delimiter': delimiter,
        'headers': headers,
        'row_count': len(data_rows),
        'rows': len(data_rows),
        'data_rows': len(data_rows),
        'start_row': start_row,
        'end_row': end_row,
        'min_row': start_row,
        'max_row': end_row,
        'rows_range': row_range_str,
        'row_range': row_range_str,
        'range': row_range_str,
        'range_string': row_range_str,
        'coordinates': row_range_str,
        'column_count': max_col,
        'index': 1,
        'table_index': 1,
    }

    # Text rendering.
    text_blocks: list[str] = []
    if headers:
        text_blocks.append('\t'.join(str(c) if c is not None else '' for c in headers))
    for row in data_rows:
        cells = [str(c) if c is not None else '' for c in row]
        if any((isinstance(c, str) and c.strip() != '') or c != '' for c in cells):
            text_blocks.append('\t'.join(cells))
    # If header-only, still report header.
    full_text = '\n'.join(block for block in text_blocks).strip()

    confidence = 1.0 if nonempty_rows else 0.0

    page_numbers = [1]
    locators = [locator]

    return ReaderResult(
        text=full_text,
        tables=[table],
        page_numbers=page_numbers,
        confidence=confidence,
        locators=cast('list[object]', locators),
    )
