"""Unit tests for margin KPI computations (issue #373)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from finsight.domain.entities.metric import Metric
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, citation_id, make_metric

_metric = make_metric
_citation_id = citation_id


# --- Margin KPI tests (issue #373) ---


@pytest.mark.parametrize(
    ('method_name', 'kpi_code', 'input_name', 'input_value', 'expected_value'),
    [
        ('compute_gross_margin', 'gross_margin', 'cogs', Decimal('150.00'), '25.00'),
        ('compute_net_margin', 'net_margin', 'net_income', Decimal('150.00'), '75.00'),
    ],
)
def test_margin_computes_percentage_from_revenue_and_input_metric(
    method_name: str,
    kpi_code: str,
    input_name: str,
    input_value: Decimal,
    expected_value: str,
) -> None:
    metrics = [
        _metric('revenue', Decimal('200.00'), metric_id='rev-1'),
        _metric(input_name, input_value, metric_id='input-1'),
    ]

    rows = getattr(KpiComputationService(RULE_VERSION), method_name)(metrics)

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': kpi_code,
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': expected_value,
            'source_citations': [_citation_id()],
            'source_metric_ids': ['rev-1', 'input-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
            'reason': None,
        }
    ]


@pytest.mark.parametrize(
    ('method_name', 'input_name', 'expected_reason'),
    [
        ('compute_gross_margin', 'cogs', 'missing_cogs'),
        ('compute_net_margin', 'net_income', 'missing_net_income'),
    ],
)
def test_margin_needs_review_when_second_input_is_missing(
    method_name: str, input_name: str, expected_reason: str
) -> None:
    rows = getattr(KpiComputationService(RULE_VERSION), method_name)(
        [_metric('revenue', Decimal('200'), metric_id='rev-only')]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason
    assert rows[0]['source_metric_ids'] == ['rev-only']
    assert rows[0]['source_citations'] == [_citation_id()]


@pytest.mark.parametrize(
    ('method_name', 'input_name'),
    [
        ('compute_gross_margin', 'cogs'),
        ('compute_net_margin', 'net_income'),
    ],
)
def test_margin_needs_review_when_revenue_is_missing(method_name: str, input_name: str) -> None:
    rows = getattr(KpiComputationService(RULE_VERSION), method_name)(
        [_metric(input_name, Decimal('50'), metric_id='input-only')]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_revenue'
    assert rows[0]['source_metric_ids'] == ['input-only']


@pytest.mark.parametrize(
    ('method_name', 'input_name'),
    [
        ('compute_gross_margin', 'cogs'),
        ('compute_net_margin', 'net_income'),
    ],
)
@pytest.mark.parametrize(
    ('field', 'mismatched_value', 'expected_reason'),
    [
        ('currency', 'EUR', 'currency_mismatch'),
        ('units', 'millions', 'units_mismatch'),
    ],
)
def test_margin_needs_review_when_inputs_disagree(
    method_name: str,
    input_name: str,
    field: str,
    mismatched_value: str,
    expected_reason: str,
) -> None:
    metrics = [
        _metric('revenue', Decimal('200'), metric_id='rev-1'),
        _metric(input_name, Decimal('50'), metric_id='input-1', **{field: mismatched_value}),
    ]

    rows = getattr(KpiComputationService(RULE_VERSION), method_name)(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


@pytest.mark.parametrize(
    ('method_name', 'input_name'),
    [
        ('compute_gross_margin', 'cogs'),
        ('compute_net_margin', 'net_income'),
    ],
)
def test_margin_never_pairs_inputs_from_different_periods(
    method_name: str, input_name: str
) -> None:
    metrics = [
        _metric('revenue', Decimal('200'), metric_id='rev-1'),
        _metric(input_name, Decimal('50'), metric_id='input-1', period='2026-Q4'),
    ]

    rows = getattr(KpiComputationService(RULE_VERSION), method_name)(metrics)

    assert len(rows) == 2
    assert all(row['value'] is None for row in rows)
    assert {row['reason'] for row in rows} == {'missing_revenue', f'missing_{input_name}'}


def test_gross_margin_sums_input_metrics_before_dividing() -> None:
    metrics = [
        _metric('revenue', Decimal('100'), metric_id='rev-a'),
        _metric('Revenue', Decimal('100'), metric_id='rev-b', page=2),
        _metric('COGS', Decimal('60'), metric_id='cogs-a'),
        _metric('cogs', Decimal('40'), metric_id='cogs-b', page=2),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_gross_margin(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] == '50.00'
    assert rows[0]['computation_status'] == 'computed'
    assert rows[0]['reason'] is None
    assert rows[0]['source_metric_ids'] == ['rev-a', 'rev-b', 'cogs-a', 'cogs-b']
    assert rows[0]['source_citations'] == [_citation_id(page=1), _citation_id(page=2)]


def test_margin_needs_review_when_an_input_lacks_a_citation() -> None:
    uncited_cogs = Metric(
        metric_id='cogs-uncited',
        company_id=COMPANY,
        name='cogs',
        value=Decimal('100'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='version-1',
        source_location={},
    )

    rows = KpiComputationService(RULE_VERSION).compute_gross_margin(
        [_metric('revenue', Decimal('200'), metric_id='rev-1'), uncited_cogs]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_citations'
    assert rows[0]['source_citations'] == [_citation_id()]


def test_margin_needs_review_when_revenue_is_zero() -> None:
    rows = KpiComputationService(RULE_VERSION).compute_net_margin(
        [
            _metric('revenue', Decimal('0'), metric_id='rev-zero'),
            _metric('net_income', Decimal('50'), metric_id='income-1'),
        ]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'zero_revenue'


def test_margin_keeps_periods_and_document_versions_separate() -> None:
    metrics = [
        _metric('revenue', Decimal('200'), metric_id='rev-q3-v1'),
        _metric('cogs', Decimal('50'), metric_id='cogs-q3-v1'),
        _metric('revenue', Decimal('400'), metric_id='rev-q3-v2', version='version-2'),
        _metric('cogs', Decimal('100'), metric_id='cogs-q3-v2', version='version-2'),
        _metric('revenue', Decimal('100'), metric_id='rev-q4', period='2026-Q4'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_gross_margin(metrics)

    assert [(row['period'], row['document_version_id'], row['value']) for row in rows] == [
        ('2026-Q3', 'version-1', '75.00'),
        ('2026-Q3', 'version-2', '75.00'),
        ('2026-Q4', 'version-1', None),
    ]
    assert rows[-1]['reason'] == 'missing_cogs'


def test_net_margin_ignores_unrelated_cogs_metrics() -> None:
    assert (
        KpiComputationService(RULE_VERSION).compute_net_margin(
            [_metric('cogs', Decimal('50'), metric_id='cogs-only')]
        )
        == []
    )


def test_margin_needs_review_when_units_are_missing() -> None:
    cogs_missing_units = make_metric('cogs', Decimal('100'), metric_id='cogs-no-units', units=None)

    rows = KpiComputationService(RULE_VERSION).compute_gross_margin(
        [_metric('revenue', Decimal('200'), metric_id='rev-1'), cogs_missing_units]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_units'


def test_margin_needs_review_when_currency_is_missing() -> None:
    no_currency = make_metric('cogs', Decimal('100'), metric_id='cogs-no-currency', currency=None)

    rows = KpiComputationService(RULE_VERSION).compute_gross_margin(
        [_metric('revenue', Decimal('200'), metric_id='rev-1'), no_currency]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_currency'
