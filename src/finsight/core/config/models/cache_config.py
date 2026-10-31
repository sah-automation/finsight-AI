from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class CacheConfig(StrictBaseModel):
    answer_enabled: bool = True
    clear_on_upload: bool = True
    ttl_seconds: int = Field(ge=1, default=3600)

    @model_validator(mode='after')
    def validate_cache(self) -> 'CacheConfig':
        if self.answer_enabled and not self.clear_on_upload:
            raise ValueError('cache.answer_enabled requires cache.clear_on_upload')
        if self.answer_enabled and self.ttl_seconds <= 0:
            raise ValueError('cache.ttl_seconds must be above 0 when cache.answer_enabled is true')
        return self
