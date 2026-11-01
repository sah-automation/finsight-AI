from .strict_base_model import (
    StrictBaseModel,
)


class SwitchesConfig(StrictBaseModel):
    # Phase 1 active switches
    parallel_steps: bool = True
    backup_request_enabled: bool = True
    prompt_cache_enabled: bool = True
    answer_cache_enabled: bool = True
    # Legacy switches for compatibility
    reranker_enabled: bool = True
    async_textract_enabled: bool = True
    ocr_fallback_enabled: bool = True
    role_cache_enabled: bool = True
    detailed_tracing_enabled: bool = True
    waiting_line_enabled: bool = True
    usage_metering_enabled: bool = True
    per_sentence_citation_check: bool = True
    parallel_retrieval_enabled: bool = True
