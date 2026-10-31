"""Named ingestion step worker: cache."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CacheStepWorker(PipelineStepWorker):
    step_name = 'cache'
