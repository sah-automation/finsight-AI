"""Calculate method mixin for :class:`Calculator`."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ._calculator_math import _to_decimal
from .calculation_result import CalculationResult


class _CalculatorCalculate:
    def calculate(self, *args: Any, **kwargs: Any) -> Any:
        return self._calculate_impl(*args, **kwargs)

    def _calculate_impl(self: Any, *args: Any, **kwargs: Any) -> CalculationResult:
        op, values, metric_ids, chunk_ids, meta = self._collect_inputs(*args, **kwargs)

        value: Decimal | None = None
        if op == 'sum':
            value = sum(values, Decimal(0)) if values else (Decimal(0) if values == [] else None)
            if not values:
                value = None
        elif op == 'average':
            if values:
                value = sum(values, Decimal(0)) / Decimal(len(values))
        elif op == 'ratio':
            denom_raw = meta.get('denominator_value')
            denom = denom_raw
            if denom is None and len(values) >= 2:
                denom = values[1]
                num = values[0]
            elif values:
                num = values[0]
            else:
                num = None
            if not isinstance(denom, Decimal):
                denom = values[1] if len(values) >= 2 else None
            if not isinstance(num, Decimal):
                num = values[0] if values else None
            if denom is None or num is None:
                value = None
            elif denom == 0:
                raise ZeroDivisionError('division by zero in ratio')
            else:
                value = num / denom
        elif op == 'margin':
            # margin = (revenue - cost) / revenue, or profit/revenue
            extra = meta.get('extra', {})
            extra_dict = extra if isinstance(extra, dict) else {}
            if 'profit' in extra_dict or meta.get('profit') is not None:
                prof = _to_decimal(meta.get('profit'))
                rev_raw = meta.get('denominator_value')
                rev = rev_raw if isinstance(rev_raw, Decimal) else None
                if prof is None and len(values) >= 1:
                    prof = values[0]
                if rev is None and len(values) >= 2:
                    rev = values[1]
                if isinstance(prof, Decimal) and isinstance(rev, Decimal) and rev != 0:
                    value = prof / rev
            elif len(values) >= 2:
                rev = values[0]
                cost = values[1]
                if isinstance(rev, Decimal) and rev != 0:
                    value = (rev - cost) / rev
        elif op == 'variance':
            if values:
                n = len(values)
                mean = sum(values, Decimal(0)) / Decimal(n)
                var = sum(((v - mean) ** 2 for v in values), Decimal(0)) / Decimal(n)
                value = var

        # If no values, maybe value None.
        meta['count'] = len(values)
        return CalculationResult(
            operation=op,
            value=value,
            values=values,
            source_metric_ids=metric_ids,
            source_chunk_ids=chunk_ids,
            metadata=meta,
        )
