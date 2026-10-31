# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, S110, E402, I001
"""API entrypoint for the document library and lifecycle (Slice 4.5)."""

from __future__ import annotations
import contextlib
import inspect
from typing import Any
from fastapi import APIRouter, Body, HTTPException
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message

_get_document_repository: Any = None
try:
    from finsight.composition.container import (
        build_document_repository as _build_document_repository,
    )

    def _get_document_repository(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
        if args or kwargs:
            return _build_document_repository(*args, **kwargs)
        try:
            from finsight.composition.container import get_default_container

            container = get_default_container()
            if (
                container is not None
                and getattr(container, 'document_repository', None) is not None
            ):
                return container.document_repository
        except Exception:
            pass
        return _build_document_repository()

except ImportError:  # pragma: no cover
    _get_document_repository = None
from finsight.core.types import Role

get_document_use_case: Any = None
try:
    from finsight.composition.documents import (
        get_document_use_case as _get_document_use_case,
    )

    get_document_use_case = _get_document_use_case
except ImportError:  # pragma: no cover
    pass
router = APIRouter(prefix='/documents', tags=['documents'])


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


class _NotFoundError(HTTPException):
    def __init__(self, message: str = 'Document not found.') -> None:
        HTTPException.__init__(self, status_code=404, detail=message)
        self.message = message
        self.code = 'NotFoundError'


class _ServerError(HTTPException):
    def __init__(self, message: str = 'Document request failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'DocumentError'


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


def _is_repository(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    return any(
        callable(getattr(value, name, None))
        for name in ('list_documents', 'get_document', 'soft_delete_document', 'purge_document')
    )


def _is_use_case(value: Any) -> bool:
    if _is_repository(value):
        return True
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if callable(value) and not hasattr(value, 'execute'):
        # Factories are resolved later.
        return False
    if any(
        hasattr(value, attr) and callable(getattr(value, attr, None))
        for attr in ('execute', 'run', 'handle', 'list_documents', 'get_document')
    ):
        return True
    return callable(value) and not _is_context(value)


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId'),
        'document_id': ('document_id', 'documentId', 'doc_id', 'id', 'document'),
        'query': ('query', 'search', 'q', 'term', 'text'),
        'category': ('category', 'document_category', 'doc_category'),
        'period': ('period', 'reporting_period', 'period_label'),
        'status': ('status', 'document_status', 'state'),
        'action': ('action', 'operation', 'mode', 'kind', 'type'),
        'deleted_retention_days': (
            'deleted_retention_days',
            'retention_days',
            'retentionDays',
        ),
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
    '_get_document_repository',
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
