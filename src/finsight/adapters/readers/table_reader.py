"""TableReader adapter for table-sensitive pages."""

from __future__ import annotations

from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class TableReader(BaseReader):
    """Read table-sensitive pages.

    The reader can either delegate to an underlying adapter selected from
    configuration (``pdfplumber``, ``textract`` or ``self_hosted_layout``) or
    perform a focused pdfplumber table extraction itself. All public read entry
    points return the shared :class:`ReaderResult` shape.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        from ._table_reader_init import _init__ as _adapter_method

        _adapter_method(self, *args, **kwargs)

    def _config_table_reader_name(self) -> str | None:
        config = self._config
        if config is None:
            return None
        docs = getattr(config, 'documents', None)
        if docs is not None:
            value = getattr(docs, 'table_reader', None)
            if value is not None:
                return str(value)
        if isinstance(config, dict):
            docs_dict = config.get('documents')
            if isinstance(docs_dict, dict):
                value = docs_dict.get('table_reader')
                if value is not None:
                    return str(value)
            if 'table_reader' in config:
                return str(config.get('table_reader'))
        value = getattr(config, 'table_reader', None)
        if value is not None:
            return str(value)
        return None

    def _resolve_underlying(self, *args: Any, **kwargs: Any) -> Any:
        from ._table_reader_resolve_underlying import _resolve_underlying as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    async def read(
        self,
        company_id: Any = None,
        content: Any = None,
        **kwargs: Any,
    ) -> ReaderResult:
        from ._table_reader_read import _read as _adapter_read

        return cast('ReaderResult', await _adapter_read(self, company_id, content, **kwargs))

    async def read_document(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def extract(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def parse(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def extract_text(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    def _clean_passthrough(
        self,
        kwargs: dict[str, Any],
        file_path: Any,
        filename: Any,
        file_name: Any,
        content_type: Any,
    ) -> dict[str, Any]:
        out = dict(kwargs)
        if file_path is not None:
            out.setdefault('file_path', file_path)
        if filename is not None:
            out.setdefault('filename', filename)
        if file_name is not None:
            out.setdefault('file_name', file_name)
        if content_type is not None:
            out.setdefault('content_type', content_type)
        return out

    def _extract_tables(self, *args: Any, **kwargs: Any) -> Any:
        from ._table_reader_extract_tables import _extract_tables as _adapter_method

        return _adapter_method(self, *args, **kwargs)

    @staticmethod
    def _meaningful_tables(tables: Any, settings: Any) -> bool:
        for table in tables or []:
            rows = table or []
            for row in rows:
                if isinstance(row, (list, tuple)):
                    populated = sum(
                        1 for cell in row if cell is not None and str(cell).strip() != ''
                    )
                    if populated >= 2:
                        return True
        strategy = ''
        if isinstance(settings, dict):
            strategy = str(settings.get('vertical_strategy', ''))
        if settings is None or 'lines' in strategy:
            return any(
                isinstance(table, (list, tuple)) and len(table or []) > 0
                for table in (tables or [])
            )
        return False

    _empty_result = BaseReader._empty_result


# Compatibility aliases.
Table = TableReader
TableDocumentReader = TableReader
TableLayoutReader = TableReader
LayoutTableReader = TableReader

__all__ = [
    'LayoutTableReader',
    'Table',
    'TableDocumentReader',
    'TableLayoutReader',
    'TableReader',
]
