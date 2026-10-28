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
        return {'pipeline': results, 'status': 'completed'}

    async def run_all(self, *args: Any, **kwargs: Any) -> Any:
        return await self.run_pipeline(*args, **kwargs)
