"""PageRouter: route document pages to the appropriate reader."""

from __future__ import annotations

from typing import Any

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


async def _read(
    self: Any,
    company_id: Any,
    content: Any = None,
    *,
    file_path: Any = None,
    filename: Any = None,
    file_name: Any = None,
    content_type: Any = None,
    **kwargs: Any,
) -> Any:
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
