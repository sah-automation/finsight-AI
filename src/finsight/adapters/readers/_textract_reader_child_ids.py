"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _child_ids(block: Any, relation_type: str = 'CHILD') -> Any:
    relations = (
        block.get('Relationships', block.get('relationships'))
        if isinstance(block, dict)
        else getattr(block, 'Relationships', getattr(block, 'relationships', None))
    )
    if not isinstance(relations, (list, tuple)):
        return []
    ids: list[Any] = []
    for rel in relations:
        rtype = (
            rel.get('Type', rel.get('type'))
            if isinstance(rel, dict)
            else getattr(rel, 'Type', getattr(rel, 'type', None))
        )
        if str(rtype).upper() != relation_type.upper():
            continue
        raw_ids = (
            rel.get('Ids', rel.get('ids'))
            if isinstance(rel, dict)
            else getattr(rel, 'Ids', getattr(rel, 'ids', None))
        )
        if isinstance(raw_ids, (list, tuple)):
            ids.extend(raw_ids)
    return ids
