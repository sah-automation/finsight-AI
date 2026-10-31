"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _block_page(block: Any) -> Any:
    page = None
    if isinstance(block, dict):
        page = block.get('Page', block.get('page'))
    else:
        page = getattr(block, 'Page', getattr(block, 'page', None))
    if page is None:
        return 1
    try:
        value = int(page)
    except (TypeError, ValueError):
        return 1
    if isinstance(page, bool):
        return 1
    return value if value >= 1 else 1
