"""Contract tests for the ``GET /charts/{chart_id}`` endpoint (issue #380)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from finsight.core.config import reset_config
from finsight.core.config.loader import ConfigError
from finsight.entrypoints.api import action_permission, charts
from finsight.entrypoints.api import app as app_module
from finsight.entrypoints.api.api_principal import ApiPrincipal
from finsight.entrypoints.api.app import create_app

pytestmark = pytest.mark.contract

COMPANY = '7e1a0000-0000-4000-8000-000000000001'
INVOICE_VERSION = '10000000-0000-4000-8000-000000000001'
BOARD_VERSION = '10000000-0000-4000-8000-000000000002'
BUDGET_VERSION = '10000000-0000-4000-8000-000000000003'

HEADERS = {'x-company-id': COMPANY, 'x-role': 'corporate_finance_planners'}
FIXED_NOW = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)


class _KpiRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.company_id: str | None = None
        self.filters: dict[str, Any] | None = None
        self.calls = 0

    async def get_current(
        self, company_id: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        self.company_id = company_id
        self.filters = filters or {}
        self.calls += 1
        codes = self.filters.get('kpi_codes')
        rows = (
            self.rows if not codes else [row for row in self.rows if row.get('kpi_code') in codes]
        )
        return [dict(row) for row in rows]


class _DocumentRepository:
    def __init__(self, versions: list[Any]) -> None:
        self.versions = versions

    async def list_document_versions(self, company_id: str, **kwargs: Any) -> list[Any]:
        return list(self.versions)

    async def get_company(self, company_id: str) -> Any:
        return SimpleNamespace(name='Acme Finance Ltd')


def _version(version_id: str, category: str, title: str) -> Any:
    return SimpleNamespace(
        document_version_id=version_id,
        category=category,
        state='committed',
        title=title,
        version='1',
    )


def _row(
    *,
    kpi_code: str = 'revenue',
    value: str | None = '100.00',
    period: str = '2025-Q1',
    version: str = INVOICE_VERSION,
    **extra: Any,
) -> dict[str, Any]:
    quarter = int(period[-1])
    start = f'{period[:4]}-{(quarter - 1) * 3 + 1:02d}-01'
    row: dict[str, Any] = {
        'kpi_code': kpi_code,
        'period': period,
        'chart_period': period,
        'chart_period_start': start,
        'currency': 'USD',
        'units': 'USD',
        'value': value,
        'source_citations': [f'cit:v1:{version}:p1'],
        'computation_status': 'computed',
        'document_version_id': version,
    }
    row.update(extra)
    return row


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep config loading hermetic when tests run in isolation or in a full suite."""

    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    yield
    reset_config()


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Any:
    kpi_repository = _KpiRepository(
        [
            _row(),
            _row(value='150.00', period='2025-Q2'),
            _row(kpi_code='burn_rate', value='60.00', version=BOARD_VERSION),
            _row(kpi_code='gross_margin', value='10.00', period='2025-Q1'),
            _row(kpi_code='gross_margin', value='11.00', period='2025-Q2'),
            _row(kpi_code='gross_margin', value='12.00', period='2025-Q3'),
            _row(kpi_code='gross_margin', value='13.00', period='2025-Q4'),
            _row(
                kpi_code='budget_vs_actual',
                value='20.00',
                version=BUDGET_VERSION,
                name='Revenue',
                actual='120.00',
                budget='100.00',
            ),
        ]
    )
    document_repository = _DocumentRepository(
        [
            _version(INVOICE_VERSION, 'invoice', 'Q1 Management Report'),
            _version(BOARD_VERSION, 'board_report', 'Board Pack'),
            _version(BUDGET_VERSION, 'budget', 'FY2025 Budget'),
        ]
    )
    container = SimpleNamespace(
        kpi_repository=kpi_repository,
        document_repository=document_repository,
    )
    monkeypatch.setattr(charts, 'get_container', lambda: container)
    monkeypatch.setattr(charts, '_utc_now', lambda: FIXED_NOW)
    monkeypatch.setattr(charts, '_opaque_slug', lambda: 'opaque-1234')

    app = FastAPI()
    app.include_router(charts.router)
    with TestClient(app) as client:
        yield client, app, kpi_repository
    reset_config()


