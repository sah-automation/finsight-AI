"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _parse_response(
    self: Any,
    response: Any,
    source: Any = None,
    content_type: Any = None,
) -> Any:
    blocks = self._blocks(response)
    by_id: dict[Any, Any] = {}
    for block in blocks:
        bid = self._block_id(block)
        if bid is not None:
            by_id[bid] = block

    text_by_page: dict[Any, list[str]] = {}
    page_set: set[int] = set()
    confidences: list[float] = []
    tables: list[dict[str, Any]] = []
    locators: list[dict[str, Any]] = []

    # Metadata page count (optional, does not drive page numbers).
    metadata = (
        response.get('DocumentMetadata', response.get('documentMetadata'))
        if isinstance(response, dict)
        else getattr(response, 'DocumentMetadata', getattr(response, 'documentMetadata', None))
    )
    metadata_pages = None
    if isinstance(metadata, dict):
        metadata_pages = metadata.get('Pages', metadata.get('pages'))

    table_index = 0
    for table_block in (b for b in blocks if self._block_type(b) == 'TABLE'):
        table_index += 1
        page = self._block_page(table_block)
        page_set.add(page)
        cell_ids = self._child_ids(table_block, 'CHILD')
        cell_blocks: list[Any] = [
            by_id[cid]
            for cid in cell_ids
            if cid in by_id and self._block_type(by_id[cid]) == 'CELL'
        ]
        # Collect any nested cell blocks as well.
        if not cell_blocks:
            cell_blocks = [by_id[cid] for cid in cell_ids if cid in by_id]

        cell_map: dict[tuple[int, int], Any] = {}
        max_row = 0
        max_col = 0
        for cell in cell_blocks:
            if self._block_type(cell) != 'CELL':
                continue
            row_idx = (
                cell.get('RowIndex', cell.get('rowIndex'))
                if isinstance(cell, dict)
                else getattr(cell, 'RowIndex', getattr(cell, 'rowIndex', 0))
            )
            col_idx = (
                cell.get('ColumnIndex', cell.get('columnIndex'))
                if isinstance(cell, dict)
                else getattr(cell, 'ColumnIndex', getattr(cell, 'columnIndex', 0))
            )
            try:
                row_idx = int(row_idx)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                row_idx = 0
            try:
                col_idx = int(col_idx)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                col_idx = 0
            row_idx = max(row_idx, 1)
            col_idx = max(col_idx, 1)
            cell_map[(row_idx, col_idx)] = cell
            max_row = max(max_row, row_idx)
            max_col = max(max_col, col_idx)

        cell_confidences: list[float] = []
        rows: list[list[str]] = []
        for r in range(1, max_row + 1):
            row: list[str] = []
            for c in range(1, max_col + 1):
                cell = cell_map.get((r, c))
                if cell is not None:
                    text = self._extract_cell_text(cell, by_id)
                    row.append(text)
                    conf = self._block_confidence(cell)
                    if isinstance(conf, (int, float)) and not isinstance(conf, bool):
                        cell_confidences.append(float(conf))
                else:
                    row.append('')
            rows.append(row)

        if cell_confidences:
            table_confidence: Any = sum(cell_confidences) / len(cell_confidences)
        else:
            conf = self._block_confidence(table_block)
            table_confidence = (
                float(conf)
                if isinstance(conf, (int, float)) and not isinstance(conf, bool)
                else None
            )

        geometry = (
            table_block.get('Geometry', table_block.get('geometry'))
            if isinstance(table_block, dict)
            else getattr(table_block, 'Geometry', getattr(table_block, 'geometry', None))
        )
        bbox = None
        if isinstance(geometry, dict):
            bbox = geometry.get(
                'BoundingBox', geometry.get('boundingBox', geometry.get('BoundingBox'))
            )

        table_obj = {
            'page': page,
            'page_number': page,
            'rows': rows,
            'table': rows,
            'data': rows,
            'cells': rows,
            'confidence': table_confidence,
            'bbox': bbox,
            'bounding_box': bbox,
            'boundaries': bbox,
            'table_index': table_index,
        }
        tables.append(table_obj)
        locators.append(
            {
                'page': page,
                'type': 'table',
                'index': table_index,
                'rows': max_row,
                'columns': max_col,
                'confidence': table_confidence,
            }
        )

    # Text/confidence extraction (canonical: append confidence for
    # CELL/TABLE/LINE/WORD blocks).
    for block in blocks:
        btype = self._block_type(block)
        page = self._block_page(block)
        page_set.add(page)
        conf = self._block_confidence(block)
        if conf is not None and btype in _CONFIDENCE_BLOCK_TYPES:
            if isinstance(conf, (int, float)) and not isinstance(conf, bool):
                confidences.append(float(conf))
        if btype != 'LINE':
            continue
        if isinstance(block, dict):
            line_text = block.get('Text', block.get('text'))
        else:
            line_text = getattr(block, 'Text', getattr(block, 'text', None))
        if line_text is None:
            continue
        text_str = str(line_text)
        if not text_str.strip():
            continue
        text_by_page.setdefault(page, []).append(text_str)

    if not page_set:
        page_set.add(1)
    ordered_pages = sorted(page_set) if page_set else []
    if not ordered_pages and metadata_pages:
        try:
            ordered_pages = list(range(1, int(metadata_pages) + 1))
        except (TypeError, ValueError):
            ordered_pages = [1]
    if not page_set and not ordered_pages:
        ordered_pages = [1]
        page_set.add(1)

    page_texts: list[str] = []
    for page in ordered_pages:
        parts = text_by_page.get(page, [])
        page_texts.append('\n'.join(parts).strip() if parts else '')
    # Build full text
    if any(page_texts):
        full_text = '\n\n'.join(part for part in page_texts)
    else:
        full_text = ''
    # clean empty joins
    full_text = '\n\n'.join(part for part in page_texts).strip() if any(page_texts) else ''

    if confidences:
        confidence: Any = sum(confidences) / len(confidences)
    else:
        full_text_stripped = full_text.strip() if isinstance(full_text, str) else ''
        confidence = 1.0 if (full_text_stripped or tables) else 0.0

    page_numbers = ordered_pages if ordered_pages else [1]

    # Remove duplicate integer pages while preserving order.
    deduped: list[int] = []
    for page in page_numbers:
        page_int = int(page)
        if page_int not in deduped:
            deduped.append(page_int)
    page_numbers = deduped

    for page in page_numbers:
        locators.append({'page': page, 'type': 'text'})

    return ReaderResult(
        text=full_text,
        tables=list(tables),
        page_numbers=page_numbers,
        confidence=confidence,
        locators=list(locators),
    )
