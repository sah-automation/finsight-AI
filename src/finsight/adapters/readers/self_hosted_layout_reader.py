"""Self-hosted (free) layout reader implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class SelfHostedLayoutReader(BaseReader):
    """Free, self-hosted layout/table reader.

    Uses pdfplumber's (bundled, local) layout primitives rather than a paid
    document-analysis service. Returns the same :class:`ReaderResult` shape as
    every other adapter, including table objects and locators.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        delegate = kwargs.pop('delegate', None)
        if delegate is None:
            delegate = kwargs.pop('reader', None)
        if delegate is None:
            delegate = kwargs.pop('layout_reader', None)
        if delegate is None:
            for arg in args:
                if hasattr(arg, 'read') and callable(getattr(arg, 'read', None)):
                    delegate = arg
                    break

        passed_config = None
        if 'config' in kwargs:
            passed_config = kwargs.pop('config')
        if 'settings' in kwargs and passed_config is None:
            passed_config = kwargs.pop('settings')
        if 'configuration' in kwargs and passed_config is None:
            passed_config = kwargs.pop('configuration')
        session = kwargs.pop('session', kwargs.pop('db_session', None))

        self._delegate = delegate
        self._config = passed_config
        self._session = session
        super().__init__(config=passed_config, session=session)

        for key, value in kwargs.items():
            if key not in self.__dict__:
                setattr(self, key, value)

    async def read(
        self,
        company_id: Any = None,
        content: Any = None,
        **kwargs: Any,
    ) -> ReaderResult:
        from ._self_hosted_layout_reader_read import _read as _adapter_read

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
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        content_type: Any = None,
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

    def _extract_layout(self, *args: Any, **kwargs: Any) -> None:
        from ._self_hosted_layout_reader_extract_layout import _extract_layout as _adapter_method

        _adapter_method(self, *args, **kwargs)

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
SelfHostedLayout = SelfHostedLayoutReader
LayoutReader = SelfHostedLayoutReader
Layout = SelfHostedLayoutReader
SelfHosted = SelfHostedLayoutReader
SelfHostedReader = SelfHostedLayoutReader
SelfHostedDocumentReader = SelfHostedLayoutReader
LayoutDocumentReader = SelfHostedLayoutReader

__all__ = [
    'Layout',
    'LayoutDocumentReader',
    'LayoutReader',
    'SelfHosted',
    'SelfHostedDocumentReader',
    'SelfHostedLayout',
    'SelfHostedLayoutReader',
    'SelfHostedReader',
]
