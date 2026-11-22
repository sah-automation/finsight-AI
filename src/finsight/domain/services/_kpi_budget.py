"""Strict budget-versus-actual KPI computation (issue #375).

A budget Metric is compared with an actual Metric only when their declared
period, currency and units match exactly. Mismatches and missing inputs produce
a ``needs_review`` row with a null value; no conversion or borrowing is used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.value_objects.computation_status import ComputationStatus

from ._kpi_metric_fields import amount, attr, code_name, exact_sum, period_fields, required

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.entities.metric import Metric
    from finsight.domain.ports.kpi_repository import KpiRow
    from finsight.domain.services.citation_factory import CitationFactory

_GroupKey = tuple[str, str, str]
_Group = dict[str, Any]
_Subject = tuple[str, str]


def compute_budget_vs_actual(
    *,
    metrics: Sequence[Metric],
    rule_version: str,
    citations: CitationFactory,
) -> list[KpiRow]:
    """Build one variance row per company, line item and document version."""
    groups: dict[_GroupKey, _Group] = {}
    for metric in metrics or ():
        subject = _subject(metric)
        if subject is None:
            continue
        role, name = subject
        company = required(metric, 'company_id', 'company_id', 'company', 'tenant_id')
        version = required(
            metric, 'document_version_id', 'document_version_id', 'document_version', 'version_id'
        )
        group = groups.setdefault((company, name, version), _new_group())
        group[role].append(metric)

    rows: list[KpiRow] = []
    for key in sorted(groups):
        group = groups[key]
        rows.append(_row(key, group, rule_version, citations))
    return rows


def _new_group() -> _Group:
    return {'budget': [], 'actual': []}


def _subject(metric: Metric) -> _Subject | None:
    """Return the comparison role and line-item name from a Metric."""
    for field in ('name', 'metric_name', 'metric', 'label', 'kpi_code'):
        value = attr(metric, field)
        if value is None:
            continue
        code = code_name(value)
        if code == 'budget_vs_actual':
            continue
        for role in ('budget', 'actual'):
            if code == role:
                return role, 'total'
            if code.startswith(f'{role}_'):
                return role, code[len(role) + 1 :]
            if code.endswith(f'_{role}'):
                return role, code[: -len(role) - 1]
    return None


def _row(key: _GroupKey, group: _Group, rule_version: str, citations: CitationFactory) -> KpiRow:
    company, _subject_name, version = key
    budgets, actuals = group['budget'], group['actual']
    label, start = period_fields(budgets[0] if budgets else actuals[0])
    source_metrics = [*budgets, *actuals]
    citation_ids: set[str] = set()
    missing_citation = False
    for metric in source_metrics:
        citation = citations.build_from_metric(metric)
        if citation:
            citation_ids.add(citation)
        else:
            missing_citation = True
    reason = _reason(budgets, actuals, missing_citation)
    value = None
    if reason is None:
        budget_total = exact_sum([amount(metric) for metric in budgets])
        actual_total = exact_sum([amount(metric) for metric in actuals])
        value = str(actual_total - budget_total)
    source = budgets[0] if budgets else actuals[0]
    return {
        'company_id': company,
        'kpi_code': 'budget_vs_actual',
        'period': label,
        'period_start': start.isoformat(),
        'chart_period': label,
        'chart_period_start': start.isoformat(),
        'currency': _field(source, 'currency'),
        'units': _field(source, 'units', 'unit'),
        'value': value,
        'source_citations': sorted(citation_ids),
        'source_metric_ids': [
            str(required(metric, 'metric_id', 'metric_id', 'id')) for metric in source_metrics
        ],
        'computation_status': (
            ComputationStatus.NEEDS_REVIEW.value if reason else ComputationStatus.COMPUTED.value
        ),
        'estimation_method': None,
        'document_version_id': version,
        'computation_rule_version': rule_version,
        'superseded_by_document_version_id': None,
        'reason': reason,
    }


def _reason(
    budgets: Sequence[Metric], actuals: Sequence[Metric], missing_citation: bool
) -> str | None:
    if not budgets:
        return 'missing_budget'
    if not actuals:
        return 'missing_actual'
    if missing_citation:
        return 'missing_citations'
    metrics = [*budgets, *actuals]
    for field, names, reason in (
        ('period', ('period', 'fiscal_period', 'reporting_period'), 'period_mismatch'),
        ('currency', ('currency',), 'currency_mismatch'),
        ('units', ('units', 'unit'), 'units_mismatch'),
    ):
        values = {_field(metric, *names) for metric in metrics}
        if '' in values:
            return f'missing_{field}'
        if len(values) > 1:
            return reason
    return None


def _field(metric: Metric, *names: str) -> str:
    value = attr(metric, *names)
    return '' if value is None else str(value).strip()


__all__ = ['compute_budget_vs_actual']
