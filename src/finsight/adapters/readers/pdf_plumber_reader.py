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
        self._config = kwargs.pop('config', kwargs.pop('settings', None))
        for key, value in kwargs.items():
            if key not in self.__dict__:
                setattr(self, key, value)

    @property
    def confidence_threshold(self) -> Any:
        return self._confidence_threshold

    async def read(
        self,
        company_id: Any,
        content: Any = None,
        *,
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        content_type: Any = None,
        **kwargs: Any,
    ) -> ReaderResult:
        source = self._resolve_source(
            content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
        )
        # Empty-input safety: never raise on empty buffers/strings.
        if self._is_empty_content(source):
            return self._empty_result()
        data = self._as_bytes(source)
        if data is not None and len(data) == 0:
            return self._empty_result()
        self._require_company_id(company_id)
        text_parts: list[str] = []
        tables: list[object] = []
        page_numbers: list[int] = []
        page_confidences: list[float] = []

        with self._open_pdf(source) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = ''
                try:
                    page_text = page.extract_text() or ''
                except Exception:
                    page_text = ''
                tables.extend(self._extract_tables(page, page_number))
                page_numbers.append(page_number)
                text_parts.append(page_text)
                page_confidences.append(1.0 if page_text.strip() else 0.0)

        full_text = '\n\n'.join(part for part in text_parts)
        confidence = (sum(page_confidences) / len(page_confidences)) if page_confidences else 1.0

        return ReaderResult(
            text=full_text,
            tables=tables,
            page_numbers=page_numbers,
            confidence=confidence,
        )

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

    def _extract_tables(self, page: Any, page_number: int) -> list[dict[str, Any]]:
        found_tables: list[Any] = []
        try:
            found_tables = list(page.find_tables() or [])
        except Exception:
            found_tables = []
        extracted: list[Any] = []
        try:
            extracted = list(page.extract_tables() or [])
        except Exception:
            extracted = []

        if not extracted and found_tables:
            for table in found_tables:
                if hasattr(table, 'extract'):
                    try:
                        extracted.append(table.extract())
                    except Exception:
                        extracted.append(None)

        result: list[dict[str, Any]] = []
        for index, rows in enumerate(extracted):
            bbox: Any = None
            if index < len(found_tables):
                bbox = getattr(found_tables[index], 'bbox', None)
            result.append(
                {
                    'page': page_number,
                    'page_number': page_number,
                    'rows': rows,
                    'table': rows,
                    'data': rows,
                    'cells': rows,
                    'bbox': bbox,
                    'bounding_box': bbox,
                    'boundaries': bbox,
                }
            )
        return result


__all__ = ['PdfPlumberReader']
