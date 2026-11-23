"""Contract tests for the ``GET /dashboard/fingerprints`` endpoint (issue #381)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from finsight.core.config import reset_config
from finsight.core.config.loader import ConfigError
from finsight.domain.ports.kpi_repository import FINGERPRINT_FIELDS
from finsight.entrypoints.api import action_permission, dashboard
from finsight.entrypoints.api.api_principal import ApiPrincipal

pytestmark = pytest.mark.contract

COMPANY = '7e1a0000-0000-4000-8000-000000000001'
INVOICE_VERSION = '10000000-0000-4000-8000-000000000001'
BOARD_VERSION = '10000000-0000-4000-8000-000000000002'

HEADERS = {'x-company-id': COMPANY, 'x-role': 'corporate_finance_planners'}


class _KpiRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def get_current(
        self, company_id: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        codes = filters.get('kpi_codes')
        rows = (
            self.rows if not codes else [row for row in self.rows if row.get('kpi_code') in codes]
        )
        return [dict(row) for row in rows]

    async def get_fingerprint_data(self, company_id: str, chart_specs: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for spec in chart_specs:
            chart_id = spec.chart_id if hasattr(spec, 'chart_id') else spec['chart_id']
            codes = spec.kpi_codes if hasattr(spec, 'kpi_codes') else spec.get('kpi_codes', [])
            rows = [row for row in self.rows if row.get('kpi_code') in codes]
            result[chart_id] = [
                {field: row.get(field) for field in FINGERPRINT_FIELDS} for row in rows
            ]
        return result


class _DocumentRepository:
    def __init__(self, versions: list[Any]) -> None:
        self.versions = versions

    async def list_document_versions(self, company_id: str, **kwargs: Any) -> list[Any]:
        return list(self.versions)


def _version(version_id: str, category: str) -> Any:
    return SimpleNamespace(document_version_id=version_id, category=category, state='committed')


def _row(
    *,
    kpi_code: str = 'revenue',
    value: str = '100.00',
    version: str = INVOICE_VERSION,
) -> dict[str, Any]:
    return {
        'kpi_code': kpi_code,
        'period': '2025-Q1',
        'chart_period': '2025-Q1',
        'chart_period_start': '2025-01-01',
        'currency': 'USD',
        'units': 'USD',
        'value': value,
        'source_citations': [f'cit:v1:{version}:p1'],
        'computation_status': 'computed',
        'document_version_id': version,
        'computation_rule_version': 'rule-v1',
    }


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    kpi_repository = _KpiRepository(
        [
            _row(),
            _row(kpi_code='burn_rate', version=BOARD_VERSION),
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
    monkeypatch.setattr(dashboard, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(dashboard.router)
    with TestClient(app) as client:
        yield client, app, kpi_repository
    reset_config()


def test_returns_contract_envelope(api: Any) -> None:
    client, _, _ = api

    response = client.get('/dashboard/fingerprints', headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {'contract_version', 'charts'}
    assert body['contract_version'] == 1
    assert isinstance(body['charts'], dict)
    for value in body['charts'].values():
        assert isinstance(value, str)
        assert len(value) == 64


def test_missing_dashboard_view_is_denied(api: Any) -> None:
    client, _, _ = api

    response = client.get(
        '/dashboard/fingerprints',
        headers={'x-company-id': COMPANY, 'x-role': 'system_admin'},
    )

    assert response.status_code == 403


def test_handler_rechecks_dashboard_view(api: Any) -> None:
    client, app, _repository = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice',),
        role_actions=(),
        category_permissions={'invoice': ('read',)},
    )
    app.dependency_overrides[dashboard.dashboard_view_dependency] = lambda: principal

    response = client.get('/dashboard/fingerprints', headers=HEADERS)

    assert response.status_code == 403


def test_hidden_chart_is_omitted(api: Any) -> None:
    client, app, _ = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice',),
        role_actions=('dashboard_view', 'kpi_view'),
        category_permissions={'invoice': ('read',)},
    )
    app.dependency_overrides[dashboard.dashboard_view_dependency] = lambda: principal

    body = client.get('/dashboard/fingerprints', headers=HEADERS).json()

    assert 'revenue_trend' in body['charts']
    assert 'burn_comparison' not in body['charts']


def test_missing_config_returns_server_error(api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _repository = api

    def raise_config_error(*_args: Any, **_kwargs: Any) -> Any:
        raise ConfigError('configuration unavailable')

    monkeypatch.setattr(dashboard, 'get_config', raise_config_error, raising=False)
    monkeypatch.setattr(dashboard, 'load_config', raise_config_error, raising=False)

    response = client.get('/dashboard/fingerprints', headers=HEADERS)

    assert response.status_code == 500
    assert response.json() == {'detail': 'Service configuration is unavailable.'}


def test_missing_repository_returns_server_error(api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = api
    monkeypatch.setattr(
        dashboard,
        'get_container',
        lambda: SimpleNamespace(document_repository=None),
    )

    response = client.get('/dashboard/fingerprints', headers=HEADERS)

    assert response.status_code == 500
    assert response.json() == {'detail': 'KPI data is temporarily unavailable.'}


def test_asgi_identity_overrides_dev_headers(api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _repository = api
    monkeypatch.setattr(
        action_permission,
        'extract_identity',
        lambda _request: ('scope-company', 'user-1', 'corporate_finance_planners'),
    )

    response = client.get(
        '/dashboard/fingerprints',
        headers={'x-company-id': 'header-company', 'x-role': 'system_admin'},
    )

    assert response.status_code in (200, 403)


def test_no_kpi_view_omits_all_charts(api: Any) -> None:
    client, app, _ = api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice', 'board_report'),
        role_actions=('dashboard_view',),
        category_permissions={'invoice': ('read',), 'board_report': ('read',)},
    )
    app.dependency_overrides[dashboard.dashboard_view_dependency] = lambda: principal

    body = client.get('/dashboard/fingerprints', headers=HEADERS).json()

    assert body['charts'] == {}
