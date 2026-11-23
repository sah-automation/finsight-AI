"""API entrypoint for dashboard fingerprints and layouts (Phase 2)."""

from __future__ import annotations

import contextlib
from typing import Any, cast

from fastapi import APIRouter, Body, Depends, HTTPException

from finsight.application.kpi_visibility_filter import KpiVisibilityFilter
from finsight.composition.container import get_container
from finsight.core.config import get_config, load_config
from finsight.core.config.loader import ConfigError
from finsight.core.types import CompanyId, UserId
from finsight.domain.ports.dashboard_layout_repository import (
    LayoutConflictError,
)
from finsight.domain.ports.kpi_repository import FINGERPRINT_FIELDS
from finsight.domain.services.fingerprint import FingerprintService
from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_draft import LayoutDraft
from finsight.domain.value_objects.visible_ids import VisibleIds

from ._permissions import (
    _check_action,
    _get_allowed_chart_ids,
    _get_allowed_kpi_codes,
    _get_default_layout,
)
from ._shared import (
    _await,
)
from .action_permission import ActionPermission
from .api_principal import ApiPrincipal  # noqa: TC001
from .dashboard_response import (
    FingerprintsResponse,
    LayoutChartRequest,
    LayoutConflictResponse,
    LayoutRequest,
    LayoutResponse,
)

router = APIRouter(prefix='/dashboard', tags=['dashboard'])
dashboard_view_dependency = ActionPermission('dashboard_view')
dashboard_edit_layout_dependency = ActionPermission('dashboard_edit_layout')
# Backwards-compatible aliases for callers/tests that use shorter names.
dashboard_edit_dependency = dashboard_edit_layout_dependency
layout_edit_dependency = dashboard_edit_layout_dependency
kpi_view_dependency = dashboard_view_dependency


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
    principal: ApiPrincipal = Depends(dashboard_view_dependency),
) -> FingerprintsResponse:
    """Get freshness fingerprints for all charts in the dashboard."""
    if 'dashboard_view' not in principal.role_actions:
        raise HTTPException(
            status_code=403, detail='You do not have permission to view dashboard fingerprints.'
        )

    try:
        config = get_config()
    except ConfigError:
        try:
            config = load_config()
        except ConfigError as exc:
            raise HTTPException(
                status_code=500, detail='Service configuration is unavailable.'
            ) from exc

    charts_config = getattr(config, 'charts', None)
    specs = getattr(charts_config, 'specs', None) if charts_config is not None else None
    if specs is None:
        raise HTTPException(status_code=500, detail='Service configuration is unavailable.')

    container = get_container()
    kpi_repository = getattr(container, 'kpi_repository', None)
    if kpi_repository is None:
        raise HTTPException(status_code=500, detail='KPI data is temporarily unavailable.')

    document_repository = getattr(container, 'document_repository', None)
    versions: list[Any] = []
    if document_repository is not None and callable(
        getattr(document_repository, 'list_document_versions', None)
    ):
        versions = list(
            await _await(document_repository.list_document_versions(principal.company_id)) or ()
        )

    visibility = KpiVisibilityFilter(
        category_permissions=principal.category_permissions,
        access_scope=principal.access_scope,
    )

    fingerprints: dict[str, str] = {}
    for chart_id, chart_spec in (specs or {}).items():
        if 'kpi_view' not in (principal.role_actions or ()):
            continue

        rows: list[dict[str, Any]] = []
        getter = getattr(kpi_repository, 'get_current', None)
        if callable(getter):
            fetched = await _await(
                getter(
                    principal.company_id,
                    {
                        'kpi_codes': list(
                            getattr(chart_spec, 'kpi_codes', None)
                            or (
                                chart_spec.get('kpi_codes', [])
                                if isinstance(chart_spec, dict)
                                else []
                            )
                        )
                    },
                )
            )
            rows = [dict(row) for row in (fetched or ())]
        else:
            gfd = getattr(kpi_repository, 'get_fingerprint_data', None)
            if callable(gfd):
                projected = await _await(gfd(principal.company_id, [chart_spec]))
                rows = [dict(row) for row in (projected.get(str(chart_id), []) or ())]

        visible_rows = visibility.filter(rows, versions)
        if not visible_rows:
            continue

        projected_visible = [
            {field: row.get(field) for field in FINGERPRINT_FIELDS} for row in visible_rows
        ]

        class _VisibleRepository:
            def __init__(self, chart_id: str, rows: list[dict[str, Any]]) -> None:
                self._chart_id = chart_id
                self._rows = rows

            async def get_fingerprint_data(
                self, company_id: Any, chart_specs: Any, **kwargs: Any
            ) -> dict[str, Any]:
                return {self._chart_id: [dict(row) for row in self._rows]}

        fingerprint = await FingerprintService(
            cast('Any', _VisibleRepository(str(chart_id), projected_visible))
        ).compute_fingerprint(CompanyId(principal.company_id), chart_spec)
        fingerprints[chart_id] = fingerprint

    return FingerprintsResponse(
        contract_version=1,
        charts=fingerprints,
    )


