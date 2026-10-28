"""Extract worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ExtractWorker(PipelineStepWorker):
    step_name = 'extract'
