# ruff: noqa: BLE001, TRY201, I001, F403, F405
from __future__ import annotations
from typing import Any

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


from ._source_viewer_0 import *
from ._source_viewer_1 import *


async def _invoke(use_case: Any, original: bool, payload: dict[str, Any], context: Any) -> Any:

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


__all__ = ['_invoke']
