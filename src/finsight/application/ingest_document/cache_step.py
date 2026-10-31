"""Named ingestion step: cache."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CacheStep(PipelineStepWorker):
    step_name = 'cache'
