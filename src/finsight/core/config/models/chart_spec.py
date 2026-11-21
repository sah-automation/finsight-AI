"""Chart Spec model."""

from __future__ import annotations

from typing import Literal

from .strict_base_model import StrictBaseModel

ChartType = Literal['trend_line', 'comparison_bar', 'breakdown_bar']
ChartPolarity = Literal['higher_is_better', 'lower_is_better', 'neutral']
ExportFormat = Literal['png', 'pdf']
BreakdownKey = Literal['document_category']


class ChartSpec(StrictBaseModel):
    """Chart specification from config."""

    chart_id: str
    chart_type: ChartType
    kpi_codes: list[str]
    supported_periods: list[int]
    periods_selectable: list[int]
    breakdown_keys: list[BreakdownKey]
    diverging: bool
    polarity: ChartPolarity
