"""Named ingestion step worker: finalize."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class FinalizeStepWorker(PipelineStepWorker):
    step_name = 'finalize'
