"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _max_poll_attempts(self: Any) -> Any:
    tc = self._textract_config()
    if tc is not None:
        value = (
            tc.get('max_poll_attempts')
            if isinstance(tc, dict)
            else getattr(tc, 'max_poll_attempts', None)
        )
        if value is not None:
            return int(value)
    return 100
