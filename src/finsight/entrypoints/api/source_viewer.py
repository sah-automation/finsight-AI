# ruff: noqa: F401, N801, N818, E501, SIM110, PLR1714, RUF100
# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, PLR2004, TRY201, TRY301, S110, S112, B004, B904, E402, I001, F811

# ===== _source_viewer_0.py =====

# ruff: noqa: BLE001, B004, I001
"""API entrypoint for source viewer backend (Slice 6.7).

Exposes two canonical authenticated endpoints:

- ``GET /documents/{document_id}/citations/{citation_id}/source``
- ``GET /documents/{document_id}/citations/{citation_id}/source/original``

All unavailable / unauthorized / tampered / temporary-storage states collapse to a
single ``404`` response with body ``{"status": "not_available"}``.
"""

from __future__ import annotations

from ._shared import (
    _BadRequestError,
    _ForbiddenError,
    _NotFoundError,
    _ServerError,
    _await,
    _flatten,
    _get,
    _is_context,
    _is_use_case,
)

from ._shared import (
    _get as _shared_get,
    _await as _shared_await,
    _ForbiddenError as _shared_ForbiddenError,
    _BadRequestError as _shared_BadRequestError,
    _NotFoundError as _shared_NotFoundError,
    _ServerError as _shared_ServerError,
    _context_lookup as _shared_context_lookup,
    _flatten as _shared_flatten,
    _is_context as _shared_is_context,
    _is_use_case as _shared_is_use_case,
    _sse as _shared_sse,
    _friendly_error as _shared_friendly_error,
    _has_ask_permission as _shared_has_ask_permission,
    _first as _shared_first,
    _build_frozen_request_context as _shared_build_frozen_request_context,
    _resolve_context_and_data as _shared_resolve_context_and_data,
    _events_from_outcome as _shared_events_from_outcome,
    _call_stream as _shared_call_stream,
    _invoke as _shared_invoke,
    _extract_company_id as _shared_extract_company_id,
    _extract_user_id as _shared_extract_user_id,
    _normalize_role as _shared_normalize_role,
    _strip_empty as _shared_strip_empty,
    _try_context_role as _shared_try_context_role,
    _PartitionMissingError as _shared_PartitionMissingError,
)
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
    from finsight.composition.providers import (
        get_source_viewer_use_case as _get_source_viewer_use_case,
    )

    get_source_viewer_use_case = _get_source_viewer_use_case
    get_source_view_use_case = _get_source_viewer_use_case
    get_view_source_use_case = _get_source_viewer_use_case
except ImportError:  # pragma: no cover
    pass
router = APIRouter(prefix='/documents', tags=['source_viewer'])


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

# ===== _source_viewer_1.py =====

# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, S110, S112, B004, I001

import contextlib
import inspect
from typing import Any

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    if candidate is not None:
        if (
            callable(candidate)
            and not hasattr(candidate, 'execute')
            and not hasattr(candidate, 'view_original')
            and not hasattr(candidate, '__call__')
        ):
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
            'source_viewer_use_case',
            'source_viewer',
            'source_view_use_case',
            'source_view',
            'view_source_use_case',
            'view_source',
            'use_case',
            'service',
            'handler',
            'orchestrator',
            'repository',
            'repo',
        ):
            if hasattr(candidate, attr):
                resolved = getattr(candidate, attr)
                if resolved is not None:
                    return await _resolve_use_case(resolved, data, context)
        return candidate

    # Fallback to composition.
    for getter_name in (
        'get_source_viewer_use_case',
        'get_source_view_use_case',
        'get_view_source_use_case',
    ):
        try:
            getter = globals().get(getter_name)
            if getter is not None:
                resolved = getter(**{k: v for k, v in data.items() if not str(k).startswith('_')})
                if inspect.isawaitable(resolved):
                    resolved = await resolved
                if resolved is not None:
                    return resolved
        except Exception:
            continue
    try:
        if get_source_viewer_use_case is not None:
            resolved = get_source_viewer_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except Exception:
        pass
    # Final fallback: build from SourceViewer directly.
    try:
        from finsight.application.source_viewer import SourceViewer

        filtered = {k: v for k, v in data.items() if not str(k).startswith('_')}
        filtered.setdefault('request_context', context)
        return SourceViewer(**filtered)
    except Exception:
        return None


def _extract_context_and_data(*args: Any, **kwargs: Any) -> tuple[Any, Any, dict[str, Any]]:
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
            or key_l in ('service', 'factory', 'container', 'composition', 'app', 'handler')
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
        if 'config' in data and 'config' not in data:
            pass
        if 'role' in data and '_role' not in data:
            data['_role'] = data.pop('role')
        if '_repository' in data and use_case_candidate is None:
            use_case_candidate = data.pop('_repository')

    # Preserve role
    _role_value = data.get('_role', data.get('role'))
    canonical_data = dict(data)
    canonical_data.update(_flatten(canonical_data))
    data = canonical_data
    for key in ('_role',):
        data.pop(key, None)
    if _role_value is not None and 'role' not in data:
        data['role'] = _role_value

    return context, use_case_candidate, data


