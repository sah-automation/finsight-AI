"""Quarterly-to-monthly KPI estimation (issue #375).

The declared period stays on every spread row; only the chart bucket changes.
Shares are exact decimal values rounded consistently to cents, never floats.
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
_METHOD = 'quarterly_spread_equal'


def spread_quarterly(rows: Sequence[KpiRow]) -> list[KpiRow]:
    """Replace computed quarterly rows with three equal estimated months."""
    result: list[KpiRow] = []
    for row in rows:
        match = _QUARTER.fullmatch(str(row.get('period', '')))
        if (
            match is None
            or row.get('value') is None
            or row.get('estimation_method') is not None
            or row.get('computation_status')
            in (ComputationStatus.ESTIMATED, ComputationStatus.NEEDS_REVIEW)
        ):
            result.append(dict(row))
            continue
        amount = Decimal(str(row['value']))
        with localcontext() as context:
            context.prec = 34
            share = str((amount / 3).quantize(_CENTS, rounding=ROUND_HALF_UP))
        year, quarter = int(match.group(1)), int(match.group(2))
        for month in range(3 * (quarter - 1) + 1, 3 * (quarter - 1) + 4):
            estimated = dict(row)
            estimated['chart_period'] = f'{year}-{month:02d}'
            estimated['chart_period_start'] = date(year, month, 1).isoformat()
            estimated['value'] = share
            estimated['computation_status'] = ComputationStatus.ESTIMATED.value
            estimated['estimation_method'] = _METHOD
            estimated['display_label'] = 'Estimated'
            result.append(estimated)
    return result


__all__ = ['spread_quarterly']
