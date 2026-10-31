"""Named ingestion step worker: post_process."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class PostProcessStepWorker(PipelineStepWorker):
    step_name = 'post_process'
