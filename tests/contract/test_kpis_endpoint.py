"""Contract tests for the ``GET /kpis`` endpoint (issue #379)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from finsight.core.config import reset_config
from finsight.core.config.loader import ConfigError
from finsight.entrypoints.api import action_permission, kpis
from finsight.entrypoints.api.api_principal import ApiPrincipal
from finsight.entrypoints.api.app import create_app

pytestmark = pytest.mark.contract

COMPANY = '7e1a0000-0000-4000-8000-000000000001'
INVOICE_VERSION = '10000000-0000-4000-8000-000000000001'
BOARD_VERSION = '10000000-0000-4000-8000-000000000002'

HEADERS = {'x-company-id': COMPANY, 'x-role': 'corporate_finance_planners'}


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
        return [dict(row) for row in self.rows]


class _DocumentRepository:
    def __init__(self, versions: list[Any]) -> None:
        self.versions = versions

    async def list_document_versions(self, company_id: str, **kwargs: Any) -> list[Any]:
        return list(self.versions)


def _version(version_id: str, category: str, state: str = 'committed') -> SimpleNamespace:
    return SimpleNamespace(document_version_id=version_id, category=category, state=state)


def _row(
    *,
    kpi_code: str = 'revenue',
    period_start: str = '2025-01-01',
    document_version_id: str = INVOICE_VERSION,
) -> dict[str, Any]:
    return {
        'kpi_code': kpi_code,
        'period': '2025-Q1',
        'period_start': period_start,
        'chart_period': '2025-Q1',
        'chart_period_start': period_start,
        'currency': 'USD',
        'units': 'USD',
        'value': '100.00',
        'source_citations': [f'cit:v1:{document_version_id}:p1'],
        'computation_status': 'computed',
        'document_version_id': document_version_id,
        'computation_rule_version': 'rule-v1',
        'created_at': '2025-01-02T00:00:00Z',
        'updated_at': '2025-01-02T00:00:00Z',
    }


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    kpi_repository = _KpiRepository(
        [
            _row(kpi_code='revenue'),
            _row(
                kpi_code='burn_rate', period_start='2025-04-01', document_version_id=BOARD_VERSION
            ),
        ]
    )
    document_repository = _DocumentRepository(
        [
            _version(INVOICE_VERSION, 'invoice'),
            _version(BOARD_VERSION, 'board_report'),
        ]
    )
    container = SimpleNamespace(
        kpi_repository=kpi_repository,
        document_repository=document_repository,
    )
    monkeypatch.setattr(kpis, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(kpis.router)
    with TestClient(app) as client:
        yield client, app, kpi_repository, document_repository
    reset_config()


def test_list_kpis_returns_contract_envelope_and_cursor_page(api: Any) -> None:
    client, _, kpi_repository, _ = api

    response = client.get('/kpis', params={'limit': 1}, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        'contract_version',
        'items',
        'next_cursor',
        'documents_processing',
        'actions',
    }
    assert body['contract_version'] == 1
    assert [item['kpi_code'] for item in body['items']] == ['burn_rate']
    assert isinstance(body['items'][0]['value'], str)
    assert body['items'][0]['value'] == '100.00'
    assert body['items'][0]['source_citations'] == [f'cit:v1:{BOARD_VERSION}:p1']
    assert isinstance(body['next_cursor'], str) and body['next_cursor']
    assert body['documents_processing'] is False
    assert body['actions'] == {'upload': True}
    assert kpi_repository.company_id == COMPANY


def test_list_kpis_uses_cursor_for_next_page(api: Any) -> None:
    client, _, _, _ = api

    first = client.get('/kpis', params={'limit': 1}, headers=HEADERS).json()
    second = client.get(
        '/kpis', params={'limit': 1, 'cursor': first['next_cursor']}, headers=HEADERS
    )

    assert second.status_code == 200
    assert [item['kpi_code'] for item in second.json()['items']] == ['revenue']
    assert second.json()['next_cursor'] is None


def test_query_filters_are_passed_to_repository(api: Any) -> None:
    client, _, kpi_repository, _ = api

    response = client.get(
        '/kpis',
        params={
            'kpi_code': 'revenue',
            'period_from': '2025-01-01',
            'period_to': '2025-03-31',
            'currency': 'USD',
            'units': 'USD',
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert kpi_repository.filters == {
        'kpi_codes': ['revenue'],
        'period_from': '2025-01-01',
        'period_to': '2025-03-31',
        'currency': 'USD',
        'units': 'USD',
    }


def test_documents_processing_covers_received_stored_and_processing(api: Any) -> None:
    client, _, _, document_repository = api
    document_repository.versions = [
        _version(INVOICE_VERSION, 'invoice', state='received'),
        _version(BOARD_VERSION, 'board_report', state='committed'),
    ]

    response = client.get('/kpis', headers=HEADERS)

    assert response.status_code == 200
    assert response.json()['documents_processing'] is True


def test_actions_upload_is_false_without_category_upload(api: Any) -> None:
    client, _, _, _ = api

    response = client.get(
        '/kpis', headers={'x-company-id': COMPANY, 'x-role': 'executive_leadership'}
    )

    assert response.status_code == 200
    assert response.json()['actions'] == {'upload': False}


def test_missing_kpi_view_is_denied_before_data_access(api: Any) -> None:
    client, _, kpi_repository, _ = api

    response = client.get('/kpis', headers={'x-company-id': COMPANY, 'x-role': 'system_admin'})

    assert response.status_code == 403
    assert kpi_repository.calls == 0


def test_unknown_role_is_denied(api: Any) -> None:
    client, _, kpi_repository, _ = api

    response = client.get('/kpis', headers={'x-company-id': COMPANY, 'x-role': 'unknown_role'})

    assert response.status_code == 403
    assert kpi_repository.calls == 0


def test_handler_rechecks_kpi_view(api: Any) -> None:
    client, app, kpi_repository, _ = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice', 'board_report'),
        role_actions=(),
        category_permissions={'invoice': ('read',), 'board_report': ('read',)},
    )
    app.dependency_overrides[kpis.kpi_view_dependency] = lambda: principal

    response = client.get('/kpis', headers=HEADERS)

    assert response.status_code == 403
    assert kpi_repository.calls == 0


def test_handler_filters_rows_by_cited_category_and_access_scope(api: Any) -> None:
    client, app, _, _ = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice',),
        role_actions=('kpi_view',),
        category_permissions={'invoice': ('read',), 'board_report': ('read',)},
    )
    app.dependency_overrides[kpis.kpi_view_dependency] = lambda: principal

    response = client.get('/kpis', headers=HEADERS)

    assert response.status_code == 200
    items = response.json()['items']
    assert [item['kpi_code'] for item in items] == ['revenue']
    assert all(item['document_version_id'] == INVOICE_VERSION for item in items)


def test_asgi_identity_overrides_dev_headers(api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, kpi_repository, _ = api
    monkeypatch.setattr(
        action_permission,
        'extract_identity',
        lambda _request: ('scope-company', 'user-1', 'corporate_finance_planners'),
    )

    response = client.get(
        '/kpis', headers={'x-company-id': 'header-company', 'x-role': 'system_admin'}
    )

    assert response.status_code == 200
    assert kpi_repository.company_id == 'scope-company'


def test_invalid_cursor_returns_bad_request(api: Any) -> None:
    client, _, _, _ = api

    response = client.get('/kpis', params={'cursor': 'not-a-cursor'}, headers=HEADERS)

    assert response.status_code == 400


def test_limit_above_configured_maximum_returns_bad_request(api: Any) -> None:
    client, _, _, _ = api

    response = client.get('/kpis', params={'limit': 101}, headers=HEADERS)

    assert response.status_code == 400


def test_router_publishes_limit_maximum_without_app_hook() -> None:
    app = FastAPI()
    app.include_router(kpis.router)

    parameters = app.openapi()['paths']['/kpis']['get']['parameters']
    limit_schema = next(
        parameter['schema'] for parameter in parameters if parameter['name'] == 'limit'
    )

    assert limit_schema['minimum'] == 1
    assert limit_schema['maximum'] == 100


def test_missing_kpi_config_returns_friendly_server_error(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, kpi_repository, _ = api

    def raise_config_error(*_args: Any, **_kwargs: Any) -> Any:
        raise ConfigError('configuration unavailable')

    monkeypatch.setattr(kpis, 'get_config', raise_config_error, raising=False)
    monkeypatch.setattr(kpis, 'load_config', raise_config_error, raising=False)

    response = client.get('/kpis', headers=HEADERS)

    assert response.status_code == 500
    assert response.json() == {'detail': 'Service configuration is unavailable.'}
    assert kpi_repository.calls == 0


def test_missing_repository_returns_friendly_server_error(
    api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _, document_repository = api
    monkeypatch.setattr(
        kpis,
        'get_container',
        lambda: SimpleNamespace(document_repository=document_repository),
    )

    response = client.get('/kpis', headers=HEADERS)

    assert response.status_code == 500
    assert response.json() == {'detail': 'KPI data is temporarily unavailable.'}


def test_openapi_schema_publishes_kpis_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()

    schema = create_app().openapi()
    operation = schema['paths']['/kpis']['get']
    parameters = {parameter['name']: parameter for parameter in operation['parameters']}

    assert operation['operationId'] == 'list_kpis'
    assert 'context' not in parameters
    assert parameters['kpi_code']['schema']['items']['enum'] == [
        'revenue',
        'gross_margin',
        'net_margin',
        'operating_expenses',
        'cash_flow',
        'burn_rate',
        'runway',
        'dso',
        'dpo',
        'budget_vs_actual',
    ]
    assert parameters['limit']['schema']['minimum'] == 1
    assert parameters['limit']['schema']['maximum'] == 100
    assert parameters['limit']['schema']['default'] == 50

    response_schema = operation['responses']['200']['content']['application/json']['schema']
    assert response_schema == {'$ref': '#/components/schemas/KpiListResponse'}
    list_schema = schema['components']['schemas']['KpiListResponse']
    assert set(list_schema['required']) == {
        'contract_version',
        'items',
        'next_cursor',
        'documents_processing',
        'actions',
    }
    assert list_schema['properties']['contract_version']['enum'] == [1]
    reset_config()
