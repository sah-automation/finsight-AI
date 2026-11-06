"""Ingestion pipeline orchestrator."""

from __future__ import annotations

from typing import Any

from .pipeline_step_worker import PipelineStepWorker


def _extracted_text_from_read_result(read_result: Any) -> str:
    """Resolve extracted text from a read step result."""
    if not isinstance(read_result, dict):
        return ''
    rr = read_result.get('reader_result')
    text = str(getattr(rr, 'text', '') or '')
    if not text:
        text = str(read_result.get('text') or read_result.get('extracted_text') or '')
    return text


class IngestionPipeline(PipelineStepWorker):
    step_name = 'pipeline'

    async def run_pipeline(self, *args: Any, **kwargs: Any) -> Any:
        results = []
        for index, step_name in enumerate(('read', 'delta', 'chunk', 'embed', 'save', 'cascade')):
            self.step_name = step_name
            r = await self._handle_request(*args, **kwargs)
            results.append(r)
            self.step_name = 'pipeline'
            if index == 0:
                read_result = r if isinstance(r, dict) else None
                extracted_text = _extracted_text_from_read_result(read_result)
                if not extracted_text.strip():
                    # Do not run downstream commit on a zero-content extraction.
                    break
        self.step_name = 'pipeline'

        # A run is successful only when extraction produced text and chunking produced
        # chunks; status is judged from the read and chunk step results.
        status = 'completed'
        read_result = results[0] if results else None
        chunk_result = results[2] if len(results) > 2 else None
        extracted_text = _extracted_text_from_read_result(read_result)
        chunk_count = 0
        try:
            if isinstance(chunk_result, dict):
                value = chunk_result.get('chunks') or chunk_result.get('chunk_count')
                if isinstance(value, (list, tuple)):
                    chunk_count = len(value)
                elif value is not None:
                    chunk_count = int(value)
        except Exception:
            chunk_count = 0
        if len(results) < 6 or chunk_count <= 0 or not extracted_text.strip():
            status = 'failed'
            if isinstance(read_result, dict):
                version = read_result.get('version')
                if version is not None:
                    vid = getattr(version, 'id', None)
                    cid = getattr(version, 'company_id', None)
                    if isinstance(version, dict):
                        vid = version.get('id', vid)
                        cid = version.get('company_id', cid)
                    if cid is not None and vid is not None:
                        await self._update_state(version, cid, vid, 'failed')
        return {'pipeline': results, 'status': status, 'chunks': chunk_count}

    async def run_all(self, *args: Any, **kwargs: Any) -> Any:
        return await self.run_pipeline(*args, **kwargs)
