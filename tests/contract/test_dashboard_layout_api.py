"""Contract tests for the ``PUT /dashboard/layout`` 409 conflict body (issue #384).

Phase 2 spec §4.4 declares the stale-save response as a top-level
``{error: layout_changed, current_layout}`` object. FastAPI's default
``HTTPException`` handler would wrap that in ``{"detail": ...}``, so the handler
must return the conflict body directly. These tests lock that wire shape and the
fallback that still supplies a ``current_layout`` when none can be read.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from finsight.core.config import reset_config
from finsight.core.errors import LayoutConflictError
from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_record import LayoutRecord
from finsight.entrypoints.api import dashboard
from finsight.entrypoints.api.app import create_app

pytestmark = pytest.mark.contract

COMPANY = '7e1a0000-0000-4000-8000-000000000001'
HEADERS = {'x-company-id': COMPANY, 'x-role': 'corporate_finance_planners'}
PAYLOAD = {'contract_version': 1, 'kpi_codes': ['revenue'], 'charts': [], 'version': 0}


class _LayoutRepository:
    """Fake layout store whose save always loses the optimistic-version race."""

    def __init__(self, conflict_layout: Any, read_result: Any = None) -> None:
        self.conflict_layout = conflict_layout
        self.read_result = read_result

    async def get_layout(self, company_id: Any, user_id: Any, *, visible_ids: Any) -> Any:
        return self.read_result

    async def save_layout(
        self,
        company_id: Any,
        user_id: Any,
        layout: Any,
        expected_version: int,
        *,
        visible_ids: Any,
    ) -> Any:
        raise LayoutConflictError(self.conflict_layout)


def _client(monkeypatch: pytest.MonkeyPatch, repository: _LayoutRepository) -> TestClient:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    container = SimpleNamespace(dashboard_layout_repository=repository)
    monkeypatch.setattr(dashboard, 'get_container', lambda: container)
    app = FastAPI()
    app.include_router(dashboard.router)
    return TestClient(app)


def test_stale_save_returns_top_level_conflict_with_current_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = LayoutRecord(
        contract_version=1,
        kpi_codes=('revenue',),
        charts=(LayoutChart(chart_id='revenue_trend', span='full'),),
        version=2,
        updated_at=None,
    )
    client = _client(monkeypatch, _LayoutRepository(current))

    response = client.put('/dashboard/layout', json=PAYLOAD, headers=HEADERS)

    assert response.status_code == 409
    body = response.json()
    # Top-level contract body, not FastAPI's {"detail": ...} wrapper.
    assert set(body) == {'error', 'current_layout'}
    assert body['error'] == 'layout_changed'
    assert body['current_layout']['contract_version'] == 1
    assert body['current_layout']['version'] == 2
    assert body['current_layout']['kpi_codes'] == ['revenue']
    reset_config()


def test_stale_save_without_readable_layout_still_returns_current_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No layout carried on the error and none readable: the handler must still
    # supply a current_layout (the role-filtered config default) per §4.4.
    client = _client(monkeypatch, _LayoutRepository(None, read_result=None))

    response = client.put('/dashboard/layout', json=PAYLOAD, headers=HEADERS)

    assert response.status_code == 409
    body = response.json()
    assert set(body) == {'error', 'current_layout'}
    assert body['error'] == 'layout_changed'
    assert body['current_layout']['contract_version'] == 1
    assert isinstance(body['current_layout']['kpi_codes'], list)
    assert isinstance(body['current_layout']['charts'], list)
    reset_config()


def test_published_409_schema_matches_the_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()
    schema = create_app().openapi()
    operation = schema['paths']['/dashboard/layout']['put']
    conflict_ref = operation['responses']['409']['content']['application/json']['schema']
    assert conflict_ref == {'$ref': '#/components/schemas/LayoutConflictResponse'}

    conflict = schema['components']['schemas']['LayoutConflictResponse']
    assert set(conflict['required']) == {'error', 'current_layout'}
    assert conflict['properties']['error']['enum'] == ['layout_changed']
    assert conflict['properties']['current_layout'] == {
        '$ref': '#/components/schemas/LayoutResponse'
    }
    reset_config()
