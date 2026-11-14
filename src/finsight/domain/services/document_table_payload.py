"""Payload helpers shared by the document-table normaliser.

Readers describe tables with different key names and value types. These helpers
coerce those descriptions into the single payload shape persisted in
``document_tables.payload``.
"""

from __future__ import annotations

import html as html_lib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from finsight.domain.entities.document_table import DocumentTable

ROW_KEYS = ('rows', 'data', 'cells', 'table', 'values')
HEADER_KEYS = ('headers', 'header', 'column_headers')
TABLE_ID_KEYS = ('table_id', 'tableId', 'id', 'name', 'title')
READER_INDEX_KEYS = ('table_index', 'index', 'position', 'ordinal')
PAGE_KEYS = ('page', 'page_number', 'pageNumber', 'virtual_page', 'page_from')
HTML_KEYS = ('html', 'html_text', 'table_html', 'html_content')
REVIEW_KEYS = ('needs_review', 'needsReview', 'review', 'flagged')
ACTIVE_KEYS = ('is_active', 'isActive', 'active')
METADATA_KEYS = (
    'bbox',
    'bounding_box',
    'boundaries',
    'confidence',
    'sheet',
    'sheet_name',
    'worksheet',
    'range',
    'cell_range',
    'range_string',
    'coordinates',
    'dimensions',
    'delimiter',
    'source',
    'reader',
    'name',
    'title',
    'heading',
    'nearest_heading',
    'section',
    'row_count',
    'column_count',
    'max_col',
    'min_row',
    'max_row',
)


def first_value(source: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(source, Mapping):
            if name in source and source.get(name) is not None:
                return source.get(name)
        elif hasattr(source, name):
            candidate = getattr(source, name, None)
            if candidate is not None:
                return candidate
    return default


def as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'1', 'true', 'yes', 'y', 'on', 'flagged'}:
            return True
        if lowered in {'0', 'false', 'no', 'n', 'off', 'unflagged'}:
            return False
    return bool(value)


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode('utf-8', 'replace')
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    return str(value)


def normalise_rows(value: Any) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple, set, frozenset)):
        value = [value]
    return [list(row) if isinstance(row, (list, tuple)) else row for row in value]


def normalise_headers(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def column_count(rows: list[Any], headers: list[Any]) -> int:
    widths = [len(row) for row in rows if isinstance(row, (list, tuple))]
    if headers:
        widths.append(len(headers))
    return max(widths, default=0)


def _escape(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, Mapping):
        value = json.dumps(jsonable(value), sort_keys=True)
    elif isinstance(value, (list, tuple, set, frozenset)):
        value = ', '.join(str(jsonable(item)) for item in value)
    return html_lib.escape(str(value), quote=True).replace('\n', '<br>')


def render_html(headers: list[Any], rows: list[Any]) -> str:
    parts = ['<table>']
    if headers:
        parts.append('<thead><tr>')
        parts.extend(f'<th>{_escape(cell)}</th>' for cell in headers)
        parts.append('</tr></thead>')
    parts.append('<tbody>')
    for row in rows:
        cells = row if isinstance(row, (list, tuple)) else [row]
        if headers and list(cells) == list(headers):
            continue
        parts.append('<tr>')
        parts.extend(f'<td>{_escape(cell)}</td>' for cell in cells)
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)


def build_metadata(raw: Any, ordinal: int) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for name in METADATA_KEYS:
        value = first_value(raw, name)
        if value is not None:
            metadata[name] = jsonable(value)
    reader_index = as_int(first_value(raw, *READER_INDEX_KEYS))
    if reader_index is not None and reader_index != ordinal:
        metadata['reader_index'] = reader_index
    return metadata


def resolve_table_id(raw: Any, ordinal: int) -> str:
    candidate = first_value(raw, *TABLE_ID_KEYS)
    if candidate is not None:
        text = str(candidate).strip()
        if text:
            return text
    return f'table-{ordinal + 1}'


def unique_table_id(candidate: str, used: set[str]) -> str:
    """Keep reader ids where possible, suffixing duplicates within one version."""
    table_id = candidate
    suffix = 2
    while table_id in used:
        table_id = f'{candidate}-{suffix}'
        suffix += 1
    used.add(table_id)
    return table_id


def resolve_page(raw: Any, ordinal: int, page_numbers: Iterable[Any] | None) -> int | None:
    page = as_int(first_value(raw, *PAGE_KEYS))
    if page is not None:
        return page
    if page_numbers is not None:
        pages = list(page_numbers)
        if ordinal < len(pages):
            return as_int(pages[ordinal])
    return None


def iter_tables(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, DocumentTable):
        return [value]
    if isinstance(value, Mapping):
        if value.get('tables') is not None:
            return iter_tables(value.get('tables'))
        return [value]
    tables = first_value(value, 'tables', default=None)
    if tables is not None and not isinstance(tables, (str, bytes)):
        return iter_tables(tables)
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        if not items:
            return []
        if all(isinstance(item, (list, tuple)) for item in items):
            return [items]
        return items
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


__all__ = [
    'ACTIVE_KEYS',
    'HEADER_KEYS',
    'HTML_KEYS',
    'PAGE_KEYS',
    'READER_INDEX_KEYS',
    'REVIEW_KEYS',
    'ROW_KEYS',
    'TABLE_ID_KEYS',
    'as_bool',
    'as_int',
    'build_metadata',
    'column_count',
    'first_value',
    'iter_tables',
    'jsonable',
    'normalise_headers',
    'normalise_rows',
    'render_html',
    'resolve_page',
    'resolve_table_id',
    'unique_table_id',
]