def _result_status(result: Any) -> str | None:
    if isinstance(result, dict):
        value = result.get('status')
        if value is None:
            value = result.get('outcome')
        if value is None:
            value = result.get('result')
        return None if value is None else str(value)
    value = _get(result, 'status', 'outcome', 'result')
    return None if value is None else str(value)


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict', None)):
        try:
            value = result.to_dict()
            if isinstance(value, dict):
                return dict(value)
        except Exception:
            pass
    output: dict[str, Any] = {}
    for attr in (
        'status',
        'document_id',
        'document_title',
        'title',
        'document_version',
        'version',
        'version_id',
        'page_number',
        'page',
        'content_type',
        'text',
        'table',
        'tables',
        'highlight',
        'needs_review',
        'newer_version_available',
        'newer_version_id',
        'original_available',
        'original_link',
        'original_url',
        'download_url',
        'signed_original_link',
        'citation',
        'citation_locator',
        'locator',
        'company_id',
        'user_id',
        'role',
        'trace_id',
        'outcome',
        'result',
    ):
        if hasattr(result, attr):
            value = getattr(result, attr, None)
            if value is not None or attr in {'text', 'table', 'tables', 'status'}:
                output[attr] = value
    if not output:
        try:
            output = dict(result)
        except Exception:
            output = {'value': result}
    return output


__all__ = ['_extract_context_and_data', '_resolve_use_case', '_result_status', '_result_to_dict']

# ===== _source_viewer_2a.py =====

# ruff: noqa: BLE001, TRY201, I001

from typing import Any

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


async def _invoke_source_viewer(
    use_case: Any, original: bool, payload: dict[str, Any], context: Any
) -> Any:

    call_payload = dict(payload)

    call_payload.setdefault('request_context', context)

    call_payload.setdefault('context', context)

    call_payload.setdefault('ctx', context)

    if original:
        call_payload['_original'] = True

        call_payload['original'] = True

        call_payload['original_only'] = True

        call_payload['mint_original_link'] = True

    method_names = []

    if original:
        method_names.extend(
            [
                'view_original',
                'open_original',
                'get_original',
                'download_original',
                'fetch_original',
                'resolve_original',
                'original',
                'mint_original_link',
                'get_original_download_url',
                'original_download_url',
                'original_url',
                'get_original_url',
                'open_original_file',
                'view_original_file',
                'get_original_file',
                'download_original_file',
                'download_url',
                'mint_original',
                'create_original_link',
                'get_original_link',
                'resolve_original_download',
            ]
        )

    method_names.extend(
        [
            'execute',
            'run',
            'handle',
            '__call__',
            'view',
            'open',
            'view_source',
            'source_view',
            'resolve',
        ]
    )

    method = None

    for name in method_names:
        candidate = getattr(use_case, name, None)

        if callable(candidate):
            method = candidate

            break

    if method is None and callable(use_case):
        method = use_case

    if method is None:
        raise RuntimeError('no callable use case')

    attempts = [
        lambda m=method: m(**call_payload),
        lambda m=method: m(call_payload),
        lambda m=method: m(context, call_payload),
        lambda m=method: m(context, **call_payload),
        lambda m=method: m(),
    ]

    last_error: Exception | None = None

    for attempt in attempts:
        try:
            return await _await(attempt())  # type: ignore[no-untyped-call]

        except TypeError as exc:
            last_error = exc

            continue

        except Exception as exc:
            raise exc

    if last_error is not None:
        raise last_error

    return None


_invoke: Any = _invoke_source_viewer


__all__ = ['_invoke']

# ===== _source_viewer_2.py =====

# ruff: noqa: BLE001, TRY301, B904, I001

from typing import Any
from finsight.application.source_viewer import SourceViewerResult

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


def _available_status(status: str | None) -> bool:
    text = str(status or '').strip().lower()
    return text in {'available', 'success', 'ok'}


