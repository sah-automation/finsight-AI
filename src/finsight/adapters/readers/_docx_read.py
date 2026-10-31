from __future__ import annotations

import io
from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult


async def _read(
    reader: Any,
    company_id: Any,
    content: Any = None,
    *,
    file_path: Any = None,
    filename: Any = None,
    file_name: Any = None,
    content_type: Any = None,
    **kwargs: Any,
) -> Any:
    reader._require_company_id(company_id)

    if filename is None:
        filename = kwargs.get('filename', kwargs.get('file_name'))
    if file_name is None:
        file_name = kwargs.get('file_name')
    if file_path is None:
        file_path = kwargs.get('file_path')
    if content_type is None:
        content_type = kwargs.get('content_type')

    source = reader._resolve_source(
        content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
    )

    if reader._is_empty_content(source):
        return reader._empty_result()

    data = reader._as_bytes(source)
    from docx import Document as DocxDocument

    if data is not None:
        document = DocxDocument(io.BytesIO(data))
    else:
        document = DocxDocument(source)

    from docx.table import Table
    from docx.text.paragraph import Paragraph

    text_blocks: list[str] = []
    tables: list[object] = []
    locators: list[object] = []
    current_heading = ''
    block_index = 0
    table_index = 0

    blocks = reader._iter_block_items(document)
    for block in blocks:
        block_index += 1
        if isinstance(block, Paragraph):
            text = str(getattr(block, 'text', '') or '')
            stripped = text.strip()
            heading = bool(reader._is_heading_paragraph(block)) and bool(stripped)
            if heading:
                current_heading = stripped
                text_blocks.append(stripped)
                locators.append(
                    {
                        'page': 1,
                        'page_number': 1,
                        'virtual_page': 1,
                        'type': 'heading',
                        'kind': 'heading',
                        'block_type': 'paragraph',
                        'index': block_index,
                        'block_index': block_index,
                        'heading': current_heading,
                        'nearest_heading': current_heading,
                        'nearest_heading_text': current_heading,
                        'section': current_heading,
                        'section_heading': current_heading,
                        'heading_text': current_heading,
                        'text': current_heading,
                    }
                )
                continue

            if stripped:
                text_blocks.append(stripped)
                locators.append(
                    {
                        'page': 1,
                        'page_number': 1,
                        'virtual_page': 1,
                        'type': 'paragraph',
                        'kind': 'paragraph',
                        'block_type': 'paragraph',
                        'index': block_index,
                        'block_index': block_index,
                        'heading': current_heading,
                        'nearest_heading': current_heading,
                        'nearest_heading_text': current_heading,
                        'section': current_heading,
                        'section_heading': current_heading,
                        'heading_text': current_heading,
                        'text': stripped,
                    }
                )
            continue

        if isinstance(block, Table):
            table_index += 1
            rows = reader._table_rows(block)
            headers = list(rows[0]) if rows else []
            max_col = 0
            for row in rows:
                max_col = max(max_col, len(row))
            if max_col == 0:
                max_col = len(headers)

            table_obj: dict[str, Any] = {
                'index': table_index,
                'table_index': table_index,
                'table_id': f'table-{table_index}',
                'name': f'Table {table_index}',
                'title': current_heading,
                'heading': current_heading,
                'nearest_heading': current_heading,
                'nearest_heading_text': current_heading,
                'section': current_heading,
                'section_heading': current_heading,
                'page': 1,
                'page_number': 1,
                'virtual_page': 1,
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
            }
            tables.append(table_obj)

            for row in rows:
                if row:
                    text_blocks.append('\t'.join(str(cell) for cell in row))
            if not rows:
                text_blocks.append(f'[Table {table_index}]')

            locators.append(
                {
                    'page': 1,
                    'page_number': 1,
                    'virtual_page': 1,
                    'type': 'table',
                    'kind': 'table',
                    'block_type': 'table',
                    'index': block_index,
                    'block_index': block_index,
                    'table_index': table_index,
                    'heading': current_heading,
                    'nearest_heading': current_heading,
                    'nearest_heading_text': current_heading,
                    'section': current_heading,
                    'section_heading': current_heading,
                    'heading_text': current_heading,
                    'rows': len(rows),
                    'row_count': len(rows),
                    'column_count': max_col,
                    'max_col': max_col,
                    'headers': headers,
                }
            )

    full_text = '\n'.join(block for block in text_blocks).strip()
    has_content = bool(full_text or tables)
    confidence: Any = 1.0 if has_content else 0.0

    page_numbers = [1]

    if not locators:
        locators.append(
            {
                'page': 1,
                'page_number': 1,
                'virtual_page': 1,
                'type': 'document',
                'kind': 'document',
                'block_type': 'document',
                'index': 0,
                'block_index': 0,
                'heading': current_heading,
                'nearest_heading': current_heading,
                'nearest_heading_text': current_heading,
                'section': current_heading,
                'section_heading': current_heading,
                'heading_text': current_heading,
            }
        )

    return ReaderResult(
        text=full_text,
        tables=tables,
        page_numbers=page_numbers,
        confidence=confidence,
        locators=locators,
    )
