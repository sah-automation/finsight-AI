"""Unit tests for opaque KPI cursor pagination."""

from __future__ import annotations

from typing import Any

import pytest

from finsight.application.kpi_cursor_paginator import KpiCursorPaginator

pytestmark = pytest.mark.unit


def _row(kpi_code: str, period_start: str, *, document_version_id: str = 'doc-1') -> dict[str, Any]:
    return {
        'kpi_code': kpi_code,
        'period_start': period_start,
        'chart_period': '2025-Q1',
        'document_version_id': document_version_id,
    }


def _paginator() -> KpiCursorPaginator:
    return KpiCursorPaginator(default_page_size=2, max_page_size=3)


def test_uses_default_page_size_and_descending_order() -> None:
    rows = [
        _row('revenue', '2025-01-01'),
        _row('gross_margin', '2025-04-01'),
        _row('burn_rate', '2025-07-01'),
    ]

    items, cursor = _paginator().paginate(rows, limit=None, cursor=None)

    assert [row['kpi_code'] for row in items] == ['burn_rate', 'gross_margin']
    assert cursor is not None


def test_cursor_returns_successive_non_overlapping_pages() -> None:
    rows = [
        _row('revenue', '2025-01-01'),
        _row('gross_margin', '2025-04-01'),
        _row('burn_rate', '2025-07-01'),
        _row('runway', '2025-10-01'),
        _row('dso', '2024-10-01'),
    ]
    paginator = _paginator()

    first, first_cursor = paginator.paginate(rows, limit=2, cursor=None)
    second, second_cursor = paginator.paginate(rows, limit=2, cursor=first_cursor)
    third, third_cursor = paginator.paginate(rows, limit=2, cursor=second_cursor)

    assert [row['kpi_code'] for row in first] == ['runway', 'burn_rate']
    assert [row['kpi_code'] for row in second] == ['gross_margin', 'revenue']
    assert [row['kpi_code'] for row in third] == ['dso']
    assert third_cursor is None


def test_rejects_limit_above_configured_maximum() -> None:
    with pytest.raises(ValueError, match='limit'):
        _paginator().paginate([], limit=4, cursor=None)


def test_rejects_invalid_cursor() -> None:
    with pytest.raises(ValueError, match='cursor'):
        _paginator().paginate([], limit=2, cursor='not-a-cursor')


def test_tie_breakers_match_repository_order() -> None:
    rows = [
        _row('z_code', '2025-01-01', document_version_id='b'),
        _row('a_code', '2025-01-01', document_version_id='a'),
        _row('a_code', '2025-01-01', document_version_id='c'),
    ]

    items, _ = _paginator().paginate(rows, limit=3, cursor=None)

    assert [row['document_version_id'] for row in items] == ['a', 'c', 'b']