def test_get_chart_returns_the_contract_envelope(api: Any) -> None:
    client, _, repository = api

    response = client.get('/charts/revenue_trend', headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        'contract_version',
        'chart_id',
        'labels',
        'datasets',
        'variance_rows',
        'reason',
        'export',
    }
    assert body['contract_version'] == 1
    assert body['chart_id'] == 'revenue_trend'
    assert body['labels'] == ['2025-Q1', '2025-Q2']
    assert body['variance_rows'] == []
    assert body['reason'] is None
    assert repository.company_id == COMPANY

    dataset = body['datasets'][0]
    assert set(dataset) == {
        'series_type',
        'label',
        'currency',
        'units',
        'period',
        'data',
        'points',
    }
    assert dataset['series_type'] == 'kpi'
    assert dataset['data'] == ['100.00', '150.00']
    point = dataset['points'][0]
    assert set(point) == {
        'value',
        'period',
        'chart_period',
        'source_citations',
        'computation_status',
        'display_label',
        'change',
        'change_direction',
        'share',
        'reason',
    }
    assert point['source_citations'] == [f'cit:v1:{INVOICE_VERSION}:p1']


def test_point_change_direction_and_share_are_server_computed(api: Any) -> None:
    client, _, _ = api

    body = client.get('/charts/revenue_trend', headers=HEADERS).json()
    points = body['datasets'][0]['points']

    assert points[0]['change'] is None
    assert points[1]['change'] == '50.00'
    assert points[1]['change_direction'] == 'good'
    assert [point['share'] for point in points] == ['40.00', '60.00']


def test_budget_variance_returns_server_computed_variance_rows(api: Any) -> None:
    client, _, _ = api

    body = client.get('/charts/budget_variance', headers=HEADERS).json()

    assert body['variance_rows'] == [
        {
            'name': 'Revenue',
            'actual': '120.00',
            'budget': '100.00',
            'variance': '20.00',
            'favourable': False,
        }
    ]


def test_export_metadata_is_server_generated_and_content_scoped(api: Any) -> None:
    client, _, _ = api

    export = client.get('/charts/revenue_trend', headers=HEADERS).json()['export']

    assert set(export) == {
        'generated_at',
        'company_name',
        'company_slug',
        'period_range',
        'currency',
        'units',
        'source_document_list',
    }
    assert export['generated_at'] == '2026-02-03T04:05:06Z'
    assert export['company_name'] == 'Acme Finance Ltd'
    assert export['company_slug'] == 'opaque-1234'
    assert export['company_slug'] not in COMPANY
    assert export['period_range'] == '2025-Q1 to 2025-Q2'
    assert export['source_document_list'] == [{'title': 'Q1 Management Report', 'version': '1'}]


@pytest.mark.parametrize(
    ('params', 'status'),
    [
        ({'chart_type': 'breakdown_pie'}, 422),
        ({'chart_type': 'comparison_bar'}, 400),
        ({'kpi_code': 'burn_rate'}, 400),
        ({'periods': [2, 99]}, 400),
        ({'periods': [99]}, 400),
        ({'breakdown_key': 'document_category'}, 400),
    ],
)
def test_overrides_are_validated_against_the_spec(
    api: Any, params: dict[str, Any], status: int
) -> None:
    client, _, repository = api

    response = client.get('/charts/revenue_trend', params=params, headers=HEADERS)

    assert response.status_code == status
    if status == 400:
        assert repository.calls == 0


def test_unknown_chart_id_is_not_found(api: Any) -> None:
    client, _, _ = api

    response = client.get('/charts/not_a_chart', headers=HEADERS)

    assert response.status_code == 404


def test_allowed_overrides_select_series_and_periods(api: Any) -> None:
    client, _, _ = api

    body = client.get(
        '/charts/margin_trend',
        params={'kpi_code': ['gross_margin'], 'periods': [2]},
        headers=HEADERS,
    ).json()

    assert [dataset['label'] for dataset in body['datasets']] == ['Gross Margin']
    assert body['labels'] == ['2025-Q3', '2025-Q4']


def test_missing_kpi_view_is_denied_before_data_access(api: Any) -> None:
    client, _, repository = api

    response = client.get(
        '/charts/revenue_trend', headers={'x-company-id': COMPANY, 'x-role': 'system_admin'}
    )

    assert response.status_code == 403
    assert repository.calls == 0


