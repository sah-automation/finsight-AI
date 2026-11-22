"""API entrypoint for chart series (Phase 2)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from finsight.composition.container import get_container

from ._permissions import (
    _check_action,
    _extract_role_actions_and_categories,
    _get_role_entry,
    _load_permissions_config,
    _require_company_id,
    _require_role_id,
)
from ._shared import (
    _await,
    _get,
)
from .charts_response import (
    ChartDatasetResponse,
    ChartPointResponse,
    ChartResponse,
    ExportMetadataResponse,
    VarianceRowResponse,
)

router = APIRouter(prefix='/charts', tags=['charts'])


class _ChartQueryParams(BaseModel):
    """Query parameters for chart endpoint."""

    chart_type: str | None = None
    kpi_code: list[str] | None = None
    periods: list[int] | None = None
    breakdown_key: str | None = None
    breakdown_period: str | None = None
    period_from: str | None = None
    period_to: str | None = None

    model_config = ConfigDict(extra='forbid')


async def _get_company_name(container: Any, company_id: str) -> str:
    """Get company display name."""
    doc_repo = getattr(container, 'document_repository', None)
    if doc_repo is not None:
        for method_name in ('get_company', 'fetch_company', 'load_company', 'find_company'):
            method = getattr(doc_repo, method_name, None)
            if not callable(method):
                continue
            try:
                result = await _await(method(company_id))
            except TypeError:
                try:
                    result = await _await(method(company_id=company_id))
                except (AttributeError, TypeError, ValueError):
                    continue
            if result is None:
                continue
            name = _get(result, 'name', 'company_name', 'display_name', 'company_display_name')
            if name is not None and str(name).strip():
                return str(name).strip()
    return company_id


async def _validate_chart_spec(chart_spec: Any, params: _ChartQueryParams) -> None:
    """Validate query parameters against chart spec."""
    if params.chart_type and params.chart_type != getattr(chart_spec, 'chart_type', None):
        raise HTTPException(
            status_code=400, detail=f'chart_type override not allowed: {params.chart_type}'
        )

    if params.kpi_code:
        allowed_codes = getattr(chart_spec, 'kpi_codes', [])
        for code in params.kpi_code:
            if code not in allowed_codes:
                raise HTTPException(status_code=400, detail=f'kpi_code not allowed by spec: {code}')

    if params.periods:
        supported = getattr(chart_spec, 'supported_periods', [])
        selectable = getattr(chart_spec, 'periods_selectable', [])
        for p in params.periods:
            if p not in supported and p not in selectable:
                raise HTTPException(status_code=400, detail=f'period not allowed by spec: {p}')

    if params.breakdown_key:
        allowed_keys = getattr(chart_spec, 'breakdown_keys', [])
        if params.breakdown_key not in allowed_keys:
            raise HTTPException(
                status_code=400, detail=f'breakdown_key not allowed by spec: {params.breakdown_key}'
            )


def _build_filters(chart_spec: Any, params: _ChartQueryParams) -> tuple[dict[str, Any], list[str]]:
    """Build filters for KPI query."""
    filters: dict[str, Any] = {}
    kpi_codes = params.kpi_code or getattr(chart_spec, 'kpi_codes', [])
    if kpi_codes:
        filters['kpi_codes'] = list(kpi_codes)
    if params.period_from:
        filters['period_from'] = params.period_from
    if params.period_to:
        filters['period_to'] = params.period_to
    return filters, kpi_codes


def _group_rows_by_kpi_and_period(
    rows: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[str]]:
    """Group rows by (kpi_code, chart_period) and return sorted periods."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row.get('kpi_code', ''), row.get('chart_period', ''))
        grouped[key].append(row)
    all_periods = sorted({row.get('chart_period', '') for row in rows})
    return grouped, all_periods


def _build_dataset(
    kpi_code_val: str,
    all_periods: list[str],
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    rows: list[dict[str, Any]],
) -> ChartDatasetResponse:
    """Build a single chart dataset for a KPI code."""
    points = []
    data_values = []
    for period in all_periods:
        period_rows = grouped.get((kpi_code_val, period), [])
        if period_rows:
            row = period_rows[0]
            value = str(row.get('value')) if row.get('value') is not None else None
            data_values.append(value)
            points.append(
                ChartPointResponse(
                    value=value,
                    period=row.get('period', ''),
                    chart_period=row.get('chart_period', ''),
                    source_citations=row.get('source_citations', []) or [],
                    computation_status=row.get('computation_status', ''),
                    display_label=None,
                    change=None,
                    change_direction=None,
                    share=None,
                    reason=None if value is not None else 'insufficient_data',
                )
            )
        else:
            data_values.append(None)
            points.append(
                ChartPointResponse(
                    value=None,
                    period='',
                    chart_period=period,
                    source_citations=[],
                    computation_status='needs_review',
                    display_label=None,
                    change=None,
                    change_direction=None,
                    share=None,
                    reason='insufficient_data',
                )
            )

    return ChartDatasetResponse(
        series_type='kpi',
        label=kpi_code_val.replace('_', ' ').title(),
        currency=rows[0].get('currency', '') if rows else '',
        units=rows[0].get('units', '') if rows else '',
        period=all_periods[0] if all_periods else '',
        data=data_values,
        points=points,
    )


