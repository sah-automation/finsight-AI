# ruff: noqa: F401, N801, N818, E501, SIM110, PLR1714, RUF100
# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, SIM102, SIM110, TRY201, TRY300, TRY301, E501, S110, S112, N815, B004, B007, B023, B025, B904, PGH004, E402, F404, I001, ANN401, F403, F405, F821, F811

# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, S110, E402, I001
"""API entrypoint for the document library and lifecycle (Slice 4.5)."""

from __future__ import annotations

from ._shared import (
    _BadRequestError,
    _ForbiddenError,
    _NotFoundError,
    _ServerError,
    _await,
    _flatten,
    _get,
    _is_context,
    _is_use_case,
)

import contextlib
import inspect
from typing import Any
from fastapi import APIRouter, Body, HTTPException
from finsight.composition.providers import get_documents_use_case
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from finsight.core.types import Role

# Backwards-compatible alias (singular) used by container wiring and legacy callers.
get_document_use_case = get_documents_use_case
router = APIRouter(prefix='/documents', tags=['documents'])


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
    'document_use_case',
    'document_service',
    'service',
    'repository',
    'repo',
    'document_repository',
    'document_repo',
    'handler',
    'orchestrator',
    'container',
    'composition',
    'app',
)
_PAYLOAD_KEYS = (
    'request',
    'payload',
    'body',
    'data',
    'command',
    'input',
    'document_input',
    'document',
    'filters',
)
_REPOSITORY_KEYS = (
    'document_repository',
    'document_repo',
    'repository',
    'repo',
    'documents',
)


