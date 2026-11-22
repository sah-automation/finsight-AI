"""Shared permission helpers for API entrypoints."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from finsight.core.config import get_config, load_config
from finsight.core.config.loader import ConfigError

from ._shared import _context_lookup


async def _require_company_id(context: Any) -> str:
    """Extract and validate company_id from authenticated context."""
    company_id_raw = _context_lookup(
        context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
    )
    if company_id_raw is None:
        raise HTTPException(status_code=403, detail='Authenticated company context is required.')
    return str(company_id_raw)


async def _require_role_id(context: Any) -> str:
    """Extract and validate role_id from authenticated context."""
    role_raw = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    role_id = (
        str(role_raw).strip().lower().replace(' ', '_').replace('-', '_') if role_raw else None
    )
    if not role_id:
        raise HTTPException(status_code=403, detail='Authenticated role context is required.')
    return role_id


async def _require_user_id(context: Any) -> str:
    """Extract and validate user_id from authenticated context."""
    user_id_raw = _context_lookup(context, 'user_id', 'userId', 'uid', 'id', 'sub')
    if user_id_raw is None:
        raise HTTPException(status_code=403, detail='Authenticated user context is required.')
    return str(user_id_raw)


def _load_permissions_config() -> Any:
    """Load config and return permissions section."""
    try:
        config = get_config()
    except ConfigError:
        try:
            config = load_config()
        except ConfigError:
            config = load_config('test')
    return config


def _get_role_entry(role_id: str, config: Any) -> dict[str, Any]:
    """Get role entry from permissions config."""
    permissions_cfg = getattr(config, 'permissions', None)
    role_entries = getattr(permissions_cfg, 'permissions', None) if permissions_cfg else None
    if not isinstance(role_entries, dict):
        if permissions_cfg and hasattr(permissions_cfg, 'model_dump'):
            dumped = permissions_cfg.model_dump()
            role_entries = dumped.get('permissions')
        elif isinstance(permissions_cfg, dict):
            role_entries = permissions_cfg.get('permissions', permissions_cfg)

    if not isinstance(role_entries, dict) or role_id not in role_entries:
        raise HTTPException(status_code=403, detail='Unknown or unauthorized role.')

    entry = role_entries[role_id]
    entry_dump = (
        entry.model_dump()
        if hasattr(entry, 'model_dump')
        else (entry.dict() if hasattr(entry, 'dict') else entry)
    )
    if not isinstance(entry_dump, dict):
        entry_dump = {'categories': {}, 'role_actions': []}
    return entry_dump


def _extract_role_actions_and_categories(
    entry_dump: dict[str, Any],
) -> tuple[list[str], dict[str, list[str]]]:
    """Extract role_actions and category_permissions from role entry."""
    category_permissions: dict[str, list[str]] = {}
    categories = entry_dump.get('categories', {}) or {}
    if isinstance(categories, dict):
        for key, value in categories.items():
            if isinstance(value, (list, tuple, set)):
                category_permissions[str(key)] = [str(item) for item in value]
            else:
                category_permissions[str(key)] = [str(value)]

    role_actions: list[str] = [str(item) for item in (entry_dump.get('role_actions') or [])]
    return role_actions, category_permissions


def _check_action(role_actions: list[str], action: str) -> bool:
    """Check if role has a specific action."""
    return action in role_actions


def _check_category_action(category_permissions: dict[str, list[str]], action: str) -> bool:
    """Check if role has an action on at least one category."""
    return any(action in actions for actions in category_permissions.values())


def _filter_by_allowed_ids(
    requested: list[str],
    allowed: set[str],
    default: list[str] | None = None,
) -> list[str]:
    """Filter requested IDs by allowed set, return default if empty."""
    filtered = [item for item in requested if item in allowed]
    if not filtered and default is not None:
        return default
    return filtered


def _get_allowed_chart_ids(config: Any) -> set[str]:
    """Get allowed chart IDs from config."""
    charts_config = getattr(config, 'charts', None)
    if charts_config and hasattr(charts_config, 'specs'):
        specs = charts_config.specs if hasattr(charts_config, 'specs') else {}
        return set(specs.keys())
    return set()


def _get_allowed_kpi_codes(config: Any) -> set[str]:
    """Get allowed KPI codes from config."""
    kpi_config = getattr(config, 'kpi', None)
    if kpi_config and hasattr(kpi_config, 'codes'):
        return set(kpi_config.codes)
    return set()


def _get_default_layout(config: Any) -> tuple[list[str], list[dict[str, str]]]:
    """Get default layout from config."""
    dashboard_config = getattr(config, 'dashboard', None)
    if dashboard_config and hasattr(dashboard_config, 'default_layout'):
        default_layout = dashboard_config.default_layout
        if hasattr(default_layout, 'model_dump'):
            default_layout = default_layout.model_dump()
        elif hasattr(default_layout, 'dict'):
            default_layout = default_layout.dict()
        if isinstance(default_layout, dict):
            return (
                default_layout.get('kpi_codes', []),
                default_layout.get('charts', []),
            )
    return [], []


__all__ = [
    '_check_action',
    '_check_category_action',
    '_extract_role_actions_and_categories',
    '_filter_by_allowed_ids',
    '_get_allowed_chart_ids',
    '_get_allowed_kpi_codes',
    '_get_default_layout',
    '_get_role_entry',
    '_load_permissions_config',
    '_require_company_id',
    '_require_role_id',
    '_require_user_id',
]
