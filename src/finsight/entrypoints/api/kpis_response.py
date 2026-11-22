"""KPI API response models (Phase 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KpiRow(BaseModel):
    """One code-computed KPI row from ``kpi_current``."""

    model_config = ConfigDict(extra='forbid')

    kpi_code: str = Field(...)
    period: str = Field(...)
    period_start: str = Field(..., json_schema_extra={'format': 'date'})
    chart_period: str = Field(...)
    chart_period_start: str = Field(..., json_schema_extra={'format': 'date'})
    currency: str = Field(...)
    units: str = Field(...)
    value: str | None = Field(...)
    source_citations: list[str] = Field(...)
    computation_status: Literal['computed', 'estimated', 'needs_review'] = Field(...)
    estimation_method: str | None = Field(default=None)
    document_version_id: str = Field(..., json_schema_extra={'format': 'uuid'})
    computation_rule_version: str = Field(...)
    superseded_by_document_version_id: str | None = Field(
        default=None, json_schema_extra={'format': 'uuid'}
    )
    conflict_marker: str | None = Field(default=None)
    created_at: str = Field(..., json_schema_extra={'format': 'date-time'})
    updated_at: str = Field(..., json_schema_extra={'format': 'date-time'})


class KpiActions(BaseModel):
    """Role-derived actions included in the KPI list envelope."""

    model_config = ConfigDict(extra='forbid')

    upload: bool = Field(...)


class KpiListResponse(BaseModel):
    """Response for GET /kpis."""

    model_config = ConfigDict(extra='forbid')

    contract_version: Literal[1] = Field(..., json_schema_extra={'enum': [1]})
    items: list[KpiRow] = Field(...)
    next_cursor: str | None = Field(...)
    documents_processing: bool = Field(...)
    actions: KpiActions = Field(...)


__all__ = ['KpiActions', 'KpiListResponse', 'KpiRow']
