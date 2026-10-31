# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

from typing import Any

from ._s3_storage_helpers import *
from ._s3_storage_supports import _supports


async def get_object(
    self: Any,
    company_id: Any,
    key: Any,
    **kwargs: Any,
) -> bytes:
    scoped_key = self._normalize_key(company_id, key)
    bucket = _first(kwargs, 'bucket', 'bucket_name', 'documents_bucket', default=None)
    if bucket is None:
        bucket = self.bucket
    params = {'Bucket': bucket, 'Key': scoped_key}
    # pass through other kwargs
    params.update(
        {k: v for k, v in kwargs.items() if k not in {'bucket', 'bucket_name', 'documents_bucket'}}
    )

    client = self._get_client()
    result: Any = None
    for method_name in ('get_object', 'get', 'download', 'fetch', 'read', 'read_object'):
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

    if result is None:
        # maybe client is itself callable
        if callable(client):
            try:
                result = client(**params)
                result = await _await_value(result)
            except Exception:
                result = None

    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    if isinstance(result, str):
        return result.encode('utf-8')
    if isinstance(result, dict):
        body = None
        for bkey in (
            'Body',
            'body',
            'Content',
            'content',
            'data',
            'Data',
            'Payload',
            'payload',
        ):
            if bkey in result and result.get(bkey) is not None:
                body = result.get(bkey)
                break
        if body is not None:
            if hasattr(body, 'read'):
                data = body.read()
                data = await _await_value(data)
                return (
                    bytes(data)
                    if not isinstance(data, bytes)
                    else data
                    if isinstance(data, (bytes, bytearray))
                    else str(data).encode('utf-8')
                )
            if isinstance(body, (bytes, bytearray)):
                return bytes(body)
            if isinstance(body, str):
                return body.encode('utf-8')
            return str(body).encode('utf-8')
        # No body; maybe result has 'content'
        for k in ('content', 'Content', 'text'):
            if k in result:
                val = result[k]
                if isinstance(val, (bytes, bytearray)):
                    return bytes(val)
                if isinstance(val, str):
                    return val.encode('utf-8')
        return b''
    if result is None:
        return b''
    if hasattr(result, 'read'):
        data = result.read()
        data = await _await_value(data)
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, str):
            return data.encode('utf-8')
        return str(data).encode('utf-8')
    try:
        return bytes(result)
    except Exception:
        return str(result).encode('utf-8')
