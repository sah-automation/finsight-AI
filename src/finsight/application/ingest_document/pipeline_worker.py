"""Pipeline worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class PipelineWorker(PipelineStepWorker):
    step_name = 'pipeline'
