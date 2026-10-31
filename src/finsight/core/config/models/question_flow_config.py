from pydantic import Field

from .strict_base_model import (
    StrictBaseModel,
)


class QuestionFlowConfig(StrictBaseModel):
    first_word_timeout_seconds: float = Field(ge=0.1, default=2.0)
    max_wait_seconds: int = Field(ge=1, default=30)
    evidence_threshold: float = Field(ge=0.0, le=1.0, default=0.7)
