from pydantic import Field

from .models_answer_config import ModelsAnswerConfig
from .models_embedding_config import ModelsEmbeddingConfig
from .models_rerank_config import ModelsRerankConfig
from .strict_base_model import StrictBaseModel


class ModelsConfig(StrictBaseModel):
    answer: ModelsAnswerConfig = Field(default_factory=ModelsAnswerConfig)
    failover_on: list[str] = Field(
        default_factory=lambda: [
            'timeout',
            'first_word_timeout',
            'rate_limit',
            'server_error',
            'provider_unavailable',
        ]
    )
    embedding: ModelsEmbeddingConfig = Field(default_factory=ModelsEmbeddingConfig)
    rerank: ModelsRerankConfig = Field(default_factory=ModelsRerankConfig)
    timeout_seconds: int = Field(ge=1, default=20)
    first_token_timeout_seconds: float = Field(ge=0.1, default=4.0)
    backup_request_enabled: bool = True
    backup_request_after_seconds: float = Field(ge=0.0, default=2.5)
    prompt_cache_enabled: bool = True
    max_output_tokens: int = Field(ge=1, default=1000)
    monthly_budget_per_company: int = Field(ge=0, default=50)
