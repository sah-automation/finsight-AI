"""Format-driven reader selection (Slice 3.8)."""

from __future__ import annotations

from typing import Any


def _extract_names(self: Any, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
    filename = kwargs.get('filename', kwargs.get('file_name'))
    file_name = kwargs.get('file_name')
    file_path = kwargs.get('file_path')
    content_type = kwargs.get('content_type', kwargs.get('mime_type', kwargs.get('contentType')))
    explicit_ext = kwargs.get('extension', kwargs.get('ext'))
    explicit_mime = kwargs.get('mime', kwargs.get('mimetype', kwargs.get('content-type')))

    sources = list(args)
    for key in ('content', 'source', 'file', 'stream', 'data', 'bytes', 'path', 'source_path'):
        if key in kwargs and kwargs.get(key) is not None:
            sources.append(kwargs.get(key))

    for src in sources:
        if isinstance(src, dict):
            if filename is None:
                filename = src.get('filename', src.get('file_name', src.get('name')))
            if file_name is None:
                file_name = src.get('file_name', src.get('filename', src.get('name')))
            if file_path is None:
                file_path = src.get('file_path', src.get('path'))
            if content_type is None:
                content_type = src.get('content_type', src.get('mime_type', src.get('mimetype')))
    for src in sources:
        if isinstance(src, dict):
            continue
        try:
            if filename is None and getattr(src, 'filename', None) is not None:
                filename = src.filename
            if file_name is None and getattr(src, 'file_name', None) is not None:
                file_name = src.file_name
            if file_path is None and getattr(src, 'file_path', None) is not None:
                file_path = src.file_path
            if (
                file_path is None
                and getattr(src, 'path', None) is not None
                and not hasattr(src, 'read')
            ):
                file_path = src.path
            if content_type is None and getattr(src, 'content_type', None) is not None:
                content_type = src.content_type
        except Exception:
            pass
    for src in sources:
        if isinstance(src, str):
            if filename is None and file_path is None and '\n' not in src:
                if '/' in src or '\\' in src or '.' in src:
                    filename = src

    if explicit_ext is not None:
        explicit_ext = str(explicit_ext).lstrip('.').lower()
    if explicit_mime is not None:
        explicit_mime = str(explicit_mime)

    return filename, file_name, file_path, content_type, explicit_ext, explicit_mime
