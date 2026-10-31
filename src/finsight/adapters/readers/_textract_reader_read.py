"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.core.errors import TextractError

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


async def _read(
    self: Any,
    company_id: Any,
    content: Any = None,
    *,
    file_path: Any = None,
    filename: Any = None,
    file_name: Any = None,
    content_type: Any = None,
    **kwargs: Any,
) -> Any:
    self._require_company_id(company_id)
    source = self._resolve_source(
        content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
    )
    if self._is_empty_content(source) and not kwargs:
        # Keep empty content handling safe even when only metadata is passed.
        if source is None and all(
            v is None for v in (file_path, filename, file_name, content_type)
        ):
            return self._empty_result()

    # Mode overrides.
    mode_override = None
    for key in ('mode', 'reader_mode', 'textract_mode'):
        if key in kwargs:
            mode_override = kwargs.pop(key)
    async_override_kw = None
    for key in ('async_', 'async_mode', 'use_async'):
        if key in kwargs:
            async_override_kw = kwargs.pop(key)

    force_async = False
    if isinstance(async_override_kw, str):
        force_async = async_override_kw.strip().lower() in {'async', '1', 'yes', 'true'}
    elif async_override_kw is not None:
        force_async = bool(async_override_kw)
    if isinstance(mode_override, str):
        force_async = mode_override.strip().lower() == 'async'

    empty = self._is_empty_content(source)
    if empty:
        return self._empty_result()

    pages_kw = kwargs.get('pages', kwargs.get('page_count'))
    try:
        use_async = force_async or self._should_use_async(
            source,
            page_count=pages_kw,
            content_type=content_type or kwargs.get('content_type'),
            filename=filename or kwargs.get('filename'),
            file_name=file_name or kwargs.get('file_name'),
            file_path=file_path or kwargs.get('file_path'),
            **{k: v for k, v in kwargs.items() if k not in {'page_count', 'pages'}},
        )
    except Exception:
        use_async = force_async

    try:
        if use_async:
            response = self._analyze_async(source)
        else:
            response = self._analyze_sync(source)
    except TextractError:
        raise
    except Exception as exc:
        raise TextractError('Textract read failed') from exc

    ct = content_type or kwargs.get('content_type')
    if 'content_type' in kwargs:
        ct = kwargs.get('content_type')
    return self._coerce_result(self._parse_response(response, source, ct))
