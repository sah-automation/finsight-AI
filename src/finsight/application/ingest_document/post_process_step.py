"""Named ingestion step: post_process."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class PostProcessStep(PipelineStepWorker):
    step_name = 'post_process'
