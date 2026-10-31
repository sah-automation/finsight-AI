"""Named ingestion step: finalize."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class FinalizeStep(PipelineStepWorker):
    step_name = 'finalize'
