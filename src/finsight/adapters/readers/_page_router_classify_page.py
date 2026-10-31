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


def _classify_page(self: Any, info: dict[str, Any]) -> Any:
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
