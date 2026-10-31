"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

from typing import Any


def _read_xls(self: Any, source: Any) -> Any:
    try:
        import xlrd  # type: ignore[import-untyped]
    except Exception as exc:
        raise ImportError('xlrd is required to read legacy .xls workbooks') from exc

    data = self._as_bytes(source)
    if data is not None:
        workbook = xlrd.open_workbook(file_contents=data)
    else:
        workbook = xlrd.open_workbook(str(source))

    extracted: list[dict[str, Any]] = []
    sheet_names = list(
        getattr(workbook, 'sheet_names', list)()
        if callable(getattr(workbook, 'sheet_names', None))
        else getattr(workbook, 'sheet_names', [])
    )
    if not sheet_names:
        try:
            sheet_names = [workbook.sheet_by_index(i).name for i in range(workbook.nsheets)]
        except Exception:
            sheet_names = []

    for sheet_name in sheet_names:
        try:
            if hasattr(workbook, 'sheet_by_name'):
                sheet = workbook.sheet_by_name(sheet_name)
            else:
                sheet = workbook.sheet_by_index(sheet_names.index(sheet_name))
        except Exception:  # noqa: S112
            continue

        nrows = getattr(sheet, 'nrows', 0) or 0
        ncols = getattr(sheet, 'ncols', 0) or 0
        raw_rows: list[list[Any]] = []
        for r in range(nrows):
            try:
                values = list(sheet.row_values(r))
            except Exception:
                values = []
            raw_rows.append(self._clean_row(values))

        header_idx = self._detect_header_row(raw_rows)
        text_rows: list[list[Any]] = [
            row for row in raw_rows if any(self._non_empty(c) for c in row)
        ]
        if header_idx is None:
            headers: list[Any] = []
            data_rows: list[list[Any]] = list(text_rows)
        else:
            headers = list(raw_rows[header_idx])
            data_rows = [
                row for row in raw_rows[header_idx + 1 :] if any(self._non_empty(c) for c in row)
            ]

        if nrows and ncols:
            range_str = f'A1:{self._col_letter(ncols - 1)}{nrows}'
        else:
            range_str = 'A1'

        max_col = max([len(headers)] + [len(row) for row in data_rows], default=0)
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

    return self._build_result_from_sheets(extracted)
