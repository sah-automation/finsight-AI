"""Named ingestion step: save."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class SaveStep(PipelineStepWorker):
    step_name = 'save'
