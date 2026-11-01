# ruff: noqa: BLE001, PLR0912
"""Request normalization helpers for the ask entrypoint."""

from __future__ import annotations

from typing import Any

from ._ask_0 import (
    _context_lookup,
    _flatten,
    _is_context,
    _is_use_case,
)

try:
    from finsight.core.types import CompanyId as _CompanyId
    from finsight.core.types import RequestContext as _RequestContext
    from finsight.core.types import Role as _Role
    from finsight.core.types import TraceId as _TraceId
    from finsight.core.types import UserId as _UserId
except Exception:  # pragma: no cover
    _CompanyId = None  # type: ignore[misc,assignment]
    _RequestContext = None  # type: ignore[misc,assignment]
    _Role = None  # type: ignore[misc,assignment]
    _TraceId = None  # type: ignore[misc,assignment]
    _UserId = None  # type: ignore[misc,assignment]


async def _resolve_context_and_data(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any], Any]:
    context = kwargs.get('context')
    data: dict[str, Any] = {}
    use_case = kwargs.get('use_case')

    if 'data' in kwargs and isinstance(kwargs.get('data'), dict):
        data.update(kwargs['data'])
    for key, value in kwargs.items():
        if key in {'context', 'use_case'}:
            continue
        if isinstance(value, dict):
            data.update(value)
        else:
            flat = _flatten(value)
            if flat:
                data.update(flat)
            else:
                data[key] = value
    for value in args:
        if _is_context(value):
            context = context or value
        elif _is_use_case(value):
            use_case = use_case or value
        elif isinstance(value, dict):
            data.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                data.update(flattened)

    # lift context/use_case
    for key in ('request_context', 'context', 'ctx'):
        if key in data and context is None:
            context = data.pop(key)
    for key in ('use_case', 'ask_use_case', 'qa_use_case'):
        if key in data and use_case is None:
            use_case = data.pop(key)

    # Propagate scoping fields if needed.
    if context is not None:
        company = _context_lookup(context, 'company_id', 'companyId', 'company')
        if company is not None and 'company_id' not in data:
            data['company_id'] = company
        role = _context_lookup(context, 'role', 'user_role', 'roleId')
        if role is not None and 'role' not in data:
            data['role'] = role
        scope = _context_lookup(context, 'access_scope', 'accessScope', 'scope')
        if scope is not None and 'access_scope' not in data:
            data['access_scope'] = scope
        user = _context_lookup(context, 'user_id', 'userId', 'user', 'uid')
        if user is not None and 'user_id' not in data:
            data['user_id'] = user

    return context, data, use_case


def _build_frozen_request_context(data: dict[str, Any], context: Any) -> Any:
    if _RequestContext is None:
        return context
    try:
        company_id = data.get('company_id')
        if company_id is None and context is not None:
            company_id = _context_lookup(context, 'company_id', 'companyId', 'company')
        if company_id is None:
            return context

        role = data.get('role')
        if role is None and context is not None:
            role = _context_lookup(context, 'role', 'user_role', 'roleId')
        if role is None:
            role = getattr(context, 'role', None) if context is not None else None
        if role is None:
            role = _Role.EXECUTIVE_LEADERSHIP
        if isinstance(role, str):
            try:
                role = _Role(role)
            except Exception:
                role = _Role.EXECUTIVE_LEADERSHIP

        user_id = data.get('user_id')
        if user_id is None and context is not None:
            user_id = _context_lookup(context, 'user_id', 'userId', 'user', 'uid')
        if user_id is None and context is not None:
            user_id = getattr(context, 'user_id', None)
        if user_id is None:
            user_id = 'unknown'

        trace_id = None
        if context is not None:
            trace_id = _context_lookup(context, 'trace_id', 'traceId', 'trace')
        if trace_id is None:
            trace_id = 'trace'

        permissions: dict[Any, Any] = {}
        if context is not None:
            perms = _context_lookup(context, 'permissions')
            if isinstance(perms, dict):
                permissions = perms

        access_scope = data.get('access_scope')
        if access_scope is None and context is not None:
            access_scope = _context_lookup(context, 'access_scope', 'accessScope', 'scope')
        scopes: list[Any]
        if isinstance(access_scope, list):
            scopes = access_scope
        elif access_scope is None:
            scopes = []
        else:
            scopes = [access_scope]

        return _RequestContext(
            company_id=_CompanyId(str(company_id)),
            user_id=_UserId(str(user_id)),
            role=role,
            trace_id=_TraceId(str(trace_id)),
            permissions=permissions,
            access_scope=scopes,
        )
    except Exception:
        return context


__all__ = ['_build_frozen_request_context', '_resolve_context_and_data']
