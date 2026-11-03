# ruff: noqa: ANN401, BLE001, C901, E501, I001, N806, PERF403, PLC0415, PLR0912, PLR0915, RUF100, UP035
"""Private request-to-context builder for the source-viewer package.

Pure mapping from the router payload / request context / positional citation to
a populated :class:`SourceViewerContext`. No repositories, storage, audit or
config/env access happens here.
"""

from __future__ import annotations

from typing import Any

from finsight.application.source_viewer._step_helpers import (
    _as_int,
    _as_list,
    _coalesce,
    _first,
    _get_attr,
)
from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.core.types import CompanyId


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
_PAYLOAD_KEYS = (
    'request',
    'payload',
    'body',
    'data',
    'command',
    'input',
    'source_input',
    'citation_input',
    'citation',
)


def _decode_locator(token: Any) -> Any:
    try:
        from finsight.application.source_viewer._step_helpers import decode_locator

        return decode_locator(token)
    except (TypeError, ValueError):
        return None


def _build_source_viewer_context(*args: Any, **kwargs: Any) -> SourceViewerContext:
    payload: dict[str, Any] = {}
    context: Any = None
    rest: list[Any] = []

    working = dict(kwargs)

    # Pull request context aliases.
    for key in _CONTEXT_KEYS:
        if key in working:
            value = working.pop(key)
            if context is None:
                context = value
            elif isinstance(value, dict):
                payload.update(value)
            else:
                payload.setdefault(key, value)

    # Pull payload aliases.
    for key in _PAYLOAD_KEYS:
        if key in working:
            value = working.pop(key)
            if key in ('citation', 'citation_input', 'citation_locator', 'locator'):
                if value is not None:
                    payload[key] = value
            elif isinstance(value, dict):
                payload.update(value)
            elif value is not None:
                payload.setdefault(key, value)

    # Drop use-case / service aliases (handled by the router, ignored here).
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
    for key in _USE_CASE_KEYS:
        working.pop(key, None)

    # Anything else is payload data.
    for key, value in working.items():
        payload[key] = value

    # Classify positional args: context, dict payload, or positional citation.
    for value in args:
        if context is None and _looks_context_value(value):
            context = value
        elif isinstance(value, dict):
            payload.update(value)
        else:
            rest.append(value)

    # If a context alias hides in the merged payload, promote it.
    if context is None:
        for key in _CONTEXT_KEYS:
            if key in payload:
                context = payload.pop(key)
                break

    # Build the request/context input that field extraction reads from.
    ctx_input = _coalesce(payload.get('request'), context)
    if ctx_input is None and len(rest) > 0 and _looks_context_value(rest[0]):
        ctx_input = rest[0]
        rest = rest[1:]

    if _looks_context_value(ctx_input):
        ctx_obj = ctx_input
    else:
        ctx_obj = None
        if ctx_input is not None and not isinstance(ctx_input, dict):
            payload.setdefault('request', ctx_input)

    request_obj = payload.get('request')

    # Company.
    company_raw = _coalesce(
        _ctx_attr(ctx_obj, 'company_id', 'companyId', 'company', 'tenant_id'),
        payload.get('company_id'),
        payload.get('companyId'),
        payload.get('company'),
        payload.get('tenant_id'),
        payload.get('tenantId'),
    )
    if company_raw is None and request_obj is not None:
        company_raw = _get_attr(request_obj, 'company_id', 'companyId', 'company', 'tenant_id')
    try:
        company_id = CompanyId(str(company_raw)) if company_raw is not None else None
    except Exception:
        company_id = company_raw

    # User.
    user_id = _coalesce(
        _ctx_attr(ctx_obj, 'user_id', 'userId', 'user', 'uid'),
        payload.get('user_id'),
        payload.get('userId'),
        payload.get('actor'),
        payload.get('user'),
    )
    if user_id is None and request_obj is not None:
        user_id = _get_attr(request_obj, 'user_id', 'userId', 'user', 'uid')

    # Role.
    role = _coalesce(
        _ctx_attr(ctx_obj, 'role', 'user_role', 'roleId'),
        payload.get('role'),
    )
    if role is None and request_obj is not None:
        role = _get_attr(request_obj, 'role', 'user_role', 'roleId')

    # Trace.
    trace_id = _coalesce(
        _ctx_attr(ctx_obj, 'trace_id', 'traceId', 'trace'),
        payload.get('trace_id'),
        payload.get('traceId'),
        payload.get('trace'),
        payload.get('TraceId'),
    )
    if trace_id is None and request_obj is not None:
        trace_id = _get_attr(request_obj, 'trace_id', 'traceId', 'trace')

    # Permissions.
    permissions = _coalesce(
        _ctx_attr(ctx_obj, 'permissions'),
        payload.get('permissions'),
    )
    if permissions is None and request_obj is not None:
        permissions = _get_attr(request_obj, 'permissions')

    # Access scope.
    access_scope = _coalesce(
        _ctx_attr(ctx_obj, 'access_scope', 'accessScope', 'scope'),
        payload.get('access_scope'),
        payload.get('accessScope'),
        payload.get('AccessScope'),
    )
    if access_scope is None and request_obj is not None:
        access_scope = _get_attr(request_obj, 'access_scope', 'accessScope', 'scope')
    scopes = _as_list(access_scope)

    # Category.
    category = _coalesce(
        payload.get('document_category'),
        payload.get('documentCategory'),
        payload.get('docCategory'),
        payload.get('category'),
        payload.get('doc_category'),
        _ctx_attr(ctx_obj, 'document_category', 'documentCategory', 'category', 'doc_category'),
    )
    if category is None and request_obj is not None:
        category = _get_attr(
            request_obj, 'document_category', 'documentCategory', 'category', 'doc_category'
        )

    # Citation input (string, locator, or object form).
    citation = _coalesce(
        payload.get('citation'),
        payload.get('citation_locator'),
        payload.get('locator'),
        payload.get('citation_id'),
        payload.get('citationId'),
        payload.get('cid'),
        payload.get('citation_input'),
        _get_attr(
            request_obj,
            'citation',
            'citation_locator',
            'locator',
            'citation_id',
            'citation_input',
        )
        if request_obj is not None
        else None,
        _ctx_attr(
            ctx_obj,
            'citation',
            'citation_input',
            'citation_locator',
            'locator',
            'citation_id',
        ),
    )
    # Positional citation.
    if citation is None and rest:
        for item in rest:
            if isinstance(item, str) and '.' in item:
                citation = item
                break
    if citation is None and rest:
        citation = rest[0]

    # Pre-compute document/version/chunk/page aliases (extra + request + ctx).
    document_id = _coalesce(
        payload.get('document_id'),
        payload.get('documentId'),
        payload.get('doc_id'),
        payload.get('docId'),
        payload.get('document'),
        payload.get('docID'),
        _get_attr(request_obj, 'document_id', 'documentId', 'doc_id')
        if request_obj is not None
        else None,
        _ctx_attr(ctx_obj, 'document_id', 'documentId', 'doc_id'),
    )
    version_id = _coalesce(
        payload.get('document_version'),
        payload.get('documentVersion'),
        payload.get('document_version_id'),
        payload.get('documentVersionId'),
        payload.get('version'),
        payload.get('version_id'),
        payload.get('versionId'),
        _get_attr(
            request_obj,
            'document_version',
            'document_version_id',
            'version',
            'version_id',
        )
        if request_obj is not None
        else None,
    )
    chunk_id = _coalesce(
        payload.get('chunk_id'),
        payload.get('chunkId'),
        payload.get('chunkID'),
        payload.get('chunk'),
        payload.get('table_id'),
        payload.get('tableId'),
        payload.get('tableID'),
        payload.get('table'),
        _get_attr(request_obj, 'chunk_id', 'chunkId', 'chunk', 'table_id', 'tableId')
        if request_obj is not None
        else None,
    )
    storage_key = _coalesce(
        payload.get('storage_key'),
        payload.get('storageKey'),
        payload.get('s3_key'),
        payload.get('s3Key'),
        payload.get('object_key'),
        payload.get('objectKey'),
        payload.get('file_key'),
        payload.get('fileKey'),
        payload.get('source_key'),
        payload.get('sourceKey'),
        payload.get('storage_path'),
        payload.get('storagePath'),
        payload.get('s3_path'),
        payload.get('s3Path'),
        payload.get('object_path'),
        payload.get('objectPath'),
        payload.get('path'),
        payload.get('uri'),
    )
    page = _coalesce(
        payload.get('page_number'),
        payload.get('pageNumber'),
        payload.get('pageNo'),
        payload.get('PageNumber'),
        payload.get('page'),
        payload.get('page_no'),
        _get_attr(request_obj, 'page_number', 'pageNumber', 'page')
        if request_obj is not None
        else None,
    )
    # category already computed above.

    # Extract fields from citation object form.
    if citation is not None and not isinstance(citation, str):
        if document_id is None:
            document_id = _first(citation, 'document_id', 'documentId', 'doc_id', 'document')
        if version_id is None:
            version_id = _first(
                citation,
                'document_version',
                'document_version_id',
                'version',
                'version_id',
            )
        if chunk_id is None:
            chunk_id = _first(
                citation, 'chunk_id', 'chunkId', 'chunk', 'table_id', 'tableId', 'table'
            )
        if page is None:
            _page = _first(citation, 'page_number', 'pageNumber', 'page')
            page = _as_int(_page) if _as_int(_page) is not None else _page
        if category is None:
            category = _first(citation, 'document_category', 'documentCategory', 'category')

    # Decode locator claims from signed/unsigned citation strings.
    if isinstance(citation, str) and ('.' in citation):
        loc_payload = _decode_locator(citation)
        if isinstance(loc_payload, dict) and loc_payload:
            if document_id is None:
                document_id = loc_payload.get('d')
            if version_id is None:
                version_id = loc_payload.get('v')
            if chunk_id is None:
                chunk_id = loc_payload.get('c')
            if page is None:
                _loc_page = loc_payload.get('p')
                _loc_page_int = _as_int(_loc_page)
                page = _loc_page_int if _loc_page_int is not None else _loc_page
            # category is not part of locator claims today.

    # Page coercion.
    if isinstance(page, str):
        _page_int = _as_int(page)
        if _page_int is not None:
            page = _page_int

    # TTL.
    ttl_raw = _coalesce(
        payload.get('source_original_link_ttl_seconds'),
        payload.get('sourceOriginalLinkTtlSeconds'),
        payload.get('ttl_seconds'),
        payload.get('ttlSeconds'),
        payload.get('expires_in'),
        payload.get('expiresIn'),
        payload.get('ttl'),
    )
    if ttl_raw is None and request_obj is not None:
        ttl_raw = _get_attr(
            request_obj,
            'source_original_link_ttl_seconds',
            'ttl_seconds',
            'expires_in',
            'ttl',
        )
    if ttl_raw is not None:
        try:
            ttl: Any = int(ttl_raw)
        except (TypeError, ValueError):
            ttl = ttl_raw
    else:
        ttl = None

    # Original flags.
    original_requested = any(
        bool(payload.get(k)) for k in ('_original', 'original', 'original_only')
    ) or (
        request_obj is not None
        and any(bool(_get_attr(request_obj, k)) for k in ('_original', 'original', 'original_only'))
    )

    return SourceViewerContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        trace_id=trace_id,
        permissions=permissions,
        access_scope=scopes,
        category=category,
        citation_input=citation,
        document_id=document_id,
        version_id=version_id,
        chunk_id=chunk_id,
        storage_key=storage_key,
        page=page,
        ttl=ttl,
        original_requested=original_requested,
    )


