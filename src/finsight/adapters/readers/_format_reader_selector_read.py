"""Format-driven reader selection (Slice 3.8)."""

from __future__ import annotations

import inspect
from typing import Any


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

    reader = self.select_reader(
        content,
        file_path=file_path,
        filename=filename,
        file_name=file_name,
        content_type=content_type,
        **kwargs,
    )

    result = reader.read(
        company_id,
        content,
        file_path=file_path,
        filename=filename,
        file_name=file_name,
        content_type=content_type,
        **kwargs,
    )
    if inspect.isawaitable(result):
        result = await result
    return result
