"""Named ingestion step worker: read."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ReadStepWorker(PipelineStepWorker):
    step_name = 'read'
