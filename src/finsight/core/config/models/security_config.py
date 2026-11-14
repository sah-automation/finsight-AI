from pydantic import Field

from .pii_action import PiiAction
from .strict_base_model import (
    StrictBaseModel,
)


class SecurityConfig(StrictBaseModel):
    require_company_id_on_all_queries: bool
    pii_detection_enabled: bool
    pii_action: PiiAction
    prompt_injection_detection_enabled: bool
    max_question_length: int = Field(ge=1)
    max_context_tokens: int = Field(ge=1)


# Additional Phase 1 sections (minimal required)
