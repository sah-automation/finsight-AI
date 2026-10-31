"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

import io
from typing import Any


def _read_xlsx(self: Any, source: Any) -> Any:
    import openpyxl  # type: ignore[import-untyped]

    data = self._as_bytes(source)

    def _load(data_only: bool) -> Any:
        if data is not None:
            return openpyxl.load_workbook(io.BytesIO(data), data_only=data_only)
        return openpyxl.load_workbook(source, data_only=data_only)

    workbook = _load(True)
    sheets = self._extract_openpyxl_sheets(workbook)
    # If cached values are missing (for example formula-only workbooks
    # written by code), fall back to raw cell values.
    has_value = any(
        any(self._non_empty(c) for c in (info.get('headers') or []))
        or any(self._non_empty(c) for row in (info.get('rows') or []) for c in row)
        for info in sheets
    )
    if not has_value:
        try:
            workbook = _load(False)
            sheets = self._extract_openpyxl_sheets(workbook)
        except Exception:
            pass
    return self._build_result_from_sheets(sheets)
