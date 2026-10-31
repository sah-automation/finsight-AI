# ruff: noqa: PLC0415, PLR0912, PLR0915, I001, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import Body, HTTPException
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from ._upload_0 import *
from ._upload_1 import *
from ._upload_2 import *


async def _handle(*args: Any, **kwargs: Any) -> Any:
    context = None
    manager = None
    metadata = None
    checker = None
    use_case_candidate = None
    data: dict[str, Any] = {}
    config = None

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
            key_l in _PARTITION_MANAGER_KEYS
            or ('partition' in key_l and ('manager' in key_l or 'gateway' in key_l))
            or key_l in ('pm', 'partition', 'partitions')
        ):
            manager = value
        elif (
            key_l in _PARTITION_METADATA_KEYS
            or ('partition' in key_l and ('metadata' in key_l or 'repo' in key_l))
            or key_l in ('metadata', 'metadata_repository', 'metadata_repo')
        ):
            metadata = value
        elif key_l in _CHECKER_KEYS or 'checker' in key_l or 'exists' in key_l:
            checker = value
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
            config = value
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
        elif _is_partition_metadata_repo(value):
            if metadata is None:
                metadata = value
        elif _is_partition_manager(value):
            if manager is None:
                manager = value
        elif callable(value) and not _is_context(value):
            if checker is None and not any(
                hasattr(value, a) for a in ('execute', 'run', 'upload', 'handle')
            ):
                checker = value
            elif use_case_candidate is None:
                use_case_candidate = value
            else:
                pass
        elif _is_use_case(value):
            if use_case_candidate is None:
                use_case_candidate = value
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
        for key in _PARTITION_MANAGER_KEYS:
            if key in data and manager is None:
                manager = data.pop(key)
        for key in _PARTITION_METADATA_KEYS:
            if key in data and metadata is None:
                metadata = data.pop(key)
        for key in _CHECKER_KEYS:
            if key in data and checker is None:
                checker = data.pop(key)
        for key in _USE_CASE_KEYS:
            if key in data and use_case_candidate is None:
                use_case_candidate = data.pop(key)
        if 'config' in data and config is None:
            config = data.pop('config')
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')

    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)

    company_id = _extract_company_id(context, data)
    if company_id is not None:
        data['company_id'] = company_id

    role_candidate = None
    if _is_context(context):
        role_candidate = _try_context_role(context)
    if role_candidate is None and isinstance(context, dict):
        role_candidate = _try_context_role(context)
    if role_candidate is None and '_role' in data:
        role_candidate = data.pop('_role', None)

    if company_id is None or str(company_id).strip() == '':
        raise _BadRequestError('company_id is required.')

    try:
        exists = await _partition_exists(manager, metadata, checker, company_id)
    except Exception as exc:
        raise _ServerError(to_user_message(exc)) from exc
    if not exists:
        raise _PartitionMissingError('partition missing')

    await _validate_form(data, config)

    use_case = await _resolve_use_case(use_case_candidate, data, context)
    if use_case is not None:
        try:
            outcome = await _run_use_case(use_case, data)
            return _as_response(outcome, data)
        except AuthorizationError as exc:
            raise _ForbiddenError(getattr(exc, 'message', None) or to_user_message(exc)) from exc
        except ValidationError as exc:
            raise _BadRequestError(getattr(exc, 'message', None) or to_user_message(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise _ServerError(to_user_message(exc)) from exc

    response_data = dict(data)
    response = _as_response(None, response_data)
    if company_id is not None:
        response['company_id'] = company_id
    return response


def upload(*args: Any, **kwargs: Any) -> Any:
    import asyncio as _asyncio

    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    return _asyncio.run(_handle(*args, **kwargs))


handle_upload = upload
upload_document = upload
upload_endpoint = upload
upload_file = upload
submit_upload = upload
handle_file_upload = upload
create_upload = upload
process_upload = upload
run_upload = upload
uploads = upload


async def health() -> dict[str, str]:
    return {'status': 'ok'}


async def http_upload(payload: Any = Body(default=None), context: Any = None) -> Any:
    return await _handle(payload, context=context)


__all__ = [
    '_handle',
    'create_upload',
    'handle_file_upload',
    'handle_upload',
    'health',
    'http_upload',
    'process_upload',
    'run_upload',
    'submit_upload',
    'upload',
    'upload_document',
    'upload_endpoint',
    'upload_file',
    'uploads',
]
