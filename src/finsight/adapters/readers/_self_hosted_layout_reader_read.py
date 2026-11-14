"""Self-hosted (free) layout reader implementing :class:`DocumentReader`."""

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

    if self._delegate is not None and hasattr(self._delegate, 'read'):
        import inspect

        result = self._delegate.read(
            company_id,
            source,
            **self._clean_passthrough(kwargs, file_path, filename, file_name, content_type),
        )
        if inspect.isawaitable(result):
            result = await result
        return BaseReader._coerce_result(result)

    return self._extract_layout(
        company_id,
        source,
        **self._clean_passthrough(kwargs, file_path, filename, file_name, content_type),
    )
