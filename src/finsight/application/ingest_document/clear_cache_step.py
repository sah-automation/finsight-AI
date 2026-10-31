"""Named ingestion step: clear_cache."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ClearCacheStep(PipelineStepWorker):
    step_name = 'clear_cache'
