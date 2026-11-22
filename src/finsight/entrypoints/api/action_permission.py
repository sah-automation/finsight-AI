"""Shared action permission dependency for Phase 2 API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request

from finsight.entrypoints.api.correlation_identity import extract_access_scope, extract_identity

from ._permissions import (
    _extract_role_actions_and_categories,
    _get_role_entry,
    _load_permissions_config,
)
from ._shared import _context_lookup
from .api_principal import ApiPrincipal

if TYPE_CHECKING:
    from collections.abc import Mapping

_SCOPE_KEYS = (
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


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_role(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text.lower().replace(' ', '_').replace('-', '_')


def _scope_from_request(request: Request) -> tuple[str, ...] | None:
    for source in (getattr(request, 'state', None), getattr(request, 'scope', None)):
        if source is None:
            continue
        value = _context_lookup(source, *_SCOPE_KEYS)
        if value is None:
            continue
        if isinstance(value, str):
            text = _text(value)
            return (text,) if text is not None else ()
        if not isinstance(value, (list, tuple, set, frozenset)):
            return ()
        values: list[str] = []
        for item in value:
            text = _text(item)
            if text is not None:
                values.append(text)
        return tuple(values)
    return None


class ActionPermission:
    """FastAPI dependency that enforces one role action before data access."""

    def __init__(self, action: str) -> None:
        self._action = action

    async def __call__(self, request: Request) -> ApiPrincipal:
        company_raw, user_raw, role_raw = extract_identity(request)
        company_id = _text(company_raw)
        role_id = _normalize_role(role_raw)
        if company_id is None or role_id is None:
            raise HTTPException(status_code=403, detail='Authenticated identity is required.')

        entry = _get_role_entry(role_id, _load_permissions_config())
        role_actions_raw, categories_raw = _extract_role_actions_and_categories(entry)
        role_actions = tuple(str(action) for action in role_actions_raw)
        if self._action not in role_actions:
            raise HTTPException(status_code=403, detail='You do not have permission to view KPIs.')

        category_permissions = {
            str(category): tuple(str(action) for action in actions)
            for category, actions in categories_raw.items()
        }
        scope = self._resolve_scope(request, category_permissions)
        return ApiPrincipal(
            company_id=company_id,
            user_id=_text(user_raw),
            role_id=role_id,
            access_scope=scope,
            role_actions=role_actions,
            category_permissions=category_permissions,
        )

    def _resolve_scope(
        self,
        request: Request,
        category_permissions: Mapping[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        readable = tuple(
            category for category, actions in category_permissions.items() if 'read' in actions
        )
        declared = _scope_from_request(request)
        if declared is None:
            declared = extract_access_scope(request)
        if declared is None:
            return readable
        return tuple(category for category in readable if category in set(declared))
