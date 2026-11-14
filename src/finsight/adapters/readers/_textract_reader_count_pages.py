"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _count_pages(self: Any, source: Any) -> int | None:
    data = self._as_bytes(source)
    if data is None:
        return None
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return len(pdf.pages)
    except Exception:
        return None
