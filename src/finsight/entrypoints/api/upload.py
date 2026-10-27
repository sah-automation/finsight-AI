"""API entrypoint for document uploads (with partition-existence gate)."""

from __future__ import annotations

import contextlib
import inspect
import re
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from finsight.core.types import DocumentCategory, Role

get_upload_use_case: Any = None
try:
    from finsight.composition.upload import get_upload_use_case as _get_upload_use_case

    get_upload_use_case = _get_upload_use_case
except ImportError:  # pragma: no cover
    pass

router = APIRouter(prefix='/upload', tags=['upload'])


class _ForbiddenError(HTTPException, AuthorizationError):
    def __init__(self, message: str = 'You do not have permission to perform this action.') -> None:
        HTTPException.__init__(self, status_code=403, detail=message)
        self.message = message
        self.code = 'AuthorizationError'


class _BadRequestError(HTTPException, ValidationError):
    def __init__(self, message: str = 'Invalid input. Please check your request.') -> None:
        HTTPException.__init__(self, status_code=422, detail=message)
        self.message = message
        self.code = 'ValidationError'


class _PartitionMissingError(HTTPException):
    def __init__(self, message: str = 'partition missing') -> None:
        HTTPException.__init__(self, status_code=409, detail=message)
        self.message = message
        self.code = 'PartitionMissing'


class _ServerError(HTTPException):
    def __init__(self, message: str = 'Upload failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'UploadError'


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
    'upload_use_case',
    'service',
    'orchestrator',
    'handler_service',
    'upload_service',
)
_PAYLOAD_KEYS = ('request', 'payload', 'body', 'data', 'command', 'input', 'upload_input')
_PARTITION_MANAGER_KEYS = (
    'partition_manager',
    'partition_gateway',
    'partition_manager_port',
    'partition_gateway_port',
    'partition_service',
    'partitioner',
)
_PARTITION_METADATA_KEYS = (
    'partition_metadata_repository',
    'partition_metadata_repo',
    'partition_metadata',
    'partition_repository',
    'partition_repo',
    'partition_metadata_port',
)
_CHECKER_KEYS = (
    'partition_checker',
    'partition_exists_checker',
    'partition_exists',
    'has_partition',
    'check_partition',
    'partition_exists_fn',
    'check_partition_exists',
)

_PERIOD_RE = re.compile(r'^\d{4}-(?:Q[1-4]|\d{2})$')
_STATUS_VALUES = {'draft', 'final'}
_UPLOAD_TYPES = {'new', 'update'}


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


