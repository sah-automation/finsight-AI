"""Named ingestion step worker: after_commit."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class AfterCommitStepWorker(PipelineStepWorker):
    step_name = 'after_commit'
