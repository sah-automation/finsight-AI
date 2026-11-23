"""Chart API response models (Phase 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceDocument(BaseModel):
    """Source document entry in export metadata."""

    model_config = ConfigDict(extra='forbid', title='SourceDocument')

    title: str
    version: str


class ChartPoint(BaseModel):
    """Single point in a chart dataset."""

    model_config = ConfigDict(extra='forbid', title='ChartPoint')

    value: str | None
    period: str
    chart_period: str
    source_citations: list[str]
    computation_status: Literal['computed', 'estimated', 'needs_review']
    display_label: Literal['Draft', 'Estimated', 'Updating'] | None
    change: str | None
    change_direction: Literal['good', 'bad'] | None
    share: str | None
    reason: str | None


class ChartDataset(BaseModel):
    """Chart dataset response."""

    model_config = ConfigDict(extra='forbid', title='ChartDataset')

    series_type: Literal['kpi', 'forecast', 'anomaly']
    label: str
    currency: str
    units: str
    period: str
    data: list[str | None]
    points: list[ChartPoint]


class VarianceRow(BaseModel):
    """Variance row for budget vs actual charts."""

    model_config = ConfigDict(extra='forbid', title='VarianceRow')

    name: str
    actual: str | None
    budget: str | None
    variance: str | None
    favourable: bool


class ExportMetadata(BaseModel):
    """Export metadata for chart export."""

    model_config = ConfigDict(extra='forbid', title='ExportMetadata')

    generated_at: str = Field(..., json_schema_extra={'format': 'date-time'})
    company_name: str
    company_slug: str
    period_range: str
    currency: str
    units: str
    source_document_list: list[SourceDocument]


class ChartResponse(BaseModel):
    """Response for GET /charts/{chart_id}."""

    model_config = ConfigDict(extra='forbid')

    contract_version: Literal[1] = Field(..., json_schema_extra={'enum': [1]})
    chart_id: str
    labels: list[str]
    datasets: list[ChartDataset]
    variance_rows: list[VarianceRow]
    reason: str | None
    export: ExportMetadata


__all__ = [
    'ChartDataset',
    'ChartPoint',
    'ChartResponse',
    'ExportMetadata',
    'SourceDocument',
    'VarianceRow',
]
