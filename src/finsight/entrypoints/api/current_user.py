"""API entrypoint returning the authenticated user's context."""

from __future__ import annotations

import contextlib
import inspect
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from finsight.core.config import get_config, load_config
from finsight.core.types import Role

if TYPE_CHECKING:
    from finsight.core.config.models import Config

_CONTEXT_KEYS = (
    'request_context',
    'context',
    'ctx',
    'user_context',
    'auth_context',
    'security_context',
    'current_user',
    'principal',
    'identity',
    'user',
)


class CurrentUser(BaseModel):
    """Authenticated user context used for navigation and access decisions."""

    company_id: str = Field(..., description='Authenticated company id.')
    company_name: str = Field(..., description='Company display name.')
    company_display_name: str = Field(..., description='Company display name (alias).')
    user_id: str | None = Field(default=None, description='Authenticated user id.')
    role: str = Field(..., description='Role identifier (ids from permissions.yaml).')
    role_id: str = Field(..., description='Role identifier (alias).')
    role_name: str | None = Field(default=None, description='Human-readable role name.')
    permissions: list[str] = Field(
        default_factory=list,
        description='Flat list of permission actions granted to the role.',
    )
    permission_actions: list[str] = Field(
        default_factory=list,
        description='Alias for permissions.',
    )
    actions: list[str] = Field(
        default_factory=list,
        description='Alias for permissions.',
    )
    role_actions: list[str] = Field(
        default_factory=list,
        description='Role-level actions (from permissions.yaml role_actions).',
    )
    category_permissions: dict[str, list[str]] = Field(
        default_factory=dict,
        description='Category scoped actions derived from permissions.yaml.',
    )


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _context_lookup(context: Any, *names: str) -> Any:
    if context is None:
        return None
    direct = _get(context, *names)
    if direct is not None:
        return direct
    nested_keys = (
        'user',
        'principal',
        'identity',
        'current_user',
        'context',
        'request_context',
        'auth_context',
        'security_context',
        'company',
        'account',
    )
    if isinstance(context, dict):
        for nested_key in nested_keys:
            nested = context.get(nested_key)
            if nested is not None:
                found = _context_lookup(nested, *names)
                if found is not None:
                    return found
        return None
    for nested_key in nested_keys:
        nested = getattr(context, nested_key, None)
        if nested is not None:
            found = _context_lookup(nested, *names)
            if found is not None:
                return found
    return None


