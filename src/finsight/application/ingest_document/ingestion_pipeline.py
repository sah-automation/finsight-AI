"""Ingestion pipeline orchestrator."""

from __future__ import annotations

from typing import Any

from .pipeline_step_worker import PipelineStepWorker


class IngestionPipeline(PipelineStepWorker):
    step_name = 'pipeline'

    async def run_pipeline(self, *args: Any, **kwargs: Any) -> Any:
        results = []
        for step_name in ('read', 'delta', 'chunk', 'embed', 'save', 'cascade'):
            self.step_name = step_name
            r = await self._handle_request(*args, **kwargs)
            results.append(r)
            self.step_name = 'pipeline'
        self.step_name = 'pipeline'

        # A run is successful only when the read step extracted non-empty text.
        status = 'completed'
        read_result = results[0] if results else None
        chunk_result = results[2] if len(results) > 2 else None
        extracted_text = ''
        try:
            if isinstance(read_result, dict):
                rr = read_result.get('reader_result')
                extracted_text = str(getattr(rr, 'text', '') or '')
                extracted_text = extracted_text or str(
                    read_result.get('text') or read_result.get('extracted_text') or ''
                )
        except Exception:
            extracted_text = ''
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
        if chunk_count <= 0 or not extracted_text.strip():
            status = 'failed'

        return {'pipeline': results, 'status': status, 'chunks': chunk_count}

    async def run_all(self, *args: Any, **kwargs: Any) -> Any:
        return await self.run_pipeline(*args, **kwargs)
