"""API entrypoint for KPI listing (Phase 2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from finsight.composition.container import get_container

from ._permissions import (
    _check_action,
    _check_category_action,
    _extract_role_actions_and_categories,
    _get_role_entry,
    _load_permissions_config,
    _require_company_id,
    _require_role_id,
)
from ._shared import (
    _await,
)
from .kpis_response import (
    KpiListResponse,
    KpiRowResponse,
)

router = APIRouter(prefix='/kpis', tags=['kpis'])


class _KpiQueryParams(BaseModel):
    """Query parameters for KPI list endpoint."""

    kpi_code: list[str] | None = None
    period_from: str | None = None
    period_to: str | None = None
    currency: str | None = None
    units: str | None = None
    limit: int | None = None
    cursor: str | None = None

    model_config = ConfigDict(extra='forbid')


def _to_kpi_row_response(row: dict[str, Any]) -> KpiRowResponse:
    """Convert database row to KpiRowResponse."""
    return KpiRowResponse(
        kpi_code=row.get('kpi_code', ''),
        period=row.get('period', ''),
        period_start=str(row.get('period_start', '')),
        chart_period=row.get('chart_period', ''),
        chart_period_start=str(row.get('chart_period_start', '')),
        currency=row.get('currency', ''),
        units=row.get('units', ''),
        value=str(row.get('value')) if row.get('value') is not None else None,
        source_citations=row.get('source_citations', []) or [],
        computation_status=row.get('computation_status', ''),
        estimation_method=row.get('estimation_method'),
        document_version_id=str(row.get('document_version_id', '')),
        computation_rule_version=row.get('computation_rule_version', ''),
        superseded_by_document_version_id=(
            str(row.get('superseded_by_document_version_id'))
            if row.get('superseded_by_document_version_id')
            else None
        ),
        conflict_marker=row.get('conflict_marker'),
        created_at=str(row.get('created_at', '')),
        updated_at=str(row.get('updated_at', '')),
    )


async def _check_documents_processing(container: Any, company_id: str) -> bool:
    """Check if any documents are processing for the company."""
    doc_repo = getattr(container, 'document_repository', None)
    if doc_repo is None:
        return False
    try:
        processing = await _await(doc_repo.list_documents(company_id, status='processing'))
        return len(processing) > 0
    except (AttributeError, TypeError, ValueError):
        return False


def _build_filters(params: _KpiQueryParams) -> dict[str, Any]:
    """Build filters from query params."""
    filters: dict[str, Any] = {}
    if params.kpi_code:
        filters['kpi_codes'] = params.kpi_code
    if params.period_from:
        filters['period_from'] = params.period_from
    if params.period_to:
        filters['period_to'] = params.period_to
    if params.currency:
        filters['currency'] = params.currency
    if params.units:
        filters['units'] = params.units
    if params.limit:
        filters['limit'] = params.limit
    if params.cursor:
        filters['cursor'] = params.cursor
    return filters


async def _fetch_and_convert_kpis(
    kpi_repository: Any,
    company_id: str,
    filters: dict[str, Any],
) -> list[KpiRowResponse]:
    """Fetch KPI rows and convert to response format."""
    rows = await _await(kpi_repository.get_current(company_id, filters))
    return [_to_kpi_row_response(row) for row in rows]


def _build_kpi_list_response(
    items: list[KpiRowResponse],
    documents_processing: bool,
    can_upload: bool,
) -> KpiListResponse:
    """Build the KPI list response."""
    return KpiListResponse(
        contract_version=1,
        items=items,
        next_cursor=None,  # TODO(finsight): implement cursor pagination (issue #378)
        documents_processing=documents_processing,
        actions={'upload': can_upload},
    )


@router.get('', operation_id='list_kpis')
async def list_kpis(
    context: Any = None,
    params: _KpiQueryParams = Query(),
) -> KpiListResponse:
    """List KPI rows for the authenticated company."""
    company_id = await _require_company_id(context)
    role_id = await _require_role_id(context)

    config = _load_permissions_config()
    entry_dump = _get_role_entry(role_id, config)
    role_actions, category_permissions = _extract_role_actions_and_categories(entry_dump)

    # Check kpi_view permission
    if not _check_action(role_actions, 'kpi_view'):
        raise HTTPException(status_code=403, detail='You do not have permission to view KPIs.')

    # Check upload permission for actions.upload
    can_upload = _check_category_action(category_permissions, 'upload')

    container = get_container()
    kpi_repository = getattr(container, 'kpi_repository', None)
    if kpi_repository is None:
        raise HTTPException(status_code=500, detail='KPI repository not configured.')

    # Build filters from query params
    filters = _build_filters(params)

    # Fetch and convert KPI rows
    items = await _fetch_and_convert_kpis(kpi_repository, company_id, filters)

    # Check if any documents are processing
    documents_processing = await _check_documents_processing(container, company_id)

    return _build_kpi_list_response(items, documents_processing, can_upload)


__all__ = ['router']
