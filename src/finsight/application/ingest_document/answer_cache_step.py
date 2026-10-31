"""Named ingestion step: answer_cache."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class AnswerCacheStep(PipelineStepWorker):
    step_name = 'answer_cache'
