"""CSV/TSV reader adapter implementing :class:`DocumentReader`.

Uses ``csv.Sniffer`` for delimiter detection, strips a UTF-8 BOM, skips
empty lines and preserves the header row. Tabular data is emitted as a single
table and a single virtual page paired with a concrete row-range locator so
citations stay meaningful beyond "Page 1".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _as_text(self: Any, source: Any) -> Any:
    if source is None:
        return None
    if isinstance(source, str):
        # Could be CSV content or a filesystem path.
        try:
            path = Path(source)
            if path.exists() and path.is_file():
                return path.read_text(encoding='utf-8-sig')
        except (OSError, ValueError):
            pass
        return source
    if isinstance(source, (bytes, bytearray)):
        return bytes(source).decode('utf-8-sig')
    if hasattr(source, 'read'):
        try:
            raw = source.read()
            if hasattr(source, 'seek'):
                try:
                    source.seek(0)
                except (OSError, ValueError):
                    pass
            if isinstance(raw, (bytes, bytearray)):
                return bytes(raw).decode('utf-8-sig')
            if isinstance(raw, str):
                return raw.lstrip('\ufeff')
        except (OSError, UnicodeDecodeError, ValueError, AttributeError):
            return None
    data = self._as_bytes(source)
    if data is not None:
        try:
            return data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return data.decode('utf-8', errors='replace')
    if isinstance(source, dict):
        for key in ('content', 'data', 'bytes', 'body', 'file', 'text'):
            value = source.get(key)
            if value is not None and value is not source:
                found = self._as_text(value)
                if found is not None:
                    return found
    for attr in ('content', 'data', 'body', 'file', 'text'):
        value = getattr(source, attr, None)
        if value is not None and value is not source:
            found = self._as_text(value)
            if found is not None:
                return found
    return None
