"""CSV/TSV reader adapter implementing :class:`DocumentReader`.

Uses ``csv.Sniffer`` for delimiter detection, strips a UTF-8 BOM, skips
empty lines and preserves the header row. Tabular data is emitted as a single
table and a single virtual page paired with a concrete row-range locator so
citations stay meaningful beyond "Page 1".
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
    if '.' in info_name and '\n' not in info_name:
        ext = info_name.rsplit('.', 1)[-1].lower()
    if not ext and isinstance(content_type, str):
        ct = content_type.lower()
        if 'tab-separated' in ct or 'tsv' in ct:
            ext = 'tsv'
        elif 'csv' in ct or 'comma-separated' in ct or 'text/plain' in ct:
            ext = 'csv'
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
