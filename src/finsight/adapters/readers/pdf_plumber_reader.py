"""pdfplumber adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class PdfPlumberReader(BaseReader):
    """Read born-digital PDFs with pdfplumber.

    Preserves page numbers and table boundaries. A page with no extractable
    text yields zero confidence so downstream can mark it ``needs_review``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        threshold = kwargs.pop('confidence_threshold', None)
        if threshold is None:
            threshold = kwargs.pop('min_confidence', None)
        if threshold is None:
            threshold = kwargs.pop('threshold', None)
        self._confidence_threshold = threshold
        self._session = kwargs.pop('session', kwargs.pop('db_session', None))
        self._config = kwargs.pop('config', kwargs.pop('settings', None))
        super().__init__(config=self._config, session=self._session)
        for key, value in kwargs.items():
            if key not in self.__dict__:
                setattr(self, key, value)

    @property
    def confidence_threshold(self) -> Any:
        return self._confidence_threshold

    async def read(self, *args: Any, **kwargs: Any) -> ReaderResult:
        from typing import cast

        from ._pdf_plumber_reader_read import _read as _adapter_read

        return cast('ReaderResult', await _adapter_read(self, *args, **kwargs))

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

    def _open_pdf(self, source: Any) -> Any:
        import pdfplumber

        data = self._as_bytes(source)
        if data is not None:
            return pdfplumber.open(io.BytesIO(data))
        return pdfplumber.open(source)

    def _extract_tables(self, *args: Any, **kwargs: Any) -> Any:
        from ._pdf_plumber_reader_extract_tables import _extract_tables as _adapter_method

        return _adapter_method(self, *args, **kwargs)


__all__ = ['PdfPlumberReader']
