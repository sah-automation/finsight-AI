"""Excel reader adapter implementing :class:`DocumentReader`.

Reads ``.xlsx`` workbooks with ``openpyxl`` and legacy ``.xls`` workbooks with
the optional ``xlrd`` dependency. A missing ``xlrd`` module raises a clear
error for legacy workbooks instead of failing silently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _extension(
    self: Any,
    source: Any = None,
    *,
    filename: Any = None,
    file_name: Any = None,
    file_path: Any = None,
    content_type: Any = None,
) -> Any:
    info_name = ''
    if filename is not None:
        info_name = str(filename)
    elif file_name is not None:
        info_name = str(file_name)
    elif file_path is not None:
        info_name = str(file_path)
    elif isinstance(source, (str, Path)):
        info_name = str(source)

    ext = ''
    if '.' in info_name:
        ext = info_name.rsplit('.', 1)[-1].lower()
    # Content type fallback.
    if not ext and isinstance(content_type, str):
        ct = content_type.lower()
        if 'spreadsheetml' in ct or 'excel' in ct:
            ext = 'xlsx'
        elif 'ms-excel' in ct or 'vnd.ms-excel' in ct:
            ext = 'xls'
    if not ext and isinstance(source, dict):
        for key in ('filename', 'file_name', 'name', 'path'):
            value = source.get(key)
            if isinstance(value, str) and '.' in value:
                ext = value.rsplit('.', 1)[-1].lower()
                break
    if not ext and isinstance(getattr(source, 'filename', None), str):
        value = str(source.filename)
        if '.' in value:
            ext = value.rsplit('.', 1)[-1].lower()
    return ext
