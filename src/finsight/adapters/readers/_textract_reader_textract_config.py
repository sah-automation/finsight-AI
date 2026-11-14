"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _textract_config(self: Any) -> Any:
    readers = self._readers_config()
    if readers is not None:
        for attr in ('textract',):
            value = readers.get(attr) if isinstance(readers, dict) else getattr(readers, attr, None)
            if value is not None:
                return value
    config = self._config
    if config is None:
        return None
    if hasattr(config, 'textract'):
        return config.textract
    if isinstance(config, dict):
        return config.get('textract')
    return None
