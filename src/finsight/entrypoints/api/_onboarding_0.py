# ruff: noqa: PLR0912, I001
"""API entrypoint for system-admin-triggered company onboarding."""

from __future__ import annotations
import contextlib
import inspect
from typing import Any
from typing import Any as _Any
from fastapi import APIRouter, Body, HTTPException
from finsight.application.onboarding import CreateCompany
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from finsight.core.types import Role

get_onboarding_use_case: _Any = None
try:
    from finsight.composition.onboarding import get_onboarding_use_case as _get_onboarding_use_case

    get_onboarding_use_case = _get_onboarding_use_case
except ImportError:  # pragma: no cover
    pass
router = APIRouter(prefix='/onboarding', tags=['onboarding'])


class _ForbiddenError(HTTPException, AuthorizationError):
    """Raised when the caller is not a System Admin."""

    def __init__(self, message: str = 'You do not have permission to perform this action.') -> None:
        HTTPException.__init__(self, status_code=403, detail=message)
        self.message = message
        self.code = 'AuthorizationError'


class _BadRequestError(HTTPException, ValidationError):
    """Raised when request inputs fail validation."""

    def __init__(self, message: str = 'Invalid input. Please check your request.') -> None:
        HTTPException.__init__(self, status_code=422, detail=message)
        self.message = message
        self.code = 'ValidationError'


class _ServerError(HTTPException):
    """Raised for unexpected onboarding failures."""

    def __init__(self, message: str = 'Onboarding failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'OnboardingError'


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
_USE_CASE_KEYS = (
    'use_case',
    'onboarding_use_case',
    'service',
    'orchestrator',
    'handler_service',
)
_PAYLOAD_KEYS = ('request', 'payload', 'body', 'data', 'command', 'input', 'onboarding_input')


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


def _is_context(value: Any) -> bool:
    return value is not None and (
        hasattr(value, 'role') and not isinstance(value, (str, Role, dict))
    )


def _is_use_case(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if hasattr(value, 'execute') and callable(getattr(value, 'execute', None)):
        return True
    if hasattr(value, 'run') and callable(getattr(value, 'run', None)):
        return True
    if hasattr(value, 'onboard') and callable(getattr(value, 'onboard', None)):
        return True
    if hasattr(value, 'create_company') and callable(getattr(value, 'create_company', None)):
        return True
    return callable(value) and not _is_context(value)


def _is_system_admin(value: Any) -> bool:
    if value is None:
        return False
    if hasattr(value, 'role') and not isinstance(value, (str, Role, dict)):
        value = value.role
    if hasattr(value, 'value'):
        value = value.value
    if isinstance(value, (list, tuple, set)):
        return any(_is_system_admin(item) for item in value)
    if isinstance(value, dict):
        for key in ('role', 'role_id', 'roleId', 'roles'):
            if key in value:
                return _is_system_admin(value.get(key))
        return False
    text = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    return text == 'system_admin'


def _flatten(obj: Any) -> Any:
    """Flatten a DTO-like object into the field names the use case understands."""
    result: dict[str, Any] = {}
    aliases = {
        'company_name': ('company_name', 'name', 'display_name', 'company_display_name', 'company'),
        'region': ('region', 'preferred_region', 'hosting_region'),
        'admin_email': (
            'admin_email',
            'first_admin_email',
            'email',
            'admin_user_email',
            'user_email',
        ),
        'request_key': ('request_key', 'request_id', 'idempotency_key'),
    }
    for canonical, names in aliases.items():
        value = _get(obj, *names)
        if value is not None:
            result[canonical] = value
    # preserve any already-canonical unexpected keys passed through
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is not None and key not in result:
                result[key] = value
    return result


async def _resolve_use_case(
    candidate: Any, data: dict[str, Any] | None = None, context: Any = None
) -> Any:
    data = data or {}
    _context = context
    if candidate is not None:
        if callable(candidate) and not hasattr(candidate, 'execute'):
            try:
                candidate = candidate()
            except TypeError:
                try:
                    candidate = candidate(_context)
                except TypeError:
                    with contextlib.suppress(TypeError):
                        candidate = candidate(
                            **{k: v for k, v in data.items() if not str(k).startswith('_')}
                        )
        if inspect.isawaitable(candidate):
            candidate = await candidate
        if (
            hasattr(candidate, 'execute')
            or hasattr(candidate, 'run')
            or hasattr(candidate, 'onboard')
        ):
            return candidate
        for attr in (
            'onboarding_use_case',
            'onboarding',
            'use_case',
            'create_company_use_case',
            'service',
        ):
            if hasattr(candidate, attr):
                resolved = getattr(candidate, attr)
                if resolved is not None:
                    return await _resolve_use_case(resolved)
        return candidate
    # Fall back to the composition root (best effort), then a dependency-free use case.
    try:
        if get_onboarding_use_case is not None:
            resolved = get_onboarding_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except (ImportError, AttributeError, TypeError, RuntimeError):
        pass
    return CreateCompany()


async def _run_use_case(use_case: Any, data: dict[str, Any]) -> Any:
    call = getattr(use_case, 'execute', None)
    if not callable(call):
        call = getattr(use_case, 'run', None)
    if not callable(call):
        call = getattr(use_case, 'onboard', None)
    if not callable(call):
        call = getattr(use_case, 'create_company', None)
    if not callable(call):
        raise _ServerError('Onboarding use case is not callable.')
    try:
        outcome = call(data)
    except TypeError:
        outcome = call(**data)
    if inspect.isawaitable(outcome):
        outcome = await outcome
    return outcome


def _as_response(outcome: Any, request_key: str | None) -> Any:
    response = _Response({'status': None})  # type: ignore[name-defined]  # noqa: F821
    if isinstance(outcome, dict):
        response.update(outcome)
    else:
        for attr in (
            'status',
            'company_id',
            'company_id_str',
            'user',
            'admin_user',
            'partition_names',
            'partitions',
            'region',
            'cell',
            'cells',
            'request_key',
        ):
            if hasattr(outcome, attr):
                value = getattr(outcome, attr)
                if value is not None:
                    response[attr] = value
    status_value = response.get('status')
    if status_value is None or str(status_value).lower() in ('none', 'null'):
        status_value = getattr(outcome, 'status', None)
    if status_value is None:
        status_value = 'setting-up'
    response['status'] = str(status_value)
    if request_key is not None and response.get('request_key') is None:
        response['request_key'] = request_key
    # preserve original result for callers/tests that inspect it
    response['_result'] = outcome
    response['result'] = outcome
    return response


__all__ = [
    '_CONTEXT_KEYS',
    '_PAYLOAD_KEYS',
    '_USE_CASE_KEYS',
    'APIRouter',
    'Any',
    'AuthorizationError',
    'Body',
    'CreateCompany',
    'HTTPException',
    'Role',
    'ValidationError',
    '_Any',
    '_BadRequestError',
    '_ForbiddenError',
    '_ServerError',
    '_as_response',
    '_flatten',
    '_get',
    '_is_context',
    '_is_system_admin',
    '_is_use_case',
    '_resolve_use_case',
    '_run_use_case',
    'annotations',
    'contextlib',
    'get_onboarding_use_case',
    'inspect',
    'router',
    'to_user_message',
]
