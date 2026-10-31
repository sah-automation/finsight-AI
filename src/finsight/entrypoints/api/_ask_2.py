# ruff: noqa: BLE001, PLR0911, PLR0912, PLR0915, S110, I001, ANN401, F403, F405
from __future__ import annotations
from typing import Any

try:
    from finsight.core.errors import InsufficientData as _InsufficientDataError
except Exception:
    _InsufficientDataError = None  # type: ignore[assignment,misc]
try:
    from finsight.domain.entities.insufficient_data import (
        InsufficientData as _InsufficientDataResult,
    )
except Exception:
    _InsufficientDataResult = None  # type: ignore[assignment,misc]
from ._ask_0 import *
from ._ask_1 import *


async def _resolve_context_and_data(
    *args: Any, **kwargs: Any
) -> tuple[Any, dict[str, Any], Any, Any]:
    working_kwargs = dict(kwargs)
    context = None
    use_case_candidate = None
    data: dict[str, Any] = {}

    for key in list(working_kwargs):
        value = working_kwargs.pop(key)
        key_l = key.lower()
        if key_l in _CONTEXT_KEYS:
            if context is None:
                context = value
            else:
                data.update(_flatten(value))
        elif (
            key_l in _USE_CASE_KEYS
            or key_l.endswith('use_case')
            or key_l in ('service', 'factory', 'container', 'composition', 'app')
        ):
            if use_case_candidate is None:
                use_case_candidate = value
            else:
                data.update(_flatten(value))
        elif key_l in _PAYLOAD_KEYS:
            if isinstance(value, dict):
                data.update(value)
            else:
                data.update(_flatten(value))
        elif key_l in ('role',):
            data['_role'] = value
        else:
            data[key] = value

    for value in args:
        if _is_context(value):
            if context is None:
                context = value
            else:
                data.update(_flatten(value))
        elif _is_use_case(value):
            if use_case_candidate is None:
                use_case_candidate = value
            else:
                data.update(_flatten(value))
        elif isinstance(value, dict):
            data.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                data.update(flattened)
            else:
                data.setdefault('_raw', value)

    # Lift context/use-case/role out of a flattened payload if present.
    if isinstance(data, dict):
        for key in _CONTEXT_KEYS:
            if key in data and context is None:
                context = data.pop(key)
        for key in _USE_CASE_KEYS:
            if key in data and use_case_candidate is None:
                use_case_candidate = data.pop(key)
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')

    _role_value = data.get('_role', data.get('role'))
    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)
    if _role_value is not None and 'role' not in data:
        data['role'] = _role_value

    role_candidate = None
    if context is not None:
        role_candidate = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId')
    if role_candidate is None and '_role' in data:
        role_candidate = data.pop('_role', None)
    if role_candidate is None and 'role' in data:
        role_candidate = data.pop('role', None)

    # Propagate scoping attributes from the request context into the payload.
    access_scope_candidate = None
    if context is not None:
        access_scope_candidate = _context_lookup(
            context,
            'access_scope',
            'accessScope',
            'scope',
            'access',
            'permission_scope',
            'categories',
            'access_scopes',
        )
    if access_scope_candidate is None:
        access_scope_candidate = _get(
            data,
            'access_scope',
            'accessScope',
            'scope',
            'access',
            'permission_scope',
            'categories',
        )
    if access_scope_candidate is not None and 'access_scope' not in data:
        data['access_scope'] = access_scope_candidate

    company_candidate = None
    if context is not None:
        company_candidate = _context_lookup(
            context,
            'company_id',
            'companyId',
            'company',
            'tenant_id',
            'tenantId',
            'tenant',
        )
    if company_candidate is not None and 'company_id' not in data:
        data['company_id'] = company_candidate

    # expose role candidate back if needed
    if role_candidate is not None and 'role' not in data:
        data['role'] = role_candidate

    return context, data, use_case_candidate, role_candidate


def _normalize_event(raw: Any) -> tuple[str, dict[str, Any]] | None:
    """Normalize a candidate event into (event_type, payload)."""
    if raw is None:
        return None

    # Already (type, data) tuple/list.
    if isinstance(raw, (tuple, list)) and len(raw) >= 1:
        etype = str(raw[0])
        payload = raw[1] if len(raw) > 1 else {}
        etype = _EVENT_ALIASES.get(etype.lower().replace('-', '_'), etype)
        if not isinstance(payload, dict):
            payload = {'value': payload}
        return etype, payload

    # dict event.
    if isinstance(raw, dict):
        etype: Any = None  # type: ignore[no-redef]
        for key in ('event', 'type', 'event_type', 'kind', 'name'):
            if key in raw and raw.get(key) is not None:
                etype = str(raw.get(key))
                break
        if etype is None:
            # Infer from content.
            if 'delta' in raw or 'token' in raw or 'text' in raw or 'answer' in raw:
                etype = 'delta'
            elif 'citation' in raw or 'source' in raw:
                etype = 'citation'
            elif 'insufficient' in raw:
                etype = 'insufficient_data'
            elif 'error' in raw or ('message' in raw and 'status' not in raw):
                # Ambiguous; default to status if status present.
                etype = 'status'
            else:
                etype = 'status'
        etype = _EVENT_ALIASES.get(str(etype).lower().replace('-', '_'), str(etype))

        payload = dict(raw)
        # Remove redundant type keys.
        for key in ('event', 'type', 'event_type', 'kind', 'name'):
            payload.pop(key, None)
        return etype, payload

    # Object with attributes.
    if hasattr(raw, 'event') or hasattr(raw, 'type') or hasattr(raw, 'kind'):
        attr_type = (
            getattr(raw, 'event', None) or getattr(raw, 'type', None) or getattr(raw, 'kind', None)
        )
        etype = (
            _EVENT_ALIASES.get(str(attr_type).lower().replace('-', '_'), str(attr_type))
            if attr_type
            else 'status'
        )
        payload_obj: dict[str, Any] = {}
        for name in ('data', 'payload', 'details', 'meta', 'metadata'):
            val = getattr(raw, name, None)
            if val is not None:
                if isinstance(val, dict):
                    payload_obj.update(val)
                else:
                    payload_obj[name] = val
        for name in (
            'delta',
            'token',
            'text',
            'content',
            'answer',
            'message',
            'reason',
            'citation',
            'source',
            'status',
            'done',
            'complete',
            'error',
            'busy',
        ):
            val = getattr(raw, name, None)
            if val is not None:
                payload_obj[name] = val
        if not payload_obj:
            payload_obj = {'value': str(raw)}
        return etype, payload_obj

    # Pydantic-like model.
    if hasattr(raw, 'model_dump'):
        try:
            return _normalize_event(raw.model_dump())
        except Exception:
            pass
    if hasattr(raw, 'dict'):
        try:
            return _normalize_event(raw.dict())
        except Exception:
            pass

    return 'status', {'value': str(raw)}


__all__ = ['_normalize_event', '_resolve_context_and_data']
