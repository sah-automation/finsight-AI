# ruff: noqa: BLE001, PLR0911, PLR0912, S110, I001, ANN401, F403, F405
from __future__ import annotations
import contextlib
import inspect
from typing import Any
from ._upload_0 import *


def _truthy(result: Any) -> bool:
    if result is None:
        return False
    if isinstance(result, bool):
        return result
    if isinstance(result, str):
        return bool(result.strip())
    if isinstance(result, (list, tuple, set, dict)):
        return len(result) > 0
    if hasattr(result, 'status'):
        status = str(result.status).strip().lower()
        if status in ('', 'none', 'null'):
            return True
        return status not in ('missing', 'not_found', 'failed', 'error')
    return True


async def _partition_exists(
    manager: Any,
    metadata: Any,
    checker: Any,
    company_id: Any,
) -> bool:
    if checker is not None:
        if (
            callable(checker)
            and not hasattr(checker, 'partition_exists')
            and not hasattr(checker, 'ensure_partition_exists')
        ):
            try:
                result = checker(company_id)
                return _truthy(await _await(result))
            except TypeError:
                try:
                    result = checker()
                    return _truthy(await _await(result))
                except Exception:
                    pass
        else:
            for attr in (
                'partition_exists',
                'has_partition',
                'exists',
                'check_partition',
                'check_partition_exists',
            ):
                method = getattr(checker, attr, None)
                if callable(method):
                    result = await _call_method(method, company_id, 'documents')
                    if result is not None:
                        return _truthy(result)
            method = getattr(checker, 'list_partitions', None)
            if callable(method):
                result = await _call_method(method, company_id)
                if result is not None:
                    return _truthy(result)
            method = getattr(checker, 'get_partition', None)
            if callable(method):
                result = await _call_method(method, company_id, 'documents')
                if result is not None:
                    return _truthy(result)

    if manager is not None:
        for attr in (
            'partition_exists',
            'has_partition',
            'exists',
            'is_partitioned',
            'check_partition',
            'check_partition_exists',
        ):
            method = getattr(manager, attr, None)
            if callable(method):
                result = await _call_method(method, company_id, None)
                if result is not None:
                    return _truthy(result)
        for attr in ('get_partition', 'get_partition_metadata', 'find_partition'):
            method = getattr(manager, attr, None)
            if callable(method):
                result = await _call_method(method, company_id, 'documents')
                if result is not None:
                    return _truthy(result)
        method = getattr(manager, 'list_partitions', None)
        if callable(method):
            result = await _call_method(method, company_id, None)
            if result is not None:
                return _truthy(result)

    if metadata is not None:
        for attr in ('partition_exists', 'has_partition', 'exists', 'check_partition'):
            method = getattr(metadata, attr, None)
            if callable(method):
                result = await _call_method(method, company_id, 'documents')
                if result is not None:
                    return _truthy(result)
        for attr in ('get_partition', 'get_partition_metadata', 'find_partition'):
            method = getattr(metadata, attr, None)
            if callable(method):
                result = await _call_method(method, company_id, 'documents')
                if result is not None:
                    return _truthy(result)
        for attr in ('list_partitions_for_company', 'list_partitions'):
            method = getattr(metadata, attr, None)
            if callable(method):
                result = await _call_method(method, company_id, None)
                if result is not None:
                    return _truthy(result)

    if manager is None and metadata is None and checker is None:
        return False
    return False


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    if candidate is not None:
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
        if (
            hasattr(candidate, 'execute')
            or hasattr(candidate, 'run')
            or hasattr(candidate, 'upload')
        ):
            return candidate
        for attr in ('upload_use_case', 'upload', 'use_case', 'service'):
            if hasattr(candidate, attr):
                resolved = getattr(candidate, attr)
                if resolved is not None:
                    return await _resolve_use_case(resolved, data, context)
        return candidate
    try:
        if get_upload_use_case is not None:
            resolved = get_upload_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except (ImportError, AttributeError, TypeError, RuntimeError):
        pass
    return None


async def _run_use_case(use_case: Any, data: dict[str, Any]) -> Any:
    for attr in ('execute', 'run', 'upload', 'handle'):
        call = getattr(use_case, attr, None)
        if callable(call):
            try:
                outcome = call(data)
            except TypeError:
                outcome = call(**data)
            if inspect.isawaitable(outcome):
                outcome = await outcome
            return outcome
    if callable(use_case):
        try:
            outcome = use_case(data)
        except TypeError:
            outcome = use_case(**data)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        return outcome
    raise _ServerError('Upload use case is not callable.')


def _as_response(outcome: Any, data: dict[str, Any]) -> dict[str, Any]:
    response = _UploadResponse()
    if isinstance(outcome, dict):
        response.update(outcome)
    for field in (
        'company_id',
        'document_category',
        'period',
        'upload_type',
        'replaces_document_id',
        'file',
    ):
        if field not in response and isinstance(data, dict) and data.get(field) is not None:
            response[field] = data.get(field)
    if (
        'document_status' not in response
        and isinstance(data, dict)
        and data.get('status') is not None
    ):
        response['document_status'] = data.get('status')
    if outcome is not None and not isinstance(outcome, dict):
        for attr in (
            'status',
            'upload_status',
            'message',
            'company_id',
            'company_id_str',
            'document_category',
            'period',
            'upload_type',
            'replaces_document_id',
            'file',
            'presigned_url',
            'upload_url',
            'partition_missing',
        ):
            if hasattr(outcome, attr):
                value = getattr(outcome, attr)
                if value is not None:
                    response[attr] = value
    if 'partition_missing' not in response:
        response['partition_missing'] = False
    if 'status' not in response:
        response['status'] = 'accepted'
    if 'upload_status' not in response:
        response['upload_status'] = response['status']
    if 'accepted' not in response:
        response['accepted'] = True
    if 'result' not in response and outcome is not None:
        response['result'] = outcome
    if '_result' not in response and outcome is not None:
        response['_result'] = outcome
    return response


class _UploadResponse(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


__all__ = [
    '_UploadResponse',
    '_as_response',
    '_partition_exists',
    '_resolve_use_case',
    '_run_use_case',
    '_truthy',
]
