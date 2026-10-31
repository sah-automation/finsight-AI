"""Tesseract OCR adapter implementing :class:`DocumentReader`."""

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
    self._require_company_id(company_id)
    source = self._resolve_source(
        content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
    )

    # Empty-input safety.
    if self._is_empty_content(source):
        return self._empty_result()

    # Allow explicit overrides from kwargs.
    filename = filename if filename is not None else kwargs.get('filename')
    file_name = file_name if file_name is not None else kwargs.get('file_name')
    file_path = file_path if file_path is not None else kwargs.get('file_path')
    content_type = content_type if content_type is not None else kwargs.get('content_type')

    images = self._load_images(
        source,
        filename=filename,
        file_name=file_name,
        file_path=file_path,
        content_type=content_type,
    )

    text_parts: list[str] = []
    page_confidences: list[float] = []
    all_confidences: list[float] = []
    page_numbers: list[int] = []

    if not images:
        return self._empty_result()

    for page_number, image in enumerate(images, start=1):
        page_text, page_confidence, confidences = self._ocr_image(image)
        text_parts.append(page_text)
        page_numbers.append(page_number)
        page_confidences.append(page_confidence)
        all_confidences.extend(confidences)

    full_text = '\n\n'.join(part for part in text_parts if part.strip()).strip()
    if not full_text:
        full_text = '\n\n'.join(text_parts).strip()

    if all_confidences:
        confidence: Any = sum(all_confidences) / len(all_confidences)
    elif page_confidences:
        confidence = sum(page_confidences) / len(page_confidences)
    else:
        confidence = 0.0

    locators: list[dict[str, Any]] = [{'page': page, 'type': 'ocr'} for page in page_numbers]

    return ReaderResult(
        text=full_text,
        tables=[],
        page_numbers=page_numbers,
        confidence=confidence,
        locators=list(locators),
    )
