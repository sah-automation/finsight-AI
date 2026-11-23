"""Build ready-to-draw chart series from KPI rows (issue #380).

The API owns all derived figures: values, changes, directions, shares and
variance rows are computed with :class:`~decimal.Decimal` and returned as
decimal strings. The browser never recomputes them.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from finsight.domain.ports.kpi_repository import KpiRow

_CENT = Decimal('0.01')
_HUNDRED = Decimal('100')
_NEEDS_REVIEW = 'needs_review'
_INSUFFICIENT_DATA = 'insufficient_data'


class _DatasetContext(NamedTuple):
    """Per-request values shared by every dataset of a chart."""

    rows: Sequence[KpiRow]
    polarity: str
    breakdown_key: str | None


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _money(value: Any) -> str | None:
    number = _number(value)
    if number is None:
        return None
    return str(number.quantize(_CENT, rounding=ROUND_HALF_UP))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_period(row: Mapping[str, Any]) -> str:
    return _text(row.get('chart_period')) or _text(row.get('period')) or ''


def _direction(change: Decimal | None, polarity: str) -> str | None:
    if change is None or change == 0 or polarity == 'neutral':
        return None
    if polarity == 'lower_is_better':
        return 'good' if change < 0 else 'bad'
    return 'good' if change > 0 else 'bad'


class ChartSeriesBuilder:
    """Derive labels, datasets, variance rows and point-level figures."""

    def build(
        self,
        rows: Sequence[KpiRow],
        *,
        kpi_codes: Sequence[str],
        polarity: str,
        diverging: bool,
        breakdown_key: str | None = None,
    ) -> dict[str, Any]:
        """Return the data part of the chart response for the selected rows."""
        if not rows:
            return {
                'labels': [],
                'datasets': [],
                'variance_rows': [],
                'reason': _INSUFFICIENT_DATA,
            }

        periods = sorted({_row_period(row) for row in rows} - {''})
        context = _DatasetContext(rows=rows, polarity=polarity, breakdown_key=breakdown_key)
        return {
            'labels': periods,
            'datasets': self._datasets(kpi_codes, rows, periods, context),
            'variance_rows': self._variance_rows(rows, polarity) if diverging else [],
            'reason': None,
        }

    def _datasets(
        self,
        kpi_codes: Sequence[str],
        rows: Sequence[KpiRow],
        periods: Sequence[str],
        context: _DatasetContext,
    ) -> list[dict[str, Any]]:
        groups = self._groups(rows, context.breakdown_key)
        datasets: list[dict[str, Any]] = []
        for kpi_code in kpi_codes:
            if not any(_text(row.get('kpi_code')) == kpi_code for row in rows):
                continue
            for group in groups:
                dataset = self._dataset(kpi_code, group, periods, context)
                if dataset is not None:
                    datasets.append(dataset)
        return datasets

    def _groups(self, rows: Sequence[KpiRow], breakdown_key: str | None) -> Sequence[str | None]:
        if breakdown_key is None:
            return [None]
        values = {_text(row.get(breakdown_key)) or 'Unknown' for row in rows}
        return sorted(values)

    def _dataset(
        self,
        kpi_code: str,
        group: str | None,
        periods: Sequence[str],
        context: _DatasetContext,
    ) -> dict[str, Any] | None:
        by_period: dict[str, KpiRow] = {}
        for row in context.rows:
            if _text(row.get('kpi_code')) != kpi_code:
                continue
            if (
                context.breakdown_key is not None
                and (_text(row.get(context.breakdown_key)) or 'Unknown') != group
            ):
                continue
            period = _row_period(row)
            if period and period not in by_period:
                by_period[period] = row
        if not by_period:
            return None

        values = [_number(row.get('value')) for row in by_period.values()]
        positive_total = sum(
            (value for value in values if value is not None and value > 0), Decimal(0)
        )
        points: list[dict[str, Any]] = []
        previous: Decimal | None = None
        for period in periods:
            selected: KpiRow | None = by_period.get(period)
            point, previous = self._point(
                selected, period, previous, context.polarity, positive_total
            )
            points.append(point)

        label = kpi_code.replace('_', ' ').title()
        if group is not None:
            label = f'{label} — {group}'
        first = by_period[next(iter(by_period))]
        return {
            'series_type': 'kpi',
            'label': label,
            'currency': _text(first.get('currency')) or '',
            'units': _text(first.get('units')) or '',
            'period': periods[0] if periods else '',
            'data': [point['value'] for point in points],
            'points': points,
        }

    def _point(
        self,
        row: KpiRow | None,
        period: str,
        previous: Decimal | None,
        polarity: str,
        positive_total: Decimal,
    ) -> tuple[dict[str, Any], Decimal | None]:
        if row is None:
            point: dict[str, Any] = {
                'value': None,
                'period': '',
                'chart_period': period,
                'source_citations': [],
                'computation_status': _NEEDS_REVIEW,
                'display_label': None,
                'change': None,
                'change_direction': None,
                'share': None,
                'reason': _INSUFFICIENT_DATA,
            }
            return point, previous

        number = _number(row.get('value'))
        change = number - previous if number is not None and previous is not None else None
        share = None
        if number is not None and positive_total > 0:
            share = _money(number * _HUNDRED / positive_total)
        row_period = _row_period(row)
        point = {
            'value': _money(row.get('value')),
            'period': _text(row.get('period')) or row_period,
            'chart_period': row_period,
            'source_citations': [str(item) for item in row.get('source_citations') or ()],
            'computation_status': _text(row.get('computation_status')) or _NEEDS_REVIEW,
            'display_label': _text(row.get('display_label')),
            'change': _money(change),
            'change_direction': _direction(change, polarity),
            'share': share,
            'reason': None if number is not None else _INSUFFICIENT_DATA,
        }
        return point, number if number is not None else previous

    def _variance_rows(self, rows: Sequence[KpiRow], polarity: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in rows:
            if _text(row.get('kpi_code')) != 'budget_vs_actual':
                continue
            actual = _number(row.get('actual'))
            budget = _number(row.get('budget'))
            variance = _number(row.get('value'))
            if variance is None and actual is not None and budget is not None:
                variance = actual - budget
            if polarity == 'higher_is_better':
                favourable = variance is not None and variance > 0
            elif polarity == 'lower_is_better':
                favourable = variance is not None and variance < 0
            else:
                favourable = False
            result.append(
                {
                    'name': _text(row.get('name')) or 'Budget vs actual',
                    'actual': _money(actual),
                    'budget': _money(budget),
                    'variance': _money(variance),
                    'favourable': favourable,
                }
            )
        return result


__all__ = ['ChartSeriesBuilder']
