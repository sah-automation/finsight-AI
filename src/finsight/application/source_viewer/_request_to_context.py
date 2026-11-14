"""Private request-to-context builder for the source-viewer package.

Pure mapping from the router payload / request context / positional citation to
a populated :class:`SourceViewerContext`. No repositories, storage, audit or
config/env access happens here.
"""

from __future__ import annotations

from typing import Any

from finsight.application.source_viewer._request_keys import (
    _CATEGORY_KEYS,
    _CHUNK_KEYS,
    _CITATION_KEYS,
    _COMPANY_KEYS,
    _CONTEXT_KEYS,
    _DOCUMENT_KEYS,
    _ORIGINAL_KEYS,
    _PAGE_KEYS,
    _PAYLOAD_KEYS,
    _ROLE_KEYS,
    _SCOPE_KEYS,
    _STORAGE_KEY_KEYS,
    _TRACE_KEYS,
    _TTL_KEYS,
    _USE_CASE_KEYS,
    _USER_KEYS,
    _VERSION_KEYS,
)
from finsight.application.source_viewer._step_helpers import (
    _as_int,
    _as_list,
    _coalesce,
    _get_attr,
    decode_locator,
)
from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.core.types import CompanyId


def _decode_locator(token: Any) -> Any:
    try:
        return decode_locator(token)
    except (TypeError, ValueError):
        return None


def _looks_context_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in value for key in _COMPANY_KEYS + _USER_KEYS + _ROLE_KEYS)
    return hasattr(value, 'company_id') or hasattr(value, 'companyId')


def _split_inputs(  # noqa: PLR0912
    args: tuple[Any, ...], kwargs: dict[str, Any]
) -> tuple[Any, dict[str, Any], list[Any]]:
    payload: dict[str, Any] = {}
    context: Any = None
    rest: list[Any] = []
    working = dict(kwargs)

    # Extract context-like values
    for key in _CONTEXT_KEYS:
        if key in working:
            value = working.pop(key)
            if context is None:
                context = value
            elif isinstance(value, dict):
                payload.update(value)
            else:
                payload.setdefault(key, value)

    # Extract payload keys
    for key in _PAYLOAD_KEYS:
        if key in working:
            value = working.pop(key)
            if key in ('citation', 'citation_input'):
                if value is not None:
                    payload[key] = value
            elif isinstance(value, dict):
                payload.update(value)
            elif value is not None:
                payload.setdefault(key, value)

    # Remove use-case keys and merge remaining
    for key in _USE_CASE_KEYS:
        working.pop(key, None)
    payload.update(working)

    # Process positional args
    for value in args:
        if context is None and _looks_context_value(value):
            context = value
        elif isinstance(value, dict):
            payload.update(value)
        else:
            rest.append(value)

    # Fallback: extract context from payload
    if context is None:
        for key in _CONTEXT_KEYS:
            if key in payload:
                context = payload.pop(key)
                break

    ctx_input = _coalesce(payload.get('request'), context)
    if ctx_input is None and rest and _looks_context_value(rest[0]):
        ctx_input = rest.pop(0)

    if _looks_context_value(ctx_input):
        ctx_obj = ctx_input
    else:
        ctx_obj = None
        if ctx_input is not None and not isinstance(ctx_input, dict):
            payload.setdefault('request', ctx_input)

    return ctx_obj, payload, rest