def _is_partition_manager(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if (
        callable(value)
        and not hasattr(value, 'partition_exists')
        and not hasattr(value, 'ensure_partition_exists')
    ):
        return False
    return any(
        hasattr(value, name)
        for name in (
            'partition_exists',
            'has_partition',
            'exists',
            'ensure_partition_exists',
            'list_partitions',
            'get_partition',
            'record_partition',
        )
    )


def _is_partition_metadata_repo(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    return any(
        hasattr(value, name)
        for name in (
            'get_partition',
            'list_partitions_for_company',
            'record_partition',
            'update_status',
            'partition_exists',
        )
    )


def _is_use_case(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if hasattr(value, 'execute') and callable(getattr(value, 'execute', None)):
        return True
    if hasattr(value, 'run') and callable(getattr(value, 'run', None)):
        return True
    if hasattr(value, 'upload') and callable(getattr(value, 'upload', None)):
        return True
    if hasattr(value, 'handle') and callable(getattr(value, 'handle', None)):
        return True
    return callable(value) and not _is_context(value)


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId'),
        'document_category': (
            'document_category',
            'documentCategory',
            'category',
            'doc_category',
            'document_type',
        ),
        'period': ('period', 'reporting_period', 'period_label'),
        'status': ('status', 'document_status', 'state'),
        'upload_type': ('upload_type', 'uploadType', 'type', 'action'),
        'replaces_document_id': (
            'replaces_document_id',
            'replacesDocumentId',
            'replace_document_id',
            'replaces',
        ),
        'file': ('file', 'files', 'filename', 'file_name', 'document', 'documents'),
    }
    for canonical, names in aliases.items():
        value = _get(obj, *names)
        if value is not None:
            result[canonical] = value
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is not None and key not in result:
                result[key] = value
    return result


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call_method(method: Any, company_id: Any, table_name: str | None = None) -> Any:
    context: dict[str, Any] = {'company_id': company_id}
    if table_name is not None:
        context.update(
            {
                'table_name': table_name,
                'table': table_name,
                'partition_table': table_name,
            }
        )
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        sig = None
    if sig is not None:
        kwargs: dict[str, Any] = {}
        for param in sig.parameters.values():
            if param.kind not in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                continue
            if param.name in context:
                kwargs[param.name] = context[param.name]
        missing_required = False
        for param in sig.parameters.values():
            if (
                param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
                and param.default is param.empty
                and param.name not in kwargs
            ):
                missing_required = True
        if not missing_required:
            try:
                return await _await(method(**kwargs))
            except TypeError:
                pass
    if table_name is None:
        try:
            return await _await(method(company_id))
        except TypeError:
            return None
    for attempt in ((company_id, table_name), (company_id,)):
        try:
            return await _await(method(*attempt))
        except TypeError:
            continue
    return None


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
        status = str(getattr(result, 'status')).strip().lower()
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


async def _validate_form(data: dict[str, Any], config: Any = None) -> None:
    company_id = data.get('company_id')
    if company_id is None or str(company_id).strip() == '':
        raise _BadRequestError('company_id is required.')

    upload_type_raw = _get(data, 'upload_type')
    if upload_type_raw is None:
        raise _BadRequestError('upload_type is required (new or update).')
    upload_type = str(upload_type_raw).strip().lower()
    if upload_type not in _UPLOAD_TYPES:
        raise _BadRequestError('upload_type must be new or update.')
    data['upload_type'] = upload_type

    document_category = _get(data, 'document_category')
    if document_category is None:
        raise _BadRequestError('document_category is required.')
    category_text = str(document_category).strip()

    allowed_categories: list[str] | None = None
    if config is not None:
        candidate = None
        if isinstance(config, dict):
            candidate = config.get('documents', config.get('document', {}))
        else:
            candidate = _get(config, 'documents', 'document')
        categories = None
        if isinstance(candidate, dict):
            categories = candidate.get('categories', candidate.get('category', None))
        elif candidate is not None:
            categories = _get(candidate, 'categories', 'category')
        if isinstance(categories, (list, tuple, set)):
            allowed_categories = [str(item) for item in categories]
    request_allowed = _get(data, 'categories', 'allowed_categories', 'document_categories')
    if isinstance(request_allowed, (list, tuple, set)):
        allowed_categories = [str(item) for item in request_allowed]

    if allowed_categories is not None:
        if category_text not in allowed_categories:
            raise _BadRequestError('document_category is not allowed.')
    else:
        try:
            DocumentCategory(category_text)
        except ValueError:
            raise _BadRequestError('document_category is not valid.')
    data['document_category'] = category_text

    period = _get(data, 'period')
    if period is None:
        raise _BadRequestError('period is required.')
    period_text = str(period).strip()
    if not _PERIOD_RE.match(period_text):
        raise _BadRequestError('period must be YYYY-QX or YYYY-MM.')
    data['period'] = period_text

    status_value = _get(data, 'status')
    if status_value is None:
        raise _BadRequestError('status is required (draft or final).')
    status_text = str(status_value).strip().lower()
    if status_text not in _STATUS_VALUES:
        raise _BadRequestError('status must be draft or final.')
    data['status'] = status_text

    if upload_type == 'update':
        replaces = _get(data, 'replaces_document_id')
        if replaces is None or str(replaces).strip() == '':
            raise _BadRequestError('replaces_document_id is required for update uploads.')


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
        loop = _asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    if loop is None:
        return _asyncio.run(_handle(*args, **kwargs))
    return loop.run_until_complete(_handle(*args, **kwargs))


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


class Upload:
    def __init__(
        self, use_case: Any = None, context: Any = None, partition_manager: Any = None, **deps: Any
    ) -> None:
        self.use_case = use_case
        self.context = context
        self.partition_manager = partition_manager
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if (
            self.use_case is not None
            and 'use_case' not in kwargs
            and 'upload_use_case' not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.partition_manager is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('partition_manager', self.partition_manager)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@router.post('')
async def http_upload(payload: Any = Body(default=None), context: Any = None) -> Any:
    return await _handle(payload, context=context)


# Backwards-compatible aliases for varied caller shapes.
UploadHandler = Upload
UploadEndpoint = Upload
UploadEntrypoint = Upload
