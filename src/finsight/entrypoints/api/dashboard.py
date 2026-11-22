"""API entrypoint for dashboard fingerprints and layouts (Phase 2)."""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from finsight.composition.container import get_container
from finsight.core.types import CompanyId
from finsight.domain.services.fingerprint import FingerprintService

from ._permissions import (
    _check_action,
    _extract_role_actions_and_categories,
    _get_allowed_chart_ids,
    _get_allowed_kpi_codes,
    _get_default_layout,
    _get_role_entry,
    _load_permissions_config,
    _require_company_id,
    _require_role_id,
    _require_user_id,
)
from ._shared import (
    _await,
)
from .dashboard_response import (
    FingerprintsResponse,
    LayoutChartRequest,
    LayoutConflictResponse,
    LayoutRequest,
    LayoutResponse,
)

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


async def _check_dashboard_view_permission(role_actions: list[str]) -> bool:
    """Check if role has dashboard_view action."""
    return _check_action(role_actions, 'dashboard_view')


async def _check_dashboard_edit_permission(role_actions: list[str]) -> bool:
    """Check if role has dashboard_edit_layout action."""
    return _check_action(role_actions, 'dashboard_edit_layout')


def _filter_layout_by_permissions(
    kpi_codes: list[str],
    charts: list[dict[str, str]],
    role_id: str,
    config: Any,
) -> tuple[list[str], list[dict[str, str]]]:
    """Filter layout by role permissions - drop unknown/unpermitted IDs."""
    allowed_chart_ids = _get_allowed_chart_ids(config)
    allowed_kpi_codes = _get_allowed_kpi_codes(config)

    filtered_kpi_codes = [code for code in kpi_codes if code in allowed_kpi_codes]
    filtered_charts = [chart for chart in charts if chart.get('chart_id') in allowed_chart_ids]

    # If nothing remains, use config defaults
    if not filtered_kpi_codes and not filtered_charts:
        default_kpi_codes, default_charts = _get_default_layout(config)
        filtered_kpi_codes = [code for code in default_kpi_codes if code in allowed_kpi_codes]
        filtered_charts = [
            chart for chart in default_charts if chart.get('chart_id') in allowed_chart_ids
        ]

    return filtered_kpi_codes, filtered_charts


def _build_layout_response(
    kpi_codes: list[str],
    charts: list[dict[str, str]],
    version: int,
    updated_at: str,
) -> LayoutResponse:
    """Build a LayoutResponse from components."""
    return LayoutResponse(
        contract_version=1,
        kpi_codes=kpi_codes,
        charts=[LayoutChartRequest(**c) for c in charts],
        version=version,
        updated_at=updated_at,
    )


async def _load_saved_layout(
    layout_repository: Any,
    company_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    """Load saved layout from repository."""
    with contextlib.suppress(Exception):
        result = await _await(layout_repository.get_layout(company_id, user_id))
        if result is not None:
            return dict(result)
    return None


def _build_default_layout_response(
    config: Any,
    role_id: str,
) -> LayoutResponse:
    """Build response from config default layout."""
    default_kpi_codes, default_charts = _get_default_layout(config)
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        default_kpi_codes, default_charts, role_id, config
    )
    return _build_layout_response(filtered_kpi_codes, filtered_charts, 0, '')


def _build_saved_layout_response(
    layout: dict[str, Any],
    config: Any,
    role_id: str,
) -> LayoutResponse:
    """Build response from saved layout."""
    layout_kpi_codes = layout.get('kpi_codes', [])
    layout_charts = layout.get('charts', [])
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        layout_kpi_codes, layout_charts, role_id, config
    )
    return _build_layout_response(
        filtered_kpi_codes,
        filtered_charts,
        layout.get('version', 0),
        str(layout.get('updated_at', '')),
    )


def _build_conflict_response(
    current_layout: dict[str, Any],
    config: Any,
    role_id: str,
) -> LayoutConflictResponse:
    """Build 409 conflict response."""
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        current_layout.get('kpi_codes', []), current_layout.get('charts', []), role_id, config
    )
    return LayoutConflictResponse(
        error='layout_changed',
        current_layout=_build_layout_response(
            filtered_kpi_codes,
            filtered_charts,
            current_layout.get('version', 0),
            str(current_layout.get('updated_at', '')),
        ),
    )


async def _save_layout_with_lock(
    layout_repository: Any,
    company_id: str,
    user_id: str,
    layout_data: dict[str, Any],
    context: dict[str, Any],
) -> LayoutResponse:
    """Save layout with optimistic locking."""
    try:
        saved_layout = await _await(layout_repository.save_layout(company_id, user_id, layout_data))
        return _build_layout_response(
            saved_layout.get('kpi_codes', []),
            saved_layout.get('charts', []),
            saved_layout.get('version', 0),
            str(saved_layout.get('updated_at', '')),
        )
    except Exception as exc:
        if '409' in str(exc) or 'stale' in str(exc).lower() or 'version' in str(exc).lower():
            current = await _load_saved_layout(layout_repository, company_id, user_id)
            if current:
                conflict_response = _build_conflict_response(
                    current, context['config'], context['role_id']
                )
                raise HTTPException(status_code=409, detail=conflict_response.model_dump()) from exc
        raise HTTPException(status_code=500, detail=f'Failed to save layout: {exc}') from exc


