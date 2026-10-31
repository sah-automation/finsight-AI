"""TableReader adapter for table-sensitive pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_reader import BaseReader


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

    if self._is_empty_content(source):
        if not (isinstance(source, (str, Path)) and Path(source).exists()):
            return BaseReader._empty_result()

    requested_override = any(
        key in kwargs and kwargs[key] is not None
        for key in ('table_reader', 'reader_name', 'backend', 'engine')
    )
    if (
        self._delegate is not None
        or self._delegate_name is not None
        or self._config_table_reader_name() is not None
        or requested_override
    ):
        underlying = self._resolve_underlying()
    else:
        underlying = None
    for key in ('table_reader', 'reader_name', 'backend', 'engine'):
        if key in kwargs and kwargs[key] is not None:
            override_name = kwargs.pop(key)
            if isinstance(override_name, str):
                self._delegate_name = override_name
                self._delegate = None
                underlying = self._resolve_underlying()
            elif hasattr(override_name, 'read'):
                self._delegate = override_name
                underlying = override_name

    if underlying is not None and hasattr(underlying, 'read'):
        import inspect

        result = underlying.read(
            company_id,
            source,
            **self._clean_passthrough(kwargs, file_path, filename, file_name, content_type),
        )
        if inspect.isawaitable(result):
            result = await result
        return BaseReader._coerce_result(result)

    return self._extract_tables(
        company_id,
        source,
        file_path=file_path,
        filename=filename,
        file_name=file_name,
        content_type=content_type,
        **kwargs,
    )
