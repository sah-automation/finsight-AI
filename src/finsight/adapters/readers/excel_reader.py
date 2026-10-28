"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

import io
from pathlib import Path
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
    def _extension(
        self,
        source: Any = None,
        *,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        content_type: Any = None,
    ) -> str:
        info_name = ''
        if filename is not None:
            info_name = str(filename)
        elif file_name is not None:
            info_name = str(file_name)
        elif file_path is not None:
            info_name = str(file_path)
        elif isinstance(source, (str, Path)):
            info_name = str(source)

        ext = ''
        if '.' in info_name:
            ext = info_name.rsplit('.', 1)[-1].lower()
        # Content type fallback.
        if not ext and isinstance(content_type, str):
            ct = content_type.lower()
            if 'spreadsheetml' in ct or 'excel' in ct:
                ext = 'xlsx'
            elif 'ms-excel' in ct or 'vnd.ms-excel' in ct:
                ext = 'xls'
        if not ext and isinstance(source, dict):
            for key in ('filename', 'file_name', 'name', 'path'):
                value = source.get(key)
                if isinstance(value, str) and '.' in value:
                    ext = value.rsplit('.', 1)[-1].lower()
                    break
        if not ext and isinstance(getattr(source, 'filename', None), str):
            value = str(source.filename)
            if '.' in value:
                ext = value.rsplit('.', 1)[-1].lower()
        return ext

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
    async def read(
        self,
        company_id: Any,
        content: Any = None,
        *,
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        content_type: Any = None,
        **kwargs: Any,
    ) -> ReaderResult:
        self._require_company_id(company_id)

        # Allow overrides to flow through kwargs.
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

        ext = self._extension(
            source,
            filename=filename,
            file_name=file_name,
            file_path=file_path,
            content_type=content_type,
        )

        if self._is_legacy_extension(ext):
            try:
                return self._read_xls(source)
            except ImportError:
                raise
            except Exception as exc:
                # Surface legacy-module expectations clearly.
                if 'xlrd' in str(exc).lower():
                    raise
                # Fall back to a clear ImportError if xlrd is unavailable.
                try:
                    import xlrd  # type: ignore[import-untyped]
                except Exception as import_exc:  # pragma: no cover - defensive
                    raise ImportError(
                        'xlrd is required to read legacy .xls workbooks'
                    ) from import_exc
                raise
        # Default to openpyxl (.xlsx and friends). If openpyxl cannot parse the
        # workbook, attempt xlrd for genuine legacy files before failing.
        try:
            return self._read_xlsx(source)
        except Exception as openpyxl_exc:
            # Any workbook openpyxl cannot parse may be a legacy .xls file.
            try:
                import xlrd  # noqa: F401
            except Exception as import_exc:
                raise ImportError('xlrd is required to read legacy .xls workbooks') from import_exc
            try:
                return self._read_xls(source)
            except Exception:
                raise openpyxl_exc from None

    def _read_xlsx(self, source: Any) -> ReaderResult:
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

    def _extract_openpyxl_sheets(self, workbook: Any) -> list[dict[str, Any]]:
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
                    row
                    for row in rows_raw[header_idx + 1 :]
                    if any(self._non_empty(c) for c in row)
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

    def _read_xls(self, source: Any) -> ReaderResult:
        try:
            import xlrd
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
                    row
                    for row in raw_rows[header_idx + 1 :]
                    if any(self._non_empty(c) for c in row)
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

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------
    def _build_result_from_sheets(self, extracted: list[dict[str, Any]]) -> ReaderResult:
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
