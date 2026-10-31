"""Named ingestion step worker: delta."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class DeltaStepWorker(PipelineStepWorker):
    step_name = 'delta'
