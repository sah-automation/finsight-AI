"""Named ingestion step: parse."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ParseStep(PipelineStepWorker):
    step_name = 'parse'
