from typing import Literal

from .strict_base_model import StrictBaseModel


class OutputGateConfig(StrictBaseModel):
    mode: Literal['per_sentence', 'full_answer'] = 'per_sentence'
    per_sentence_citation_check: bool = True
    number_check_enabled: bool = True
    block_on_failure: bool = True
