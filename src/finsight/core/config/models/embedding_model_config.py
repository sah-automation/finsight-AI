from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class EmbeddingModelConfig(StrictBaseModel):
    provider: str = 'litellm'
    model_id: str
    dimensions: int = Field(ge=1)
    batch_size: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
