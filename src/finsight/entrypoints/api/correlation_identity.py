"""Identity extraction helpers for correlation middleware."""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

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

_SCOPE_KEYS = (
    'custom:access_scope',
    'custom:accessScope',
    'custom:scope',
    'access_scope',
    'accessScope',
    'scope',
    'AccessScope',
    'access',
    'permission_scope',
    'allowed_categories',
    'allowedCategories',
    'document_categories',
    'allowed_document_categories',
    'categories',
)

_IDENTITY_CLAIM_KEYS = frozenset(
    {
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
)
_SCOPE_CLAIM_KEYS = frozenset(_SCOPE_KEYS)


def _find_claims(
    obj: Any,
    depth: int = 0,
    claim_keys: frozenset[str] = _IDENTITY_CLAIM_KEYS,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if depth > _MAX_CLAIMS_DEPTH or obj is None:
        return results
    if isinstance(obj, dict):
        if claim_keys & set(obj.keys()):
            results.append(obj)
        for value in obj.values():
            results.extend(_find_claims(value, depth + 1, claim_keys))
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            results.extend(_find_claims(item, depth + 1, claim_keys))
    elif hasattr(obj, 'claims'):
        results.extend(_find_claims(obj.claims, depth + 1, claim_keys))

    return results


def _split_scope_text(text: str) -> tuple[str, ...]:
    if not text:
        return ()
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError):
        return tuple(part.strip() for part in text.split(',') if part.strip())
    normalized = _normalize_scope(decoded)
    return () if normalized is None else normalized


def _normalize_scope(value: Any) -> tuple[str, ...] | None:
    """Return an explicit scope, or ``None`` when no scope was declared."""
    if value is None:
        return None
    if isinstance(value, str):
        return _split_scope_text(value.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        normalized: list[str] = []
        for item in value:
            part = _normalize_scope(item)
            if part is None or not part:
                return ()
            normalized.extend(part)
        return tuple(normalized)
    return ()


def _first_scope_value(claims: Mapping[str, Any]) -> Any:
    for key in _SCOPE_KEYS:
        if key in claims and claims[key] is not None:
            return claims[key]
    return None


def _extract_access_scope(request: Request) -> tuple[str, ...] | None:
    state = getattr(request, 'state', None)
    if state is not None:
        declared = _attr(state, *_SCOPE_KEYS)
        if declared is not None:
            return _normalize_scope(declared)

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
    if 'user' in scope:
        with contextlib.suppress(Exception):
            candidates.append(request.user)

    claims_list: list[dict[str, Any]] = []
    for candidate in candidates:
        claims_list.extend(_find_claims(candidate, claim_keys=_SCOPE_CLAIM_KEYS))
    claims_list.extend(_find_claims(scope, claim_keys=_SCOPE_CLAIM_KEYS))
    for claims in claims_list:
        declared = _first_scope_value(claims)
        if declared is not None:
            return _normalize_scope(declared)
    return None


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
    if 'user' in scope:
        with contextlib.suppress(Exception):
            candidates.append(request.user)

    claims_list: list[dict[str, Any]] = []
    for candidate in candidates:
        claims_list.extend(_find_claims(candidate))
    claims_list.extend(_find_claims(scope))

    company_id, user_id, role = _apply_claims(company_id, user_id, role, claims_list)

    # Client-supplied identity headers are a local-development fallback only:
    # authoritative state/claims above always win.
    headers = getattr(request, 'headers', {}) or {}
    company_id = _coalesce(
        company_id,
        headers.get(_HEADER_COMPANY_ID),
        headers.get('x-company_id'),
    )
    user_id = _coalesce(user_id, headers.get(_HEADER_USER_ID), headers.get('x-user_id'))
    role = _coalesce(role, headers.get(_HEADER_ROLE), headers.get('x-user-role'))

    return company_id, user_id, role


__all__ = ['extract_access_scope', 'extract_identity']


extract_identity = _extract_identity
extract_access_scope = _extract_access_scope
