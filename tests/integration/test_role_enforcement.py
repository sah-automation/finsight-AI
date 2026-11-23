"""Integration tests for Phase 2 role enforcement (issue #383)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from finsight.core.config import reset_config
from finsight.entrypoints.api import charts, dashboard, kpis
from finsight.entrypoints.api.api_principal import ApiPrincipal

pytestmark = pytest.mark.integration

COMPANY = '7e1a0000-0000-4000-8000-000000000001'
INVOICE_VERSION = '10000000-0000-4000-8000-000000000001'
BOARD_VERSION = '10000000-0000-4000-8000-000000000002'

HEADERS = {'x-company-id': COMPANY, 'x-role': 'corporate_finance_planners'}

EXPECTED_ROLE_ACTIONS: dict[str, set[str]] = {
    'executive_leadership': {
        'approve',
        'dashboard_view',
        'dashboard_edit_layout',
        'chart_export',
        'kpi_view',
        'kpi_export',
    },
    'corporate_finance_planners': {
        'dashboard_view',
        'dashboard_edit_layout',
        'chart_export',
        'kpi_view',
        'kpi_export',
        'document_purge',
    },
    'audit_compliance': {
        'view_audit_log',
        'dashboard_view',
        'chart_export',
        'kpi_view',
        'kpi_export',
    },
    'system_admin': {
        'manage_users',
        'manage_settings',
        'view_audit_log',
    },
}

SIX_ACTIONS = {
    'dashboard_view',
    'dashboard_edit_layout',
    'chart_export',
    'kpi_view',
    'kpi_export',
    'document_purge',
}


def _version(version_id: str, category: str) -> SimpleNamespace:
    return SimpleNamespace(document_version_id=version_id, category=category, state='committed')


def _row(
    *,
    kpi_code: str = 'revenue',
    document_version_id: str = INVOICE_VERSION,
) -> dict[str, Any]:
    return {
        'kpi_code': kpi_code,
        'period': '2025-Q1',
        'period_start': '2025-01-01',
        'chart_period': '2025-Q1',
        'chart_period_start': '2025-01-01',
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
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()


from finsight.entrypoints.api.current_user import _handle


@pytest.mark.parametrize('role', list(EXPECTED_ROLE_ACTIONS))
def test_current_user_role_actions_matrix(role: str, env: None) -> None:
    ctx = SimpleNamespace(company_id=COMPANY, company_name='Acme', role=role, user_id='user-1')

    result = asyncio.run(_handle(context=ctx))
    assert set(result.role_actions) == EXPECTED_ROLE_ACTIONS[role]
    for action in SIX_ACTIONS:
        assert (action in result.permission_actions) == (action in EXPECTED_ROLE_ACTIONS[role])


@pytest.fixture
def finance_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    app = FastAPI()
    app.include_router(kpis.router)
    app.include_router(dashboard.router)
    app.include_router(charts.router)
    return app


@pytest.mark.parametrize(
    'path',
    ['/kpis', '/charts/revenue_trend', '/dashboard/fingerprints', '/dashboard/layout'],
)
def test_system_admin_denied_financial_content(finance_app: FastAPI, path: str) -> None:
    client = TestClient(finance_app)
    headers = {'x-company-id': COMPANY, 'x-role': 'system_admin'}
    response = client.get(path, headers=headers)
    assert response.status_code == 403


def test_system_admin_denied_layout_put(finance_app: FastAPI) -> None:
    client = TestClient(finance_app)
    response = client.put(
        '/dashboard/layout',
        json={'contract_version': 1, 'kpi_codes': [], 'charts': [], 'version': 0},
        headers={'x-company-id': COMPANY, 'x-role': 'system_admin'},
    )
    assert response.status_code == 403


@pytest.fixture
def kpi_api(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    kpi_repository = SimpleNamespace()
    kpi_repository.rows = [
        _row(kpi_code='revenue', document_version_id=INVOICE_VERSION),
        _row(kpi_code='burn_rate', document_version_id=BOARD_VERSION),
    ]

    async def get_current(
        company_id: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        codes = filters.get('kpi_codes')
        rows = (
            kpi_repository.rows
            if not codes
            else [row for row in kpi_repository.rows if row.get('kpi_code') in codes]
        )
        return [dict(row) for row in rows]

    kpi_repository.get_current = get_current

    document_repository = SimpleNamespace()

    async def list_document_versions(company_id: str, **kwargs: Any) -> list[Any]:
        return [
            _version(INVOICE_VERSION, 'invoice'),
            _version(BOARD_VERSION, 'board_report'),
        ]

    document_repository.list_document_versions = list_document_versions

    container = SimpleNamespace(
        kpi_repository=kpi_repository,
        document_repository=document_repository,
    )
    monkeypatch.setattr(kpis, 'get_container', lambda: container)

    app = FastAPI()
    app.include_router(kpis.router)
    with TestClient(app) as client:
        yield client, app
    reset_config()


def test_kpi_visibility_filters_by_cited_category_and_scope(kpi_api: Any) -> None:
    client, app = kpi_api
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


def test_hidden_series_leaves_no_placeholder_or_count(kpi_api: Any) -> None:
    client, app = kpi_api
    # Override repository rows to only hidden
    container = kpis.get_container()
    container.kpi_repository.rows = [
        _row(kpi_code='burn_rate', document_version_id=BOARD_VERSION),
    ]

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
    body = response.json()
    assert body['items'] == []
    assert 'hidden_count' not in body
    assert 'omitted_count' not in body
    assert 'placeholder' not in str(body).lower()


def test_kpi_mixed_citation_row_is_dropped(kpi_api: Any) -> None:
    client, app = kpi_api
    mixed = _row(kpi_code='revenue', document_version_id=INVOICE_VERSION)
    mixed['source_citations'] = [
        f'cit:v1:{INVOICE_VERSION}:p1',
        f'cit:v1:{BOARD_VERSION}:p2',
    ]
    container = kpis.get_container()
    container.kpi_repository.rows = [mixed]

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
    assert response.json()['items'] == []


@pytest.fixture
def fingerprint_api(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()

    class _KpiRepository:
        def __init__(self, rows: list[dict[str, Any]]) -> None:
            self.rows = rows

        async def get_current(
            self, company_id: str, filters: dict[str, Any] | None = None
        ) -> list[dict[str, Any]]:
            filters = filters or {}
            codes = filters.get('kpi_codes')
            rows = (
                self.rows
                if not codes
                else [row for row in self.rows if row.get('kpi_code') in codes]
            )
            return [dict(row) for row in rows]

    class _DocumentRepository:
        def __init__(self, versions: list[Any]) -> None:
            self.versions = versions

        async def list_document_versions(self, company_id: str, **kwargs: Any) -> list[Any]:
            return list(self.versions)

    kpi_repository = _KpiRepository(
        [
            _row(kpi_code='revenue', document_version_id=INVOICE_VERSION),
            _row(kpi_code='burn_rate', document_version_id=BOARD_VERSION),
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
        yield client, app
    reset_config()


def test_fully_hidden_chart_omitted_from_fingerprints(fingerprint_api: Any) -> None:
    client, app = fingerprint_api
    principal = ApiPrincipal(
        company_id=COMPANY,
        user_id='user-1',
        role_id='corporate_finance_planners',
        access_scope=('invoice',),
        role_actions=('dashboard_view', 'kpi_view'),
        category_permissions={'invoice': ('read',), 'board_report': ('read',)},
    )
    app.dependency_overrides[dashboard.dashboard_view_dependency] = lambda: principal

    body = client.get('/dashboard/fingerprints', headers=HEADERS).json()

    assert 'revenue_trend' in body['charts']
    assert 'burn_comparison' not in body['charts']
