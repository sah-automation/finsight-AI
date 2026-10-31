"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _is_image_source(
    source: Any,
    filename: Any = None,
    file_name: Any = None,
    file_path: Any = None,
    content_type: Any = None,
) -> Any:
    from .textract_reader import TextractReader

    info = TextractReader._normalise_name(source, filename, file_name, file_path, content_type)
    ct = info['content_type']
    if isinstance(ct, str) and ct.lower().startswith('image/'):
        return True
    if info['ext'] in _IMAGE_EXTENSIONS:
        return True
    # Rely on bytes sniffing for common image signatures when available.
    try:
        raw = source if isinstance(source, (bytes, bytearray)) else None
        if raw is None and hasattr(source, 'read'):
            raw = source.read()
            if hasattr(source, 'seek'):
                source.seek(0)
        if isinstance(raw, (bytes, bytearray)):
            if raw[:4] == b'\x89PNG' or raw[:3] == b'\xff\xd8\xff':
                return True
            if raw[:6] in (b'GIF87a', b'GIF89a'):
                return True
            if raw[:2] == b'BM':
                return True
    except Exception:
        pass
    return False
