"""Named ingestion step worker: clear_cache."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ClearCacheStepWorker(PipelineStepWorker):
    step_name = 'clear_cache'
