"""Unit tests for the shared API action permission dependency."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from finsight.entrypoints.api.action_permission import _scope_from_request

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
