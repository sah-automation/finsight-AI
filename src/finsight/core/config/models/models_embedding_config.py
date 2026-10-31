from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class ModelsEmbeddingConfig(StrictBaseModel):
    primary: str = 'gemini/text-embedding-004'
    version: str = 'v1'
    dimensions: int = Field(ge=1, default=1024)
    retry_attempts: int = Field(ge=0, le=5, default=3)
    retry_wait_seconds: int = Field(ge=1, le=10, default=2)

    @model_validator(mode='after')
    def validate_retry_budget(self) -> 'ModelsEmbeddingConfig':
        retry_budget_limit = 10
        if self.retry_attempts * self.retry_wait_seconds >= retry_budget_limit:
            raise ValueError(
                'embedding retry_attempts times retry_wait_seconds must stay under 10 seconds'
            )
        return self
