"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _switches_async(self: Any) -> bool | None:
    config = self._config
    switches = None
    if config is not None:
        switches = (
            getattr(config, 'switches', None)
            if not isinstance(config, dict)
            else config.get('switches')
        )
        readers = self._readers_config()
        if switches is None and isinstance(readers, dict):
            switches = readers.get('switches')
    if switches is None:
        return None
    for key in ('async_textract_enabled', 'textract_async_enabled', 'async_enabled'):
        value = switches.get(key) if isinstance(switches, dict) else getattr(switches, key, None)
        if value is not None:
            return bool(value)
    return None
