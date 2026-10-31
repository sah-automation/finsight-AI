"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _normalise_name(
    source: Any,
    filename: Any = None,
    file_name: Any = None,
    file_path: Any = None,
    content_type: Any = None,
) -> Any:
    name = ''
    if filename is not None:
        name = str(filename)
    elif file_name is not None:
        name = str(file_name)
    elif file_path is not None:
        name = str(file_path)
    ext = ''
    if '.' in name:
        ext = name.rsplit('.', 1)[-1].lower()
    ct = content_type
    if ct is None and source is not None:
        ct = getattr(source, 'content_type', None)
    return {'name': name, 'ext': ext, 'content_type': ct}