def test_handler_rechecks_kpi_view(api: Any) -> None:
    client, app, repository = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice',),
        role_actions=(),
        category_permissions={'invoice': ('read',)},
    )
    app.dependency_overrides[charts.kpi_view_dependency] = lambda: principal

    response = client.get('/charts/revenue_trend', headers=HEADERS)

    assert response.status_code == 403
    assert repository.calls == 0


def test_hidden_citations_drop_series_and_export_entries(api: Any) -> None:
    client, app, _ = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice',),
        role_actions=('kpi_view',),
        category_permissions={'invoice': ('read',), 'board_report': ('read',)},
    )
    app.dependency_overrides[charts.kpi_view_dependency] = lambda: principal

    revenue = client.get('/charts/revenue_trend', headers=HEADERS).json()
    variance = client.get('/charts/budget_variance', headers=HEADERS).json()

    assert [dataset['label'] for dataset in revenue['datasets']] == ['Revenue']
    assert revenue['export']['source_document_list'] == [
        {'title': 'Q1 Management Report', 'version': '1'}
    ]
    assert variance['reason'] == 'insufficient_data'
    assert variance['datasets'] == []
    assert variance['variance_rows'] == []
    assert variance['export']['source_document_list'] == []


def test_empty_data_is_a_normal_200(api: Any) -> None:
    client, _, repository = api
    repository.rows = []

    response = client.get('/charts/revenue_trend', headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body['labels'] == []
    assert body['datasets'] == []
    assert body['reason'] == 'insufficient_data'


def test_missing_chart_config_returns_friendly_error(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, repository = api

    def raise_config_error(*_args: Any, **_kwargs: Any) -> Any:
        raise ConfigError('configuration unavailable')

    monkeypatch.setattr(charts, 'get_config', raise_config_error, raising=False)
    monkeypatch.setattr(charts, 'load_config', raise_config_error, raising=False)

    response = client.get('/charts/revenue_trend', headers=HEADERS)

    assert response.status_code == 500
    assert response.json() == {'detail': 'Service configuration is unavailable.'}
    assert repository.calls == 0


def test_asgi_identity_overrides_dev_headers(api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, repository = api
    monkeypatch.setattr(
        action_permission,
        'extract_identity',
        lambda _request: ('scope-company', 'user-1', 'corporate_finance_planners'),
    )

    client.get(
        '/charts/revenue_trend',
        headers={'x-company-id': 'header-company', 'x-role': 'system_admin'},
    )

    assert repository.company_id == 'scope-company'


def test_openapi_schema_publishes_the_chart_contract() -> None:
    schema = create_app().openapi()
    operation = schema['paths']['/charts/{chart_id}']['get']
    parameters = {parameter['name']: parameter for parameter in operation['parameters']}

    assert operation['operationId'] == 'get_chart'
    assert 'context' not in parameters
    assert parameters['chart_type']['schema']['enum'] == [
        'trend_line',
        'comparison_bar',
        'breakdown_bar',
    ]
    response_schema = operation['responses']['200']['content']['application/json']['schema']
    assert response_schema == {'$ref': '#/components/schemas/ChartResponse'}

    components = schema['components']['schemas']
    assert set(components['ChartResponse']['required']) == {
        'contract_version',
        'chart_id',
        'labels',
        'datasets',
        'variance_rows',
        'reason',
        'export',
    }
    assert components['ChartPoint']['properties']['change_direction']['enum'] == ['good', 'bad']
    assert components['ChartDataset']['properties']['series_type']['enum'] == [
        'kpi',
        'forecast',
        'anomaly',
    ]
    assert components['VarianceRow']['required'] == [
        'name',
        'actual',
        'budget',
        'variance',
        'favourable',
    ]
    assert set(components['ExportMetadata']['required']) == {
        'generated_at',
        'company_name',
        'company_slug',
        'period_range',
        'currency',
        'units',
        'source_document_list',
    }


def test_installed_chart_schema_helper_is_hermetic() -> None:
    app = FastAPI()
    app.include_router(charts.router)
    config = SimpleNamespace(charts=SimpleNamespace(specs={}))
    app_module._install_chart_openapi_schema(app, config)

    operation = app.openapi()['paths']['/charts/{chart_id}']['get']
    parameter = next(item for item in operation['parameters'] if item['name'] == 'chart_type')
    assert parameter['schema']['enum'] == ['trend_line', 'comparison_bar', 'breakdown_bar']
