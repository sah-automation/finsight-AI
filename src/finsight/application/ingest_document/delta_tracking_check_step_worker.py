"""Named ingestion step worker: delta_tracking_check."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class DeltaTrackingCheckStepWorker(PipelineStepWorker):
    step_name = 'delta_tracking_check'
