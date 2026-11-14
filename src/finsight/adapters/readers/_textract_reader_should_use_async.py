"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _should_use_async(  # noqa: PLR0917
    self: Any,
    source: Any,
    page_count: Any = None,
    pages: Any = None,
    content_type: Any = None,
    filename: Any = None,
    file_name: Any = None,
    file_path: Any = None,
    **kwargs: Any,
) -> Any:
    # Explicit override always wins.
    if 'async_mode' in kwargs or 'use_async' in kwargs or 'mode' in kwargs:
        mode_kw = kwargs.get('mode', kwargs.get('async_mode', kwargs.get('use_async')))
        if isinstance(mode_kw, str):
            return mode_kw.strip().lower() in {'async', '1', 'yes', 'true'}
        if mode_kw is not None:
            return bool(mode_kw)

    count = page_count if page_count is not None else pages
    if count is None:
        count = kwargs.get('page_count', kwargs.get('pages'))
    if count is None:
        if self._is_image_source(source, filename, file_name, file_path, content_type):
            return False
        if self._is_pdf_source(source, filename, file_name, file_path, content_type):
            counted = self._count_pages(source)
            if counted is None:
                # Page count unknown: defer to config/async switch instead of
                # silently forcing a single page (sync).
                return self._async_enabled()
            count = counted
        else:
            return False
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 1
    if count <= 1:
        return False
    return self._async_enabled()
