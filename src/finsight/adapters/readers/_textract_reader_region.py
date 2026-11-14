"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _region(self: Any) -> str | None:
    if self._region_override is not None:
        return str(self._region_override)
    tc = self._textract_config()
    if tc is not None:
        value = tc.get('region') if isinstance(tc, dict) else getattr(tc, 'region', None)
        if value is not None:
            return str(value)
    config = self._config
    if config is not None:
        for section_name in ('aws', 'storage', 'textract'):
            section = (
                getattr(config, section_name, None)
                if not isinstance(config, dict)
                else config.get(section_name)
            )
            if section is None:
                continue
            value = (
                section.get('region')
                if isinstance(section, dict)
                else getattr(section, 'region', None)
            )
            if value is not None:
                return str(value)
    return None
