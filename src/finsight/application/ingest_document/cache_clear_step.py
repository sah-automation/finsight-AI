"""Named ingestion step: cache_clear."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CacheClearStep(PipelineStepWorker):
    step_name = 'cache_clear'
