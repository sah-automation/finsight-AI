"""API entrypoint for chart series (Phase 2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from finsight.application.chart_series_builder import ChartSeriesBuilder
from finsight.application.kpi_visibility_filter import KpiVisibilityFilter
from finsight.composition.container import get_container
from finsight.core.config import get_config, load_config
from finsight.core.config.loader import ConfigError
from finsight.core.config.models.chart_spec import ChartType  # noqa: TC001
from finsight.domain.services.kpi_computation_service import KpiComputationService

from ._shared import _await, _get
from .action_permission import ActionPermission
from .api_principal import ApiPrincipal  # noqa: TC001
from .charts_response import (
    ChartDataset,
    ChartResponse,
    ExportMetadata,
    VarianceRow,
)

if TYPE_CHECKING:
    from finsight.core.config.models.chart_spec import ChartSpec

router = APIRouter(prefix='/charts', tags=['charts'])
kpi_view_dependency = ActionPermission('kpi_view')

_VERSION_ID_FIELDS = ('document_version_id', 'version_id', 'id')
_CATEGORY_FIELDS = ('category', 'document_category')
_STATE_FIELDS = ('state', 'status', 'document_status')
_TITLE_FIELDS = ('title', 'document_title')
_DOCUMENT_VERSION_FIELDS = ('version', 'document_version')
_MAX_PERIOD_SELECTIONS = 4
_CITATION_MIN_PARTS = 3


class _ChartQueryParams(BaseModel):
    """Query parameters for the chart endpoint, bounded by the resolved spec."""

    chart_type: ChartType | None = None
    kpi_code: list[str] | None = None
    periods: list[int] | None = None
    breakdown_key: str | None = None
    breakdown_period: str | None = None
    period_from: str | None = None
    period_to: str | None = None

    model_config = ConfigDict(extra='forbid')


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field(source: Any, *names: str) -> Any:
    if isinstance(source, Mapping):
        for name in names:
            if source.get(name) is not None:
                return source.get(name)
        return None
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _opaque_slug() -> str:
    """Return an opaque export slug that is not derived from company data."""

    return uuid4().hex[:12]


def _load_chart_spec(chart_id: str) -> ChartSpec:
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
    specs = getattr(charts_config, 'specs', None)
    if specs is None:
        raise HTTPException(status_code=500, detail='Service configuration is unavailable.')
    spec = specs.get(chart_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f'Chart spec not found: {chart_id}')
    return cast('ChartSpec', spec)


def _validate_overrides(spec: ChartSpec, params: _ChartQueryParams) -> None:
    if params.chart_type is not None and params.chart_type != spec.chart_type:
        raise HTTPException(status_code=400, detail='chart_type override not allowed by spec.')
    for code in params.kpi_code or ():
        if code not in spec.kpi_codes:
            raise HTTPException(status_code=400, detail=f'kpi_code not allowed by spec: {code}')
    allowed = set(spec.supported_periods) | set(spec.periods_selectable)
    if len(params.periods or ()) > _MAX_PERIOD_SELECTIONS or any(
        period not in allowed for period in params.periods or ()
    ):
        raise HTTPException(status_code=400, detail='periods not allowed by spec.')
    if params.breakdown_key is not None and params.breakdown_key not in spec.breakdown_keys:
        raise HTTPException(status_code=400, detail='breakdown_key not allowed by spec.')


def _build_filters(kpi_codes: Sequence[str], params: _ChartQueryParams) -> dict[str, Any]:
    filters: dict[str, Any] = {'kpi_codes': list(kpi_codes)}
    if params.period_from:
        filters['period_from'] = params.period_from
    if params.period_to:
        filters['period_to'] = params.period_to
    return filters


def _row_period(row: Mapping[str, Any]) -> str:
    return _text(row.get('chart_period')) or _text(row.get('period')) or ''


def _select_periods(rows: list[dict[str, Any]], params: _ChartQueryParams) -> list[dict[str, Any]]:
    selected = rows
    if params.periods:
        available = sorted({_row_period(row) for row in selected} - {''})
        keep = set(available[-max(params.periods) :])
        selected = [row for row in selected if _row_period(row) in keep]
    if params.breakdown_period:
        wanted = params.breakdown_period
        selected = [
            row for row in selected if wanted in (_row_period(row), _text(row.get('period')) or '')
        ]
    return selected


async def _get_company_name(container: Any, company_id: str) -> str:
    doc_repo = getattr(container, 'document_repository', None)
    if doc_repo is not None and callable(getattr(doc_repo, 'get_company', None)):
        company = await _await(doc_repo.get_company(company_id))
        name = _text(_get(company, 'name', 'company_name', 'display_name'))
        if name is not None:
            return name
    return company_id


async def _visible_rows(
    container: Any,
    company_id: str,
    principal: ApiPrincipal,
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[Any]]:
    doc_repo = getattr(container, 'document_repository', None)
    versions: list[Any] = []
    if doc_repo is not None and callable(getattr(doc_repo, 'list_document_versions', None)):
        versions = list(await _await(doc_repo.list_document_versions(company_id)) or ())
    kpi_repo = getattr(container, 'kpi_repository', None)
    if kpi_repo is None:
        raise HTTPException(status_code=500, detail='KPI data is temporarily unavailable.')
    rows = list(await _await(kpi_repo.get_current(company_id, filters)) or ())
    visibility = KpiVisibilityFilter(
        category_permissions=principal.category_permissions,
        access_scope=principal.access_scope,
    )
    return visibility.filter(rows, versions), versions


def _version_index(versions: Sequence[Any]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for version in versions:
        version_id = _text(_field(version, *_VERSION_ID_FIELDS))
        if version_id is None:
            continue
        index[version_id] = {
            'category': _text(_field(version, *_CATEGORY_FIELDS)) or '',
            'state': _text(_field(version, *_STATE_FIELDS)) or '',
            'title': _text(_field(version, *_TITLE_FIELDS)) or '',
            'version': _text(_field(version, *_DOCUMENT_VERSION_FIELDS)) or '',
        }
    return index


def _prepare_rows(
    rows: Sequence[dict[str, Any]],
    versions: Sequence[Any],
    breakdown_key: str | None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    index = _version_index(versions)
    statuses = {version_id: meta['state'] for version_id, meta in index.items() if meta['state']}
    prepared: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        category = index.get(_text(row.get('document_version_id')) or '', {}).get('category')
        if breakdown_key and category:
            enriched[breakdown_key] = category
        prepared.append(enriched)
    labelled = KpiComputationService('chart').apply_display_labels(
        prepared, document_statuses=statuses
    )
    return labelled, index


def _source_documents(
    rows: Sequence[dict[str, Any]],
    versions: Sequence[Any],
    index: Mapping[str, dict[str, str]],
) -> list[dict[str, str]]:
    referenced: set[str] = set()
    for row in rows:
        version_id = _text(row.get('document_version_id'))
        if version_id:
            referenced.add(version_id)
        for citation in row.get('source_citations') or ():
            parts = str(citation).split(':')
            if str(citation).startswith('cit:v1:') and len(parts) >= _CITATION_MIN_PARTS:
                referenced.add(parts[2])
    documents: list[dict[str, str]] = []
    for version in versions:
        version_id = _text(_field(version, *_VERSION_ID_FIELDS))
        if version_id not in referenced:
            continue
        meta = index.get(version_id, {})
        if meta.get('title') or meta.get('version'):
            documents.append({'title': meta.get('title', ''), 'version': meta.get('version', '')})
    return documents


def _build_export_metadata(
    company_name: str,
    labels: Sequence[str],
    datasets: Sequence[ChartDataset],
    source_documents: Sequence[dict[str, str]],
) -> ExportMetadata:
    return ExportMetadata(
        generated_at=_utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        company_name=company_name,
        company_slug=_opaque_slug(),
        period_range=f'{labels[0]} to {labels[-1]}' if labels else 'unknown',
        currency=datasets[0].currency if datasets else '',
        units=datasets[0].units if datasets else '',
        source_document_list=list(source_documents),
    )


def _serialize_response(
    chart_id: str, series: dict[str, Any], export: ExportMetadata
) -> ChartResponse:
    return ChartResponse(
        contract_version=1,
        chart_id=chart_id,
        labels=list(series['labels']),
        datasets=[ChartDataset(**item) for item in series['datasets']],
        variance_rows=[VarianceRow(**item) for item in series['variance_rows']],
        reason=series['reason'],
        export=export,
    )


@router.get('/{chart_id}', operation_id='get_chart', response_model=ChartResponse)
async def get_chart(
    chart_id: str,
    principal: ApiPrincipal = Depends(kpi_view_dependency),
    params: _ChartQueryParams = Query(),
) -> ChartResponse:
    """Get chart series for the authenticated company."""
    if 'kpi_view' not in principal.role_actions:
        raise HTTPException(status_code=403, detail='You do not have permission to view charts.')
    spec = _load_chart_spec(chart_id)
    _validate_overrides(spec, params)
    kpi_codes = list(params.kpi_code or spec.kpi_codes)
    breakdown_key = params.breakdown_key or (
        spec.breakdown_keys[0]
        if spec.chart_type == 'breakdown_bar' and spec.breakdown_keys
        else None
    )
    container = get_container()
    rows, versions = await _visible_rows(
        container, principal.company_id, principal, _build_filters(kpi_codes, params)
    )
    rows, index = _prepare_rows(_select_periods(rows, params), versions, breakdown_key)
    series = ChartSeriesBuilder().build(
        rows,
        kpi_codes=kpi_codes,
        polarity=spec.polarity,
        diverging=spec.diverging,
        breakdown_key=breakdown_key,
    )
    datasets = [ChartDataset(**item) for item in series['datasets']]
    export = _build_export_metadata(
        await _get_company_name(container, principal.company_id),
        series['labels'],
        datasets,
        _source_documents(rows, versions, index),
    )
    return _serialize_response(chart_id, series, export)


__all__ = ['kpi_view_dependency', 'router']
