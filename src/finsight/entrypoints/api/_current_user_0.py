# ruff: noqa: PLR0911, SIM102, SIM110, B007, I001
"""API entrypoint returning the authenticated user's context."""

from __future__ import annotations
import inspect
from typing import TYPE_CHECKING, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from finsight.core.config import get_config, load_config
from finsight.core.config.loader import ConfigError
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
    except ConfigError:
        pass
    try:
        return load_config()
    except ConfigError:
        return load_config('test')


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
            try:
                result = method(company_id)
            except TypeError:
                result = method(company_id=company_id)
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


__all__ = [
    'TYPE_CHECKING',
    '_CONTEXT_KEYS',
    'APIRouter',
    'Any',
    'BaseModel',
    'ConfigError',
    'Field',
    'HTTPException',
    'Role',
    '_await',
    '_context_lookup',
    '_ensure_config',
    '_extract_context_and_ids',
    '_fetch_company_name',
    '_find_repo_candidates',
    '_get',
    '_is_context',
    '_normalize_role',
    'annotations',
    'get_config',
    'inspect',
    'load_config',
]
