"""API entrypoint for dashboard fingerprints and layouts (Phase 2)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

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


def _filter_layout_by_permissions(
    kpi_codes: list[str],
    charts: list[dict[str, str]],
    role_id: str,
    config: Any,
    visible_chart_ids: set[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Filter layout by role permissions - drop unknown/unpermitted IDs."""
    allowed_chart_ids = _get_allowed_chart_ids(config)
    allowed_kpi_codes = _get_allowed_kpi_codes(config)
    if visible_chart_ids is not None:
        allowed_chart_ids = allowed_chart_ids & visible_chart_ids

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


@router.get('/fingerprints', operation_id='get_dashboard_fingerprints')
async def get_dashboard_fingerprints(
    principal: ApiPrincipal = Depends(dashboard_view_dependency),
) -> FingerprintsResponse:
    """Get freshness fingerprints for all charts in the dashboard."""
    if 'dashboard_view' not in principal.role_actions:
        raise HTTPException(
            status_code=403, detail='You do not have permission to view dashboard fingerprints.'
        )

    config = _resolve_config()

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


def _record_value(record: Any, name: str, default: Any = None) -> Any:
    """Read a field from a record that may be an object or a mapping."""
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


async def _visible_chart_ids(
    principal: ApiPrincipal,
    config: Any,
    container: Any,
) -> set[str] | None:
    """Return chart ids with at least one KPI row visible to the principal.

    Returns ``None`` when no KPI/document repositories are available, so
    callers fall back to config-level filtering (preserving prior behaviour
    for fakes and unit tests).
    """
    charts_config = getattr(config, 'charts', None)
    specs = getattr(charts_config, 'specs', None) if charts_config is not None else None
    if not isinstance(specs, dict) or not specs:
        return None

    document_repository = getattr(container, 'document_repository', None)
    kpi_repository = getattr(container, 'kpi_repository', None)
    if document_repository is None and kpi_repository is None:
        return None

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

    visible: set[str] = set()
    for chart_id, chart_spec in specs.items():
        kpi_codes = getattr(chart_spec, 'kpi_codes', None)
        if kpi_codes is None and isinstance(chart_spec, dict):
            kpi_codes = chart_spec.get('kpi_codes', [])
        kpi_codes = list(kpi_codes or ())
        if not kpi_codes:
            visible.add(str(chart_id))
            continue
        rows: list[dict[str, Any]] = []
        if kpi_repository is not None and callable(getattr(kpi_repository, 'get_current', None)):
            fetched = await _await(
                kpi_repository.get_current(principal.company_id, {'kpi_codes': kpi_codes})
            )
            rows = [dict(row) for row in (fetched or ())]

        if visibility.filter(rows, versions):
            visible.add(str(chart_id))

    return visible


def _resolve_config() -> Any:
    """Load config, raising a 500 HTTPException when unavailable."""
    try:
        return get_config()
    except ConfigError:
        try:
            return load_config()
        except ConfigError as exc:
            raise HTTPException(
                status_code=500, detail='Service configuration is unavailable.'
            ) from exc


@router.get('/layout', operation_id='get_dashboard_layout')
async def get_dashboard_layout(
    principal: ApiPrincipal = Depends(dashboard_view_dependency),
) -> LayoutResponse:
    """Get saved dashboard layout or config default."""
    if 'dashboard_view' not in principal.role_actions:
        raise HTTPException(
            status_code=403, detail='You do not have permission to view dashboard layout.'
        )

    config = _resolve_config()

    container = get_container()
    layout_repository = getattr(container, 'dashboard_layout_repository', None)
    if layout_repository is None:
        layout_repository = getattr(container, 'layout_repository', None)
    if layout_repository is None:
        raise HTTPException(status_code=500, detail='Dashboard layout repository not configured.')

    visible_chart_ids = await _visible_chart_ids(principal, config, container)

    visible_ids = VisibleIds(
        tuple(sorted(_get_allowed_kpi_codes(config))),
        tuple(
            sorted(
                visible_chart_ids
                if visible_chart_ids is not None
                else _get_allowed_chart_ids(config)
            )
        ),
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

    kpi_codes = [str(code) for code in (_record_value(record, 'kpi_codes', ()) or ())]
    charts_raw = _record_value(record, 'charts', ()) or ()
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
        kpi_codes, charts, role_id, config, visible_chart_ids=visible_chart_ids
    )

    updated_at = _record_value(record, 'updated_at', None)
    updated_at_str = '' if updated_at is None else str(updated_at)

    return _build_layout_response(
        filtered_kpi_codes,
        filtered_charts,
        int(_record_value(record, 'version', 0) or 0),
        updated_at_str,
    )


