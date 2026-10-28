"""Commit worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CommitWorker(PipelineStepWorker):
    step_name = 'commit'
