"""Unit tests for derived burn_rate and runway KPI computations (issue #374)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from finsight.domain.entities.metric import Metric
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, citation_id, make_metric

_metric = make_metric
_citation_id = citation_id


def test_burn_rate_emits_computed_row_with_exact_decimal_string() -> None:
    metrics = [
        _metric('operating_expenses', Decimal('300.00'), metric_id='opex-1'),
        _metric('cash_flow', Decimal('100.00'), metric_id='cf-1'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(metrics)

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': 'burn_rate',
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': '200.00',
            'source_citations': [_citation_id()],
            'source_metric_ids': ['opex-1', 'cf-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
            'reason': None,
        }
    ]


def test_burn_rate_sums_each_input_code_before_subtracting() -> None:
    metrics = [
        _metric('operating expenses', Decimal('300.10'), metric_id='opex-1'),
        _metric('operating_expenses', Decimal('0.20'), metric_id='opex-2', page=2),
        _metric('cash flow', Decimal('100.10'), metric_id='cf-1'),
        _metric('cash_flow', Decimal('0.05'), metric_id='cf-2', page=2),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] == '200.15'
    assert rows[0]['source_metric_ids'] == ['opex-1', 'opex-2', 'cf-1', 'cf-2']
    assert rows[0]['source_citations'] == [_citation_id(page=1), _citation_id(page=2)]


@pytest.mark.parametrize(
    ('metrics', 'expected_reason'),
    [
        ([_metric('cash_flow', Decimal('100'), metric_id='cf-only')], 'missing_operating_expenses'),
        (
            [_metric('operating_expenses', Decimal('200'), metric_id='opex-only')],
            'missing_cash_flow',
        ),
    ],
)
def test_burn_rate_needs_review_when_an_input_is_missing(
    metrics: list[Metric], expected_reason: str
) -> None:
    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason
    assert rows[0]['source_citations'] == [_citation_id()]


@pytest.mark.parametrize(
    ('field', 'mismatched_value', 'expected_reason'),
    [
        ('currency', 'EUR', 'currency_mismatch'),
        ('units', 'millions', 'units_mismatch'),
    ],
)
def test_burn_rate_needs_review_when_inputs_disagree(
    field: str, mismatched_value: str, expected_reason: str
) -> None:
    metrics = [
        _metric('operating_expenses', Decimal('200'), metric_id='opex-1'),
        _metric('cash_flow', Decimal('100'), metric_id='cf-1', **{field: mismatched_value}),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


@pytest.mark.parametrize(
    ('field', 'expected_reason'),
    [('currency', 'missing_currency'), ('units', 'missing_units')],
)
def test_burn_rate_needs_review_when_a_dimension_is_missing(
    field: str, expected_reason: str
) -> None:
    metrics = [
        _metric('operating_expenses', Decimal('200'), metric_id='opex-1'),
        make_metric('cash_flow', Decimal('100'), metric_id='cf-1', **{field: None}),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


def test_burn_rate_needs_review_when_an_input_lacks_a_citation() -> None:
    uncited_flow = Metric(
        metric_id='cf-uncited',
        company_id=COMPANY,
        name='cash_flow',
        value=Decimal('100'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='version-1',
        source_location={},
    )

    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(
        [_metric('operating_expenses', Decimal('200'), metric_id='opex-1'), uncited_flow]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_citations'
    assert rows[0]['source_citations'] == [_citation_id()]


def test_burn_rate_keeps_periods_and_document_versions_separate() -> None:
    metrics = [
        _metric('operating_expenses', Decimal('300'), metric_id='opex-q3-v1'),
        _metric('cash_flow', Decimal('100'), metric_id='cf-q3-v1'),
        _metric('operating_expenses', Decimal('600'), metric_id='opex-q3-v2', version='version-2'),
        _metric('cash_flow', Decimal('200'), metric_id='cf-q3-v2', version='version-2'),
        _metric('operating_expenses', Decimal('400'), metric_id='opex-q4', period='2026-Q4'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_burn_rate(metrics)

    assert [(row['period'], row['document_version_id'], row['value']) for row in rows] == [
        ('2026-Q3', 'version-1', '200'),
        ('2026-Q3', 'version-2', '400'),
        ('2026-Q4', 'version-1', None),
    ]
    assert rows[-1]['reason'] == 'missing_cash_flow'


def test_burn_rate_ignores_unrelated_metrics() -> None:
    assert (
        KpiComputationService(RULE_VERSION).compute_burn_rate(
            [_metric('revenue', Decimal('100'), metric_id='rev-only')]
        )
        == []
    )


def test_runway_emits_computed_row_from_cash_over_burn_rate() -> None:
    metrics = [
        _metric('cash', Decimal('1200.00'), metric_id='cash-1'),
        _metric('operating_expenses', Decimal('300.00'), metric_id='opex-1'),
        _metric('cash_flow', Decimal('100.00'), metric_id='cf-1'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_runway(metrics)

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': 'runway',
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': '6.00',
            'source_citations': [_citation_id()],
            'source_metric_ids': ['cash-1', 'opex-1', 'cf-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
            'reason': None,
        }
    ]


@pytest.mark.parametrize(
    ('metrics', 'expected_reason'),
    [
        (
            [
                _metric('operating_expenses', Decimal('300'), metric_id='opex-1'),
                _metric('cash_flow', Decimal('100'), metric_id='cf-1'),
            ],
            'missing_cash',
        ),
        (
            [
                _metric('cash', Decimal('1200'), metric_id='cash-1'),
                _metric('cash_flow', Decimal('100'), metric_id='cf-1'),
            ],
            'missing_operating_expenses',
        ),
        (
            [
                _metric('cash', Decimal('1200'), metric_id='cash-1'),
                _metric('operating_expenses', Decimal('300'), metric_id='opex-1'),
            ],
            'missing_cash_flow',
        ),
    ],
)
def test_runway_needs_review_when_an_input_is_missing(
    metrics: list[Metric], expected_reason: str
) -> None:
    rows = KpiComputationService(RULE_VERSION).compute_runway(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason
    assert rows[0]['source_citations'] == [_citation_id()]


def test_runway_needs_review_when_burn_rate_is_zero() -> None:
    rows = KpiComputationService(RULE_VERSION).compute_runway(
        [
            _metric('cash', Decimal('1200'), metric_id='cash-1'),
            _metric('operating_expenses', Decimal('200'), metric_id='opex-1'),
            _metric('cash_flow', Decimal('200'), metric_id='cf-1'),
        ]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'zero_burn_rate'
    assert rows[0]['source_citations'] == [_citation_id()]


@pytest.mark.parametrize(
    ('field', 'mismatched_value', 'expected_reason'),
    [
        ('currency', 'EUR', 'currency_mismatch'),
        ('units', 'millions', 'units_mismatch'),
    ],
)
def test_runway_needs_review_when_inputs_disagree(
    field: str, mismatched_value: str, expected_reason: str
) -> None:
    rows = KpiComputationService(RULE_VERSION).compute_runway(
        [
            _metric('cash', Decimal('1200'), metric_id='cash-1'),
            _metric('operating_expenses', Decimal('300'), metric_id='opex-1'),
            _metric('cash_flow', Decimal('100'), metric_id='cf-1', **{field: mismatched_value}),
        ]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == expected_reason


def test_runway_needs_review_when_an_input_lacks_a_citation() -> None:
    uncited_cash = Metric(
        metric_id='cash-uncited',
        company_id=COMPANY,
        name='cash',
        value=Decimal('1200'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='version-1',
        source_location={},
    )

    rows = KpiComputationService(RULE_VERSION).compute_runway(
        [
            uncited_cash,
            _metric('operating_expenses', Decimal('300'), metric_id='opex-1'),
            _metric('cash_flow', Decimal('100'), metric_id='cf-1'),
        ]
    )

    assert len(rows) == 1
    assert rows[0]['value'] is None
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['reason'] == 'missing_citations'
    assert rows[0]['source_citations'] == [_citation_id()]


def test_runway_keeps_periods_and_document_versions_separate() -> None:
    metrics = [
        _metric('cash', Decimal('1200'), metric_id='cash-q3-v1'),
        _metric('operating_expenses', Decimal('300'), metric_id='opex-q3-v1'),
        _metric('cash_flow', Decimal('100'), metric_id='cf-q3-v1'),
        _metric('cash', Decimal('2400'), metric_id='cash-q3-v2', version='version-2'),
        _metric('operating_expenses', Decimal('600'), metric_id='opex-q3-v2', version='version-2'),
        _metric('cash_flow', Decimal('200'), metric_id='cf-q3-v2', version='version-2'),
        _metric('cash', Decimal('900'), metric_id='cash-q4', period='2026-Q4'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_runway(metrics)

    assert [(row['period'], row['document_version_id'], row['value']) for row in rows] == [
        ('2026-Q3', 'version-1', '6.00'),
        ('2026-Q3', 'version-2', '6.00'),
        ('2026-Q4', 'version-1', None),
    ]
    assert rows[-1]['reason'] == 'missing_operating_expenses'


def test_runway_divides_with_two_decimal_places() -> None:
    rows = KpiComputationService(RULE_VERSION).compute_runway(
        [
            _metric('cash', Decimal('100'), metric_id='cash-1'),
            _metric('operating_expenses', Decimal('3'), metric_id='opex-1'),
            _metric('cash_flow', Decimal('0'), metric_id='cf-1'),
        ]
    )

    assert len(rows) == 1
    assert rows[0]['computation_status'] == 'computed'
    assert rows[0]['reason'] is None
    assert rows[0]['value'] == '33.33'


def test_runway_ignores_unrelated_metrics() -> None:
    assert (
        KpiComputationService(RULE_VERSION).compute_runway(
            [_metric('revenue', Decimal('100'), metric_id='rev-only')]
        )
        == []
    )
