"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class ExcelReader(BaseReader):
    """Read Excel workbooks one worksheet at a time.

    Each worksheet becomes a separate table object carrying its headers, data
    rows and cell range. Virtual page indices are one per worksheet and every
    index is paired with a concrete locator naming the sheet and its range.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config = kwargs.pop('config', kwargs.pop('settings', None))
        # Allow overrides that mirrored builders might pass.
        for alias in ('configuration', 'app_config', 'ctx'):
            if alias in kwargs and self._config is None:
                self._config = kwargs.pop(alias)
            elif alias in kwargs:
                kwargs.pop(alias)

        session = kwargs.pop('session', kwargs.pop('db_session', None))
        self._session = session
        super().__init__(config=self._config, session=session)

        # Keep any reader-specific overrides passed through kwargs.
        for key, value in list(kwargs.items()):
            if key not in self.__dict__:
                setattr(self, key, value)
            kwargs.pop(key, None)

    # ------------------------------------------------------------------
    # Configuration helpers (kept for parity with sibling readers)
    # ------------------------------------------------------------------
    def _extension(self, *args: Any, **kwargs: Any) -> Any:
        from ._excel_reader_extension import _extension as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    def _is_legacy_extension(self, ext: str) -> bool:
        return ext == 'xls'

    @staticmethod
    def _col_letter(index: int) -> str:
        # 0-based column index -> A1 style letter.
        result = ''
        number = max(1, int(index) + 1)
        while number > 0:
            number, remainder = divmod(number - 1, 26)
            result = chr(65 + remainder) + result
        return result or 'A'

    @staticmethod
    def _clean_row(values: Any) -> list[Any]:
        values = list(values or [])
        # Trim trailing empty cells while preserving meaningful leading None.
        while values and (
            values[-1] is None or (isinstance(values[-1], str) and values[-1].strip() == '')
        ):
            values.pop()
        return values  # type: ignore[no-any-return]

    @staticmethod
    def _non_empty(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ''
        return True

    def _detect_header_row(self, rows: list[list[Any]]) -> int | None:
        nonempty = [
            (idx, row) for idx, row in enumerate(rows) if any(self._non_empty(c) for c in row)
        ]
        if not nonempty:
            return None
        # Prefer the first row containing at least two populated cells; this skips
        # title/subtitle rows while still handling single-column sheets.
        for idx, row in nonempty:
            populated = sum(1 for cell in row if self._non_empty(cell))
            if populated >= 2:
                return idx
        return nonempty[0][0]

    # ------------------------------------------------------------------
    # Read entry point
    # ------------------------------------------------------------------
    async def read(self, *args: Any, **kwargs: Any) -> ReaderResult:
        from typing import cast

        from ._excel_reader_read import _read as _adapter_read

        return cast('ReaderResult', await _adapter_read(self, *args, **kwargs))

    def _read_xlsx(self, *args: Any, **kwargs: Any) -> Any:
        from ._excel_reader_read_xlsx import _read_xlsx as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    def _extract_openpyxl_sheets(self, *args: Any, **kwargs: Any) -> Any:
        from ._excel_reader_extract_openpyxl_sheets import (
            _extract_openpyxl_sheets as _adapter_method,
        )

        return _adapter_method(self, *args, **kwargs)

    def _read_xls(self, *args: Any, **kwargs: Any) -> Any:
        from ._excel_reader_read_xls import _read_xls as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------
    def _build_result_from_sheets(self, *args: Any, **kwargs: Any) -> Any:
        from ._excel_reader_build_result_from_sheets import (
            _build_result_from_sheets as _adapter_method,
        )

        return _adapter_method(self, *args, **kwargs)

    # Convenience aliases for Liskov/port parity.
    async def read_document(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def extract(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def parse(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def extract_text(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)


# Compatibility aliases.
Excel = ExcelReader
XlsxReader = ExcelReader
XlsReader = ExcelReader
ExcelDocumentReader = ExcelReader
XlsxDocumentReader = ExcelReader
SpreadsheetReader = ExcelReader

__all__ = [
    'Excel',
    'ExcelDocumentReader',
    'ExcelReader',
    'SpreadsheetReader',
    'XlsReader',
    'XlsxDocumentReader',
    'XlsxReader',
]
