"""Cascade worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CascadeWorker(PipelineStepWorker):
    step_name = 'cascade'