@router.put(
    '/layout',
    operation_id='save_dashboard_layout',
    response_model=LayoutResponse,
    responses={
        409: {
            'description': 'Stale version; current layout returned for reapplication',
            'model': LayoutConflictResponse,
        }
    },
)
async def save_dashboard_layout(
    principal: ApiPrincipal = Depends(dashboard_edit_layout_dependency),
    request: LayoutRequest = Body(...),
) -> LayoutResponse | JSONResponse:
    """Save dashboard layout with optimistic locking."""
    if 'dashboard_edit_layout' not in principal.role_actions:
        raise HTTPException(
            status_code=403, detail='You do not have permission to edit dashboard layout.'
        )

    config = _resolve_config()

    container = get_container()
    layout_repository = getattr(container, 'dashboard_layout_repository', None)
    if layout_repository is None:
        layout_repository = getattr(container, 'layout_repository', None)
    if layout_repository is None:
        raise HTTPException(status_code=500, detail='Dashboard layout repository not configured.')

    visible_chart_ids = await _visible_chart_ids(principal, config, container)

    visible_ids = VisibleIds(
        tuple(sorted(_get_allowed_kpi_codes(config))),
        tuple(
            sorted(
                visible_chart_ids
                if visible_chart_ids is not None
                else _get_allowed_chart_ids(config)
            )
        ),
    )

    company_id = principal.company_id
    user_id = principal.user_id or ''
    role_id = principal.role_id

    kpi_codes = request.kpi_codes
    charts = [c.model_dump() for c in request.charts]
    filtered_kpi_codes, filtered_charts = _filter_layout_by_permissions(
        kpi_codes, charts, role_id, config, visible_chart_ids=visible_chart_ids
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
            try:
                current = await _await(
                    layout_repository.get_layout(
                        CompanyId(company_id), UserId(user_id), visible_ids=visible_ids
                    )
                )
            except Exception:  # noqa: BLE001
                current = None
        if current is not None:
            if hasattr(current, 'kpi_codes'):
                current_kpi = [
                    str(code) for code in (_record_value(current, 'kpi_codes', ()) or ())
                ]
                current_charts_raw = _record_value(current, 'charts', ()) or ()
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
                current_version = int(_record_value(current, 'version', 0) or 0)
                current_updated = _record_value(current, 'updated_at', None)
                current_updated_str = '' if current_updated is None else str(current_updated)
            else:
                current_kpi = current.get('kpi_codes', [])
                current_charts = current.get('charts', [])
                current_version = current.get('version', 0)
                current_updated_str = str(current.get('updated_at', ''))
            filtered_current_kpi, filtered_current_charts = _filter_layout_by_permissions(
                current_kpi, current_charts, role_id, config, visible_chart_ids=visible_chart_ids
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
            return JSONResponse(status_code=409, content=conflict_response.model_dump())
        # No stored layout could be read; offer the role-filtered config default
        # so the 409 body still carries a current_layout for reapplication (§4.4).
        default_kpi_codes, default_charts = _get_default_layout(config)
        filtered_default_kpi, filtered_default_charts = _filter_layout_by_permissions(
            default_kpi_codes, default_charts, role_id, config, visible_chart_ids=visible_chart_ids
        )
        conflict_response = LayoutConflictResponse(
            error='layout_changed',
            current_layout=_build_layout_response(
                filtered_default_kpi, filtered_default_charts, 0, ''
            ),
        )
        return JSONResponse(status_code=409, content=conflict_response.model_dump())
    except Exception as exc:
        message = str(exc).lower()
        if '409' in str(exc) or 'stale' in message or 'version' in message or 'conflict' in message:
            try:
                current = await _await(
                    layout_repository.get_layout(
                        CompanyId(company_id), UserId(user_id), visible_ids=visible_ids
                    )
                )
            except Exception:  # noqa: BLE001
                current = None
            if current is not None:
                current_kpi = [
                    str(code) for code in (_record_value(current, 'kpi_codes', ()) or ())
                ]
                current_charts_raw = _record_value(current, 'charts', ()) or ()
                current_charts = [
                    {
                        'chart_id': str(getattr(c, 'chart_id', '')),
                        'span': str(getattr(c, 'span', '')),
                    }
                    for c in current_charts_raw
                ]
                current_version = int(_record_value(current, 'version', 0) or 0)
                current_updated = _record_value(current, 'updated_at', None)
                current_updated_str = '' if current_updated is None else str(current_updated)
                filtered_current_kpi, filtered_current_charts = _filter_layout_by_permissions(
                    current_kpi,
                    current_charts,
                    role_id,
                    config,
                    visible_chart_ids=visible_chart_ids,
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
                return JSONResponse(status_code=409, content=conflict_response.model_dump())
        raise HTTPException(status_code=500, detail=f'Failed to save layout: {exc}') from exc

    saved_kpi = [str(code) for code in (_record_value(saved, 'kpi_codes', ()) or ())]
    saved_charts_raw = _record_value(saved, 'charts', ()) or ()
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
    saved_updated = _record_value(saved, 'updated_at', None)
    saved_updated_str = '' if saved_updated is None else str(saved_updated)

    return _build_layout_response(
        filtered_saved_kpi,
        filtered_saved_charts,
        int(_record_value(saved, 'version', 0) or 0),
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