async def _handle(*args: Any, **kwargs: Any) -> Any:
    original = False
    for key in (
        'original',
        '_original',
        'original_only',
        'original_file',
        'mint_original',
        'download_original',
    ):
        value = kwargs.pop(key, None)
        if value:
            original = True
    if any(
        str(arg).lower() in {'original', 'original_file', 'download_original'}
        for arg in args
        if isinstance(arg, str)
    ):
        original = True
    # infer from a path-ish extra
    if kwargs.get('path') and 'original' in str(kwargs.get('path')):
        original = True

    context, use_case_candidate, data = _extract_context_and_data(*args, **kwargs)

    document_id = _get(
        data, 'document_id', 'documentId', 'doc_id', default=kwargs.get('document_id')
    )
    citation_id = _get(
        data,
        'citation_id',
        'citationId',
        'citation',
        'locator',
        'citation_locator',
        default=kwargs.get('citation_id'),
    )
    data['document_id'] = document_id
    data['citation_id'] = citation_id

    try:
        use_case = await _resolve_use_case(use_case_candidate, data, context)
        outcome = await _invoke(use_case, original, data, context)
        status = _result_status(outcome)
        result_dict = _result_to_dict(outcome) if outcome is not None else {}

        if not _available_status(status):
            raise _NotFoundError()

        if original:
            link = _get(
                result_dict,
                'original_link',
                'original_url',
                'download_url',
                'signed_original_link',
                'signed_url',
                'url',
                'link',
                'presigned_url',
                'presigned_download_url',
            )
            if link is None and isinstance(outcome, SourceViewerResult):
                link = outcome.original_link
            if link is None:
                raise _NotFoundError()
            payload = {
                'status': 'available',
                'original_link': link,
                'original_available': True,
            }
        else:
            payload = _result_to_dict(outcome)
            for key in (
                'original_link',
                'original_url',
                'download_url',
                'signed_original_link',
                'signed_url',
                'url',
                'link',
                'presigned_url',
                'presigned_download_url',
            ):
                payload.pop(key, None)
            payload['status'] = payload.get('status') or (status or 'available')
    except Exception:
        raise _NotFoundError()

    # Normalize None fields
    if payload.get('table') is None and payload.get('tables'):
        # keep first if available? Use case already decides; leave as is.
        pass

    response = _Response()
    response.update(payload)
    response.status_code = 200
    response['_status_code'] = 200
    return response


def _raise_not_available() -> None:
    raise _NotFoundError()


def source(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'source')
    return _handle(*args, **kwargs)


def view_source(*args: Any, **kwargs: Any) -> Any:
    return source(*args, **kwargs)


def open_source(*args: Any, **kwargs: Any) -> Any:
    return source(*args, **kwargs)


def resolve_source(*args: Any, **kwargs: Any) -> Any:
    return source(*args, **kwargs)


def get_source(*args: Any, **kwargs: Any) -> Any:
    return source(*args, **kwargs)


def source_view(*args: Any, **kwargs: Any) -> Any:
    return source(*args, **kwargs)


def citations_source(*args: Any, **kwargs: Any) -> Any:
    return source(*args, **kwargs)


def original(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs['original'] = True
    return _handle(*args, **kwargs)


def source_original(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def open_original(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def view_original(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def get_original(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def original_source(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def mint_original_link(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def get_original_link(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def original_download_url(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def download_original_url(*args: Any, **kwargs: Any) -> Any:
    return original(*args, **kwargs)


def documents(*args: Any, **kwargs: Any) -> Any:
    # support action switch
    action = str(kwargs.get('action', '')).lower()
    if 'original' in action:
        return original(*args, **kwargs)
    return source(*args, **kwargs)


__all__ = [
    '_available_status',
    '_handle',
    '_invoke',
    '_raise_not_available',
    'citations_source',
    'documents',
    'download_original_url',
    'get_original',
    'get_original_link',
    'get_source',
    'mint_original_link',
    'open_original',
    'open_source',
    'original',
    'original_download_url',
    'original_source',
    'resolve_source',
    'source',
    'source_original',
    'source_view',
    'view_original',
    'view_source',
]

# ===== _source_viewer_3.py =====

# ruff: noqa: BLE001, PLR2004, I001

from typing import Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


def handle_documents(*args: Any, **kwargs: Any) -> Any:
    return documents(*args, **kwargs)


def handle_source_viewer(*args: Any, **kwargs: Any) -> Any:
    return documents(*args, **kwargs)


async def http_source(
    document_id: str, citation_id: str, context: Any = None, **kwargs: Any
) -> Any:
    try:
        return await _handle(
            {'document_id': document_id, 'citation_id': citation_id},
            context=context,
            **kwargs,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={'status': 'not_available'})
        raise
    except Exception:
        return JSONResponse(status_code=404, content={'status': 'not_available'})


async def http_original(
    document_id: str, citation_id: str, context: Any = None, **kwargs: Any
) -> Any:
    try:
        return await _handle(
            {'document_id': document_id, 'citation_id': citation_id},
            context=context,
            original=True,
            **kwargs,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={'status': 'not_available'})
        raise
    except Exception:
        return JSONResponse(status_code=404, content={'status': 'not_available'})


__all__ = ['handle_documents', 'handle_source_viewer', 'http_original', 'http_source']


class SourceViewer:
    """Thin wrapper exposing the source viewer entrypoint as a callable object."""

    def __init__(self, context: Any = None, **deps: Any) -> None:
        from finsight.composition.providers import get_source_viewer_use_case

        self.use_case = get_source_viewer_use_case()
        self.context = context
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if (
            self.use_case is not None
            and 'use_case' not in kwargs
            and 'source_viewer_use_case' not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('source_viewer_use_case', self.use_case)
            kwargs.setdefault('source_view_use_case', self.use_case)
            kwargs.setdefault('view_source_use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


SourceViewerEntrypoint = SourceViewer
SourceViewerHandler = SourceViewer
SourceViewerEndpoint = SourceViewer


__all__ = [
    'SourceViewer',
    'SourceViewerEndpoint',
    'SourceViewerEntrypoint',
    'SourceViewerHandler',
]
