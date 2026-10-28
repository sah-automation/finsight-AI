"""Processing worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ProcessingWorker(PipelineStepWorker):
    step_name = 'processing'
