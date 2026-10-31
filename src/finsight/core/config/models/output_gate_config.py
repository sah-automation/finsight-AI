from .strict_base_model import (
    StrictBaseModel,
)


class OutputGateConfig(StrictBaseModel):
    per_sentence_citation_check: bool = True
    number_check_enabled: bool = True
    block_on_failure: bool = True
