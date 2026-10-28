"""Cache clear worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CacheClearWorker(PipelineStepWorker):
    step_name = 'cache_clear'
