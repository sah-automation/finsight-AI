"""Save worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class SaveWorker(PipelineStepWorker):
    step_name = 'save'
