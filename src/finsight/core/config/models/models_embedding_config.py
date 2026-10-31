from pydantic import Field

from .strict_base_model import StrictBaseModel


class ModelsEmbeddingConfig(StrictBaseModel):
    primary: str = 'provider_a/embed_model'
    version: str = 'v1'
    dimensions: int = Field(ge=1, default=1024)
    retry_attempts: int = Field(ge=0, default=3)
    retry_wait_seconds: int = Field(ge=0, default=2)
