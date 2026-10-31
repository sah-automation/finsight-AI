"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.core.errors import TextractError

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _analyze_sync(self: Any, source: Any) -> Any:
    client = self._get_client()
    document = self._document_arg(source)
    feature_types = self._feature_types()
    kwargs = {'Document': document}
    if feature_types:
        kwargs['FeatureTypes'] = feature_types
    try:
        return client.analyze_document(**kwargs)
    except Exception as exc:
        raise TextractError('Textract synchronous analysis failed') from exc
