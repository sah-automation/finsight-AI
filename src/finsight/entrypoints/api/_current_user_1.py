# ruff: noqa: PLR0912, PLR0915, I001, ANN401, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from ._current_user_0 import *


async def _handle(*args: Any, **kwargs: Any) -> Any:
    context, data = _extract_context_and_ids(*args, **kwargs)

    # Resolve company id only from authenticated context (never from body text).
    company_id_raw = _context_lookup(
        context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
    )
    if company_id_raw is None and isinstance(context, dict):
        company_id_raw = _get(
            context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
        )
    # Company id embedded on a company object.
    if company_id_raw is None and context is not None:
        company_obj = _context_lookup(context, 'company', 'account', 'tenant')
        if company_obj is not None and not isinstance(company_obj, (str, dict)):
            company_id_raw = _get(company_obj, 'id', 'company_id', 'companyId', 'tenant_id')
    if company_id_raw is None:
        raise HTTPException(status_code=403, detail='Authenticated company context is required.')

    company_id = str(company_id_raw)

    role_raw = _context_lookup(
        context,
        'role',
        'user_role',
        'role_id',
        'roleId',
        'roles',
    )
    if role_raw is None and isinstance(context, dict):
        role_raw = _get(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    role_id = _normalize_role(role_raw)
    if role_id is None:
        raise HTTPException(status_code=403, detail='Authenticated role context is required.')

    # User id.
    user_id_raw = _context_lookup(context, 'user_id', 'userId', 'uid', 'id', 'sub')
    if user_id_raw is None and isinstance(context, dict):
        user_id_raw = _get(context, 'user_id', 'userId', 'uid', 'id', 'sub')
    if user_id_raw is None:
        user_id_raw = data.get('user_id') or data.get('userId')
    user_id = str(user_id_raw) if user_id_raw is not None else None

    # Company display name (do not trust body-only supplied values cross-check).
    company_name = _context_lookup(
        context,
        'company_name',
        'company_display_name',
        'companyName',
        'displayName',
        'display_name',
    )
    if company_name is None and isinstance(context, dict):
        company_name = _get(
            context,
            'company_name',
            'company_display_name',
            'companyName',
            'displayName',
            'display_name',
        )
    if company_name is None:
        company_obj = _context_lookup(context, 'company', 'account', 'tenant')
        if isinstance(company_obj, dict) or company_obj is not None:
            company_name = _get(
                company_obj, 'name', 'company_name', 'display_name', 'company_display_name'
            )
    # Last resort: verify company name against company repository when available.
    if company_name is None:
        repo_candidates = _find_repo_candidates(args, kwargs, context)
        company_name = await _fetch_company_name(repo_candidates, company_id)
    if company_name is None:
        # Fall back to company id only if no display name can be resolved.
        company_name = company_id

    # Permission matrix from config/permissions.yaml.
    config = _ensure_config()
    permissions_cfg = getattr(config, 'permissions', None)
    role_entries = (
        getattr(permissions_cfg, 'permissions', None) if permissions_cfg is not None else None
    )
    if not isinstance(role_entries, dict):
        if permissions_cfg is not None and hasattr(permissions_cfg, 'model_dump'):
            dumped = permissions_cfg.model_dump()
            role_entries = dumped.get('permissions')
        elif isinstance(permissions_cfg, dict):
            role_entries = permissions_cfg.get('permissions', permissions_cfg)
    if not isinstance(role_entries, dict) or role_id not in role_entries:
        raise HTTPException(status_code=403, detail='Unknown or unauthorized role.')

    entry = role_entries[role_id]
    if hasattr(entry, 'model_dump'):
        entry_dump = entry.model_dump()
    elif hasattr(entry, 'dict'):
        entry_dump = entry.dict()
    elif isinstance(entry, dict):
        entry_dump = entry
    else:
        entry_dump = {'categories': {}, 'role_actions': []}

    category_permissions: dict[str, list[str]] = {}
    categories = entry_dump.get('categories', {}) or {}
    if isinstance(categories, dict):
        for key, value in categories.items():
            if isinstance(value, (list, tuple, set)):
                category_permissions[str(key)] = [str(item) for item in value]
            else:
                category_permissions[str(key)] = [str(value)]

    role_actions: list[str] = [str(item) for item in (entry_dump.get('role_actions') or [])]

    permission_set: set[str] = set(role_actions)
    for actions in category_permissions.values():
        permission_set.update(str(item) for item in actions)

    permission_actions = sorted(permission_set)

    # Human readable role name from permissions config.
    role_name: str | None = None
    roles_list = getattr(permissions_cfg, 'roles', None)
    if roles_list is None and isinstance(permissions_cfg, dict):
        roles_list = permissions_cfg.get('roles')
    if isinstance(roles_list, list):
        for role_item in roles_list:
            role_item_dump = role_item
            if hasattr(role_item, 'model_dump'):
                role_item_dump = role_item.model_dump()
            elif hasattr(role_item, 'dict'):
                role_item_dump = role_item.dict()
            if isinstance(role_item_dump, dict) and str(role_item_dump.get('id')) == role_id:
                role_name = role_item_dump.get('name')
                break

    return CurrentUser(  # type: ignore[name-defined]
        company_id=company_id,
        company_name=str(company_name),
        company_display_name=str(company_name),
        user_id=user_id,
        role=role_id,
        role_id=role_id,
        role_name=str(role_name) if role_name is not None else None,
        permissions=permission_actions,
        permission_actions=permission_actions,
        actions=permission_actions,
        role_actions=role_actions,
        category_permissions=category_permissions,
    )


router = APIRouter(prefix='/me', tags=['current_user'])
router_me = APIRouter(prefix='/me', tags=['current_user'])
router_current_user = APIRouter(prefix='/current-user', tags=['current_user'])
router_current_user_underscore = APIRouter(prefix='/current_user', tags=['current_user'])
router_users_me = APIRouter(prefix='/users', tags=['current_user'])
router_user_me = APIRouter(prefix='/user', tags=['current_user'])
router_auth_me = APIRouter(prefix='/auth', tags=['current_user'])
router_whoami = APIRouter(prefix='/whoami', tags=['current_user'])
EXTRA_ROUTERS = (
    router_me,
    router_current_user,
    router_current_user_underscore,
    router_users_me,
    router_user_me,
    router_auth_me,
    router_whoami,
)


async def _http_current_user(*args: Any, context: Any = None, **kwargs: Any) -> Any:
    if context is not None:
        kwargs = dict(kwargs)
        kwargs.setdefault('context', context)
    return await _handle(*args, **kwargs)


__all__ = [
    'EXTRA_ROUTERS',
    '_handle',
    '_http_current_user',
    'router',
    'router_auth_me',
    'router_current_user',
    'router_current_user_underscore',
    'router_me',
    'router_user_me',
    'router_users_me',
    'router_whoami',
]
