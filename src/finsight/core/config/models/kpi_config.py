"""KPI Configuration models."""

from __future__ import annotations

from typing import Annotated, Literal, cast

from pydantic import Field

from .kpi_tolerance import (
    ToleranceAbsolute,
    ToleranceExactOrNeedsReview,
    TolerancePercentOfExpected,
    TolerancePercentOfExpectedPlusAbsoluteFloor,
)
from .strict_base_model import StrictBaseModel

KpiCode = Literal[
    'revenue',
    'gross_margin',
    'net_margin',
    'operating_expenses',
    'cash_flow',
    'burn_rate',
    'runway',
    'dso',
    'dpo',
    'budget_vs_actual',
]

KPI_CODES: tuple[KpiCode, ...] = (
    'revenue',
    'gross_margin',
    'net_margin',
    'operating_expenses',
    'cash_flow',
    'burn_rate',
    'runway',
    'dso',
    'dpo',
    'budget_vs_actual',
)


def _default_estimation_methods() -> dict[KpiCode, Literal['quarterly_spread_equal']]:
    return cast(
        'dict[KpiCode, Literal["quarterly_spread_equal"]]',
        dict.fromkeys(KPI_CODES, 'quarterly_spread_equal'),
    )


KpiTolerance = Annotated[
    TolerancePercentOfExpectedPlusAbsoluteFloor
    | ToleranceAbsolute
    | TolerancePercentOfExpected
    | ToleranceExactOrNeedsReview,
    Field(discriminator='kind'),
]


class KpiConfig(StrictBaseModel):
    codes: tuple[KpiCode, ...] = KPI_CODES
    budget_vs_actual_match: Literal['strict'] = 'strict'
    estimation_methods: dict[KpiCode, Literal['quarterly_spread_equal']] = Field(
        default_factory=_default_estimation_methods
    )
    tolerances: dict[KpiCode, KpiTolerance]
    page_size_default: Annotated[int, Field(ge=1)] = 50
    page_size_max: Annotated[int, Field(ge=1)] = 100
    rebuild_batch_size: Annotated[int, Field(ge=1)] = 10
    rebuild_priority: Literal['rebuilds', 'background'] = 'rebuilds'

    @property
    def code_set(self) -> frozenset[str]:
        return frozenset(self.codes)
