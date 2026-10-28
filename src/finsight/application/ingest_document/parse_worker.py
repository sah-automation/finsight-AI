"""Parse worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ParseWorker(PipelineStepWorker):
    step_name = 'parse'
