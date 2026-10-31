"""CSV/TSV reader adapter implementing :class:`DocumentReader`.

Uses ``csv.Sniffer`` for delimiter detection, strips a UTF-8 BOM, skips
empty lines and preserves the header row. Tabular data is emitted as a single
table and a single virtual page paired with a concrete row-range locator so
citations stay meaningful beyond "Page 1".
"""

from __future__ import annotations

from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class CsvReader(BaseReader):
    """Read CSV and TSV inputs with delimiter detection.

    The delimiter is sniffed from the leading non-empty lines (supporting
    commas, tabs, semicolons and pipes). A UTF-8 BOM is removed, blank lines
    are skipped and the (sniffed or first-row) header is preserved. A single
    virtual page (``1``) is always paired with a concrete row-range locator.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config = kwargs.pop('config', kwargs.pop('settings', None))
        for alias in ('configuration', 'app_config', 'ctx'):
            if alias in kwargs and self._config is None:
                self._config = kwargs.pop(alias)
            elif alias in kwargs:
                kwargs.pop(alias)

        session = kwargs.pop('session', kwargs.pop('db_session', None))
        self._session = session
        super().__init__(config=self._config, session=session)

        for key, value in list(kwargs.items()):
            if key not in self.__dict__:
                setattr(self, key, value)
            kwargs.pop(key, None)

    # ------------------------------------------------------------------
    # Configuration / source helpers
    # ------------------------------------------------------------------
    def _extension(self, *args: Any, **kwargs: Any) -> Any:
        from ._csv_reader_extension import _extension as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    # ------------------------------------------------------------------
    # Text decoding
    # ------------------------------------------------------------------
    def _as_text(self, *args: Any, **kwargs: Any) -> Any:
        from ._csv_reader_as_text import _as_text as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    @staticmethod
    def _non_empty(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ''
        return True

    @staticmethod
    def _clean_row(values: Any) -> list[Any]:
        values = list(values or [])
        while values and (
            values[-1] is None or (isinstance(values[-1], str) and values[-1].strip() == '')
        ):
            values.pop()
        return list(values)

    # ------------------------------------------------------------------
    # Delimiter detection
    # ------------------------------------------------------------------
    def _detect_delimiter(self, *args: Any, **kwargs: Any) -> Any:
        from ._csv_reader_detect_delimiter import _detect_delimiter as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    # ------------------------------------------------------------------
    # Read entry point
    # ------------------------------------------------------------------
    async def read(self, *args: Any, **kwargs: Any) -> ReaderResult:
        from ._csv_reader_read import _read as _adapter_read

        return cast('ReaderResult', await _adapter_read(self, *args, **kwargs))

    # Convenience aliases (parity with sibling readers).
    async def read_document(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        """Alias for :meth:`read`."""
        return await self.read(company_id, content, **kwargs)

    async def extract(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        """Alias for :meth:`read`."""
        return await self.read(company_id, content, **kwargs)

    async def parse(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        """Alias for :meth:`read`."""
        return await self.read(company_id, content, **kwargs)

    async def extract_text(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        """Alias for :meth:`read`."""
        return await self.read(company_id, content, **kwargs)


# Compatibility aliases (mirrors Excel/Textract naming).
Csv = CsvReader
CSV = CsvReader
CSVReader = CsvReader
CsvDocumentReader = CsvReader
CSVDocumentReader = CsvReader
DelimitedReader = CsvReader
DelimitedDocumentReader = CsvReader
TsvReader = CsvReader
TSVReader = CsvReader
TsvDocumentReader = CsvReader
TSVDocumentReader = CsvReader
TabularReader = CsvReader

__all__ = [
    'CSV',
    'CSVDocumentReader',
    'CSVReader',
    'Csv',
    'CsvDocumentReader',
    'CsvReader',
    'DelimitedDocumentReader',
    'DelimitedReader',
    'TSVDocumentReader',
    'TSVReader',
    'TabularReader',
    'TsvDocumentReader',
    'TsvReader',
]
