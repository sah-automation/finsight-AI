"""Unit tests for the current-user entrypoint."""

from __future__ import annotations

import asyncio

from finsight.entrypoints.api.current_user import CurrentUser, _handle


def test_current_user_returns_permissions_from_context() -> None:
    async def run() -> CurrentUser:
        class Ctx:
            company_id = 'company-1'
            company_name = 'Acme Corp'
            role = 'audit_compliance'
            user_id = 'user-1'

        return await _handle(context=Ctx())

    result = asyncio.run(run())
    assert result.company_id == 'company-1'
    assert result.company_name == 'Acme Corp'
    assert result.role == 'audit_compliance'
    assert 'view_audit_log' in result.permissions
    assert result.category_permissions['invoice'] == ['read', 'view_original']
