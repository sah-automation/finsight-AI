"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.core.errors import TextractError

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _get_client(self: Any) -> Any:
    if self._client_override is not None:
        return self._client_override
    if getattr(self, '_client', None) is not None:
        return self._client
    if self._client_factory is not None:
        if not callable(self._client_factory):
            raise TextractError('Textract client factory is not callable')
        client = self._client_factory()
        if client is None:
            raise TextractError('Textract client factory returned None')
        self._client = client
        return client
    try:
        client = self._create_client()
    except Exception as exc:
        raise TextractError(str(exc) or 'Failed to construct Textract client') from exc
    self._client = client
    return client
