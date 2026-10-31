# ruff: noqa: PLC0415, PLR0912, PLR0915, I001, ANN401, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import Body
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from ._onboarding_0 import *


class _Response(dict[str, Any]):
    """Dict that also supports attribute access (test-friendly)."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


async def _handle(*args: Any, **kwargs: Any) -> Any:
    # Collect and classify arguments.
    context = None
    use_case_candidate = None
    data: dict[str, Any] = {}

    # explicit key handling
    working_kwargs = dict(kwargs)
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
        elif key_l == 'role':
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
                data.setdefault('request_key', value)

    # Lift context/use-case/role out of a flattened dict payload if present.
    if isinstance(data, dict):
        for key in _CONTEXT_KEYS:
            if key in data and context is None:
                context = data.pop(key)
        for key in _USE_CASE_KEYS:
            if key in data and use_case_candidate is None:
                use_case_candidate = data.pop(key)
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')

    # Canonicalise input field aliases so downstream gets canonical names too.
    # Preserve the role before canonicalisation drops private keys.
    _role_value = data.get('_role', data.get('role'))
    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)
    if _role_value is not None and 'role' not in data:
        data['role'] = _role_value

    role_candidate = None
    if _is_context(context):
        role_candidate = _get(context, 'role')
    if role_candidate is None and isinstance(context, dict):
        role_candidate = _get(context, 'role')
    if role_candidate is None and '_role' in data:
        role_candidate = data.pop('_role', None)
    if role_candidate is None and 'role' in data:
        role_candidate = data.pop('role', None)

    # Enforce System Admin authorization.
    if not _is_system_admin(role_candidate):
        raise _ForbiddenError()

    request_key = _get(data, 'request_key', 'request_id', 'idempotency_key')
    if request_key is not None:
        request_key = str(request_key).strip() or None
        if request_key is None:
            request_key = None

    # Validation is performed by the onboarding use case itself, before submit.
    use_case = await _resolve_use_case(use_case_candidate)

    try:
        outcome = await _run_use_case(use_case, data)
    except AuthorizationError as exc:
        raise _ForbiddenError(getattr(exc, 'message', None) or to_user_message(exc)) from exc
    except ValidationError as exc:
        raise _BadRequestError(getattr(exc, 'message', None) or to_user_message(exc)) from exc
    except Exception as exc:
        raise _ServerError(to_user_message(exc)) from exc

    return _as_response(outcome, request_key)


def onboarding(*args: Any, **kwargs: Any) -> Any:
    """Run an onboarding request (System Admin only).

    Works both synchronously outside an event loop and as an awaitable
    when called from within a running event loop.
    """
    import asyncio as _asyncio

    try:
        loop = _asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    if loop is None:
        return _asyncio.run(_handle(*args, **kwargs))
    return loop.run_until_complete(_handle(*args, **kwargs))


onboard = onboarding
onboard_company = onboarding
onboarding_endpoint = onboarding
onboard_endpoint = onboarding
handle_onboarding = onboarding
run_onboarding = onboarding
submit_onboarding = onboarding
create_company_onboarding = onboarding
create_company_endpoint = onboarding
onboard_admin = onboarding
system_admin_onboard = onboarding


async def health() -> dict[str, str]:
    return {'status': 'ok'}


async def http_onboard(payload: Any = Body(default=None), context: Any = None) -> Any:
    return await _handle(payload, context=context)


__all__ = [
    '_Response',
    '_handle',
    'create_company_endpoint',
    'create_company_onboarding',
    'handle_onboarding',
    'health',
    'http_onboard',
    'onboard',
    'onboard_admin',
    'onboard_company',
    'onboard_endpoint',
    'onboarding',
    'onboarding_endpoint',
    'run_onboarding',
    'submit_onboarding',
    'system_admin_onboard',
]
