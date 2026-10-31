"""Named ingestion step: commit."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CommitStep(PipelineStepWorker):
    step_name = 'commit'
