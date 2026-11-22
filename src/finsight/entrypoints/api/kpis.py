"""API entrypoint for KPI listing (Phase 2)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from finsight.application.kpi_cursor_paginator import KpiCursorPaginator
from finsight.application.kpi_visibility_filter import KpiVisibilityFilter
from finsight.composition.container import get_container
from finsight.core.config import get_config, load_config
from finsight.core.config.loader import ConfigError
from finsight.core.config.models.kpi_config import KpiCode  # noqa: TC001
from finsight.domain.entities.document_version_state import DocumentVersionState

from ._shared import _await
from .action_permission import ActionPermission
from .api_principal import ApiPrincipal  # noqa: TC001
from .kpis_response import KpiListResponse, KpiRow

if TYPE_CHECKING:
    from collections.abc import Sequence

router = APIRouter(prefix='/kpis', tags=['kpis'])
kpi_view_dependency = ActionPermission('kpi_view')

_PROCESSING_STATES = frozenset(
    {
        DocumentVersionState.RECEIVED,
        DocumentVersionState.STORED,
        DocumentVersionState.PROCESSING,
    }
)
_STATE_FIELDS = ('state', 'status', 'document_status', 'lifecycle_state')


class _KpiQueryParams(BaseModel):
    """Query parameters for KPI list endpoint."""

    kpi_code: list[KpiCode] | None = None
    period_from: str | None = None
    period_to: str | None = None
    currency: str | None = None
    units: str | None = None
    limit: int | None = Field(
        default=None,
        ge=1,
        json_schema_extra={'minimum': 1, 'maximum': 100},
    )
    cursor: str | None = None

    model_config = ConfigDict(extra='forbid')


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _version_state(version: Any) -> str | None:
    for field_name in _STATE_FIELDS:
        value = (
            version.get(field_name)
            if isinstance(version, Mapping)
            else getattr(version, field_name, None)
        )
        state = _text(value)
        if state is not None:
            return state
    return None


def _documents_processing(versions: Sequence[Any]) -> bool:
    return any(_version_state(version) in _PROCESSING_STATES for version in versions)


def _to_kpi_row_response(row: Mapping[str, Any]) -> KpiRow:
    """Convert a repository row to the ADR-0010 wire shape."""
    return KpiRow(
        kpi_code=str(row.get('kpi_code', '')),
        period=str(row.get('period', '')),
        period_start=str(row.get('period_start', '')),
        chart_period=str(row.get('chart_period', '')),
        chart_period_start=str(row.get('chart_period_start', '')),
        currency=str(row.get('currency', '')),
        units=str(row.get('units', '')),
        value=str(row.get('value')) if row.get('value') is not None else None,
        source_citations=list(row.get('source_citations') or ()),
        computation_status=str(row.get('computation_status') or 'needs_review'),
        estimation_method=row.get('estimation_method'),
        document_version_id=str(row.get('document_version_id', '')),
        computation_rule_version=str(row.get('computation_rule_version', '')),
        superseded_by_document_version_id=(
            str(row.get('superseded_by_document_version_id'))
            if row.get('superseded_by_document_version_id')
            else None
        ),
        conflict_marker=row.get('conflict_marker'),
        created_at=str(row.get('created_at', '')),
        updated_at=str(row.get('updated_at', '')),
    )


def _build_filters(params: _KpiQueryParams) -> dict[str, Any]:
    """Build repository filters; page size and cursor stay in the handler."""
    filters: dict[str, Any] = {}
    if params.kpi_code:
        filters['kpi_codes'] = list(params.kpi_code)
    if params.period_from:
        filters['period_from'] = params.period_from
    if params.period_to:
        filters['period_to'] = params.period_to
    if params.currency:
        filters['currency'] = params.currency
    if params.units:
        filters['units'] = params.units
    return filters


def _load_kpi_paginator() -> KpiCursorPaginator:
    """Build the paginator from validated config without a test-config fallback."""
    try:
        config = get_config()
    except ConfigError:
        try:
            config = load_config()
        except ConfigError as exc:
            raise HTTPException(
                status_code=500, detail='Service configuration is unavailable.'
            ) from exc
    kpi_config = getattr(config, 'kpi', None)
    if kpi_config is None:
        raise HTTPException(status_code=500, detail='Service configuration is unavailable.')
    return KpiCursorPaginator(
        default_page_size=kpi_config.page_size_default,
        max_page_size=kpi_config.page_size_max,
    )


def _get_container_repository(container: Any, name: str) -> Any:
    repository = getattr(container, name, None)
    if repository is None:
        raise HTTPException(status_code=500, detail='KPI data is temporarily unavailable.')
    return repository


async def _load_document_versions(container: Any, company_id: str) -> list[Any]:
    repository = _get_container_repository(container, 'document_repository')
    versions = await _await(repository.list_document_versions(company_id))
    return list(versions or ())


def _can_upload(principal: ApiPrincipal) -> bool:
    return any('upload' in actions for actions in principal.category_permissions.values())


@router.get('', operation_id='list_kpis')
async def list_kpis(
    principal: ApiPrincipal = Depends(kpi_view_dependency),
    params: _KpiQueryParams = Query(),
) -> KpiListResponse:
    """List KPI rows for the authenticated company."""
    if 'kpi_view' not in principal.role_actions:
        raise HTTPException(status_code=403, detail='You do not have permission to view KPIs.')

    paginator = _load_kpi_paginator()
    container = get_container()
    versions = await _load_document_versions(container, principal.company_id)

    kpi_repository = _get_container_repository(container, 'kpi_repository')
    rows = await _await(kpi_repository.get_current(principal.company_id, _build_filters(params)))

    visibility = KpiVisibilityFilter(
        category_permissions=principal.category_permissions,
        access_scope=principal.access_scope,
    )
    visible_rows = visibility.filter(list(rows), versions)
    try:
        page, next_cursor = paginator.paginate(
            visible_rows,
            limit=params.limit,
            cursor=params.cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid pagination parameters.') from exc

    return KpiListResponse(
        contract_version=1,
        items=[_to_kpi_row_response(row) for row in page],
        next_cursor=next_cursor,
        documents_processing=_documents_processing(versions),
        actions={'upload': _can_upload(principal)},
    )


__all__ = ['kpi_view_dependency', 'router']
