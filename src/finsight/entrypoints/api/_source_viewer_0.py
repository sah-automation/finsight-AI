# ruff: noqa: BLE001, B004, I001
"""API entrypoint for source viewer backend (Slice 6.7).

Exposes two canonical authenticated endpoints:

- ``GET /documents/{document_id}/citations/{citation_id}/source``
- ``GET /documents/{document_id}/citations/{citation_id}/source/original``

All unavailable / unauthorized / tampered / temporary-storage states collapse to a
single ``404`` response with body ``{"status": "not_available"}``.
"""

from __future__ import annotations
import contextlib
import inspect
from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from finsight.application.source_viewer import SourceViewerResult
from finsight.core.errors import AuthorizationError, ValidationError
from finsight.core.types import Role

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


get_source_viewer_use_case: Any = None
get_source_view_use_case: Any = None
get_view_source_use_case: Any = None
try:
    from finsight.composition.source_viewer import (
        get_source_view_use_case as _get_source_view_use_case,
    )
    from finsight.composition.source_viewer import (
        get_source_viewer_use_case as _get_source_viewer_use_case,
    )
    from finsight.composition.source_viewer import (
        get_view_source_use_case as _get_view_source_use_case,
    )

    get_source_viewer_use_case = _get_source_viewer_use_case
    get_source_view_use_case = _get_source_view_use_case
    get_view_source_use_case = _get_view_source_use_case
except ImportError:  # pragma: no cover
    pass
router = APIRouter(prefix='/documents', tags=['source_viewer'])


class _NotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=404, detail={'status': 'not_available'})
        self.message = 'not_available'
        self.code = 'NotAvailable'


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


class _ServerError(HTTPException):
    def __init__(self, message: str = 'Source unavailable.') -> None:
        super().__init__(status_code=404, detail={'status': 'not_available'})
        self.message = message
        self.code = 'SourceError'


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
    'source_viewer_use_case',
    'source_viewer',
    'source_view_use_case',
    'source_view',
    'view_source_use_case',
    'view_source',
    'service',
    'handler',
    'orchestrator',
    'handler_service',
    'container',
    'composition',
    'app',
    'factory',
)
_PAYLOAD_KEYS = (
    'request',
    'payload',
    'body',
    'data',
    'command',
    'input',
    'source_input',
    'citation_input',
)


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif obj is not None and hasattr(obj, name):
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
        for name in (
            'get_document_version',
            'list_document_versions',
            'list_chunks_by_version',
            'list_document_tables',
            'generate_presigned_download_url',
        )
    )


def _is_use_case(value: Any) -> bool:
    if _is_repository(value):
        return True
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if (
        callable(value)
        and not hasattr(value, 'execute')
        and not hasattr(value, 'run')
        and not hasattr(value, '__call__')
        and not hasattr(value, 'view_original')
        and not hasattr(value, 'view_source')
    ):
        return False
    if any(
        hasattr(value, attr) and callable(getattr(value, attr, None))
        for attr in (
            'execute',
            'run',
            'handle',
            '__call__',
            'view',
            'open',
            'view_original',
            'view_source',
            'source_view',
        )
    ):
        return True
    return callable(value) and not _is_context(value)


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'document_id': ('document_id', 'documentId', 'doc_id', 'document'),
        'citation_id': ('citation_id', 'citationId', 'citation', 'locator', 'citation_locator'),
        'citation': ('citation', 'citation_id', 'citationId', 'citation_locator', 'locator'),
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId'),
        'role': ('role', 'user_role', 'roleId'),
        'access_scope': ('access_scope', 'accessScope', 'scope', 'permission_scope'),
        'user_id': ('user_id', 'userId', 'user', 'uid'),
        'trace_id': ('trace_id', 'traceId', 'trace'),
        'permissions': ('permissions', 'permission_matrix', 'perms'),
        'locator': ('locator', 'citation', 'citation_id', 'citationId', 'citation_locator'),
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


__all__ = [
    '_CONTEXT_KEYS',
    '_PAYLOAD_KEYS',
    '_USE_CASE_KEYS',
    'APIRouter',
    'Any',
    'AuthorizationError',
    'HTTPException',
    'JSONResponse',
    'Role',
    'SourceViewerResult',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_NotFoundError',
    '_ServerError',
    '_await',
    '_flatten',
    '_get',
    '_is_context',
    '_is_repository',
    '_is_use_case',
    'annotations',
    'contextlib',
    'get_source_view_use_case',
    'get_source_viewer_use_case',
    'get_view_source_use_case',
    'inspect',
    'router',
]
