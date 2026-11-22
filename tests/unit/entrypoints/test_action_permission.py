"""Unit tests for the shared API action permission dependency."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.requests import Request

from finsight.core.config import reset_config
from finsight.entrypoints.api.action_permission import ActionPermission, _scope_from_request

pytestmark = pytest.mark.unit


def test_scope_alias_from_asgi_scope_is_honored() -> None:
    request = SimpleNamespace(state=SimpleNamespace(), scope={'scope': ['invoice']})

    assert _scope_from_request(request) == ('invoice',)


def test_nested_access_scope_is_honored() -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(),
        scope={'context': {'accessScope': ['invoice']}},
    )

    assert _scope_from_request(request) == ('invoice',)


def test_invalid_scope_value_fails_closed() -> None:
    request = SimpleNamespace(state=SimpleNamespace(), scope={'access_scope': object()})

    assert _scope_from_request(request) == ()


def _claims_request(access_scope: Any) -> Request:
    claims = {
        'custom:company_id': 'claims-company',
        'sub': 'claims-user',
        'role': 'corporate_finance_planners',
        'custom:access_scope': access_scope,
    }
    return Request(
        {
            'type': 'http',
            'headers': [],
            'aws.event': {'requestContext': {'authorizer': {'claims': claims}}},
        }
    )


@pytest.mark.parametrize(
    ('claim_value', 'expected'),
    [
        ('invoice', ('invoice',)),
        ('["invoice"]', ('invoice',)),
        ('invoice, board_report', ('invoice', 'board_report')),
    ],
)
def test_authenticated_claim_scope_is_honored(
    monkeypatch: pytest.MonkeyPatch,
    claim_value: Any,
    expected: tuple[str, ...],
) -> None:
    monkeypatch.setenv('ENVIRONMENT', 'test')
    reset_config()

    principal = asyncio.run(ActionPermission('kpi_view')(_claims_request(claim_value)))

    assert principal.access_scope == expected
    reset_config()
