"""Named ingestion step: extract."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ExtractStep(PipelineStepWorker):
    step_name = 'extract'
