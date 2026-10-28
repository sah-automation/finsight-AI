"""Read worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ReadWorker(PipelineStepWorker):
    step_name = 'read'
