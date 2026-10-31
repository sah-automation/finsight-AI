# ruff: noqa: BLE001, TRY301, B904, I001, F403, F405
from __future__ import annotations
from typing import Any
from finsight.application.source_viewer import SourceViewerResult

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


from ._source_viewer_0 import *
from ._source_viewer_1 import *


from ._source_viewer_2a import *


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
