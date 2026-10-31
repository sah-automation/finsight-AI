"""Named ingestion step worker: answer_cache."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class AnswerCacheStepWorker(PipelineStepWorker):
    step_name = 'answer_cache'
