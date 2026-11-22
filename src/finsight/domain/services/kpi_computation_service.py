"""Pure code computations for the simple aggregation KPI codes (issue #372).

A row is built only from Metrics with provenance: no I/O, no model calls and no
conversion between currencies or units. Metrics are selected by their code or
name; the LLM never supplies a KPI value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._kpi_derived import compute_burn_rate as _compute_burn_rate
from ._kpi_derived import compute_runway as _compute_runway
from ._kpi_margin import compute_margin as _compute_margin
from ._kpi_metric_fields import amount as _amount
from ._kpi_metric_fields import exact_sum as _exact_sum
from ._kpi_metric_fields import matches_code as _matches_code
from ._kpi_metric_fields import period_fields as _period_fields
from ._kpi_metric_fields import required as _required
from ._kpi_period import compute_collection_period as _compute_collection_period
from .citation_factory import CitationFactory

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from finsight.domain.entities.metric import Metric
    from finsight.domain.ports.kpi_repository import KpiRow


class KpiComputationService:
    """Compute computed KPI rows from Metrics without I/O or model calls."""

    def __init__(self, computation_rule_version: str) -> None:
        version = '' if computation_rule_version is None else str(computation_rule_version).strip()
        if not version:
            raise ValueError('computation_rule_version is required')
        self._computation_rule_version = version
        self._citation_factory = CitationFactory()

    def compute_revenue(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Sum revenue Metrics into one computed KPI row per period."""
        return self._aggregate('revenue', metrics)

    def compute_operating_expenses(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Sum operating-expense Metrics into one computed KPI row per period."""
        return self._aggregate('operating_expenses', metrics)

    def compute_cash_flow(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Sum cash-flow Metrics into one computed KPI row per period."""
        return self._aggregate('cash_flow', metrics)

    def compute_burn_rate(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Compute burn rate from operating-expense and cash-flow Metrics."""
        return _compute_burn_rate(
            metrics=metrics,
            rule_version=self._computation_rule_version,
            citations=self._citation_factory,
        )

    def compute_runway(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Compute runway in months from cash, operating-expense and cash-flow Metrics."""
        return _compute_runway(
            metrics=metrics,
            rule_version=self._computation_rule_version,
            citations=self._citation_factory,
        )

    def compute_gross_margin(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Compute gross margin percentages from revenue and COGS Metrics."""
        return self._margin('gross_margin', 'cogs', metrics, subtract_input=True)

    def compute_net_margin(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Compute net margin percentages from revenue and net-income Metrics."""
        return self._margin('net_margin', 'net_income', metrics, subtract_input=False)

    def compute_dso(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Compute days sales outstanding from receivables and revenue Metrics."""
        return _compute_collection_period(
            kpi_code='dso',
            numerator_code='accounts_receivable',
            denominator_code='revenue',
            metrics=metrics,
            rule_version=self._computation_rule_version,
            citations=self._citation_factory,
        )

    def compute_dpo(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Compute days payable outstanding from payables and COGS Metrics."""
        return _compute_collection_period(
            kpi_code='dpo',
            numerator_code='accounts_payable',
            denominator_code='cogs',
            metrics=metrics,
            rule_version=self._computation_rule_version,
            citations=self._citation_factory,
        )

    def _margin(
        self,
        kpi_code: str,
        input_code: str,
        metrics: Sequence[Metric],
        *,
        subtract_input: bool,
    ) -> list[KpiRow]:
        return _compute_margin(
            kpi_code=kpi_code,
            input_code=input_code,
            metrics=metrics,
            subtract_input=subtract_input,
            rule_version=self._computation_rule_version,
            citations=self._citation_factory,
        )

    def _aggregate(self, kpi_code: str, metrics: Sequence[Metric]) -> list[KpiRow]:
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for metric in metrics or ():
            if metric is None or not _matches_code(metric, kpi_code):
                continue
            label, start = _period_fields(metric)
            company = _required(metric, 'company_id', 'company_id', 'company', 'tenant_id')
            version = _required(
                metric,
                'document_version_id',
                'document_version_id',
                'document_version',
                'version_id',
            )
            currency = _required(metric, 'currency', 'currency')
            units = _required(metric, 'units', 'unit', 'units')
            key = (company, label, version)
            group = groups.setdefault(
                key,
                {
                    'start': start,
                    'currency': currency,
                    'units': units,
                    'amounts': [],
                    'source_metric_ids': [],
                    'metrics_for_citations': [],
                },
            )
            self._check_group(group, start, currency, units)
            group['amounts'].append(_amount(metric))
            metric_id = _required(metric, 'metric_id', 'metric_id', 'id')
            if metric_id not in group['source_metric_ids']:
                group['source_metric_ids'].append(metric_id)
            # Track the metric for citation building
            group['metrics_for_citations'].append(metric)
        return [
            self._row(kpi_code, company, label, version, group)
            for (company, label, version), group in sorted(
                groups.items(), key=lambda item: (item[1]['start'], item[0])
            )
        ]

    @staticmethod
    def _check_group(group: dict[str, Any], start: date, currency: str, units: str) -> None:
        if group['start'] != start:
            raise ValueError('Metrics for one KPI period disagree on period_start')
        if group['currency'] != currency:
            raise ValueError('Metrics for one KPI period disagree on currency')
        if group['units'] != units:
            raise ValueError('Metrics for one KPI period disagree on units')

    def _row(
        self,
        kpi_code: str,
        company: str,
        label: str,
        version: str,
        group: dict[str, Any],
    ) -> KpiRow:
        start = group['start'].isoformat()

        # Build CitationIds from each metric's provenance individually
        # Track which metrics failed to produce a citation
        metrics_for_citations = group['metrics_for_citations']
        citations: list[str] = []
        any_missing_citation = False
        for metric in metrics_for_citations:
            cit = self._citation_factory.build_from_metric(metric)
            if cit:
                citations.append(cit)
            else:
                any_missing_citation = True

        # Deduplicate and sort citations
        citations = sorted(set(citations))

        # Determine computation_status: "needs_review" if ANY metric lacked citations
        computation_status = 'needs_review' if any_missing_citation else 'computed'

        return {
            'company_id': company,
            'kpi_code': kpi_code,
            'period': label,
            'period_start': start,
            'chart_period': label,
            'chart_period_start': start,
            'currency': group['currency'],
            'units': group['units'],
            'value': str(_exact_sum(group['amounts'])),
            'source_citations': citations,
            'source_metric_ids': list(group['source_metric_ids']),
            'computation_status': computation_status,
            'estimation_method': None,
            'document_version_id': version,
            'computation_rule_version': self._computation_rule_version,
            'superseded_by_document_version_id': None,
        }


__all__ = ['KpiComputationService']
