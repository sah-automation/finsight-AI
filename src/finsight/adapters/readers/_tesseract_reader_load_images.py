"""Tesseract OCR adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any


def _load_images(  # noqa: PLR0917
    self: Any,
    source: Any,
    filename: Any = None,
    file_name: Any = None,
    file_path: Any = None,
    content_type: Any = None,
) -> Any:
    if self._is_pdf_source(source, filename, file_name, file_path, content_type):
        import pdf2image

        data = self._as_bytes(source)
        if data is not None:
            return list(pdf2image.convert_from_bytes(data, dpi=self._dpi()))
        if isinstance(source, (str, Path)):
            return list(pdf2image.convert_from_path(str(source), dpi=self._dpi()))
        path = file_path or filename or file_name
        if path is not None:
            return list(pdf2image.convert_from_path(str(path), dpi=self._dpi()))
        raise ValueError('Unable to resolve a PDF source for Tesseract rendering')

    # Image handling.
    data = self._as_bytes(source)
    if data is not None:
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(data))
            image.load()
        except (OSError, ValueError):
            pass
        else:
            return [image]
    if hasattr(source, 'save') and hasattr(source, 'size'):
        return [source]
    if isinstance(source, (str, Path)):
        try:
            from PIL import Image

            return [Image.open(str(source))]
        except Exception:
            pass
    raise ValueError('Unable to resolve an image source for Tesseract OCR')
