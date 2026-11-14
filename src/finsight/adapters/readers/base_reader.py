"""Shared base adapter for every :class:`DocumentReader` implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from finsight.domain.ports.document_reader import DocumentReader
from finsight.domain.value_objects.reader_result import ReaderResult


class BaseReader(DocumentReader):
    """Common scaffolding shared by all document reader adapters.

    Adapters keep their vendor-specific parsing in their own ``read`` method but
    reuse the helpers here for company scoping, empty-input safety, source
    resolution, byte handling and virtual-page numbering. Application and domain
    code still depend only on :class:`DocumentReader`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Shared, optional configuration bag. Concrete readers may pop their
        # own keys before/after calling super().__init__.
        self._config = kwargs.pop('config', kwargs.pop('settings', None))
        self._session = kwargs.pop('session', kwargs.pop('db_session', None))
        super().__init__()

    # Company scoping -----------------------------------------------------
    def _require_company_id(self, company_id: Any) -> Any:
        """Return *company_id* after ensuring it is present."""
        if company_id is None:
            raise ValueError('BaseReader requires a company_id')
        return company_id

    def _company_id_str(self, company_id: Any) -> str:
        return str(getattr(company_id, 'value', company_id))

    # Empty-input safety --------------------------------------------------
    @staticmethod
    def _empty_result(*, confidence: Any = None) -> ReaderResult:
        """Return a safe, citation-friendly empty result."""
        return ReaderResult(
            text='',
            tables=[],
            page_numbers=[],
            confidence=confidence,
            locators=[],
        )

    @staticmethod
    def _is_empty_content(content: Any) -> bool:
        if content is None:
            return True
        if isinstance(content, (bytes, bytearray)):
            return len(content) == 0
        if isinstance(content, str):
            return content.strip() == ''
        return False

    # Source resolution ---------------------------------------------------
    def _resolve_source(
        self,
        content: Any = None,
        *,
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        **kwargs: Any,
    ) -> Any:
        if content is not None:
            return content
        if file_path is not None:
            return file_path
        if filename is not None:
            return filename
        if file_name is not None:
            return file_name
        for key in ('path', 'source', 'file', 'stream', 'data', 'bytes', 'content'):
            if key in kwargs and kwargs[key] is not None:
                return kwargs[key]
        return None

    # Byte handling -------------------------------------------------------
    def _as_bytes(self, source: Any) -> bytes | None:
        if source is None:
            return None
        if isinstance(source, (bytes, bytearray)):
            return bytes(source)
        if hasattr(source, 'read'):
            try:
                raw = source.read()
                if hasattr(source, 'seek'):
                    try:
                        source.seek(0)
                    except Exception:
                        pass
                if isinstance(raw, (bytes, bytearray)):
                    return bytes(raw)
                if isinstance(raw, str):
                    return raw.encode('utf-8')
            except Exception:
                return None
        if isinstance(source, (str, Path)):
            try:
                path = Path(source)
                if path.exists() and path.is_file():
                    return path.read_bytes()
            except Exception:
                return None
        if isinstance(source, dict):
            for key in ('content', 'data', 'bytes', 'body', 'file'):
                if source.get(key) is not None:
                    found = self._as_bytes(source.get(key))
                    if found is not None:
                        return found
        for attr in ('content', 'data', 'body', 'file'):
            value = getattr(source, attr, None)
            if value is not None and value is not source:
                found = self._as_bytes(value)
                if found is not None:
                    return found
        return None

    # Virtual page numbering ----------------------------------------------
    @staticmethod
    def _virtual_page_numbers(count: int, *, start: int = 1) -> list[int]:
        safe = max(0, int(count) if not isinstance(count, bool) else 0)
        return [start + index for index in range(safe)]

    @staticmethod
    def _ensure_locators(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    # Shared result coercion ----------------------------------------------
    @staticmethod
    def _coerce_result(result: Any) -> ReaderResult:
        if isinstance(result, ReaderResult):
            if result.locators is None:
                # ReaderResult already normalises this, but keep belt and braces.
                return result
            return result
        if isinstance(result, dict):
            return ReaderResult(
                text=str(result.get('text') or ''),
                tables=list(result.get('tables') or []),
                page_numbers=list(result.get('page_numbers') or []),
                confidence=result.get('confidence'),
                locators=BaseReader._ensure_locators(result.get('locators')),
            )
        return ReaderResult(text=str(result) if result is not None else '')

    @staticmethod
    def _merge_locators(*groups: Any) -> list[Any]:
        merged: list[Any] = []
        for group in groups:
            merged.extend(BaseReader._ensure_locators(group))
        return merged


__all__ = ['BaseReader']
