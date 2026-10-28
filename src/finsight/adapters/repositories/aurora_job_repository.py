"""Compatibility alias for the Aurora job repository."""

from __future__ import annotations

from .job_repository import JobRepository


class AuroraJobRepository(JobRepository):
    """Compatibility alias."""
