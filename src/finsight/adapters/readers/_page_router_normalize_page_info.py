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


def _normalize_page_info(self: Any, page: Any) -> Any:
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
