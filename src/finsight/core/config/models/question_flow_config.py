from typing import Literal

from pydantic import Field, model_validator

from .strict_base_model import StrictBaseModel


class QuestionFlowConfig(StrictBaseModel):
    first_word_timeout_seconds: float = Field(ge=0.1, default=2.0)
    max_wait_seconds: int = Field(ge=1, default=30)
    evidence_threshold: float = Field(ge=0.0, le=1.0, default=0.7)
    understand_mode: Literal['rules_then_model', 'model_only'] = 'rules_then_model'
    rules_confidence_min: float = Field(ge=0.0, le=1.0, default=0.9)
    chunk_token_budget: int = Field(ge=1, default=4000)

    @model_validator(mode='after')
    def validate_understand_mode(self) -> 'QuestionFlowConfig':
        min_confidence = 0.5
        max_confidence = 1.0
        if self.understand_mode == 'rules_then_model' and not (
            min_confidence <= self.rules_confidence_min <= max_confidence
        ):
            raise ValueError('rules_confidence_min must be between 0.5 and 1')
        return self
