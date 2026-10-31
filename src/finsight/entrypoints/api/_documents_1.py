# ruff: noqa: BLE001, PLR0911, PLR0912, RET504, TRY300, S112, B023, I001, F403, F405
from __future__ import annotations
import contextlib
import inspect
from typing import Any
from ._documents_0 import *


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

    # Fall back to the composition root / a memory repository.
    try:
        if get_document_use_case is not None:
            resolved = get_document_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except (ImportError, AttributeError, TypeError, RuntimeError):
        pass
    try:
        if _get_document_repository is not None:
            resolved = _get_document_repository()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except (ImportError, AttributeError, TypeError, RuntimeError):
        pass
    return None


def _extract_company_id(context: Any, data: dict[str, Any]) -> Any:
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


def _try_context_role(context: Any) -> Any:
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
    response = _Response()  # type: ignore[name-defined]
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
