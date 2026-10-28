"""Cache adapter (DynamoDB + job progress view)."""

from .job_progress import (
    DynamoDBJobProgress,
    DynamoDBProgressView,
    DynamoJobProgress,
    DynamoJobProgressView,
    DynamoProgress,
    DynamoProgressView,
    JobProgress,
    JobProgressView,
)

__all__ = [
    'DynamoDBJobProgress',
    'DynamoDBProgressView',
    'DynamoJobProgress',
    'DynamoJobProgressView',
    'DynamoProgress',
    'DynamoProgressView',
    'JobProgress',
    'JobProgressView',
]

try:
    from .job_progress import DynamoDBJobProgress, DynamoDBJobProgressView, DynamoDBProgressView
except Exception:
    from .job_progress import DynamoJobProgress as DynamoDBJobProgress
    from .job_progress import DynamoJobProgressView as DynamoDBJobProgressView
    from .job_progress import DynamoProgressView as DynamoDBProgressView

try:
    from . import dynamodb_job_progress, dynamodb_job_progress_view, dynamodb_progress_view
except Exception:
    pass
