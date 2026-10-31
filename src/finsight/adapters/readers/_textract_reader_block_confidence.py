"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _block_confidence(block: Any) -> Any:
    if isinstance(block, dict):
        for key in ('Confidence', 'confidence'):
            if key in block:
                return block.get(key)
        return None
    for key in ('Confidence', 'confidence'):
        value = getattr(block, key, None)
        if value is not None:
            return value
    return getattr(block, 'Confidence', None)
