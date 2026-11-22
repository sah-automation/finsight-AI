"""Chart API response models (Phase 2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChartPointResponse(BaseModel):
    """Single point in a chart dataset."""

    model_config = ConfigDict(extra='forbid')

    value: str | None
    period: str
    chart_period: str
    source_citations: list[str]
    computation_status: str
    display_label: str | None = None
    change: str | None = None
    change_direction: str | None = None
    share: str | None = None
    reason: str | None = None


class ChartDatasetResponse(BaseModel):
    """Chart dataset response."""

    model_config = ConfigDict(extra='forbid')

    series_type: str
    label: str
    currency: str
    units: str
    period: str
    data: list[str | None]
    points: list[ChartPointResponse]


class VarianceRowResponse(BaseModel):
    """Variance row for budget vs actual charts."""

    model_config = ConfigDict(extra='forbid')

    name: str
    actual: str | None
    budget: str | None
    variance: str | None
    favourable: bool


class ExportMetadataResponse(BaseModel):
    """Export metadata for chart export."""

    model_config = ConfigDict(extra='forbid')

    generated_at: str
    company_name: str
    company_slug: str
    period_range: str
    currency: str
    units: str
    source_document_list: list[dict[str, str]]


class ChartResponse(BaseModel):
    """Response for GET /charts/{chart_id}."""

    model_config = ConfigDict(extra='forbid')

    contract_version: int = 1
    chart_id: str
    labels: list[str]
    datasets: list[ChartDatasetResponse]
    variance_rows: list[VarianceRowResponse] = Field(default_factory=list)
    reason: str | None = None
    export: ExportMetadataResponse


__all__ = [
    'ChartDatasetResponse',
    'ChartPointResponse',
    'ChartResponse',
    'ExportMetadataResponse',
    'VarianceRowResponse',
]
