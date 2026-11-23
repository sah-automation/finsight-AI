"""Unit tests for the pure core KPI aggregation service (issues #372, #397)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from finsight.domain.entities.metric import Metric
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, citation_id, make_metric

_metric = make_metric
_citation_id = citation_id


def test_compute_revenue_emits_one_computed_row_with_exact_decimal_string() -> None:
    metric = Metric(
        metric_id='metric-revenue-1',
        company_id=COMPANY,
        name='revenue',
        value=Decimal('1234.50'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='version-1',
        source_location={'page': 1},
    )

    rows = KpiComputationService(RULE_VERSION).compute_revenue([metric])

    assert rows == [
        {
            'company_id': str(COMPANY),
            'kpi_code': 'revenue',
            'period': '2026-Q3',
            'period_start': '2026-07-01',
            'chart_period': '2026-Q3',
            'chart_period_start': '2026-07-01',
            'currency': 'USD',
            'units': 'USD',
            'value': '1234.50',
            'source_citations': [_citation_id()],
            'source_metric_ids': ['metric-revenue-1'],
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': 'version-1',
            'computation_rule_version': RULE_VERSION,
            'superseded_by_document_version_id': None,
        }
    ]


def test_compute_revenue_sums_metrics_per_period_and_ignores_other_codes() -> None:
    metrics = [
        _metric('revenue', Decimal('100.10'), metric_id='metric-1'),
        _metric('Revenue', Decimal('200.20'), metric_id='metric-2'),
        _metric('gross_margin', Decimal('40'), metric_id='metric-3'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_revenue(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] == '300.30'
    # Same page/version -> deduplicated to single citation
    assert rows[0]['source_citations'] == [_citation_id()]
    assert rows[0]['source_metric_ids'] == ['metric-1', 'metric-2']
    assert rows[0]['kpi_code'] == 'revenue'


def test_compute_revenue_keeps_periods_and_document_versions_separate() -> None:
    metrics = [
        _metric('revenue', Decimal('20'), metric_id='metric-q4', period='2026-Q4'),
        _metric('revenue', Decimal('10'), metric_id='metric-q3'),
        _metric('revenue', Decimal('5'), metric_id='metric-q3-v2', version='version-2'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_revenue(metrics)

    assert [(row['period'], row['document_version_id'], row['value']) for row in rows] == [
        ('2026-Q3', 'version-1', '10'),
        ('2026-Q3', 'version-2', '5'),
        ('2026-Q4', 'version-1', '20'),
    ]
    assert [row['period_start'] for row in rows] == [
        '2026-07-01',
        '2026-07-01',
        '2026-10-01',
    ]


def test_compute_revenue_rejects_mixed_currency_for_one_period() -> None:
    metrics = [
        _metric('revenue', Decimal('10'), metric_id='metric-usd'),
        _metric('revenue', Decimal('10'), metric_id='metric-eur', currency='EUR'),
    ]

    with pytest.raises(ValueError, match='currency'):
        KpiComputationService(RULE_VERSION).compute_revenue(metrics)


def test_compute_revenue_rejects_mixed_units_for_one_period() -> None:
    metrics = [
        _metric('revenue', Decimal('10'), metric_id='metric-units'),
        _metric('revenue', Decimal('10'), metric_id='metric-millions', units='millions'),
    ]

    with pytest.raises(ValueError, match='units'):
        KpiComputationService(RULE_VERSION).compute_revenue(metrics)


def test_compute_revenue_never_accepts_a_float_value() -> None:
    with pytest.raises(TypeError, match='never float'):
        KpiComputationService(RULE_VERSION).compute_revenue(
            [_metric('revenue', 10.5, metric_id='metric-float')]
        )


def test_compute_revenue_rejects_a_period_it_cannot_derive_a_start_date_from() -> None:
    with pytest.raises(ValueError, match='period label'):
        KpiComputationService(RULE_VERSION).compute_revenue(
            [_metric('revenue', Decimal('10'), metric_id='metric-period', period='last summer')]
        )


def test_compute_revenue_returns_no_rows_without_matching_metrics() -> None:
    service = KpiComputationService(RULE_VERSION)

    assert service.compute_revenue([]) == []
    assert (
        service.compute_revenue([_metric('cash_flow', Decimal('10'), metric_id='metric-cf')]) == []
    )


def test_computation_rule_version_must_not_be_blank() -> None:
    with pytest.raises(ValueError, match='computation_rule_version'):
        KpiComputationService('   ')


def test_compute_operating_expenses_emits_computed_rows_for_each_period() -> None:
    metrics = [
        _metric('operating expenses', Decimal('80.00'), metric_id='opex-1'),
        _metric('operating_expenses', Decimal('20.00'), metric_id='opex-2', period='2026-Q4'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_operating_expenses(metrics)

    assert [(row['kpi_code'], row['period'], row['value']) for row in rows] == [
        ('operating_expenses', '2026-Q3', '80.00'),
        ('operating_expenses', '2026-Q4', '20.00'),
    ]
    assert all(row['computation_status'] == 'computed' for row in rows)
    assert all(row['estimation_method'] is None for row in rows)


def test_compute_operating_expenses_sums_metrics_without_decimal_rounding() -> None:
    metrics = [
        _metric(
            'operating_expenses',
            Decimal('12345678901234567890.123456789'),
            metric_id='opex-large',
        ),
        _metric('operating_expenses', Decimal('0.000000001'), metric_id='opex-small'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_operating_expenses(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] == '12345678901234567890.123456790'
    # Same page/version -> deduplicated to single citation
    assert rows[0]['source_citations'] == [_citation_id()]
    assert rows[0]['source_metric_ids'] == ['opex-large', 'opex-small']


def test_compute_cash_flow_sums_metrics_and_keeps_provenance_fields() -> None:
    metrics = [
        _metric('cash flow', Decimal('-100.50'), metric_id='cash-1'),
        _metric('cash_flow', Decimal('250.25'), metric_id='cash-2'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_cash_flow(metrics)

    assert len(rows) == 1
    assert rows[0]['value'] == '149.75'
    assert rows[0]['kpi_code'] == 'cash_flow'
    # Same page/version -> deduplicated to single citation
    assert rows[0]['source_citations'] == [_citation_id()]
    assert rows[0]['source_metric_ids'] == ['cash-1', 'cash-2']
    assert rows[0]['computation_status'] == 'computed'
    assert rows[0]['estimation_method'] is None
    assert rows[0]['computation_rule_version'] == RULE_VERSION
    assert rows[0]['superseded_by_document_version_id'] is None


def test_compute_cash_flow_preserves_exact_decimal_scale() -> None:
    metrics = [
        _metric(
            'cash_flow',
            Decimal('12345678901234567890.123456789'),
            metric_id='cash-large',
        ),
        _metric('cash_flow', Decimal('0.000000001'), metric_id='cash-small'),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_cash_flow(metrics)

    assert rows[0]['value'] == '12345678901234567890.123456790'


def test_compute_operating_expenses_from_one_metric_emits_full_row() -> None:
    rows = KpiComputationService(RULE_VERSION).compute_operating_expenses(
        [_metric('operating_expenses', Decimal('75.25'), metric_id='opex-single')]
    )

    assert len(rows) == 1
    assert rows[0]['kpi_code'] == 'operating_expenses'
    assert rows[0]['period'] == '2026-Q3'
    assert rows[0]['chart_period'] == '2026-Q3'
    assert rows[0]['period_start'] == '2026-07-01'
    assert rows[0]['chart_period_start'] == '2026-07-01'
    assert rows[0]['currency'] == 'USD'
    assert rows[0]['units'] == 'USD'
    assert rows[0]['value'] == '75.25'
    assert rows[0]['source_citations'] == [_citation_id()]
    assert rows[0]['source_metric_ids'] == ['opex-single']
    assert rows[0]['computation_status'] == 'computed'
    assert rows[0]['estimation_method'] is None
    assert rows[0]['document_version_id'] == 'version-1'
    assert rows[0]['computation_rule_version'] == RULE_VERSION
    assert rows[0]['superseded_by_document_version_id'] is None


def test_compute_cash_flow_from_one_metric_emits_full_row() -> None:
    rows = KpiComputationService(RULE_VERSION).compute_cash_flow(
        [_metric('cash_flow', Decimal('-42.50'), metric_id='cash-single')]
    )

    assert len(rows) == 1
    assert rows[0]['kpi_code'] == 'cash_flow'
    assert rows[0]['period'] == '2026-Q3'
    assert rows[0]['chart_period'] == '2026-Q3'
    assert rows[0]['period_start'] == '2026-07-01'
    assert rows[0]['chart_period_start'] == '2026-07-01'
    assert rows[0]['currency'] == 'USD'
    assert rows[0]['units'] == 'USD'
    assert rows[0]['value'] == '-42.50'
    assert rows[0]['source_citations'] == [_citation_id()]
    assert rows[0]['source_metric_ids'] == ['cash-single']
    assert rows[0]['computation_status'] == 'computed'
    assert rows[0]['estimation_method'] is None
    assert rows[0]['document_version_id'] == 'version-1'
    assert rows[0]['computation_rule_version'] == RULE_VERSION
    assert rows[0]['superseded_by_document_version_id'] is None


@pytest.mark.parametrize(
    ('method_name', 'code'),
    [
        ('compute_operating_expenses', 'operating_expenses'),
        ('compute_cash_flow', 'cash_flow'),
    ],
)
def test_remaining_core_codes_reject_mixed_currency(method_name: str, code: str) -> None:
    service = KpiComputationService(RULE_VERSION)
    compute = getattr(service, method_name)
    metrics = [
        _metric(code, Decimal('10'), metric_id=f'{code}-usd'),
        _metric(code, Decimal('10'), metric_id=f'{code}-eur', currency='EUR'),
    ]

    with pytest.raises(ValueError, match='currency'):
        compute(metrics)


@pytest.mark.parametrize(
    ('method_name', 'code'),
    [
        ('compute_operating_expenses', 'operating_expenses'),
        ('compute_cash_flow', 'cash_flow'),
    ],
)
def test_remaining_core_codes_reject_mixed_units(method_name: str, code: str) -> None:
    service = KpiComputationService(RULE_VERSION)
    compute = getattr(service, method_name)
    metrics = [
        _metric(code, Decimal('10'), metric_id=f'{code}-units'),
        _metric(code, Decimal('10'), metric_id=f'{code}-millions', units='millions'),
    ]

    with pytest.raises(ValueError, match='units'):
        compute(metrics)


# --- CitationFactory tests (issue #397) ---

from finsight.domain.services.citation_factory import CitationFactory


def test_citation_factory_builds_basic_citation_id() -> None:
    metric = _metric('revenue', Decimal('100'), metric_id='m1', version='ver-1', page=5)
    factory = CitationFactory()

    cit = factory.build_from_metric(metric)

    assert cit == 'cit:v1:ver-1:p5'


def test_citation_factory_includes_table_id_when_present() -> None:
    metric = _metric(
        'revenue', Decimal('100'), metric_id='m1', version='ver-1', page=3, table_id='tbl-42'
    )
    factory = CitationFactory()

    cit = factory.build_from_metric(metric)

    assert cit == 'cit:v1:ver-1:p3:ttbl-42'


def test_citation_factory_includes_chunk_id_when_present() -> None:
    metric = _metric(
        'revenue', Decimal('100'), metric_id='m1', version='ver-1', page=2, chunk_id='chk-7'
    )
    factory = CitationFactory()

    cit = factory.build_from_metric(metric)

    assert cit == 'cit:v1:ver-1:p2:cchk-7'


def test_citation_factory_includes_char_range_when_present() -> None:
    metric = _metric(
        'revenue',
        Decimal('100'),
        metric_id='m1',
        version='ver-1',
        page=1,
        start_char=100,
        end_char=200,
    )
    factory = CitationFactory()

    cit = factory.build_from_metric(metric)

    assert cit == 'cit:v1:ver-1:p1:o100-200'


def test_citation_factory_returns_none_when_no_document_version() -> None:
    metric = _metric('revenue', Decimal('100'), metric_id='m1', version='', page=1)
    factory = CitationFactory()

    cit = factory.build_from_metric(metric)

    assert cit is None


def test_citation_factory_returns_none_when_no_page() -> None:
    # Metric with no page in source_location
    metric = Metric(
        metric_id='m1',
        company_id=COMPANY,
        name='revenue',
        value=Decimal('100'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='ver-1',
        source_location={},  # No page
    )
    factory = CitationFactory()

    cit = factory.build_from_metric(metric)

    assert cit is None


def test_citation_factory_deduplicates_and_sorts() -> None:
    metrics = [
        _metric('revenue', Decimal('100'), metric_id='m1', version='ver-1', page=2),
        _metric('revenue', Decimal('200'), metric_id='m2', version='ver-1', page=1),
        _metric(
            'revenue', Decimal('300'), metric_id='m3', version='ver-1', page=1
        ),  # Same page as m2
    ]
    factory = CitationFactory()

    citations = factory.build_from_metrics(metrics)

    assert citations == ['cit:v1:ver-1:p1', 'cit:v1:ver-1:p2']


def test_kpi_computation_marks_needs_review_when_no_citations() -> None:
    # Metric without page in source_location
    metric = Metric(
        metric_id='m1',
        company_id=COMPANY,
        name='revenue',
        value=Decimal('100'),
        unit='USD',
        currency='USD',
        period='2026-Q3',
        document_id='doc-1',
        document_version_id='ver-1',
        source_location={},  # No page
    )

    rows = KpiComputationService(RULE_VERSION).compute_revenue([metric])

    assert len(rows) == 1
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['source_citations'] == []
    assert rows[0]['source_metric_ids'] == ['m1']


def test_kpi_computation_marks_needs_review_when_any_metric_lacks_citation() -> None:
    # One metric with page, one without - spec says "if either is missing... needs review"
    metrics = [
        _metric('revenue', Decimal('100'), metric_id='m1', page=1),  # Has citation
        Metric(
            metric_id='m2',
            company_id=COMPANY,
            name='revenue',
            value=Decimal('200'),
            unit='USD',
            currency='USD',
            period='2026-Q3',
            document_id='doc-1',
            document_version_id='version-1',
            source_location={},  # No page
        ),
    ]

    rows = KpiComputationService(RULE_VERSION).compute_revenue(metrics)

    assert len(rows) == 1
    # Per spec: "If either is missing, no citation is created and the KPI is marked 'needs review'"
    assert rows[0]['computation_status'] == 'needs_review'
    assert rows[0]['source_citations'] == [_citation_id()]  # Only one valid citation
    assert rows[0]['source_metric_ids'] == ['m1', 'm2']
