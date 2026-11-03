from __future__ import annotations

import asyncio

from finsight.application.source_viewer import StepResult
from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.steps.authorize_step import AuthorizeStep


def _step(permission_policy=None) -> AuthorizeStep:
    return AuthorizeStep(permission_policy=permission_policy)


def test_system_admin_denied_with_matrix() -> None:
    matrix = {
        'system_admin': {'categories': {}, 'role_actions': []},
    }
    step = _step(matrix)
    ctx = SourceViewerContext(
        role='system_admin', permissions=None, access_scope=['financial'], category='financial'
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'not_available'
    assert ctx.original_available is False


def test_missing_scope_membership_denied() -> None:
    matrix = {
        'analyst': {'categories': {'financial': ['read', 'view_original']}, 'role_actions': []},
    }
    step = _step(matrix)
    ctx = SourceViewerContext(
        role='analyst', permissions=None, access_scope=['invoices'], category='financial'
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'not_available'


def test_analyst_allowed_on_and_original_available() -> None:
    matrix = {
        'analyst': {'categories': {'financial': ['read', 'view_original']}, 'role_actions': []},
    }
    step = _step(matrix)
    ctx = SourceViewerContext(
        role='analyst', permissions=None, access_scope=['financial'], category='financial'
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.original_available is True


def test_executive_corporate_finance_audit_allowed() -> None:
    matrix = {
        'executive_leadership': {'categories': {'billing': ['read']}, 'role_actions': []},
        'corporate_finance_planners': {'categories': {'billing': ['read']}, 'role_actions': []},
        'audit_compliance': {'categories': {'billing': ['read']}, 'role_actions': []},
    }
    for role in ('executive_leadership', 'corporate_finance_planners', 'audit_compliance'):
        step = _step(matrix)
        ctx = SourceViewerContext(
            role=role, permissions=None, access_scope=['billing'], category='billing'
        )
        result = asyncio.run(step.run(ctx))
        assert result.kind == 'continue', role


def test_unknown_category_behavior_preserved() -> None:
    matrix = {
        'analyst': {'categories': {}, 'role_actions': []},
    }
    step = _step(matrix)
    # unknown category: scope not enforced; read permission False (no read entry)
    ctx = SourceViewerContext(
        role='analyst', permissions=None, access_scope=['financial'], category=None
    )
    result = asyncio.run(step.run(ctx))
    # system admin not involved; unknown category => allowed by authorize, read permission fallback None+no matrix? matrix exists but category None not looked up
    assert result.kind == 'continue'


def test_permission_map_fallback() -> None:
    # request permission map present; no configured matrix
    step = _step(None)
    ctx = SourceViewerContext(
        role='analyst',
        permissions={'financial': ['read']},
        access_scope=['financial'],
        category='financial',
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.original_available is False  # view_original not in map


def test_permission_map_original_available_off() -> None:
    step = _step(None)
    ctx = SourceViewerContext(
        role='analyst',
        permissions={'financial': ['read', 'view_original']},
        access_scope=['financial'],
        category='financial',
    )
    # current-user map with view_original in direct list => original_available True
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.original_available is True


def test_no_permissions_no_matrix_allows() -> None:
    step = _step(None)
    ctx = SourceViewerContext(
        role='analyst', permissions=None, access_scope=[], category='financial'
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'


def test_configured_matrix_fallback_for_view_original_off() -> None:
    matrix = {
        'analyst': {'categories': {'financial': ['read']}, 'role_actions': []},
    }
    step = _step(matrix)
    ctx = SourceViewerContext(
        role='analyst', permissions=None, access_scope=['financial'], category='financial'
    )
    result = asyncio.run(step.run(ctx))
    assert result.kind == 'continue'
    assert ctx.original_available is False


def test_denial_returns_not_available_not_exception() -> None:
    matrix = {
        'analyst': {'categories': {'financial': ['read']}, 'role_actions': []},
    }
    step = _step(matrix)
    ctx = SourceViewerContext(
        role='system_admin', permissions=None, access_scope=['financial'], category='financial'
    )
    result = asyncio.run(step.run(ctx))
    assert isinstance(result, StepResult)
    assert result.kind == 'not_available'
