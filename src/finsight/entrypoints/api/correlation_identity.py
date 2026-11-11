"""Identity extraction helpers for correlation middleware."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.requests import Request


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            text = str(value).strip()
            if text and text.lower() not in {'none', 'null', ''}:
                return value
    return None


def _attr(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return None


_MAX_CLAIMS_DEPTH = 8


def _find_claims(obj: Any, depth: int = 0) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if depth > _MAX_CLAIMS_DEPTH or obj is None:
        return results
    if isinstance(obj, dict):
        claim_keys = {
            'custom:company_id',
            'company_id',
            'companyId',
            'sub',
            'user_id',
            'userId',
            'cognito:groups',
            'groups',
            'role',
        }
        if claim_keys & set(obj.keys()):
            results.append(obj)
        for value in obj.values():
            results.extend(_find_claims(value, depth + 1))
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            results.extend(_find_claims(item, depth + 1))
    elif hasattr(obj, 'claims'):
        results.extend(_find_claims(obj.claims, depth + 1))

    return results


_HEADER_COMPANY_ID = 'x-company-id'
_HEADER_USER_ID = 'x-user-id'
_HEADER_ROLE = 'x-role'


def _apply_claims(
    company_id: Any,
    user_id: Any,
    role: Any,
    claims_list: list[dict[str, Any]],
) -> tuple[Any, Any, Any]:
    for claims in claims_list:
        if company_id is None:
            company_id = _coalesce(
                claims.get('custom:company_id'),
                claims.get('company_id'),
                claims.get('companyId'),
            )
        if user_id is None:
            user_id = _coalesce(
                claims.get('sub'),
                claims.get('user_id'),
                claims.get('userId'),
                claims.get('username'),
                claims.get('email'),
            )
        if role is None:
            groups = claims.get('cognito:groups') or claims.get('groups')
            if isinstance(groups, (list, tuple, set)) and groups:
                role = next(iter(groups))
            role = _coalesce(role, claims.get('role'), claims.get('custom:role'))
    return company_id, user_id, role


def _extract_identity(request: Request) -> tuple[Any, Any, Any]:
    company_id: Any = None
    user_id: Any = None
    role: Any = None

    state = getattr(request, 'state', None)
    if state is not None:
        company_id = _coalesce(company_id, _attr(state, 'company_id', 'companyId', 'company'))
        user_id = _coalesce(user_id, _attr(state, 'user_id', 'userId', 'sub', 'user'))
        role = _coalesce(role, _attr(state, 'role', 'role_id', 'roleId'))

    headers = getattr(request, 'headers', {}) or {}
    company_id = _coalesce(
        company_id,
        headers.get(_HEADER_COMPANY_ID),
        headers.get('x-company_id'),
    )
    user_id = _coalesce(user_id, headers.get(_HEADER_USER_ID), headers.get('x-user_id'))
    role = _coalesce(role, headers.get(_HEADER_ROLE), headers.get('x-user-role'))

    scope = getattr(request, 'scope', {}) or {}
    candidates: list[Any] = []
    for key in (
        'aws.event',
        'lambda.event',
        'event',
        'user',
        'auth',
        'claims',
        'principal',
        'identity',
        'current_user',
        'context',
    ):
        if key in scope:
            candidates.append(scope[key])
    if 'user' in (getattr(request, 'scope', {}) or {}):
        with contextlib.suppress(Exception):
            candidates.append(request.user)

    claims_list: list[dict[str, Any]] = []
    for candidate in candidates:
        claims_list.extend(_find_claims(candidate))
    claims_list.extend(_find_claims(scope))

    return _apply_claims(company_id, user_id, role, claims_list)


__all__ = ['extract_identity']


extract_identity = _extract_identity
