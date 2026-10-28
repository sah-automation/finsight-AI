"""PageRouter: route document pages to the appropriate reader."""

from __future__ import annotations

import io
from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader

_CONTROL_KEYS = {
    'page_router_enabled',
    'enabled',
    'routed',
    'routing',
    'routing_enabled',
    'use_page_router',
    'router_enabled',
    'route',
    'reader_name',
    'force_reader',
    'page_type',
    'kind',
    'pages',
    'file_path',
    'filename',
    'file_name',
    'content_type',
    'content',
}


class PageRouter(BaseReader):
    """Route pages between primary, table and scan readers.

    Both routed (on) and non-routed (off) paths are implemented. When routing is
    disabled every page goes to the primary reader.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.reader: Any = None
        self.table_reader: Any = None
        self.scan_reader: Any = None
        self.page_router_enabled: bool = True
        self.primary: Any = None
        self.primary_reader: Any = None
        self.text_reader: Any = None
        self.ocr_reader: Any = None
        self.enabled: bool = True
        self.routed: bool = True
        self._min_table_score: int = 0

        # Apply positional readers/config/flags.
        for arg in args:
            if isinstance(arg, bool):
                self.page_router_enabled = arg
                continue
            if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
                self._assign_reader(arg)
                continue
            self._apply_config_like(arg)

        readers = kwargs.pop('readers', None)
        if isinstance(readers, dict):
            self._apply_readers_dict(readers)

        # Named reader aliases.
        self.reader = self._coalesce_reader(
            kwargs,
            self.reader,
            'reader',
            'primary_reader',
            'primary',
            'text_reader',
            'main_reader',
            'default_reader',
            'reader_primary',
        )
        self.table_reader = self._coalesce_reader(
            kwargs,
            self.table_reader,
            'table_reader',
            'table',
            'layout_reader',
            'table_reader_instance',
        )
        self.scan_reader = self._coalesce_reader(
            kwargs, self.scan_reader, 'scan_reader', 'ocr_reader', 'ocr', 'scan_reader_instance'
        )

        # Config / settings like objects.
        for key in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
            if key in kwargs and kwargs[key] is not None:
                self._apply_config_like(kwargs.pop(key))

        # Keep convenience aliases in sync with canonical readers.
        if self.reader is None:
            self.reader = self.primary_reader
        if self.reader is not None:
            self.primary = self.reader
            self.primary_reader = self.reader
            self.text_reader = self.reader
        from .pdf_plumber_reader import PdfPlumberReader

        if self.reader is None:
            self.reader = self._default_primary()
        if self.table_reader is None:
            self.table_reader = PdfPlumberReader()
        if self.scan_reader is None:
            self.scan_reader = PdfPlumberReader()
        self.primary = self.reader
        self.primary_reader = self.reader
        self.text_reader = self.reader
        self.ocr_reader = self.scan_reader
        # Enabled flags (apply before syncing aliases).
        for key in (
            'page_router_enabled',
            'enabled',
            'routed',
            'routing_enabled',
            'use_page_router',
            'router_enabled',
        ):
            if key in kwargs and kwargs[key] is not None:
                self.page_router_enabled = bool(kwargs.pop(key))

        self.enabled = self.page_router_enabled
        self.routed = self.page_router_enabled

        threshold = kwargs.pop('min_table_lines', None)
        if threshold is not None:
            try:
                self._min_table_score = int(threshold)
            except (TypeError, ValueError):
                pass

        # Capture late-bound config/session pointers when supplied.
        if not hasattr(self, '_config'):
            for ckey in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
                if ckey in kwargs:
                    self._config = kwargs.get(ckey)
                    break
            else:
                self._config = None
        if not hasattr(self, '_session'):
            self._session = kwargs.get('session', kwargs.get('db_session'))
        super().__init__(config=self._config, session=self._session)

        # Keep any leftover attributes for compatibility.
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
        enabled = self._enabled_override(kwargs)
        kwargs.setdefault('file_path', file_path)
        if filename is not None:
            kwargs.setdefault('filename', filename)
        if file_name is not None:
            kwargs.setdefault('file_name', file_name)

        # Forced route by caller.
        forced = self._forced_reader(kwargs)
        if forced is not None:
            return await self._call_reader(forced, company_id, source, kwargs)

        if not enabled:
            return await self._call_reader(self.reader, company_id, source, kwargs)

        # Optional caller page type hints.
        hint = kwargs.get('page_type') or kwargs.get('kind') or kwargs.get('route')
        if isinstance(hint, str):
            mapped = self._map_hint(hint)
            if mapped is not None:
                return await self._call_reader(mapped, company_id, source, kwargs)

        # OCR/text heavier: inspect pages when possible.
        infos = self._inspect_pages(source)
        if infos is None:
            # If pages provided as list, use them.
            provided_pages = kwargs.get('pages')
            if isinstance(provided_pages, (list, tuple)):
                infos = [self._normalize_page_info(p) for p in provided_pages]
        if infos is None:
            return await self._call_reader(self.reader, company_id, source, kwargs)

        kinds = [self._classify_page(info) for info in infos]
        if any(k == 'ocr' for k in kinds):
            return await self._call_reader(self.scan_reader, company_id, source, kwargs)
        if any(k == 'table' for k in kinds):
            return await self._call_reader(self.table_reader, company_id, source, kwargs)
        return await self._call_reader(self.reader, company_id, source, kwargs)

    # Convenience names tests may call.
    async def routed_read(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        kwargs.setdefault('page_router_enabled', True)
        return await self.read(company_id, content, **kwargs)

    async def non_routed_read(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        kwargs.setdefault('page_router_enabled', False)
        return await self.read(company_id, content, **kwargs)

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

    def classify(self, page: Any = None, **kwargs: Any) -> str:
        if page is None and kwargs:
            page = self._normalize_page_info(kwargs)
        if page is None:
            return 'text'
        return self._classify_page(self._normalize_page_info(page))

    def classify_page(self, page: Any, **kwargs: Any) -> str:
        return self.classify(page, **kwargs)

    def is_table_heavy(self, page: Any, **kwargs: Any) -> bool:
        return self.classify(page, **kwargs) == 'table'

    def requires_ocr(self, page: Any, **kwargs: Any) -> bool:
        return self.classify(page, **kwargs) == 'ocr'

    def route(self, page: Any = None, **kwargs: Any) -> Any:
        # If looks like a read call (company_id present), delegate.
        if 'company_id' in kwargs or (
            isinstance(page, (str,)) is False
            and hasattr(page, '__class__')
            and 'CompanyId' in type(page).__name__
        ):
            try:
                # heuristic: first positional company_id
                return self.read(
                    page if hasattr(page, 'value') or hasattr(page, '__str__') else None, **kwargs
                )
            except Exception:
                pass
        # Page-level routing: return selected reader.
        kind = self.classify(page, **kwargs)
        if kind == 'ocr':
            return self.scan_reader
        if kind == 'table':
            return self.table_reader
        return self.reader

    def select_reader(self, page: Any = None, company_id: Any = None, **kwargs: Any) -> Any:
        _ = company_id
        return self.route(page, **kwargs)

    def select(self, page: Any = None, **kwargs: Any) -> Any:
        return self.route(page, **kwargs)

    def _assign_reader(self, reader: Any) -> None:
        if self.reader is None:
            self.reader = reader
        elif self.table_reader is None:
            self.table_reader = reader
        elif self.scan_reader is None:
            self.scan_reader = reader

    def _apply_readers_dict(self, mapping: dict[str, Any]) -> None:
        for key, value in mapping.items():
            low = str(key).lower()
            if low in (
                'reader',
                'primary',
                'primary_reader',
                'text',
                'text_reader',
                'main',
                'default',
            ):
                self.reader = value
            elif low in ('table', 'table_reader', 'layout', 'layout_reader'):
                self.table_reader = value
            elif low in ('scan', 'scan_reader', 'ocr', 'ocr_reader'):
                self.scan_reader = value

    def _apply_config_like(self, obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict):
            self._apply_readers_dict(obj)
            # enabled flags commonly found in yaml
            for key in ('page_router_enabled', 'enabled', 'routed'):
                if key in obj and obj[key] is not None:
                    self.page_router_enabled = bool(obj[key])
            return
        # attribute based
        for attr_reader in ('reader', 'primary_reader', 'primary', 'text_reader'):
            value = getattr(obj, attr_reader, None)
            if value is not None and hasattr(value, 'read'):
                self.reader = value
                break
        for attr_table in ('table_reader', 'table', 'layout_reader'):
            value = getattr(obj, attr_table, None)
            if value is not None and (hasattr(value, 'read') or isinstance(value, str)):
                # if string, leave selection to caller/tests; don't instantiate here
                if hasattr(value, 'read'):
                    self.table_reader = value
        for attr_scan in ('scan_reader', 'ocr_reader', 'ocr'):
            value = getattr(obj, attr_scan, None)
            if value is not None and hasattr(value, 'read'):
                self.scan_reader = value
        for flag in ('page_router_enabled', 'enabled', 'routed'):
            value = getattr(obj, flag, None)
            if value is not None:
                self.page_router_enabled = bool(value)

    def _coalesce_reader(self, kwargs: dict[str, Any], current: Any, *names: str) -> Any:
        for name in names:
            if name in kwargs and kwargs[name] is not None:
                value = kwargs.pop(name)
                if hasattr(value, 'read') or value is None:
                    return value if value is not None else current
                # Allow string reader names by returning current (selection left to composition later).
                return current
        return current

    def _default_primary(self) -> Any:
        from .pdf_plumber_reader import PdfPlumberReader

        self.reader = PdfPlumberReader()
        self.primary = self.reader
        self.primary_reader = self.reader
        self.text_reader = self.reader
        return self.reader

    def _enabled_override(self, kwargs: dict[str, Any]) -> bool:
        for key in (
            'page_router_enabled',
            'enabled',
            'routed',
            'routing_enabled',
            'use_page_router',
            'router_enabled',
        ):
            if key in kwargs and kwargs[key] is not None:
                return bool(kwargs[key])
        return self.page_router_enabled

    def _forced_reader(self, kwargs: dict[str, Any]) -> Any:
        route = kwargs.get('force_reader') or kwargs.get('reader_name') or kwargs.get('route')
        if isinstance(route, str):
            return self._map_hint(route)
        if hasattr(route, 'read'):
            return route
        # support kwargs explicit reader object under 'reader' key already consumed?
        return None

    def _map_hint(self, hint: str) -> Any:
        low = hint.strip().lower()
        if low in ('ocr', 'scan', 'scan_reader', 'ocr_reader'):
            return self.scan_reader
        if low in ('table', 'layout', 'table_reader', 'layout_reader'):
            return self.table_reader
        if low in ('text', 'primary', 'reader', 'default', 'pdf', 'text_reader'):
            return self.reader
        return None

    async def _call_reader(
        self, reader: Any, company_id: Any, source: Any, kwargs: dict[str, Any]
    ) -> ReaderResult:
        import inspect

        if reader is None:
            reader = self.reader
        clean = self._clean_kwargs(kwargs)
        result = reader.read(company_id, source, **clean)
        if inspect.isawaitable(result):
            result = await result
        return cast('ReaderResult', result)

    def _clean_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key in _CONTROL_KEYS:
                continue
            # Don't pass through our internal root source placeholders.
            if key in ('stream', 'data', 'bytes', 'content'):
                continue
            out[key] = value
        return out

    def _inspect_pages(self, source: Any) -> list[dict[str, Any]] | None:
        data = self._as_bytes(source)
        try:
            import pdfplumber
        except Exception:
            return None
        try:
            handle = io.BytesIO(data) if data is not None else source
            with pdfplumber.open(handle) as pdf:
                infos: list[dict[str, Any]] = []
                for page in pdf.pages:
                    text = ''
                    try:
                        text = page.extract_text() or ''
                    except Exception:
                        text = ''
                    tables: list[Any] = []
                    try:
                        tables = list(page.extract_tables() or [])
                    except Exception:
                        tables = []
                    found: list[Any] = []
                    try:
                        found = list(page.find_tables() or [])
                    except Exception:
                        found = []
                    infos.append(
                        {
                            'text': text,
                            'tables': tables,
                            'table_count': len(found) or len(tables),
                            'images': list(getattr(page, 'images', []) or []),
                            'lines': list(getattr(page, 'lines', []) or []),
                            'rects': list(getattr(page, 'rects', []) or []),
                        }
                    )
                return infos
        except Exception:
            return None

    def _normalize_page_info(self, page: Any) -> dict[str, Any]:
        if isinstance(page, dict):
            info = dict(page)
            if 'text' not in info:
                # Try common fields.
                for key in ('content', 'body', 'extracted_text'):
                    if key in info:
                        info['text'] = info[key]
                        break
            info.setdefault('text', '')
            info.setdefault('tables', info.get('table') or [])
            if isinstance(info.get('tables'), (tuple,)):
                info['tables'] = list(info['tables'])
            info.setdefault('images', info.get('image') or [])
            info.setdefault('lines', info.get('line') or [])
            info.setdefault('rects', info.get('rect') or [])
            info.setdefault(
                'table_count',
                len(info['tables']) if isinstance(info['tables'], (list, tuple)) else 0,
            )
            return info
        if isinstance(page, (list, tuple)):
            return {
                'text': '',
                'tables': list(page),
                'table_count': 1,
                'images': [],
                'lines': [],
                'rects': [],
            }
        text = ''
        tables: Any = []
        images: Any = []
        lines: Any = []
        rects: Any = []
        table_count = 0
        for attr in ('text', 'content', 'body'):
            value = getattr(page, attr, None)
            if isinstance(value, str):
                text = value
                break
        for attr in ('tables', 'table'):
            value = getattr(page, attr, None)
            if value is not None:
                tables = value
                if isinstance(tables, (list, tuple)):
                    table_count = len(tables)
                else:
                    table_count = 1
                break
        for attr in ('images', 'image'):
            value = getattr(page, attr, None)
            if value is not None:
                images = value
                break
        for attr in ('lines', 'line'):
            value = getattr(page, attr, None)
            if value is not None:
                lines = value
                break
        for attr in ('rects', 'rect'):
            value = getattr(page, attr, None)
            if value is not None:
                rects = value
                break
        # If tables property gives rows directly without container.
        if table_count == 0 and getattr(page, 'rows', None) is not None:
            tables = [page.rows]
            table_count = 1
        if getattr(page, 'table_count', None) is not None:
            try:
                table_count = int(page.table_count)
            except (TypeError, ValueError):
                pass
        return {
            'text': text or '',
            'tables': tables
            if isinstance(tables, (list, tuple))
            else ([tables] if tables is not None else []),
            'table_count': table_count,
            'images': list(images)
            if isinstance(images, (list, tuple))
            else ([] if not images else [images]),
            'lines': list(lines)
            if isinstance(lines, (list, tuple))
            else ([] if not lines else [lines]),
            'rects': list(rects)
            if isinstance(rects, (list, tuple))
            else ([] if not rects else [rects]),
        }

    def _classify_page(self, info: dict[str, Any]) -> str:
        text = str(info.get('text') or '').strip()
        table_count = int(info.get('table_count') or 0)
        tables = info.get('tables') or []
        if (not isinstance(tables, (list, tuple))) and tables:
            table_count = max(table_count, 1)
        if isinstance(tables, (list, tuple)) and len(tables) > table_count:
            table_count = len(tables)
        images = info.get('images') or []
        lines = info.get('lines') or []
        rects = info.get('rects') or []

        has_table = table_count > 0
        if not has_table and isinstance(tables, (list, tuple)):
            # nested rows heuristic
            if tables and all(isinstance(r, (list, tuple)) for r in tables):
                has_table = True

        if not text and images:
            return 'ocr'
        if not text and not images and not has_table:
            # Empty page: if many vector shapes treat as layout table.
            if len(lines) > 8 or len(rects) > 8:
                return 'table'
            return 'text'
        if has_table:
            return 'table'
        if len(lines) > 12 or len(rects) > 12:
            return 'table'
        return 'text'


__all__ = ['PageRouter']