@router.get('/fingerprints', operation_id='get_dashboard_fingerprints')
async def get_dashboard_fingerprints(
    context: Any = None,
) -> FingerprintsResponse:
    """Get freshness fingerprints for all charts in the dashboard."""
    company_id = await _require_company_id(context)
    role_id = await _require_role_id(context)

    config = _load_permissions_config()
    entry_dump = _get_role_entry(role_id, config)
    role_actions, _category_permissions = _extract_role_actions_and_categories(entry_dump)

    # Check dashboard_view permission
    if not await _check_dashboard_view_permission(role_actions):
        raise HTTPException(
            status_code=403, detail='You do not have permission to view dashboard fingerprints.'
        )

    # Get KPI repository from container
    container = get_container()
    kpi_repository = getattr(container, 'kpi_repository', None)
    if kpi_repository is None:
        raise HTTPException(status_code=500, detail='KPI repository not configured.')

    # Get fingerprint service
    fingerprint_service = FingerprintService(kpi_repository)

    # Get chart specs from config
    charts_config = getattr(config, 'charts', None)
    if charts_config is None or not hasattr(charts_config, 'specs'):
        raise HTTPException(status_code=500, detail='Charts configuration not found.')

    specs = charts_config.specs if hasattr(charts_config, 'specs') else {}

    # For each chart spec, compute fingerprint
    fingerprints = {}
    for chart_id, chart_spec in specs.items():
        fingerprint = await fingerprint_service.compute_fingerprint(
            CompanyId(company_id), chart_spec
        )
        fingerprints[chart_id] = fingerprint

    return FingerprintsResponse(
        contract_version=1,
        charts=fingerprints,
    )


@router.get('/layout', operation_id='get_dashboard_layout')
async def get_dashboard_layout(
    context: Any = None,
) -> LayoutResponse:
    """Get saved dashboard layout or config default."""
    company_id = await _require_company_id(context)
    role_id = await _require_role_id(context)
    user_id = await _require_user_id(context)

    config = _load_permissions_config()
    entry_dump = _get_role_entry(role_id, config)
    role_actions, _category_permissions = _extract_role_actions_and_categories(entry_dump)

    # Check dashboard_view permission
    if not await _check_dashboard_view_permission(role_actions):
        raise HTTPException(
            status_code=403, detail='You do not have permission to view dashboard layout.'
        )

    # Get layout repository from container
    container = get_container()
    layout_repository = getattr(container, 'dashboard_layout_repository', None)
    if layout_repository is None:
        raise HTTPException(status_code=500, detail='Dashboard layout repository not configured.')

    # Try to load saved layout
    layout = await _load_saved_layout(layout_repository, company_id, user_id)

    if layout is None:
        # Return config default (no row written on miss per spec)
        return _build_default_layout_response(config, role_id)

    # Filter loaded layout by role permissions
    return _build_saved_layout_response(layout, config, role_id)


@router.put('/layout', operation_id='save_dashboard_layout')
async def save_dashboard_layout(
    context: Any = None,
    request: LayoutRequest = Body(...),
) -> LayoutResponse:
    """Save dashboard layout with optimistic locking."""
    company_id = await _require_company_id(context)
    role_id = await _require_role_id(context)
    user_id = await _require_user_id(context)

    config = _load_permissions_config()
    entry_dump = _get_role_entry(role_id, config)
    role_actions, _category_permissions = _extract_role_actions_and_categories(entry_dump)

    # Check dashboard_edit_layout permission
    if not await _check_dashboard_edit_permission(role_actions):
        raise HTTPException(
            status_code=403, detail='You do not have permission to edit dashboard layout.'
        )

    # Get layout repository from container
    container = get_container()
    layout_repository = getattr(container, 'dashboard_layout_repository', None)
    if layout_repository is None:
        raise HTTPException(status_code=500, detail='Dashboard layout repository not configured.')

    # Filter request by role permissions
    kpi_codes = request.kpi_codes
    charts = [c.model_dump() for c in request.charts]
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        kpi_codes, charts, role_id, config
    )

    # Prepare layout data
    layout_data = {
        'kpi_codes': filtered_kpi_codes,
        'charts': filtered_charts,
        'version': request.version,
    }

    return await _save_layout_with_lock(
        layout_repository, company_id, user_id, layout_data, {'config': config, 'role_id': role_id}
    )


__all__ = ['router']
