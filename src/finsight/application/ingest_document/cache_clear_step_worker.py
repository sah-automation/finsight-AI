"""Named ingestion step worker: cache_clear."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CacheClearStepWorker(PipelineStepWorker):
    step_name = 'cache_clear'
