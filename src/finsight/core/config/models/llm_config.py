from pydantic import field_validator, model_validator

from .embedding_model_config import EmbeddingModelConfig
from .model_config import ModelConfig
from .router_config import RouterConfig
from .strict_base_model import (
    _MAX_FALLBACK_MODELS,
    StrictBaseModel,
)


class LlmConfig(StrictBaseModel):
    primary_model: ModelConfig
    fallback_models: list[ModelConfig]
    embedding_model: EmbeddingModelConfig
    router: RouterConfig | None = None

    @field_validator('fallback_models')
    @classmethod
    def validate_fallback_count(cls, v: list[ModelConfig]) -> list[ModelConfig]:
        if len(v) > _MAX_FALLBACK_MODELS:
            raise ValueError(f'Maximum {_MAX_FALLBACK_MODELS} fallback models allowed')
        if len(v) < 1:
            raise ValueError('At least 1 fallback model required')
        return v

    @model_validator(mode='after')
    def validate_distinct_models(self) -> 'LlmConfig':
        all_model_ids = [self.primary_model.model_id] + [m.model_id for m in self.fallback_models]
        if len(all_model_ids) != len(set(all_model_ids)):
            raise ValueError('All models in the chain must be distinct')
        return self
