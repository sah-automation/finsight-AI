"""pdfplumber adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any


def _extract_tables(self: Any, page: Any, page_number: int) -> Any:
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
