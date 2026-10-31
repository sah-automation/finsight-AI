"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any

from finsight.core.errors import TextractError

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _start_async_job(self: Any, source: Any) -> Any:
    client = self._get_client()
    document = self._document_arg(source)
    feature_types = self._feature_types()
    kwargs = {'Document': document}
    if feature_types:
        kwargs['FeatureTypes'] = feature_types
    try:
        result = client.start_document_analysis(**kwargs)
    except Exception as exc:
        raise TextractError('Textract asynchronous analysis failed to start') from exc
    job_id = None
    if isinstance(result, dict):
        job_id = result.get('JobId', result.get('JobID'))
    else:
        job_id = getattr(result, 'JobId', getattr(result, 'JobID', None))
    if not job_id:
        raise TextractError('Textract asynchronous analysis did not return a job id')
    return str(job_id)
