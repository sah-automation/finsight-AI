"""Pure code computations for the simple aggregation KPI codes (issue #372).

A row is built only from Metrics with provenance: no I/O, no model calls and no
conversion between currencies or units. Metrics are selected by their code or
name; the LLM never supplies a KPI value.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.entities.metric import Metric
    from finsight.domain.ports.kpi_repository import KpiRow

_QUARTER_START_MONTHS = (1, 4, 7, 10)


def _attr(value: Any, *names: str) -> Any:
    """Read the first present field from a mapping or an object."""
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None
    for name in names:
        found = getattr(value, name, None)
        if found is not None:
            return found
    return None


def _code_name(value: Any) -> str:
    text = '' if value is None else str(value).strip().lower()
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def _matches_code(metric: Metric, kpi_code: str) -> bool:
    explicit = _attr(metric, 'kpi_code')
    if explicit is not None:
        return _code_name(explicit) == kpi_code
    for field in ('name', 'metric_name', 'metric', 'label'):
        name = _attr(metric, field)
        if name is not None:
            return _code_name(name) == kpi_code
    return False


def _period_start(period: Any) -> date:
    start = getattr(period, 'start_date', None)
    if isinstance(start, date):
        return start
    label = '' if period is None else str(period).strip()
    try:
        return date.fromisoformat(label)
    except ValueError:
        pass
    match = re.fullmatch(r'(\d{4})-(Q[1-4])', label, re.IGNORECASE)
    if match:
        quarter = int(match.group(2)[1])
        return date(int(match.group(1)), _QUARTER_START_MONTHS[quarter - 1], 1)
    match = re.fullmatch(r'(\d{4})-(\d{2})', label)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    raise ValueError(f'Unsupported KPI period label: {label!r}')


def _period_fields(metric: Metric) -> tuple[str, date]:
    period = _attr(metric, 'period', 'fiscal_period', 'reporting_period')
    start = _period_start(period)
    label = period if isinstance(period, str) else getattr(period, 'label', None)
    text = start.isoformat() if label is None else str(label).strip()
    return text, start


def _required(metric: Metric, field: str, *names: str) -> str:
    value = _attr(metric, *names)
    text = '' if value is None else str(value).strip()
    if not text:
        raise ValueError(f'KPI Metrics require {field}')
    return text


def _amount(metric: Metric) -> Decimal:
    value = _attr(metric, 'value', 'amount', 'figure')
    if isinstance(value, (bool, float)):
        raise TypeError('KPI Metric values must be Decimal, int or str, never float')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'Invalid KPI Metric value: {value!r}') from None
    if not amount.is_finite():
        raise ValueError(f'KPI Metric value must be finite: {value!r}')
    return amount


def _exact_sum(values: list[Decimal]) -> Decimal:
    """Add exact decimals without letting the ambient context round them."""
    if not values:
        return Decimal('0')
    highest = max(value.adjusted() for value in values)
    lowest = min(cast('int', value.as_tuple().exponent) for value in values)
    required_precision = max(highest - lowest + 1, 1)
    with localcontext() as context:
        context.prec = max(context.prec, required_precision)
        return sum(values, Decimal('0'))


class KpiComputationService:
    """Compute computed KPI rows from Metrics without I/O or model calls."""

    def __init__(self, computation_rule_version: str) -> None:
        version = '' if computation_rule_version is None else str(computation_rule_version).strip()
        if not version:
            raise ValueError('computation_rule_version is required')
        self._computation_rule_version = version

    def compute_revenue(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Sum revenue Metrics into one computed KPI row per period."""
        return self._aggregate('revenue', metrics)

    def compute_operating_expenses(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Sum operating-expense Metrics into one computed KPI row per period."""
        return self._aggregate('operating_expenses', metrics)

    def compute_cash_flow(self, metrics: Sequence[Metric]) -> list[KpiRow]:
        """Sum cash-flow Metrics into one computed KPI row per period."""
        return self._aggregate('cash_flow', metrics)

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
                    'citations': [],
                },
            )
            self._check_group(group, start, currency, units)
            group['amounts'].append(_amount(metric))
            citation = _required(metric, 'metric_id', 'metric_id', 'id')
            if citation not in group['citations']:
                group['citations'].append(citation)
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
            'source_citations': list(group['citations']),
            'computation_status': 'computed',
            'estimation_method': None,
            'document_version_id': version,
            'computation_rule_version': self._computation_rule_version,
            'superseded_by_document_version_id': None,
        }


__all__ = ['KpiComputationService']
