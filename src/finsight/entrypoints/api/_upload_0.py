# ruff: noqa: PLR0912, I001
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


__all__ = [
    '_CHECKER_KEYS',
    '_CONTEXT_KEYS',
    '_PARTITION_MANAGER_KEYS',
    '_PARTITION_METADATA_KEYS',
    '_PAYLOAD_KEYS',
    '_PERIOD_RE',
    '_STATUS_VALUES',
    '_UPLOAD_TYPES',
    '_USE_CASE_KEYS',
    'APIRouter',
    'Any',
    'AuthorizationError',
    'Body',
    'DocumentCategory',
    'HTTPException',
    'Role',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_PartitionMissingError',
    '_ServerError',
    '_await',
    '_call_method',
    '_flatten',
    '_get',
    '_is_context',
    '_is_partition_manager',
    '_is_partition_metadata_repo',
    '_is_use_case',
    'annotations',
    'contextlib',
    'get_upload_use_case',
    'inspect',
    're',
    'router',
    'to_user_message',
]
