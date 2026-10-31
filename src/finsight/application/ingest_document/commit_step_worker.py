"""Named ingestion step worker: commit."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CommitStepWorker(PipelineStepWorker):
    step_name = 'commit'
