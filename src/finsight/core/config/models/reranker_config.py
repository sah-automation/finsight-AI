from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class RerankerConfig(StrictBaseModel):
    provider: str
    model: str
    top_n: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    batch_size: int = Field(ge=1)
