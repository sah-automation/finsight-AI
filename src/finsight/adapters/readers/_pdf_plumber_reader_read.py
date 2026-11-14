"""pdfplumber adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult


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
