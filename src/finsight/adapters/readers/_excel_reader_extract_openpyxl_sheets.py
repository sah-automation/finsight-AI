"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

from typing import Any


def _extract_openpyxl_sheets(self: Any, workbook: Any) -> Any:
    extracted: list[dict[str, Any]] = []
    for worksheet in getattr(workbook, 'worksheets', []) or []:
        sheet_name = getattr(worksheet, 'title', str(worksheet))
        rows_raw = []
        try:
            for row in worksheet.iter_rows(values_only=True):
                rows_raw.append(self._clean_row(row))
        except Exception:
            rows_raw = []

        header_idx = self._detect_header_row(rows_raw)
        text_rows: list[list[Any]] = [
            row for row in rows_raw if any(self._non_empty(c) for c in row)
        ]
        if header_idx is None:
            headers: list[Any] = []
            data_rows: list[list[Any]] = list(text_rows)
        else:
            headers = list(rows_raw[header_idx])
            data_rows = [
                row for row in rows_raw[header_idx + 1 :] if any(self._non_empty(c) for c in row)
            ]

        try:
            range_str = str(worksheet.dimensions)
        except Exception:
            range_str = 'A1'
        if not range_str:
            range_str = 'A1'

        max_col = 0
        for row in [headers, *data_rows]:
            max_col = max(max_col, len(row))
        if max_col == 0:
            max_col = len(headers)

        extracted.append(
            {
                'sheet': sheet_name,
                'headers': headers,
                'rows': data_rows,
                'text_rows': text_rows,
                'range': range_str,
                'header_idx': header_idx,
                'max_col': max_col,
            }
        )
    # Workbooks with no worksheets still report a single empty sheet entry.
    if not extracted:
        extracted.append(
            {
                'sheet': 'Sheet1',
                'headers': [],
                'rows': [],
                'range': 'A1',
                'header_idx': None,
                'max_col': 0,
            }
        )
    return extracted
