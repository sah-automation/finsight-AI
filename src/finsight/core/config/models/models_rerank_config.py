from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class ModelsRerankConfig(StrictBaseModel):
    primary: str
    timeout_ms: int = Field(ge=100, le=1000, default=600)
    on_failure: str = 'search_order'

    @model_validator(mode='after')
    def validate_rerank(self) -> 'ModelsRerankConfig':
        if self.on_failure != 'search_order':
            raise ValueError('models.rerank.on_failure must be search_order')
        return self
