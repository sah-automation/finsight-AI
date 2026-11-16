from typing import Literal

from .strict_base_model import (
    StrictBaseModel,
)


class SwitchesConfig(StrictBaseModel):
    # Phase 1 active switches
    parallel_steps: bool = True
    backup_request_enabled: bool = True
    prompt_cache_enabled: bool = True
    answer_cache_enabled: bool = True
    # Vector store switch: neon_pgvector (pilot) or aurora_pgvector (standard)
    vector_store: Literal['neon_pgvector', 'aurora_pgvector'] = 'neon_pgvector'
    # Secrets provider switch: parameter_store (pilot) or secrets_manager (standard)
    secrets_provider: Literal['parameter_store', 'secrets_manager'] = 'parameter_store'
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
    llm_content_capture_enabled: bool = True