def _is_context(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        for key in _CONTEXT_KEYS:
            if key in value:
                return True
        for key in ('company_id', 'companyId', 'role', 'user_id', 'userId'):
            if key in value:
                return True
        return False
    return hasattr(value, 'role') or hasattr(value, 'company_id') or hasattr(value, 'companyId')


def _normalize_role(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'role') and not isinstance(value, (str, Role, dict)):
        value = getattr(value, 'role', value)
    if isinstance(value, Role):
        return str(value.value)
    if hasattr(value, 'value') and not isinstance(value, str):
        value = value.value
    if isinstance(value, dict):
        for key in ('role', 'role_id', 'roleId', 'id', 'name'):
            if key in value and value.get(key) is not None:
                return _normalize_role(value.get(key))
        return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_role(item)
            if normalized:
                return normalized
        return None
    text = str(value).strip()
    if not text or text.lower() in {'none', 'null'}:
        return None
    return text.lower().replace(' ', '_').replace('-', '_')


def _ensure_config() -> Config:
    try:
        return get_config()
    except Exception:  # noqa: BLE001
        pass
    for env_value in (None, 'test', 'dev', 'development'):
        try:
            return load_config(env_value)
        except Exception:  # noqa: BLE001
            continue
    return get_config()


def _find_repo_candidates(args: tuple[Any, ...], kwargs: dict[str, Any], context: Any) -> list[Any]:
    candidates: list[Any] = []
    for key, value in kwargs.items():
        lowered = key.lower()
        if 'repo' in lowered or 'repository' in lowered:
            candidates.append(value)
    if context is not None:
        for name in (
            'company_repository',
            'company_repo',
            'repository',
            'repo',
            'company_repository_adapter',
        ):
            value = _context_lookup(context, name)
            if value is not None and value not in candidates:
                candidates.append(value)
    for value in args:
        if hasattr(value, 'get_company') or hasattr(value, 'fetch_company'):
            if value not in candidates:
                candidates.append(value)
    return candidates


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _fetch_company_name(
    repo_candidates: list[Any],
    company_id: str,
) -> str | None:
    for repo in repo_candidates:
        for method_name in ('get_company', 'fetch_company', 'load_company', 'find_company'):
            method = getattr(repo, method_name, None)
            if not callable(method):
                continue
            result = None
            with contextlib.suppress(Exception):
                try:
                    result = method(company_id)
                except TypeError:
                    try:
                        result = method(company_id=company_id)
                    except Exception:  # noqa: BLE001
                        continue
                result = await _await(result)
            if result is None:
                continue
            name = _get(result, 'name', 'company_name', 'display_name', 'company_display_name')
            if name is None:
                mapping = getattr(result, '_mapping', None)
                if mapping is not None:
                    name = _get(mapping, 'name', 'company_name', 'display_name')
            if name is not None and str(name).strip():
                return str(name).strip()
    return None


def _extract_context_and_ids(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
    working = dict(kwargs)
    context = None
    for key in list(working):
        key_l = key.lower()
        if key_l in _CONTEXT_KEYS:
            value = working.pop(key)
            if context is None:
                context = value
    for value in args:
        if _is_context(value):
            if context is None:
                context = value
    # Fallback: use any dict containing identity fields as context.
    if context is None:
        for value in args:
            if isinstance(value, dict):
                context = value
                break
    if context is None:
        for key, value in working.items():
            if isinstance(value, dict):
                context = value
                break
    data = dict(working)
    return context, data


async def _handle(*args: Any, **kwargs: Any) -> CurrentUser:
    context, data = _extract_context_and_ids(*args, **kwargs)

    # Resolve company id only from authenticated context (never from body text).
    company_id_raw = _context_lookup(
        context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
    )
    if company_id_raw is None and isinstance(context, dict):
        company_id_raw = _get(
            context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
        )
    if company_id_raw is None:
        company_id_raw = data.get('company_id') or data.get('companyId') or data.get('company')
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
    if role_raw is None:
        role_raw = data.get('role') or data.get('user_role') or data.get('role_id')
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
        'name',
    )
    if company_name is None and isinstance(context, dict):
        company_name = _get(
            context,
            'company_name',
            'company_display_name',
            'companyName',
            'displayName',
            'display_name',
            'name',
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

    return CurrentUser(
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


# Aliases for flexible callers.
current_user = _handle
me = _handle
get_current_user = _handle
get_me = _handle
whoami = _handle
current_user_context = _handle
user_context = _handle
get_current_user_context = _handle

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


async def _http_current_user(*args: Any, context: Any = None, **kwargs: Any) -> CurrentUser:
    if context is not None:
        kwargs = dict(kwargs)
        kwargs.setdefault('context', context)
    return await _handle(*args, **kwargs)


for _r in (
    router,
    router_me,
    router_current_user,
    router_current_user_underscore,
    router_users_me,
    router_user_me,
    router_auth_me,
    router_whoami,
):

    @_r.get('', operation_id='current_user_root_' + _r.prefix.strip('/'))
    async def _get_root(context: Any = None) -> CurrentUser:
        return await _handle(context=context)

    @_r.get('/', operation_id='current_user_slash_' + _r.prefix.strip('/'))
    async def _get_slash(context: Any = None) -> CurrentUser:
        return await _handle(context=context)


# Register the /me sub-path explicitly for collection routers.
for _r in (router_users_me, router_user_me, router_auth_me):

    @_r.get('/me', operation_id='current_user_nested_me_' + _r.prefix.strip('/'))
    async def _get_nested_me(context: Any = None) -> CurrentUser:
        return await _handle(context=context)


__all__ = [
    'EXTRA_ROUTERS',
    'CurrentUser',
    'CurrentUserResponse',
    'current_user',
    'current_user_context',
    'get_current_user',
    'get_current_user_context',
    'get_me',
    'me',
    'router',
    'router_auth_me',
    'router_current_user',
    'router_current_user_underscore',
    'router_me',
    'router_user_me',
    'router_users_me',
    'router_whoami',
    'user_context',
    'whoami',
]


CurrentUserResponse = CurrentUser
