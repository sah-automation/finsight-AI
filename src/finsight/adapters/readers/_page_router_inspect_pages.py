"""PageRouter: route document pages to the appropriate reader."""

from __future__ import annotations

import io
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


def _inspect_pages(self: Any, source: Any) -> list[dict[str, Any]] | None:
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
