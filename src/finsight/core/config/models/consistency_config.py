from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class ConsistencyConfig(StrictBaseModel):
    check_interval_seconds: int = Field(ge=1, default=300)
    fresh_read_window_seconds: int = Field(ge=0, le=60, default=10)
    job_max_receive_count: int = Field(ge=1, le=10, default=5)
