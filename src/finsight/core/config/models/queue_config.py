from pydantic import Field, model_validator

from .strict_base_model import (
    StrictBaseModel,
)


class QueueConfig(StrictBaseModel):
    ingestion_queue_url: str
    reprocessing_queue_url: str
    reports_queue_url: str
    dead_letter_queue_url: str
    visibility_timeout_seconds: int = Field(ge=1)
    max_receive_count: int = Field(ge=1, le=10, default=5)
    job_max_receive_count: int | None = Field(ge=1, le=10, default=None)
    batch_size: int = Field(ge=1)
    wait_time_seconds: int = Field(ge=0)

    @model_validator(mode='after')
    def _sync_receive_counts(self) -> 'QueueConfig':
        target = self.max_receive_count
        object.__setattr__(self, 'job_max_receive_count', target)
        return self
