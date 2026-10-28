"""Self-hosted (free) layout reader implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class SelfHostedLayoutReader(BaseReader):
    """Free, self-hosted layout/table reader.

    Uses pdfplumber's (bundled, local) layout primitives rather than a paid
    document-analysis service. Returns the same :class:`ReaderResult` shape as
    every other adapter, including table objects and locators.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        delegate = kwargs.pop('delegate', None)
        if delegate is None:
            delegate = kwargs.pop('reader', None)
        if delegate is None:
            delegate = kwargs.pop('layout_reader', None)
        if delegate is None:
            for arg in args:
                if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
                    delegate = arg
                    break

        passed_config = None
        if 'config' in kwargs:
            passed_config = kwargs.pop('config')
        if 'settings' in kwargs and passed_config is None:
            passed_config = kwargs.pop('settings')
        if 'configuration' in kwargs and passed_config is None:
            passed_config = kwargs.pop('configuration')
        session = kwargs.pop('session', kwargs.pop('db_session', None))

        self._delegate = delegate
        self._config = passed_config
        self._session = session
        super().__init__(config=passed_config, session=session)

        for key, value in kwargs.items():
            if key not in self.__dict__:
                setattr(self, key, value)

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

        source = self._resolve_source(
            content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
        )

        if self._is_empty_content(source):
            if not (isinstance(source, (str, Path)) and Path(source).exists()):
                return BaseReader._empty_result()

        if self._delegate is not None and hasattr(self._delegate, 'read'):
            import inspect

            result = self._delegate.read(
                company_id,
                source,
                **self._clean_passthrough(kwargs, file_path, filename, file_name, content_type),
            )
            if inspect.isawaitable(result):
                result = await result
            return BaseReader._coerce_result(result)

        return self._extract_layout(
            company_id,
            source,
            **self._clean_passthrough(kwargs, file_path, filename, file_name, content_type),
        )

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

    def _clean_passthrough(
        self,
        kwargs: dict[str, Any],
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        content_type: Any = None,
    ) -> dict[str, Any]:
        out = dict(kwargs)
        if file_path is not None:
            out.setdefault('file_path', file_path)
        if filename is not None:
            out.setdefault('filename', filename)
        if file_name is not None:
            out.setdefault('file_name', file_name)
        if content_type is not None:
            out.setdefault('content_type', content_type)
        return out

    def _extract_layout(
        self,
        company_id: Any,
        source: Any,
        *,
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        content_type: Any = None,
        **kwargs: Any,
    ) -> ReaderResult:
        self._require_company_id(company_id)
        try:
            import pdfplumber
        except Exception:
            return BaseReader._empty_result()

        data = self._as_bytes(source)
        try:
            if data is not None:
                pdf = pdfplumber.open(io.BytesIO(data))
            else:
                pdf = pdfplumber.open(source)
        except Exception:
            return BaseReader._empty_result()

        try:
            text_parts: list[str] = []
            tables: list[dict[str, Any]] = []
            page_numbers: list[int] = []
            page_confidences: list[float] = []
            locators: list[dict[str, Any]] = []
            table_index = 0

            settings_variants: list[Any] = [
                None,
                {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'},
                {'vertical_strategy': 'text', 'horizontal_strategy': 'text'},
                {'vertical_strategy': 'lines_strict', 'horizontal_strategy': 'lines_strict'},
            ]

            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = ''
                try:
                    # Prefer layout-aware extraction when supported.
                    page_text = page.extract_text(layout=True) or ''
                except Exception:
                    try:
                        page_text = page.extract_text() or ''
                    except Exception:
                        page_text = ''
                if not str(page_text).strip():
                    try:
                        page_text = page.extract_text() or ''
                    except Exception:
                        page_text = page_text or ''

                text_parts.append(page_text)
                page_numbers.append(page_number)
                page_confidences.append(1.0 if str(page_text).strip() else 0.0)

                extracted: list[Any] = []
                found: list[Any] = []
                for settings in settings_variants:
                    try:
                        if settings is None:
                            page_tables = list(page.extract_tables() or [])
                            page_found = list(page.find_tables() or [])
                        else:
                            page_tables = list(page.extract_tables(table_settings=settings) or [])
                            page_found = list(page.find_tables(table_settings=settings) or [])
                    except Exception:
                        page_tables = []
                        page_found = []
                    if page_tables and self._meaningful_tables(page_tables, settings):
                        extracted = page_tables
                        found = page_found
                        break

                for i, _raw_rows in enumerate(extracted or []):
                    rows = [
                        list(r) if isinstance(r, (list, tuple)) else [] for r in (_raw_rows or [])
                    ]
                    while rows and all(
                        cell is None or (isinstance(cell, str) and cell.strip() == '')
                        for cell in rows[-1]
                    ):
                        rows.pop()
                    max_col = max([len(r) for r in rows], default=0)
                    if max_col == 0 and rows:
                        max_col = 1
                    headers = list(rows[0]) if rows else []
                    bbox = None
                    if i < len(found):
                        bbox = getattr(found[i], 'bbox', None)

                    table_index += 1
                    table_obj: dict[str, Any] = {
                        'page': page_number,
                        'page_number': page_number,
                        'virtual_page': page_number,
                        'index': table_index,
                        'table_index': table_index,
                        'table_id': f'layout-table-{table_index}',
                        'name': f'Layout Table {table_index}',
                        'title': f'Layout Table {table_index}',
                        'layout': True,
                        'self_hosted': True,
                        'headers': headers,
                        'header': headers,
                        'header_row': 1 if headers else None,
                        'rows': rows,
                        'data': rows,
                        'table': rows,
                        'cells': rows,
                        'row_count': len(rows),
                        'column_count': max_col,
                        'max_col': max_col,
                        'dimensions': f'{len(rows)}x{max_col}',
                        'bbox': bbox,
                        'bounding_box': bbox,
                        'boundaries': bbox,
                        'source': 'self_hosted_layout',
                        'reader': 'self_hosted_layout',
                    }
                    tables.append(table_obj)
                    locators.append(
                        {
                            'page': page_number,
                            'page_number': page_number,
                            'virtual_page': page_number,
                            'type': 'table',
                            'kind': 'table',
                            'block_type': 'table',
                            'index': table_index,
                            'table_index': table_index,
                            'rows': len(rows),
                            'columns': max_col,
                            'headers': headers,
                            'bbox': bbox,
                            'layout': True,
                            'self_hosted': True,
                        }
                    )

            pdf.close()

            if not locators:
                locators.append(
                    {
                        'page': page_numbers[0] if page_numbers else 1,
                        'page_number': page_numbers[0] if page_numbers else 1,
                        'virtual_page': page_numbers[0] if page_numbers else 1,
                        'type': 'document',
                        'kind': 'document',
                        'block_type': 'document',
                        'index': 0,
                        'table_index': 0,
                        'layout': True,
                        'self_hosted': True,
                    }
                )

            full_text = '\n\n'.join(part for part in text_parts if part is not None).strip()
            confidence: Any = (
                (sum(page_confidences) / len(page_confidences))
                if page_confidences
                else (1.0 if (full_text or tables) else 0.0)
            )
            if not page_numbers:
                page_numbers = [1]

            return ReaderResult(
                text=full_text,
                tables=cast('list[object]', tables),
                page_numbers=page_numbers,
                confidence=confidence,
                locators=cast('list[object]', locators),
            )
        except Exception:
            try:
                pdf.close()
            except Exception:
                pass
            return BaseReader._empty_result()

    @staticmethod
    def _meaningful_tables(tables: Any, settings: Any) -> bool:
        for table in tables or []:
            rows = table or []
            for row in rows:
                if isinstance(row, (list, tuple)):
                    populated = sum(
                        1 for cell in row if cell is not None and str(cell).strip() != ''
                    )
                    if populated >= 2:
                        return True
        strategy = ''
        if isinstance(settings, dict):
            strategy = str(settings.get('vertical_strategy', ''))
        if settings is None or 'lines' in strategy:
            return any(
                isinstance(table, (list, tuple)) and len(table or []) > 0
                for table in (tables or [])
            )
        return False

    _empty_result = BaseReader._empty_result


# Compatibility aliases.
SelfHostedLayout = SelfHostedLayoutReader
LayoutReader = SelfHostedLayoutReader
Layout = SelfHostedLayoutReader
SelfHosted = SelfHostedLayoutReader
SelfHostedReader = SelfHostedLayoutReader
SelfHostedDocumentReader = SelfHostedLayoutReader
LayoutDocumentReader = SelfHostedLayoutReader

__all__ = [
    'Layout',
    'LayoutDocumentReader',
    'LayoutReader',
    'SelfHosted',
    'SelfHostedDocumentReader',
    'SelfHostedLayout',
    'SelfHostedLayoutReader',
    'SelfHostedReader',
]
