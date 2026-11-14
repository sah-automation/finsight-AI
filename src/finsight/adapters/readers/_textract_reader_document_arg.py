"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.core.errors import TextractError

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _document_arg(self: Any, source: Any) -> Any:
    if isinstance(source, dict):
        for key in ('bucket', 'Bucket'):
            bucket = source.get(key)
            if bucket:
                key_name = source.get('key', source.get('Key', source.get('object_key')))
                if key_name:
                    return {'S3Object': {'Bucket': bucket, 'Name': key_name}}
        if source.get('Bytes') is not None:
            return {'Bytes': source['Bytes']}
        if source.get('S3Object') is not None:
            return {'S3Object': source['S3Object']}
        for key in ('content', 'data', 'bytes', 'body', 'file'):
            if source.get(key) is not None:
                return self._document_arg(source.get(key))
    if isinstance(source, str):
        if source.lower().startswith('s3://'):
            parts = source[5:].split('/', 1)
            if len(parts) == 2:
                return {'S3Object': {'Bucket': parts[0], 'Name': parts[1]}}
        path_bytes = self._as_bytes(source)
        if path_bytes is not None:
            return {'Bytes': path_bytes}
        raise TextractError('Unable to resolve a Textract document source')
    raw = self._as_bytes(source)
    if raw is not None:
        return {'Bytes': raw}
    bucket = getattr(source, 'bucket', None) or getattr(source, 'Bucket', None)
    key_value: Any = (
        getattr(source, 'key', None)
        or getattr(source, 'Key', None)
        or getattr(source, 'object_key', None)
    )
    if bucket and key_value:
        return {'S3Object': {'Bucket': bucket, 'Name': key_value}}
    raise TextractError('Unable to resolve a Textract document source')
