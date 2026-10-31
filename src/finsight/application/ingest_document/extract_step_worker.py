"""Named ingestion step worker: extract."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ExtractStepWorker(PipelineStepWorker):
    step_name = 'extract'
