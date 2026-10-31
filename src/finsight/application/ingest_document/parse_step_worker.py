"""Named ingestion step worker: parse."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ParseStepWorker(PipelineStepWorker):
    step_name = 'parse'