@router.get('/layout', operation_id='get_dashboard_layout')
async def get_dashboard_layout(
    principal: ApiPrincipal = Depends(dashboard_view_dependency),
) -> LayoutResponse:
    """Get saved dashboard layout or config default."""
    if 'dashboard_view' not in principal.role_actions:
        raise HTTPException(
            status_code=403, detail='You do not have permission to view dashboard layout.'
        )

    try:
        config = get_config()
    except ConfigError:
        try:
            config = load_config()
        except ConfigError as exc:
            raise HTTPException(
                status_code=500, detail='Service configuration is unavailable.'
            ) from exc

    container = get_container()
    layout_repository = getattr(container, 'dashboard_layout_repository', None)
    if layout_repository is None:
        layout_repository = getattr(container, 'layout_repository', None)
    if layout_repository is None:
        raise HTTPException(status_code=500, detail='Dashboard layout repository not configured.')

    visible_ids = VisibleIds(
        tuple(sorted(_get_allowed_kpi_codes(config))),
        tuple(sorted(_get_allowed_chart_ids(config))),
    )

    company_id = principal.company_id
    user_id = principal.user_id or ''
    role_id = principal.role_id

    try:
        record = await _await(
            layout_repository.get_layout(
                CompanyId(company_id), UserId(user_id), visible_ids=visible_ids
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to load layout: {exc}') from exc

    kpi_codes = [str(code) for code in getattr(record, 'kpi_codes', ()) or ()]
    charts_raw = getattr(record, 'charts', ()) or ()
    charts = [
        {
            'chart_id': str(
                getattr(chart, 'chart_id', chart.get('chart_id') if isinstance(chart, dict) else '')
            ),
            'span': str(
                getattr(chart, 'span', chart.get('span') if isinstance(chart, dict) else '')
            ),
        }
        for chart in charts_raw
    ]
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        kpi_codes, charts, role_id, config
    )

    updated_at = getattr(record, 'updated_at', None)
    updated_at_str = '' if updated_at is None else str(updated_at)

    return _build_layout_response(
        filtered_kpi_codes,
        filtered_charts,
        int(getattr(record, 'version', 0) or 0),
        updated_at_str,
    )


@router.put('/layout', operation_id='save_dashboard_layout')
async def save_dashboard_layout(
    principal: ApiPrincipal = Depends(dashboard_edit_layout_dependency),
    request: LayoutRequest = Body(...),
) -> LayoutResponse:
    """Save dashboard layout with optimistic locking."""
    if 'dashboard_edit_layout' not in principal.role_actions:
        raise HTTPException(
            status_code=403, detail='You do not have permission to edit dashboard layout.'
        )

    try:
        config = get_config()
    except ConfigError:
        try:
            config = load_config()
        except ConfigError as exc:
            raise HTTPException(
                status_code=500, detail='Service configuration is unavailable.'
            ) from exc

    container = get_container()
    layout_repository = getattr(container, 'dashboard_layout_repository', None)
    if layout_repository is None:
        layout_repository = getattr(container, 'layout_repository', None)
    if layout_repository is None:
        raise HTTPException(status_code=500, detail='Dashboard layout repository not configured.')

    visible_ids = VisibleIds(
        tuple(sorted(_get_allowed_kpi_codes(config))),
        tuple(sorted(_get_allowed_chart_ids(config))),
    )

    company_id = principal.company_id
    user_id = principal.user_id or ''
    role_id = principal.role_id

    kpi_codes = request.kpi_codes
    charts = [c.model_dump() for c in request.charts]
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        kpi_codes, charts, role_id, config
    )

    draft = LayoutDraft(
        contract_version=request.contract_version,
        kpi_codes=tuple(filtered_kpi_codes),
        charts=tuple(
            LayoutChart(chart_id=str(chart['chart_id']), span=str(chart['span']))
            for chart in filtered_charts
        ),
    )

    try:
        saved = await _await(
            layout_repository.save_layout(
                CompanyId(company_id),
                UserId(user_id),
                draft,
                request.version,
                visible_ids=visible_ids,
            )
        )
    except LayoutConflictError as exc:
        current = getattr(exc, 'current_layout', None)
        if current is None:
            current = await _load_saved_layout(layout_repository, company_id, user_id)
        if current is not None:
            if hasattr(current, 'kpi_codes'):
                current_kpi = [str(code) for code in getattr(current, 'kpi_codes', ()) or ()]
                current_charts_raw = getattr(current, 'charts', ()) or ()
                current_charts = [
                    {
                        'chart_id': str(
                            getattr(c, 'chart_id', c.get('chart_id') if isinstance(c, dict) else '')
                        ),
                        'span': str(
                            getattr(c, 'span', c.get('span') if isinstance(c, dict) else '')
                        ),
                    }
                    for c in current_charts_raw
                ]
                current_version = int(getattr(current, 'version', 0) or 0)
                current_updated = getattr(current, 'updated_at', None)
                current_updated_str = '' if current_updated is None else str(current_updated)
            else:
                current_kpi = current.get('kpi_codes', [])
                current_charts = current.get('charts', [])
                current_version = current.get('version', 0)
                current_updated_str = str(current.get('updated_at', ''))
            filtered_current_kpi, filtered_current_charts = _filter_layout_by_permissions(
                current_kpi, current_charts, role_id, config
            )
            conflict_response = LayoutConflictResponse(
                error='layout_changed',
                current_layout=_build_layout_response(
                    filtered_current_kpi,
                    filtered_current_charts,
                    current_version,
                    current_updated_str,
                ),
            )
            raise HTTPException(status_code=409, detail=conflict_response.model_dump()) from exc
        raise HTTPException(status_code=409, detail={'error': 'layout_changed'}) from exc
    except Exception as exc:
        message = str(exc).lower()
        if '409' in str(exc) or 'stale' in message or 'version' in message or 'conflict' in message:
            current = await _load_saved_layout(layout_repository, company_id, user_id)
            if current is not None:
                conflict_response = _build_conflict_response(current, config, role_id)
                raise HTTPException(status_code=409, detail=conflict_response.model_dump()) from exc
        raise HTTPException(status_code=500, detail=f'Failed to save layout: {exc}') from exc

    saved_kpi = [str(code) for code in getattr(saved, 'kpi_codes', ()) or ()]
    saved_charts_raw = getattr(saved, 'charts', ()) or ()
    saved_charts = [
        {
            'chart_id': str(
                getattr(c, 'chart_id', c.get('chart_id') if isinstance(c, dict) else '')
            ),
            'span': str(getattr(c, 'span', c.get('span') if isinstance(c, dict) else '')),
        }
        for c in saved_charts_raw
    ]
    filtered_saved_kpi, filtered_saved_charts = _filter_layout_by_permissions(
        saved_kpi, saved_charts, role_id, config
    )
    saved_updated = getattr(saved, 'updated_at', None)
    saved_updated_str = '' if saved_updated is None else str(saved_updated)

    return _build_layout_response(
        filtered_saved_kpi,
        filtered_saved_charts,
        int(getattr(saved, 'version', 0) or 0),
        saved_updated_str,
    )


__all__ = [
    'dashboard_edit_dependency',
    'dashboard_edit_layout_dependency',
    'dashboard_view_dependency',
    'kpi_view_dependency',
    'layout_edit_dependency',
    'router',
]