def _looks_context_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            k in value
            for k in (
                'company_id',
                'companyId',
                'company',
                'tenant_id',
                'user_id',
                'userId',
                'role',
                'permissions',
                'access_scope',
                'accessScope',
                'trace_id',
                'traceId',
            )
        )
    return (
        hasattr(value, 'company_id')
        or hasattr(value, 'companyId')
        or hasattr(value, 'user_id')
        or hasattr(value, 'userId')
    ) and (
        hasattr(value, 'role')
        or hasattr(value, 'permissions')
        or hasattr(value, 'access_scope')
        or hasattr(value, 'accessScope')
        or hasattr(value, 'trace_id')
        or hasattr(value, 'traceId')
    )


def _ctx_attr(obj: Any, *names: str) -> Any:
    return _get_attr(obj, *names)


# --- public/private aliases -------------------------------------------------

build_source_viewer_context = _build_source_viewer_context
build_request_context = _build_source_viewer_context
build_context = _build_source_viewer_context
request_to_context = _build_source_viewer_context
build_source_viewer_request_context = _build_source_viewer_context
map_request_to_context = _build_source_viewer_context
populate_context = _build_source_viewer_context
build_viewer_context = _build_source_viewer_context
build_sv_context = _build_source_viewer_context

# private aliases
_build_context = _build_source_viewer_context
_build_request_context = _build_source_viewer_context
_request_to_context = _build_source_viewer_context
_build_viewer_context = _build_source_viewer_context

__all__ = [
    '_build_context',
    '_build_request_context',
    '_build_source_viewer_context',
    '_build_viewer_context',
    '_request_to_context',
    'build_context',
    'build_request_context',
    'build_source_viewer_context',
    'build_source_viewer_request_context',
    'build_sv_context',
    'build_viewer_context',
    'map_request_to_context',
    'populate_context',
    'request_to_context',
]
