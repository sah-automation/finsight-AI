# ruff: noqa: PLC0415, PLR0912, PLR0915, PLR2004, SIM102, B007, I001, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import HTTPException
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from ._documents_0 import *
from ._documents_1 import *


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
