"""KPI API response models (Phase 2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KpiRowResponse(BaseModel):
    """Single KPI row in the list response."""

    model_config = ConfigDict(extra='forbid')

    kpi_code: str
    period: str
    period_start: str
    chart_period: str
    chart_period_start: str
    currency: str
    units: str
    value: str | None
    source_citations: list[str]
    computation_status: str
    estimation_method: str | None = None
    document_version_id: str
    computation_rule_version: str
    superseded_by_document_version_id: str | None = None
    conflict_marker: str | None = None
    created_at: str
    updated_at: str


class KpiListResponse(BaseModel):
    """Response for GET /kpis."""

    model_config = ConfigDict(extra='forbid')

    contract_version: int = 1
    items: list[KpiRowResponse]
    next_cursor: str | None = None
    documents_processing: bool
    actions: dict[str, bool]


__all__ = ['KpiListResponse', 'KpiRowResponse']
