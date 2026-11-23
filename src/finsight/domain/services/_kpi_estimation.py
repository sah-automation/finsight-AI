"""Quarterly-to-monthly KPI estimation (issue #375).

The declared period stays on every spread row; only the chart bucket changes.
Shares are rounded to cents and the residual is added to the final month, so
the monthly series reconciles to the declared quarterly figure.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import TYPE_CHECKING

from finsight.domain.value_objects.computation_status import ComputationStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from finsight.domain.ports.kpi_repository import KpiRow

_QUARTER = re.compile(r'(\d{4})-Q([1-4])', re.IGNORECASE)
_CENTS = Decimal('0.01')
_MONTHS = 3
_METHOD = 'quarterly_spread_equal'


def spread_quarterly(rows: Sequence[KpiRow]) -> list[KpiRow]:
    """Replace computed quarterly rows with three estimated monthly rows."""
    result: list[KpiRow] = []
    for row in rows:
        match = _QUARTER.fullmatch(str(row.get('period', '')))
        if match is None or _unchanged(row):
            result.append(dict(row))
            continue
        values = _shares(Decimal(str(row['value'])))
        year, quarter = int(match.group(1)), int(match.group(2))
        months = range(3 * (quarter - 1) + 1, 3 * (quarter - 1) + _MONTHS + 1)
        for month, value in zip(months, values, strict=True):
            estimated = dict(row)
            estimated['chart_period'] = f'{year}-{month:02d}'
            estimated['chart_period_start'] = date(year, month, 1).isoformat()
            estimated['value'] = value
            estimated['computation_status'] = ComputationStatus.ESTIMATED.value
            estimated['estimation_method'] = _METHOD
            estimated['display_label'] = 'Estimated'
            result.append(estimated)
    return result


def _unchanged(row: KpiRow) -> bool:
    return (
        row.get('value') is None
        or row.get('estimation_method') is not None
        or row.get('computation_status')
        in (ComputationStatus.ESTIMATED, ComputationStatus.NEEDS_REVIEW)
    )


def _shares(amount: Decimal) -> list[str]:
    with localcontext() as context:
        context.prec = 34
        share = (amount / _MONTHS).quantize(_CENTS, rounding=ROUND_HALF_UP)
        residual = amount - share * _MONTHS
    return [str(share)] * (_MONTHS - 1) + [str(share + residual)]


__all__ = ['spread_quarterly']
