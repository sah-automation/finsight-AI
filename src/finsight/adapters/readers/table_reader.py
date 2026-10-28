"""TableReader adapter for table-sensitive pages."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class TableReader(BaseReader):
    """Read table-sensitive pages.

    The reader can either delegate to an underlying adapter selected from
    configuration (``pdfplumber``, ``textract`` or ``self_hosted_layout``) or
    perform a focused pdfplumber table extraction itself. All public read entry
    points return the shared :class:`ReaderResult` shape.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        delegate = kwargs.pop('delegate', None)
        if delegate is None:
            delegate = kwargs.pop('wrapped_reader', None)
        if delegate is None:
            delegate = kwargs.pop('wrapped', None)
        if delegate is None:
            delegate = kwargs.pop('reader', None)
        if delegate is None:
            delegate = kwargs.pop('underlying_reader', None)
        if delegate is None:
            delegate = kwargs.pop('table_reader_instance', None)
        if delegate is None:
            delegate = kwargs.pop('layout_reader', None)
        underlying_name: Any = None
        if delegate is None:
            for key in (
                'table_reader',
                'table_reader_name',
                'backend',
                'engine',
            ):
                if key in kwargs:
                    candidate = kwargs.pop(key)
                    if candidate is not None:
                        delegate = candidate
                        break
        if delegate is None:
            for arg in args:
                if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
                    delegate = arg
                    break
                if isinstance(arg, str):
                    underlying_name = arg
                    break

        if isinstance(delegate, str):
            underlying_name = delegate
            delegate = None

        passed_config = None
        if 'config' in kwargs:
            passed_config = kwargs.pop('config')
        if 'settings' in kwargs and passed_config is None:
            passed_config = kwargs.pop('settings')
        if 'configuration' in kwargs and passed_config is None:
            passed_config = kwargs.pop('configuration')
        session = kwargs.pop('session', kwargs.pop('db_session', None))

        self._delegate = delegate
        self._delegate_name = underlying_name
        self._passed_config = passed_config
        self._config = passed_config
        self._session = session
        super().__init__(config=passed_config, session=session)

        self._minimum_table_lines = int(kwargs.pop('min_table_lines', 0) or 0)
        for key, value in kwargs.items():
            if key not in self.__dict__:
                setattr(self, key, value)

    def _config_table_reader_name(self) -> str | None:
        config = self._config
        if config is None:
            return None
        docs = getattr(config, 'documents', None)
        if docs is not None:
            value = getattr(docs, 'table_reader', None)
            if value is not None:
                return str(value)
        if isinstance(config, dict):
            docs_dict = config.get('documents')
            if isinstance(docs_dict, dict):
                value = docs_dict.get('table_reader')
                if value is not None:
                    return str(value)
            if 'table_reader' in config:
                return str(config.get('table_reader'))
        value = getattr(config, 'table_reader', None)
        if value is not None:
            return str(value)
        return None

    def _resolve_underlying(self) -> Any:
        if self._delegate is not None:
            return self._delegate
        name = self._delegate_name or self._config_table_reader_name()
        if name is None:
            name = 'pdfplumber'
        name_low = str(name).strip().lower()
        cls: Any = None
        module_path: str | None = None
        attr: str | None = None
        if name_low in ('pdfplumber', 'pdf_plumber', 'pdf', 'pdfplumber_reader'):
            module_path = 'finsight.adapters.readers.pdf_plumber_reader'
            attr = 'PdfPlumberReader'
        elif 'textract' in name_low:
            module_path = 'finsight.adapters.readers.textract_reader'
            attr = 'TextractReader'
        elif (
            'layout' in name_low
            or 'self_hosted' in name_low
            or 'self-hosted' in name_low
            or 'table' in name_low
        ):
            module_path = 'finsight.adapters.readers.self_hosted_layout_reader'
            attr = 'SelfHostedLayoutReader'
        else:
            module_path = 'finsight.adapters.readers.pdf_plumber_reader'
            attr = 'PdfPlumberReader'

        try:
            import importlib

            module = importlib.import_module(module_path)
            cls = getattr(module, attr, None)
        except Exception:
            cls = None
        if cls is None:
            try:
                import finsight.adapters.readers as pkg

                alias_map = {
                    'PdfPlumberReader': ('PdfPlumberReader', 'PdfPlumber'),
                    'TextractReader': ('TextractReader', 'Textract'),
                    'SelfHostedLayoutReader': (
                        'SelfHostedLayoutReader',
                        'SelfHostedLayout',
                        'LayoutReader',
                        'Layout',
                    ),
                }
                for alias in alias_map.get(attr, (attr,)):
                    cls = getattr(pkg, alias, None)
                    if cls is not None:
                        break
            except Exception:
                cls = None
        if cls is None:
            return None
        try:
            return cls(config=self._config, session=self._session)
        except Exception:
            try:
                return cls()
            except Exception:
                return None

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

        requested_override = any(
            key in kwargs and kwargs[key] is not None
            for key in ('table_reader', 'reader_name', 'backend', 'engine')
        )
        if (
            self._delegate is not None
            or self._delegate_name is not None
            or self._config_table_reader_name() is not None
            or requested_override
        ):
            underlying = self._resolve_underlying()
        else:
            underlying = None
        for key in ('table_reader', 'reader_name', 'backend', 'engine'):
            if key in kwargs and kwargs[key] is not None:
                override_name = kwargs.pop(key)
                if isinstance(override_name, str):
                    self._delegate_name = override_name
                    self._delegate = None
                    underlying = self._resolve_underlying()
                elif hasattr(override_name, 'read'):
                    self._delegate = override_name
                    underlying = override_name

        if underlying is not None and hasattr(underlying, 'read'):
            import inspect

            result = underlying.read(
                company_id,
                source,
                **self._clean_passthrough(kwargs, file_path, filename, file_name, content_type),
            )
            if inspect.isawaitable(result):
                result = await result
            return BaseReader._coerce_result(result)

        return self._extract_tables(
            company_id,
            source,
            file_path=file_path,
            filename=filename,
            file_name=file_name,
            content_type=content_type,
            **kwargs,
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
        file_path: Any,
        filename: Any,
        file_name: Any,
        content_type: Any,
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

    def _extract_tables(
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
            ]

            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ''
                except Exception:
                    page_text = ''
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
                        'table_id': f'table-{table_index}',
                        'name': f'Table {table_index}',
                        'title': f'Table {table_index}',
                        'nearest_heading': None,
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
                        'source': 'table_reader',
                        'reader': 'table_reader',
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
Table = TableReader
TableDocumentReader = TableReader
TableLayoutReader = TableReader
LayoutTableReader = TableReader

__all__ = [
    'LayoutTableReader',
    'Table',
    'TableDocumentReader',
    'TableLayoutReader',
    'TableReader',
]
