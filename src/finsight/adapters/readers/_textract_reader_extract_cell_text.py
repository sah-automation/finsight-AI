"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _extract_cell_text(self: Any, cell_block: Any, by_id: dict[Any, Any]) -> Any:
    words: list[str] = []
    queue = list(self._child_ids(cell_block, 'CHILD'))
    visited: set[Any] = set()
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        child = by_id.get(current)
        if not child:
            continue
        btype = self._block_type(child).upper()
        if btype == 'WORD':
            value = (
                child.get('Text', child.get('text'))
                if isinstance(child, dict)
                else getattr(child, 'Text', getattr(child, 'text', None))
            )
            if value is not None:
                words.append(str(value))
        elif btype == 'SELECTION_ELEMENT':
            sel = (
                child.get('SelectionStatus', child.get('selectionStatus'))
                if isinstance(child, dict)
                else getattr(child, 'SelectionStatus', getattr(child, 'selectionStatus', None))
            )
            if sel:
                words.append(str(sel))
        queue.extend(self._child_ids(child, 'CHILD'))
    if words:
        return ' '.join(words).strip()
    value = (
        cell_block.get('Text', cell_block.get('text'))
        if isinstance(cell_block, dict)
        else getattr(cell_block, 'Text', getattr(cell_block, 'text', None))
    )
    if value is not None:
        return str(value).strip()
    return ''
