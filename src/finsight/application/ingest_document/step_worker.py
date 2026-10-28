"""Step worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class StepWorker(PipelineStepWorker):
    step_name = 'step'
