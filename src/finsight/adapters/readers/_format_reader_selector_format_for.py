"""Format-driven reader selection (Slice 3.8)."""

from __future__ import annotations

from typing import Any

from .format_reader_selector import (
    UnsupportedFormatError,
)


def _format_for(self: Any, *args: Any, **kwargs: Any) -> Any:
    filename, file_name, file_path, content_type, explicit_ext, explicit_mime = self._extract_names(
        *args, **kwargs
    )

    ext = explicit_ext or ''
    if not ext:
        ext = self._extension(filename, file_name, file_path, content_type)

    mime = explicit_mime or content_type
    mime_format = self._format_from_mime(mime) if mime is not None else None
    ext_format = self._format_from_extension(ext) if ext else None

    fmt = ext_format or mime_format

    if fmt is None and isinstance(file_path, str) and '.' in file_path and '\n' not in file_path:
        fmt = self._format_from_extension(file_path.rsplit('.', 1)[-1].lower())

    if fmt is None:
        for src in args:
            if isinstance(src, str):
                for token in src.replace('\\', '/').split():
                    if '.' in token:
                        cand = token.rsplit('.', 1)[-1].lower().rstrip('.,;:')
                        fm = self._format_from_extension(cand)
                        if fm is not None:
                            fmt = fm
                            break
                if fmt is not None:
                    break

    if fmt is None:
        mime_str = '' if mime is None else str(mime)
        ext_str = ext or '<none>'
        raise UnsupportedFormatError(
            f'Unsupported or unknown document format (extension={ext_str!r}, '
            f'content_type={mime_str!r}); supported formats: PDF, Excel, CSV/TSV, DOCX'
        )
    if fmt == 'tsv':
        return 'tsv'
    return fmt
