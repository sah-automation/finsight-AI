"""pdfplumber adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from finsight.domain.ports.document_reader import DocumentReader
from finsight.domain.value_objects.reader_result import ReaderResult


class PdfPlumberReader(DocumentReader):
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

    def _resolve_source(
        self,
        content: Any,
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

    def _open_pdf(self, source: Any) -> Any:
        import pdfplumber

        data = self._as_bytes(source)
        if data is not None:
            return pdfplumber.open(io.BytesIO(data))
        return pdfplumber.open(source)

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
