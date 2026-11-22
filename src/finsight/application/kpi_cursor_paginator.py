"""Opaque cursor pagination for the KPI list endpoint."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_SENTINEL_KEY = '__kpi_cursor_sentinel__'
_CURSOR_FIELDS = ('period_start', 'kpi_code', 'chart_period', 'document_version_id')


def _text(value: Any) -> str:
    return '' if value is None else str(value)


def _encode_cursor(row: Mapping[str, Any]) -> str:
    payload = [_text(row.get(field_name)) for field_name in _CURSOR_FIELDS]
    raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _decode_cursor(cursor: str) -> dict[str, str]:
    try:
        padding = '=' * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding).decode('utf-8'))
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError('Invalid cursor.') from exc
    if not isinstance(payload, list) or len(payload) != len(_CURSOR_FIELDS):
        raise ValueError('Invalid cursor.')
    return dict(zip(_CURSOR_FIELDS, (_text(value) for value in payload), strict=True))


class KpiCursorPaginator:
    """Sort KPI rows and return one cursor-paginated page."""

    def __init__(self, *, default_page_size: int, max_page_size: int) -> None:
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size

    def paginate(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        limit: int | None,
        cursor: str | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return the requested page and an opaque cursor for the next page."""
        page_size = self.resolve_limit(limit)
        ordered = self._sort_rows(rows)
        if cursor is not None:
            start = self._index_after_cursor(ordered, _decode_cursor(cursor))
        else:
            start = 0
        page = [dict(row) for row in ordered[start : start + page_size]]
        next_cursor = None
        if start + page_size < len(ordered) and page:
            next_cursor = _encode_cursor(page[-1])
        return page, next_cursor

    def resolve_limit(self, limit: int | None) -> int:
        """Validate the requested page size against configured bounds."""
        resolved = self._default_page_size if limit is None else int(limit)
        if resolved < 1 or resolved > self._max_page_size:
            raise ValueError(f'limit must be between 1 and {self._max_page_size}.')
        return resolved

    def _sort_rows(self, rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        ordered = list(rows)
        ordered.sort(key=lambda row: tuple(_text(row.get(name)) for name in _CURSOR_FIELDS[1:]))
        ordered.sort(key=lambda row: _text(row.get('period_start')), reverse=True)
        return ordered

    def _index_after_cursor(
        self,
        rows: Sequence[Mapping[str, Any]],
        cursor_row: Mapping[str, str],
    ) -> int:
        marker: dict[str, Any] = dict(cursor_row)
        marker[_SENTINEL_KEY] = True
        ordered = self._sort_rows([*rows, marker])
        for index, row in enumerate(ordered):
            if row.get(_SENTINEL_KEY) is True:
                return index
        return len(ordered)
