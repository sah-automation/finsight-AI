"""Compatibility alias for the Postgres job repository."""

from __future__ import annotations

from .job_repository import JobRepository


class PostgresJobRepository(JobRepository):
    """Compatibility alias."""
