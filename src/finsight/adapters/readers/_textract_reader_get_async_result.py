"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import time
from typing import Any

from finsight.core.errors import TextractError

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


def _get_async_result(self: Any, job_id: str) -> Any:
    client = self._get_client()
    collected_blocks: list[Any] = []
    metadata: dict[str, Any] = {}
    next_token = None
    attempts = 0
    max_attempts = self._max_poll_attempts()
    while attempts < max_attempts:
        attempts += 1
        kwargs = {'JobId': job_id}
        if next_token:
            kwargs['NextToken'] = next_token
        try:
            response = client.get_document_analysis(**kwargs)
        except Exception as exc:
            raise TextractError('Textract asynchronous analysis failed') from exc
        status = None
        if isinstance(response, dict):
            status = response.get('JobStatus')
            md = response.get('DocumentMetadata') or response.get('documentMetadata')
            if md and not metadata:
                metadata = md
            page_meta = response.get('DocumentMetadata') or metadata
            if page_meta and isinstance(page_meta, dict):
                metadata = page_meta
            blocks = response.get('Blocks') or response.get('blocks') or []
            collected_blocks.extend(blocks if isinstance(blocks, (list, tuple)) else [blocks])
            next_token = response.get('NextToken') or response.get('nextToken')
        else:
            status = getattr(response, 'JobStatus', None)
            md = getattr(response, 'DocumentMetadata', None) or getattr(
                response, 'documentMetadata', None
            )
            if md and not metadata:
                metadata = md
            if md:
                metadata = md
            blocks = getattr(response, 'Blocks', None) or getattr(response, 'blocks', None) or []
            collected_blocks.extend(blocks if isinstance(blocks, (list, tuple)) else [blocks])
            next_token = getattr(response, 'NextToken', None) or getattr(
                response, 'nextToken', None
            )
        status_text = str(status).upper() if status is not None else ''
        if status_text in {'SUCCEEDED', 'SUCCESS', 'PARTIAL_SUCCESS', 'COMPLETED', 'COMPLETE'}:
            if next_token:
                time.sleep(0)
                continue
            return {'Blocks': collected_blocks, 'DocumentMetadata': metadata}
        if status_text in {'FAILED', 'ERROR'}:
            raise TextractError('Textract asynchronous analysis failed')
        if status_text in {'IN_PROGRESS', 'RUNNING', 'PROCESSING', 'STARTED'} or not status_text:
            time.sleep(self._poll_interval())
            continue
        # Unknown status: wait briefly then continue.
        time.sleep(self._poll_interval())
    raise TextractError('Textract asynchronous analysis timed out')
