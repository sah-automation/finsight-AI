"""Named ingestion step: read."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ReadStep(PipelineStepWorker):
    step_name = 'read'
