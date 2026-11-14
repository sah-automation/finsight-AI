from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class AnswerCheckConfig(StrictBaseModel):
    enabled: bool = True
    retry_max: int = Field(ge=0, le=1, default=1)
    retry_time_limit_seconds: int = Field(ge=1, le=4, default=4)
