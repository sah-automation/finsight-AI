"""Alias for the DynamoDB job-progress adapter."""

from __future__ import annotations

from .job_progress import JobProgress


class DynamodbJobProgress(JobProgress):
    """Compatibility alias for JobProgress."""


DynamoDBJobProgress = DynamodbJobProgress
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
    globals().setdefault(_alias, DynamodbJobProgress)
