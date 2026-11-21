"""KPI Tolerance Configuration models."""

from __future__ import annotations

from decimal import Decimal  # noqa: TC003 - needed at runtime for Annotated[Decimal, Field(...)]
from typing import Annotated, Literal

from pydantic import Field

from .strict_base_model import StrictBaseModel


class _TolerancePercentOfExpectedPlusAbsoluteFloor(StrictBaseModel):
    kind: Literal['percent_of_expected_plus_absolute_floor']
    percent: Annotated[Decimal, Field(gt=0)]
    floor: Annotated[Decimal, Field(gt=0)]
    floor_unit: Literal['kpi_currency']


class _ToleranceAbsolute(StrictBaseModel):
    kind: Literal['absolute']
    value: Annotated[Decimal, Field(gt=0)]
    unit: Literal['percentage_points', 'days']


class _TolerancePercentOfExpected(StrictBaseModel):
    kind: Literal['percent_of_expected']
    percent: Annotated[Decimal, Field(gt=0)]


class _ToleranceExactOrNeedsReview(StrictBaseModel):
    kind: Literal['exact_or_needs_review']


TolerancePercentOfExpectedPlusAbsoluteFloor = _TolerancePercentOfExpectedPlusAbsoluteFloor
ToleranceAbsolute = _ToleranceAbsolute
TolerancePercentOfExpected = _TolerancePercentOfExpected
ToleranceExactOrNeedsReview = _ToleranceExactOrNeedsReview
