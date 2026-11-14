"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _feature_types(self: Any) -> Any:
    tc = self._textract_config()
    if tc is not None:
        value = (
            tc.get('feature_types') if isinstance(tc, dict) else getattr(tc, 'feature_types', None)
        )
        if value is not None:
            return list(value)
    return ['TABLES', 'FORMS']