def _build_export_metadata(
    company_name: str,
    company_slug: str,
    all_periods: list[str],
    datasets: list[ChartDatasetResponse],
) -> ExportMetadataResponse:
    """Build export metadata for chart response."""
    return ExportMetadataResponse(
        generated_at='2026-01-01T00:00:00Z',  # TODO(finsight): use actual timestamp (issue #378)
        company_name=company_name,
        company_slug=company_slug,
        period_range=f'{all_periods[0]} to {all_periods[-1]}' if all_periods else 'unknown',
        currency=datasets[0].currency if datasets else '',
        units=datasets[0].units if datasets else '',
        source_document_list=[],
    )


async def _fetch_chart_data(
    kpi_repository: Any,
    company_id: str,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fetch KPI rows for chart."""
    result = await _await(kpi_repository.get_current(company_id, filters))
    return [dict(row) for row in result] if result else []


def _build_datasets(
    kpi_codes: list[str],
    all_periods: list[str],
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    rows: list[dict[str, Any]],
) -> list[ChartDatasetResponse]:
    """Build all chart datasets."""
    return [_build_dataset(kpi_code_val, all_periods, grouped, rows) for kpi_code_val in kpi_codes]


def _build_chart_response(
    chart_id: str,
    all_periods: list[str],
    response_data: dict[str, Any],
) -> ChartResponse:
    """Build the chart response from a data dict."""
    return ChartResponse(
        contract_version=1,
        chart_id=chart_id,
        labels=all_periods,
        datasets=response_data['datasets'],
        variance_rows=response_data['variance_rows'],
        reason=None if response_data['has_rows'] else 'insufficient_data',
        export=response_data['export'],
    )


@router.get('/{chart_id}', operation_id='get_chart')
async def get_chart(
    chart_id: str,
    context: Any = None,
    params: _ChartQueryParams = Query(),
) -> ChartResponse:
    """Get chart series for the authenticated company."""
    company_id = await _require_company_id(context)
    role_id = await _require_role_id(context)

    config = _load_permissions_config()
    entry_dump = _get_role_entry(role_id, config)
    role_actions, _category_permissions = _extract_role_actions_and_categories(entry_dump)

    # Check kpi_view permission (charts require kpi_view)
    if not _check_action(role_actions, 'kpi_view'):
        raise HTTPException(status_code=403, detail='You do not have permission to view charts.')

    container = get_container()
    kpi_repository = getattr(container, 'kpi_repository', None)
    if kpi_repository is None:
        raise HTTPException(status_code=500, detail='KPI repository not configured.')

    # Get chart spec from config
    charts_config = getattr(config, 'charts', None)
    if charts_config is None or not hasattr(charts_config, 'specs'):
        raise HTTPException(status_code=500, detail='Charts configuration not found.')

    specs = charts_config.specs if hasattr(charts_config, 'specs') else {}
    if chart_id not in specs:
        raise HTTPException(status_code=404, detail=f'Chart spec not found: {chart_id}')

    chart_spec = specs[chart_id]

    # Validate query parameters
    await _validate_chart_spec(chart_spec, params)

    # Build filters and fetch KPI rows
    filters, kpi_codes = _build_filters(chart_spec, params)
    rows = await _fetch_chart_data(kpi_repository, company_id, filters)

    # Group rows and build datasets
    grouped, all_periods = _group_rows_by_kpi_and_period(rows)
    datasets = _build_datasets(kpi_codes, all_periods, grouped, rows)

    # Build variance rows if diverging (budget_vs_actual)
    variance_rows: list[VarianceRowResponse] = []
    diverging = getattr(chart_spec, 'diverging', False)
    if diverging and 'budget_vs_actual' in kpi_codes:
        # TODO(finsight): implement variance row computation (issue #378)
        pass

    # Get company name for export metadata
    company_name = await _get_company_name(container, company_id)
    company_slug = company_id[:8]  # Opaque identifier

    export = _build_export_metadata(company_name, company_slug, all_periods, datasets)

    response_data = {
        'datasets': datasets,
        'variance_rows': variance_rows,
        'export': export,
        'has_rows': bool(rows),
    }
    return _build_chart_response(chart_id, all_periods, response_data)


__all__ = ['router']
