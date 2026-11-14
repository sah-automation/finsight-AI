# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._s3_storage_helpers import *
from ._s3_storage_supports import _supports


async def head_object(*args: Any, **kwargs: Any) -> Any:
    return await _head_object_impl(*args, **kwargs)


async def _head_object_impl(
    self: Any,
    company_id: Any,
    key: Any,
    **kwargs: Any,
) -> dict[str, object]:
    scoped_key = self._normalize_key(company_id, key)
    bucket = _first(kwargs, 'bucket', 'bucket_name', 'documents_bucket', default=None)
    if bucket is None:
        bucket = self.bucket
    params = {'Bucket': bucket, 'Key': scoped_key}
    params.update(
        {k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name', 'documents_bucket'}}
    )

    client = self._get_client()
    result: Any = None
    for method_name in (
        'head_object',
        'head',
        'stat',
        'metadata',
        'get_object_metadata',
        'describe_object',
    ):
        method = getattr(client, method_name, None)
        if callable(method):
            try:
                if _supports(client, method_name, params):
                    result = method(**params)
                else:
                    result = method(**params)
            except TypeError:
                try:
                    result = method(bucket, scoped_key)
                except TypeError:
                    try:
                        result = method(scoped_key)
                    except TypeError:
                        result = None
            result = await _await_value(result)
            if result is not None:
                break

    if result is None and callable(client):
        try:
            result = client(**params)
            result = await _await_value(result)
        except Exception:
            result = None

    if isinstance(result, dict):
        return result
    if result is None:
        return {}
    return {'result': result, 'metadata': result}


# ------------------------------------------------------------------ aliases
