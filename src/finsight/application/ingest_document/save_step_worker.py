"""Named ingestion step worker: save."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class SaveStepWorker(PipelineStepWorker):
    step_name = 'save'
