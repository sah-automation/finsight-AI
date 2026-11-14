"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _blocks(response: Any) -> Any:
    if isinstance(response, dict):
        blocks = response.get('Blocks', response.get('blocks'))
    else:
        blocks = getattr(response, 'Blocks', None) or getattr(response, 'blocks', None)
    if isinstance(blocks, (list, tuple)):
        return list(blocks)
    if blocks is None:
        return []
    return [blocks]
