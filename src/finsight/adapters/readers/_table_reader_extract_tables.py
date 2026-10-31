"""TableReader adapter for table-sensitive pages."""

from __future__ import annotations

import io
from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


def _extract_tables(
    self: Any,
    company_id: Any,
    source: Any,
    *,
    file_path: Any = None,
    filename: Any = None,
    file_name: Any = None,
    content_type: Any = None,
    **kwargs: Any,
) -> Any:
    self._require_company_id(company_id)
    try:
        import pdfplumber
    except Exception:
        return BaseReader._empty_result()

    data = self._as_bytes(source)
    try:
        if data is not None:
            pdf = pdfplumber.open(io.BytesIO(data))
        else:
            pdf = pdfplumber.open(source)
    except Exception:
        return BaseReader._empty_result()

    try:
        text_parts: list[str] = []
        tables: list[dict[str, Any]] = []
        page_numbers: list[int] = []
        page_confidences: list[float] = []
        locators: list[dict[str, Any]] = []
        table_index = 0

        settings_variants: list[Any] = [
            None,
            {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'},
            {'vertical_strategy': 'text', 'horizontal_strategy': 'text'},
        ]

        for page_number, page in enumerate(pdf.pages, start=1):
            try:
                page_text = page.extract_text() or ''
            except Exception:
                page_text = ''
            text_parts.append(page_text)
            page_numbers.append(page_number)
            page_confidences.append(1.0 if str(page_text).strip() else 0.0)

            extracted: list[Any] = []
            found: list[Any] = []
            for settings in settings_variants:
                try:
                    if settings is None:
                        page_tables = list(page.extract_tables() or [])
                        page_found = list(page.find_tables() or [])
                    else:
                        page_tables = list(page.extract_tables(table_settings=settings) or [])
                        page_found = list(page.find_tables(table_settings=settings) or [])
                except Exception:
                    page_tables = []
                    page_found = []
                if page_tables and self._meaningful_tables(page_tables, settings):
                    extracted = page_tables
                    found = page_found
                    break

            for i, _raw_rows in enumerate(extracted or []):
                rows = [list(r) if isinstance(r, (list, tuple)) else [] for r in (_raw_rows or [])]
                while rows and all(
                    cell is None or (isinstance(cell, str) and cell.strip() == '')
                    for cell in rows[-1]
                ):
                    rows.pop()
                max_col = max([len(r) for r in rows], default=0)
                if max_col == 0 and rows:
                    max_col = 1
                headers = list(rows[0]) if rows else []
                bbox = None
                if i < len(found):
                    bbox = getattr(found[i], 'bbox', None)

                table_index += 1
                table_obj: dict[str, Any] = {
                    'page': page_number,
                    'page_number': page_number,
                    'virtual_page': page_number,
                    'index': table_index,
                    'table_index': table_index,
                    'table_id': f'table-{table_index}',
                    'name': f'Table {table_index}',
                    'title': f'Table {table_index}',
                    'nearest_heading': None,
                    'headers': headers,
                    'header': headers,
                    'header_row': 1 if headers else None,
                    'rows': rows,
                    'data': rows,
                    'table': rows,
                    'cells': rows,
                    'row_count': len(rows),
                    'column_count': max_col,
                    'max_col': max_col,
                    'dimensions': f'{len(rows)}x{max_col}',
                    'bbox': bbox,
                    'bounding_box': bbox,
                    'boundaries': bbox,
                    'source': 'table_reader',
                    'reader': 'table_reader',
                }
                tables.append(table_obj)
                locators.append(
                    {
                        'page': page_number,
                        'page_number': page_number,
                        'virtual_page': page_number,
                        'type': 'table',
                        'kind': 'table',
                        'block_type': 'table',
                        'index': table_index,
                        'table_index': table_index,
                        'rows': len(rows),
                        'columns': max_col,
                        'headers': headers,
                        'bbox': bbox,
                    }
                )

        pdf.close()

        if not locators:
            locators.append(
                {
                    'page': page_numbers[0] if page_numbers else 1,
                    'page_number': page_numbers[0] if page_numbers else 1,
                    'virtual_page': page_numbers[0] if page_numbers else 1,
                    'type': 'document',
                    'kind': 'document',
                    'block_type': 'document',
                    'index': 0,
                    'table_index': 0,
                }
            )

        full_text = '\n\n'.join(part for part in text_parts if part is not None).strip()
        confidence: Any = (
            (sum(page_confidences) / len(page_confidences))
            if page_confidences
            else (1.0 if (full_text or tables) else 0.0)
        )
        if not page_numbers:
            page_numbers = [1]

        return ReaderResult(
            text=full_text,
            tables=cast('list[object]', tables),
            page_numbers=page_numbers,
            confidence=confidence,
            locators=cast('list[object]', locators),
        )
    except Exception:
        try:
            pdf.close()
        except Exception:
            pass
        return BaseReader._empty_result()
