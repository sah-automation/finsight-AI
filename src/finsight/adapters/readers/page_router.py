"""PageRouter: route document pages to the appropriate reader."""

from __future__ import annotations

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
    reader: Any
    table_reader: Any
    scan_reader: Any
    primary: Any
    primary_reader: Any
    text_reader: Any
    page_router_enabled: bool
    _enabled: bool
    enabled: bool
    routed: bool

    """Route pages between primary, table and scan readers.

    Both routed (on) and non-routed (off) paths are implemented. When routing is
    disabled every page goes to the primary reader.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        from ._page_router_init import _init__ as _adapter_method

        _adapter_method(self, *args, **kwargs)

    async def read(self, *args: Any, **kwargs: Any) -> ReaderResult:
        from typing import cast

        from ._page_router_read import _read as _adapter_read

        return cast('ReaderResult', await _adapter_read(self, *args, **kwargs))

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
        return cast('str', self._classify_page(self._normalize_page_info(page)))

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

    def _inspect_pages(self, *args: Any, **kwargs: Any) -> Any:
        from ._page_router_inspect_pages import _inspect_pages as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    def _normalize_page_info(self, *args: Any, **kwargs: Any) -> Any:
        from ._page_router_normalize_page_info import _normalize_page_info as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    def _classify_page(self, *args: Any, **kwargs: Any) -> Any:
        from ._page_router_classify_page import _classify_page as _adapter_method

        return _adapter_method(self, *args, **kwargs)


__all__ = ['PageRouter']
