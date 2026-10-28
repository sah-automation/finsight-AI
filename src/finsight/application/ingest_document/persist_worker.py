"""Persist worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class PersistWorker(PipelineStepWorker):
    step_name = 'persist'
