"""Unit tests for cited-document KPI visibility filtering."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.kpi_visibility_filter import KpiVisibilityFilter

pytestmark = pytest.mark.unit

INVOICE_VERSION = '10000000-0000-4000-8000-000000000001'
BOARD_VERSION = '10000000-0000-4000-8000-000000000002'
UNKNOWN_VERSION = '10000000-0000-4000-8000-000000000003'


def _version(version_id: str, category: str, state: str = 'committed') -> SimpleNamespace:
    return SimpleNamespace(
        document_version_id=version_id,
        version_id=version_id,
        category=category,
        state=state,
    )


def _row(
    *,
    kpi_code: str = 'revenue',
    document_version_id: str = INVOICE_VERSION,
    citations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'kpi_code': kpi_code,
        'period': '2025-Q1',
        'period_start': '2025-01-01',
        'chart_period': '2025-Q1',
        'chart_period_start': '2025-01-01',
        'currency': 'USD',
        'units': 'USD',
        'value': '100.00',
        'source_citations': (
            [f'cit:v1:{document_version_id}:p1'] if citations is None else list(citations)
        ),
        'computation_status': 'computed',
        'document_version_id': document_version_id,
        'computation_rule_version': 'rule-v1',
        'created_at': '2025-01-02T00:00:00Z',
        'updated_at': '2025-01-02T00:00:00Z',
    }


def test_filters_rows_and_citations_by_access_scope() -> None:
    permissions = {'invoice': ['read'], 'board_report': ['read']}
    visibility = KpiVisibilityFilter(
        category_permissions=permissions,
        access_scope=['invoice'],
    )
    rows = [
        _row(kpi_code='revenue', document_version_id=INVOICE_VERSION),
        _row(kpi_code='burn_rate', document_version_id=BOARD_VERSION),
    ]

    filtered = visibility.filter(
        rows, [_version(INVOICE_VERSION, 'invoice'), _version(BOARD_VERSION, 'board_report')]
    )

    assert [row['kpi_code'] for row in filtered] == ['revenue']
    assert filtered[0]['source_citations'] == [f'cit:v1:{INVOICE_VERSION}:p1']


def test_absent_scope_uses_readable_role_categories() -> None:
    permissions = {'invoice': ['read'], 'board_report': ['view_original']}
    visibility = KpiVisibilityFilter(category_permissions=permissions)

    filtered = visibility.filter(
        [
            _row(document_version_id=INVOICE_VERSION),
            _row(kpi_code='burn_rate', document_version_id=BOARD_VERSION),
        ],
        [_version(INVOICE_VERSION, 'invoice'), _version(BOARD_VERSION, 'board_report')],
    )

    assert [row['kpi_code'] for row in filtered] == ['revenue']


def test_hidden_row_leaves_no_placeholder() -> None:
    visibility = KpiVisibilityFilter(
        category_permissions={'invoice': ['read']},
        access_scope=['board_report'],
    )

    filtered = visibility.filter([_row()], [_version(INVOICE_VERSION, 'invoice')])

    assert filtered == []


def test_unresolved_document_version_is_dropped() -> None:
    visibility = KpiVisibilityFilter(
        category_permissions={'invoice': ['read']},
        access_scope=['invoice'],
    )

    filtered = visibility.filter([_row(document_version_id=UNKNOWN_VERSION)], [])

    assert filtered == []


def test_opaque_citations_are_removed_but_visible_row_is_kept() -> None:
    visibility = KpiVisibilityFilter(
        category_permissions={'invoice': ['read']},
        access_scope=['invoice'],
    )

    filtered = visibility.filter(
        [_row(citations=[f'cit:v1:{INVOICE_VERSION}:p1', 'metric-legacy-token'])],
        [_version(INVOICE_VERSION, 'invoice')],
    )

    assert len(filtered) == 1
    assert filtered[0]['source_citations'] == [f'cit:v1:{INVOICE_VERSION}:p1']


def test_hidden_citation_is_stripped_but_visible_primary_row_is_kept() -> None:
    visibility = KpiVisibilityFilter(
        category_permissions={'invoice': ['read'], 'board_report': ['read']},
        access_scope=['invoice'],
    )

    filtered = visibility.filter(
        [
            _row(
                citations=[
                    f'cit:v1:{INVOICE_VERSION}:p1',
                    f'cit:v1:{BOARD_VERSION}:p2',
                ]
            )
        ],
        [_version(INVOICE_VERSION, 'invoice'), _version(BOARD_VERSION, 'board_report')],
    )

    assert len(filtered) == 1
    assert filtered[0]['source_citations'] == [f'cit:v1:{INVOICE_VERSION}:p1']


def test_row_is_dropped_when_any_cited_document_is_hidden() -> None:
    visibility = KpiVisibilityFilter(
        category_permissions={'invoice': ['read'], 'board_report': ['read']},
        access_scope=['invoice'],
    )

    filtered = visibility.filter(
        [
            _row(
                citations=[
                    f'cit:v1:{INVOICE_VERSION}:p1',
                    f'cit:v1:{BOARD_VERSION}:p2',
                ]
            )
        ],
        [_version(INVOICE_VERSION, 'invoice'), _version(BOARD_VERSION, 'board_report')],
    )

    assert filtered == []


def test_hidden_primary_row_is_dropped_even_when_a_citation_is_visible() -> None:
    visibility = KpiVisibilityFilter(
        category_permissions={'invoice': ['read'], 'board_report': ['read']},
        access_scope=['invoice'],
    )

    filtered = visibility.filter(
        [
            _row(
                document_version_id=BOARD_VERSION,
                citations=[f'cit:v1:{BOARD_VERSION}:p1', f'cit:v1:{INVOICE_VERSION}:p2'],
            )
        ],
        [_version(INVOICE_VERSION, 'invoice'), _version(BOARD_VERSION, 'board_report')],
    )

    assert filtered == []
