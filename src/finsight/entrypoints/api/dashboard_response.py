"""Dashboard API response models (Phase 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FingerprintsResponse(BaseModel):
    """Response for GET /dashboard/fingerprints."""

    model_config = ConfigDict(extra='forbid')

    contract_version: int = 1
    charts: dict[str, str]


class LayoutChartRequest(BaseModel):
    """Chart in a layout request."""

    model_config = ConfigDict(extra='forbid')

    chart_id: str
    span: Literal['full', 'half']


class LayoutRequest(BaseModel):
    """Request body for PUT /dashboard/layout."""

    model_config = ConfigDict(extra='forbid')

    contract_version: Literal[1] = 1
    kpi_codes: list[str]
    charts: list[LayoutChartRequest]
    version: int = Field(ge=0)


class LayoutResponse(BaseModel):
    """Response for GET/PUT /dashboard/layout."""

    model_config = ConfigDict(extra='forbid')

    contract_version: Literal[1] = 1
    kpi_codes: list[str]
    charts: list[LayoutChartRequest]
    version: int
    updated_at: str


class LayoutConflictResponse(BaseModel):
    """Response for 409 conflict on layout save."""

    model_config = ConfigDict(extra='forbid')

    error: str
    current_layout: LayoutResponse


__all__ = [
    'FingerprintsResponse',
    'LayoutChartRequest',
    'LayoutConflictResponse',
    'LayoutRequest',
    'LayoutResponse',
]