def _build_source_viewer_context(*args: Any, **kwargs: Any) -> SourceViewerContext:
    ctx_obj, payload, rest = _split_inputs(args, kwargs)
    request_obj = payload.get('request')

    company_raw = _coalesce(
        _get_attr(ctx_obj, *_COMPANY_KEYS),
        _get_attr(payload, *_COMPANY_KEYS),
        _get_attr(request_obj, *_COMPANY_KEYS),
    )
    try:
        company_id = CompanyId(str(company_raw)) if company_raw is not None else None
    except (TypeError, ValueError):
        company_id = company_raw

    user_id = _coalesce(
        _get_attr(ctx_obj, *_USER_KEYS),
        _get_attr(payload, *_USER_KEYS),
        _get_attr(request_obj, *_USER_KEYS),
    )
    role = _coalesce(
        _get_attr(ctx_obj, *_ROLE_KEYS),
        _get_attr(payload, *_ROLE_KEYS),
        _get_attr(request_obj, *_ROLE_KEYS),
    )
    trace_id = _coalesce(
        _get_attr(ctx_obj, *_TRACE_KEYS),
        _get_attr(payload, *_TRACE_KEYS),
        _get_attr(request_obj, *_TRACE_KEYS),
    )
    permissions = _coalesce(
        _get_attr(ctx_obj, 'permissions'),
        _get_attr(payload, 'permissions'),
        _get_attr(request_obj, 'permissions'),
    )
    access_scope = _coalesce(
        _get_attr(ctx_obj, *_SCOPE_KEYS),
        _get_attr(payload, *_SCOPE_KEYS),
        _get_attr(request_obj, *_SCOPE_KEYS),
    )
    category = _coalesce(
        _get_attr(payload, *_CATEGORY_KEYS),
        _get_attr(ctx_obj, *_CATEGORY_KEYS),
        _get_attr(request_obj, *_CATEGORY_KEYS),
    )
    citation = _coalesce(
        _get_attr(payload, *_CITATION_KEYS),
        _get_attr(request_obj, *_CITATION_KEYS),
        _get_attr(ctx_obj, *_CITATION_KEYS),
    )
    if citation is None and rest:
        citation = next((item for item in rest if isinstance(item, str) and '.' in item), rest[0])

    document_id = _coalesce(
        _get_attr(payload, *_DOCUMENT_KEYS),
        _get_attr(request_obj, *_DOCUMENT_KEYS),
        _get_attr(ctx_obj, *_DOCUMENT_KEYS),
    )
    version_id = _coalesce(
        _get_attr(payload, *_VERSION_KEYS),
        _get_attr(request_obj, *_VERSION_KEYS),
    )
    chunk_id = _coalesce(
        _get_attr(payload, *_CHUNK_KEYS),
        _get_attr(request_obj, *_CHUNK_KEYS),
    )
    storage_key = _get_attr(payload, *_STORAGE_KEY_KEYS)
    page = _coalesce(
        _get_attr(payload, *_PAGE_KEYS),
        _get_attr(request_obj, *_PAGE_KEYS),
    )

    if citation is not None and not isinstance(citation, str):
        document_id = _coalesce(document_id, _get_attr(citation, *_DOCUMENT_KEYS))
        version_id = _coalesce(version_id, _get_attr(citation, *_VERSION_KEYS))
        chunk_id = _coalesce(chunk_id, _get_attr(citation, *_CHUNK_KEYS))
        if page is None:
            raw_page = _get_attr(citation, *_PAGE_KEYS)
            page = _as_int(raw_page) if _as_int(raw_page) is not None else raw_page
        category = _coalesce(category, _get_attr(citation, *_CATEGORY_KEYS))

    if isinstance(citation, str) and '.' in citation:
        claims = _decode_locator(citation)
        if isinstance(claims, dict) and claims:
            document_id = _coalesce(document_id, claims.get('d'))
            version_id = _coalesce(version_id, claims.get('v'))
            chunk_id = _coalesce(chunk_id, claims.get('c'))
            if page is None:
                raw_page = claims.get('p')
                page = _as_int(raw_page) if _as_int(raw_page) is not None else raw_page

    if isinstance(page, str):
        page = _as_int(page) or page

    ttl_raw = _coalesce(
        _get_attr(payload, *_TTL_KEYS),
        _get_attr(request_obj, *_TTL_KEYS),
    )
    try:
        ttl: Any = int(ttl_raw) if ttl_raw is not None else None
    except (TypeError, ValueError):
        ttl = ttl_raw

    original_requested = any(bool(_get_attr(payload, key)) for key in _ORIGINAL_KEYS) or any(
        bool(_get_attr(request_obj, key)) for key in _ORIGINAL_KEYS
    )

    return SourceViewerContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        trace_id=trace_id,
        permissions=permissions,
        access_scope=_as_list(access_scope),
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
