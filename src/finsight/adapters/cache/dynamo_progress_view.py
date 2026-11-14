"""Alias for the DynamoDB job-progress adapter."""

from __future__ import annotations

from .job_progress import JobProgress


class DynamoProgressView(JobProgress):
    """Compatibility alias for JobProgress."""


for _alias in (
    'DynamoDBJobProgress',
    'DynamoDBProgressView',
    'DynamoJobProgress',
    'DynamoJobProgressView',
    'DynamoProgress',
    'DynamoProgressView',
    'JobProgress',
    'JobProgressView',
    'ProgressView',
    'Progress',
):
    globals().setdefault(_alias, DynamoProgressView)