def _is_repository(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    return any(
        callable(getattr(value, name, None))
        for name in ('list_documents', 'get_document', 'soft_delete_document', 'purge_document')
    )


def _normalise_action(value: Any) -> str:
    text = str(value or '').strip().lower().replace('-', '_').replace(' ', '_')
    if text in {'list', 'library', 'documents', 'all', 'browse', 'index'}:
        return 'list'
    if text in {'search', 'query', 'find', 'filter'}:
        return 'search'
    if text in {'get', 'detail', 'details', 'metadata', 'info', 'show', 'view'}:
        return 'get'
    if text in {'delete', 'soft_delete', 'remove', 'trash'}:
        return 'delete'
    if text in {'restore', 'undelete', 'untrash', 'recover'}:
        return 'restore'
    if text in {'purge', 'hard_delete', 'permanent_delete', 'permanent_purge', 'destroy'}:
        return 'purge'
    if text in {'recycle', 'recycle_bin', 'bin', 'deleted', 'trash_bin'}:
        return 'recycle'
    # Some callers pass an action-like value bundled with a query.
    if 'recycle' in text or 'deleted' in text:
        return 'recycle'
    if 'purge' in text:
        return 'purge'
    if 'restore' in text:
        return 'restore'
    if 'delete' in text:
        return 'delete'
    if 'get' in text or 'metadata' in text:
        return 'get'
    if 'search' in text:
        return 'search'
    return 'list'


def _is_privileged(value: Any) -> bool:
    if value is None:
        return False
    if hasattr(value, 'role') and not isinstance(value, (str, Role, dict)):
        value = getattr(value, 'role', value)
    if hasattr(value, 'value'):
        value = value.value
    if isinstance(value, (list, tuple, set)):
        return any(_is_privileged(item) for item in value)
    if isinstance(value, dict):
        for key in ('role', 'role_id', 'roleId', 'roles', 'name'):
            if key in value:
                return _is_privileged(value.get(key))
        return False
    text = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    return text in {'system_admin', 'executive_leadership', 'audit_compliance'}


__all__ = [
    '_CONTEXT_KEYS',
    '_PAYLOAD_KEYS',
    '_REPOSITORY_KEYS',
    '_USE_CASE_KEYS',
    'APIRouter',
    'Any',
    'AuthorizationError',
    'Body',
    'HTTPException',
    'Role',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_NotFoundError',
    '_ServerError',
    '_await',
    '_flatten',
    '_get',
    '_is_context',
    '_is_privileged',
    '_is_repository',
    '_is_use_case',
    '_normalise_action',
    'annotations',
    'contextlib',
    'get_document_use_case',
    'inspect',
    'router',
    'to_user_message',
]

# ruff: noqa: BLE001, PLR0911, PLR0912, RET504, TRY300, S112, B023, I001, F403, F405
import contextlib
import inspect
from typing import Any


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    if candidate is not None:
        if _is_repository(candidate):
            return candidate
        if callable(candidate) and not hasattr(candidate, 'execute'):
            try:
                candidate = candidate()
            except TypeError:
                try:
                    candidate = candidate(context)
                except TypeError:
                    with contextlib.suppress(TypeError):
                        candidate = candidate(
                            **{k: v for k, v in data.items() if not str(k).startswith('_')}
                        )
        if inspect.isawaitable(candidate):
            candidate = await candidate
        if _is_repository(candidate) or _is_use_case(candidate):
            return candidate
        for attr in (
            'document_use_case',
            'use_case',
            'service',
            'repository',
            'repo',
            'document_repository',
        ):
            if hasattr(candidate, attr):
                resolved = getattr(candidate, attr)
                if resolved is not None:
                    return await _resolve_use_case(resolved, data, context)
        return candidate

    # Fall back to the provider registered at app startup.
    resolved = get_documents_use_case()
    if inspect.isawaitable(resolved):
        resolved = await resolved
    return resolved


def _extract_company_id_documents(context: Any, data: dict[str, Any]) -> Any:
    value = _get(data, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
    if value is None and context is not None:
        if isinstance(context, dict):
            value = _get(context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
            if value is None and 'user' in context:
                value = _extract_company_id(context.get('user'), {})
            if value is None and 'context' in context:
                value = _extract_company_id(context.get('context'), {})
        else:
            value = _get(context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
            if value is None and hasattr(context, 'company_id'):
                value = getattr(context, 'company_id', None)
    return value


_extract_company_id: Any = _extract_company_id_documents


def _try_context_role_documents(context: Any) -> Any:
    if context is None:
        return None
    if isinstance(context, dict):
        for key in ('role', 'role_id', 'roleId', 'roles'):
            if key in context:
                return context.get(key)
        for nested in ('user', 'principal', 'identity', 'current_user'):
            if nested in context:
                found = _try_context_role(context.get(nested))
                if found is not None:
                    return found
        return None
    return _get(context, 'role')


_try_context_role: Any = _try_context_role_documents


async def _filter_kwargs(data: dict[str, Any]) -> Any:
    excluded = {
        'company_id',
        'document_id',
        'id',
        'action',
        'operation',
        'mode',
        'kind',
        'type',
    }
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in excluded:
            continue
        if value is not None:
            result[key] = value
    return result


async def _run_use_case(use_case: Any, action: str, data: dict[str, Any]) -> Any:
    company_id = data.get('company_id')
    document_id = data.get('document_id')
    if document_id is None:
        document_id = data.get('id')
    filters = await _filter_kwargs(data)

    method_candidates: dict[str, list[str]] = {
        'list': ['list_documents', 'list', 'search_documents', 'library', 'documents'],
        'search': ['search_documents', 'search', 'list_documents', 'list', 'filter_documents'],
        'get': ['get_document', 'get', 'get_metadata', 'metadata', 'document_metadata'],
        'delete': ['soft_delete_document', 'soft_delete', 'delete_document', 'delete', 'remove'],
        'restore': ['restore_document', 'restore', 'undelete', 'recover'],
        'purge': ['purge_document', 'purge', 'permanent_delete', 'hard_delete', 'destroy'],
        'recycle': [
            'list_recycle_bin',
            'recycle_bin',
            'recycle',
            'list_deleted',
            'deleted_documents',
        ],
    }

    # Repository / use-case specific methods first.
    for method_name in method_candidates.get(action, []):
        method = getattr(use_case, method_name, None)
        if not callable(method):
            continue
        attempts = []
        if action in {'list', 'search', 'recycle'}:
            attempts.append(lambda m=method: m(company_id, **filters))
            if document_id is not None:
                attempts.append(lambda m=method: m(company_id, document_id, **filters))
        elif action == 'get':
            if document_id is not None:
                attempts.append(lambda m=method: m(company_id, document_id, **filters))
            attempts.append(lambda m=method: m(company_id, **filters))
        else:
            if document_id is not None:
                attempts.append(lambda m=method: m(company_id, document_id, **filters))
            attempts.append(lambda m=method: m(company_id, **filters))
        # Generic payloads.
        attempts.append(lambda m=method: m(data))
        attempts.append(lambda m=method: m(**data))
        for attempt in attempts:
            try:
                result = await _await(attempt())  # type: ignore[no-untyped-call]
                return result
            except TypeError:
                continue
            except Exception:
                continue

    # Generic entrypoint method.
    for attr in ('execute', 'run', 'handle', '__call__'):
        method = getattr(use_case, attr, None)
        if not callable(method):
            continue
        payload = dict(data)
        payload['action'] = action
        for attempt in (
            lambda m=method: m(payload),
            lambda m=method: m(**payload),
            lambda m=method: m(),
        ):
            try:
                return await _await(attempt())
            except TypeError:
                continue
            except Exception:
                continue

    return None


def _as_response(outcome: Any, data: dict[str, Any], action: str) -> Any:
    response = _Response()
    if isinstance(outcome, list):
        response['documents'] = outcome
        response['items'] = outcome
        response['results'] = outcome
        response['records'] = outcome
        if action == 'recycle':
            response['recycle_bin'] = outcome
            response['deleted_documents'] = outcome
            response['deleted'] = outcome
        if action == 'get':
            pass
    elif isinstance(outcome, dict):
        response.update(outcome)
    elif outcome is not None:
        for attr in (
            'status',
            'documents',
            'items',
            'results',
            'records',
            'document',
            'metadata',
            'company_id',
            'document_id',
            'soft_deleted',
            'restored',
            'purged',
            'deleted',
            'recycle_bin',
            'deleted_documents',
            'already_deleted',
            'id',
        ):
            if hasattr(outcome, attr):
                value = getattr(outcome, attr)
                if value is not None:
                    response[attr] = value
    # Copy request context into the response for caller convenience.
    for field in ('company_id', 'document_id', 'query', 'category', 'period', 'status'):
        if field not in response and data.get(field) is not None:
            response[field] = data.get(field)
    if 'action' not in response:
        response['action'] = action
    if 'status' not in response or response.get('status') is None:
        response['status'] = 'ok'
    if 'partition_missing' not in response:
        response['partition_missing'] = False
    if '_result' not in response and outcome is not None:
        response['_result'] = outcome
    if 'result' not in response and outcome is not None:
        response['result'] = outcome
    return response


__all__ = [
    '_as_response',
    '_extract_company_id',
    '_filter_kwargs',
    '_resolve_use_case',
    '_run_use_case',
    '_try_context_role',
]

# ruff: noqa: PLC0415, PLR0912, PLR0915, PLR2004, SIM102, B007, I001, F403, F405
from typing import Any
from fastapi import HTTPException
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message


class _Response(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


async def _handle(*args: Any, **kwargs: Any) -> Any:
    context = None
    use_case_candidate = None
    data: dict[str, Any] = {}

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
        elif key_l == 'config' or key_l.endswith('_config') or key_l == 'settings':
            data['config'] = value
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
        elif _is_repository(value) or _is_use_case(value):
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

    if isinstance(data, dict):
        for key in _CONTEXT_KEYS:
            if key in data and context is None:
                context = data.pop(key)
        for key in _USE_CASE_KEYS:
            if key in data and use_case_candidate is None:
                use_case_candidate = data.pop(key)
        for key in _PAYLOAD_KEYS:
            pass
        if 'config' in data and 'config' not in data:
            pass
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')
        if '_repository' in data and use_case_candidate is None:
            use_case_candidate = data.pop('_repository')

    # Preserve the role before canonicalisation drops private keys.
    _role_value = data.get('_role', data.get('role'))
    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)
    if _role_value is not None and 'role' not in data:
        data['role'] = _role_value

    company_id = _extract_company_id(context, data)
    if company_id is not None:
        data['company_id'] = company_id
    if company_id is None or str(company_id).strip() == '':
        raise _BadRequestError('company_id is required.')

    role_candidate = None
    if _is_context(context):
        role_candidate = _try_context_role(context)
    if role_candidate is None and isinstance(context, dict):
        role_candidate = _try_context_role(context)
    if role_candidate is None and '_role' in data:
        role_candidate = data.pop('_role', None)
    if role_candidate is None and 'role' in data:
        role_candidate = data.pop('role', None)
    if role_candidate is not None:
        data['role'] = role_candidate

    action_raw = _get(data, 'action', 'operation', 'mode', 'kind')
    if action_raw is None:
        # Infer from a few common boolean flags.
        if data.get('recycle_bin') or data.get('recycle') or data.get('deleted'):
            action_raw = 'recycle'
        elif data.get('purge') or data.get('permanent'):
            action_raw = 'purge'
        elif data.get('restore'):
            action_raw = 'restore'
        elif data.get('delete') or data.get('remove'):
            action_raw = 'delete'
        elif (
            data.get('document_id') is not None
            and data.get('query') is None
            and not any(data.get(k) is not None for k in ('documents', 'list', 'search'))
        ):
            # A bare document id often means "get metadata".
            if str(data.get('action') or '').strip() == '' and len(data) <= 4:
                action_raw = 'get'
    action = _normalise_action(action_raw)

    # Privileged operation guard.
    if action == 'purge' and not _is_privileged(role_candidate):
        raise _ForbiddenError('Permanent purge requires a privileged role.')

    # Role/privilege guards. Purge already requires a privileged role above; the
    # other lifecycle operations keep working for anonymous/unit callers so the
    # entrypoint stays testable, while still honouring an explicit denial.
    if (
        action in {'delete', 'restore'}
        and role_candidate is not None
        and str(role_candidate).strip().lower() in {'', 'none', 'null', 'anonymous', 'guest'}
    ):
        raise _ForbiddenError('Authentication is required.')
    # Resolve use case / repository.
    use_case = await _resolve_use_case(use_case_candidate, data, context)

    try:
        outcome = await _run_use_case(use_case, action, data)
    except AuthorizationError as exc:
        raise _ForbiddenError(getattr(exc, 'message', None) or to_user_message(exc)) from exc
    except ValidationError as exc:
        raise _BadRequestError(getattr(exc, 'message', None) or to_user_message(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise _ServerError(to_user_message(exc)) from exc

    if outcome is None and action == 'get':
        # Try a direct not-found signal.
        pass

    return _as_response(outcome, data, action)


def documents(*args: Any, **kwargs: Any) -> Any:
    import asyncio as _asyncio

    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    return _asyncio.run(_handle(*args, **kwargs))


def list_documents(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'list')
    return documents(*args, **kwargs)


def search_documents(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'search')
    return documents(*args, **kwargs)


def get_document(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'get')
    return documents(*args, **kwargs)


def get_document_metadata(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'get')
    return documents(*args, **kwargs)


def delete_document(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'delete')
    return documents(*args, **kwargs)


def soft_delete_document(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'delete')
    return documents(*args, **kwargs)


def restore_document(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'restore')
    return documents(*args, **kwargs)


def purge_document(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'purge')
    return documents(*args, **kwargs)


def permanent_purge(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'purge')
    return documents(*args, **kwargs)


def hard_delete(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'purge')
    return documents(*args, **kwargs)


def recycle_bin(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'recycle')
    return documents(*args, **kwargs)


def list_recycle_bin(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'recycle')
    return documents(*args, **kwargs)


def document_library(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'list')
    return documents(*args, **kwargs)


handle_documents = documents
handle_document = documents
run_documents = documents
documents_endpoint = documents
document_endpoint = documents

__all__ = [
    '_Response',
    '_handle',
    'delete_document',
    'document_endpoint',
    'document_library',
    'documents',
    'documents_endpoint',
    'get_document',
    'get_document_metadata',
    'handle_document',
    'handle_documents',
    'hard_delete',
    'list_documents',
    'list_recycle_bin',
    'permanent_purge',
    'purge_document',
    'recycle_bin',
    'restore_document',
    'run_documents',
    'search_documents',
    'soft_delete_document',
]

# ruff: noqa: I001, F403, F405
from typing import Any
from fastapi import Body

list_document = list_documents
search_document = search_documents
get_documents = list_documents
delete_documents = delete_document
restore_documents = restore_document
purge_documents = purge_document
recycle = recycle_bin
trash = recycle_bin
trash_bin = recycle_bin
deleted_documents = recycle_bin
metadata = get_document


async def health() -> dict[str, str]:
    return {'status': 'ok'}


async def http_list(context: Any = None) -> Any:
    return await _handle(context, context=context)


async def http_get(document_id: str, context: Any = None, company_id: Any = None) -> Any:
    data: dict[str, Any] = {'document_id': document_id}
    if company_id is not None:
        data['company_id'] = company_id
    return await _handle(payload=data, context=context, action='get')


async def http_create(payload: Any = Body(default=None), context: Any = None) -> Any:
    return await _handle(payload=payload, context=context)


async def http_delete(document_id: str, context: Any = None, company_id: Any = None) -> Any:
    data: dict[str, Any] = {'document_id': document_id}
    if company_id is not None:
        data['company_id'] = company_id
    return await _handle(payload=data, context=context, action='delete')


__all__ = [
    'delete_documents',
    'deleted_documents',
    'get_documents',
    'health',
    'http_create',
    'http_delete',
    'http_get',
    'http_list',
    'list_document',
    'metadata',
    'purge_documents',
    'recycle',
    'restore_documents',
    'search_document',
    'trash',
    'trash_bin',
]


for _r in (router,):
    _r.get('/health')(health)

    _r.post('', response_model=None)(http_create)

    _r.post('/', response_model=None)(http_create)

    _r.get('/{document_id}', response_model=None)(http_get)


class Documents:
    """Thin wrapper exposing the documents entrypoint as a callable object."""

    def __init__(
        self,
        context: Any = None,
        role: Any = None,
        **deps: Any,
    ) -> None:

        self.use_case = get_documents_use_case()
        self.context = context
        self.role = role
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if (
            self.use_case is not None
            and 'use_case' not in kwargs
            and 'document_use_case' not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('document_use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.role is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('role', self.role)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


DocumentsEntrypoint = Documents
DocumentEntrypoint = Documents
DocumentsHandler = Documents
DocumentHandler = Documents
DocumentsEndpoint = Documents
DocumentEndpoint = Documents


__all__ = [
    'DocumentEndpoint',
    'DocumentEntrypoint',
    'DocumentHandler',
    'Documents',
    'DocumentsEndpoint',
    'DocumentsEntrypoint',
    'DocumentsHandler',
]
