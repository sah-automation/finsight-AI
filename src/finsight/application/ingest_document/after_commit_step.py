"""Named ingestion step: after_commit."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class AfterCommitStep(PipelineStepWorker):
    step_name = 'after_commit'
