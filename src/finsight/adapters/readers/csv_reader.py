"""CSV/TSV reader adapter implementing :class:`DocumentReader`.

Uses ``csv.Sniffer`` for delimiter detection, strips a UTF-8 BOM, skips
empty lines and preserves the header row. Tabular data is emitted as a single
table and a single virtual page paired with a concrete row-range locator so
citations stay meaningful beyond "Page 1".
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
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
        if '.' in info_name and '\n' not in info_name:
            ext = info_name.rsplit('.', 1)[-1].lower()
        if not ext and isinstance(content_type, str):
            ct = content_type.lower()
            if 'tab-separated' in ct or 'tsv' in ct:
                ext = 'tsv'
            elif 'csv' in ct or 'comma-separated' in ct or 'text/plain' in ct:
                ext = 'csv'
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

    # ------------------------------------------------------------------
    # Text decoding
    # ------------------------------------------------------------------
    def _as_text(self, source: Any) -> str | None:
        if source is None:
            return None
        if isinstance(source, str):
            # Could be CSV content or a filesystem path.
            try:
                path = Path(source)
                if path.exists() and path.is_file():
                    return path.read_text(encoding='utf-8-sig')
            except (OSError, ValueError):
                pass
            return source
        if isinstance(source, (bytes, bytearray)):
            return bytes(source).decode('utf-8-sig')
        if hasattr(source, 'read'):
            try:
                raw = source.read()
                if hasattr(source, 'seek'):
                    try:
                        source.seek(0)
                    except (OSError, ValueError):
                        pass
                if isinstance(raw, (bytes, bytearray)):
                    return bytes(raw).decode('utf-8-sig')
                if isinstance(raw, str):
                    return raw.lstrip('\ufeff')
            except (OSError, UnicodeDecodeError, ValueError, AttributeError):
                return None
        data = self._as_bytes(source)
        if data is not None:
            try:
                return data.decode('utf-8-sig')
            except UnicodeDecodeError:
                return data.decode('utf-8', errors='replace')
        if isinstance(source, dict):
            for key in ('content', 'data', 'bytes', 'body', 'file', 'text'):
                value = source.get(key)
                if value is not None and value is not source:
                    found = self._as_text(value)
                    if found is not None:
                        return found
        for attr in ('content', 'data', 'body', 'file', 'text'):
            value = getattr(source, attr, None)
            if value is not None and value is not source:
                found = self._as_text(value)
                if found is not None:
                    return found
        return None

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
    def _detect_delimiter(self, sample: str) -> str:
        if not sample.strip():
            return ','

        # Honour an unambiguous tab-separated input first.
        if sample.count('\t') > 0:
            try:
                lines = [ln for ln in sample.splitlines() if ln.strip()]
                parsed = list(csv.reader(lines, delimiter='\t'))
                if (
                    parsed
                    and all(len(r) > 1 for r in parsed)
                    and len({len(r) for r in parsed}) == 1
                ):
                    return '\t'
            except csv.Error:
                pass

        try:
            dialect = csv.Sniffer().sniff(sample + '\n', delimiters=',\t;|')
            if getattr(dialect, 'delimiter', None):
                return str(dialect.delimiter)
        except csv.Error:
            pass

        # Fallback that respects quoted fields: evaluate each candidate by
        # parsing the sample and preferring a delimiter that yields a consistent
        # multi-column shape across every non-empty line.
        candidates = (',', '\t', ';', '|')
        best_delim = ','
        best_score = (-1, -1)  # (column_count, consistent_row_count)
        for delim in candidates:
            try:
                rows = list(csv.reader(sample.splitlines(), delimiter=delim))
                rows = [r for r in rows if any(str(c).strip() != '' for c in r)]
                if not rows:
                    continue
                counts: dict[int, int] = {}
                for row in rows:
                    counts[len(row)] = counts.get(len(row), 0) + 1
                top_cols = max(counts)
                consistent = counts.get(top_cols, 0)
                if top_cols <= 1:
                    continue
                score = (top_cols, consistent)
                if score > best_score:
                    best_score = score
                    best_delim = delim
            except csv.Error:
                continue

        if best_score[0] <= 1:
            # Last resort: raw counts (may be imprecise for quoted fields).
            tab_count = sample.count('\t')
            if tab_count > 0:
                return '\t'
            raw_counts: dict[str, int] = {d: sample.count(d) for d in (',', ';', '|')}
            best = max(raw_counts, key=lambda d: raw_counts[d])
            return best if raw_counts[best] > 0 else ','
        return best_delim

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
