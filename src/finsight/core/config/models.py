# Config Models - Pydantic models for typed, validated configuration
# This is the ONLY place that defines config structure.
# All config access goes through the validated Config object.

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ============================================================
# Validation Limits
# ============================================================

_MAX_FALLBACK_MODELS = 3
_MIN_PRODUCTION_TRACE_SAMPLE_RATE = 0.01
_MIN_ANSWER_CACHE_TTL_SECONDS = 300
_MIN_ROLE_CACHE_TTL_SECONDS = 60


class Environment(StrEnum):
    DEVELOPMENT = 'development'
    TEST = 'test'
    STAGING = 'staging'
    PRODUCTION = 'production'


class LogFormat(StrEnum):
    JSON = 'json'
    TEXT = 'text'


class PiiAction(StrEnum):
    MASK = 'mask'
    BLOCK = 'block'
    LOG = 'log'


class ChunkingStrategy(StrEnum):
    SEMANTIC = 'semantic'
    FIXED = 'fixed'
    RECURSIVE = 'recursive'


class SslMode(StrEnum):
    DISABLE = 'disable'
    ALLOW = 'allow'
    PREFER = 'prefer'
    REQUIRE = 'require'
    VERIFY_CA = 'verify-ca'
    VERIFY_FULL = 'verify-full'


# ============================================================
# Nested Config Models
# ============================================================


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: str = Field(..., description='Provider name (litellm, bedrock, etc.)')
    model_id: str = Field(..., description='Model identifier')
    max_tokens: int = Field(..., gt=0, le=100000)
    temperature: float = Field(..., ge=0.0, le=2.0)
    timeout_seconds: int = Field(..., gt=0, le=300)
    max_retries: int = Field(..., ge=0, le=10)
    retry_base_delay_seconds: float = Field(..., gt=0, le=60)


class EmbeddingModelConfig(BaseModel):
    """Embedding model configuration."""

    provider: str
    model_id: str
    dimensions: int = Field(..., gt=0, le=10000)
    batch_size: int = Field(..., gt=0, le=1000)
    timeout_seconds: int = Field(..., gt=0, le=120)
    max_retries: int = Field(..., ge=0, le=10)


class RouterConfig(BaseModel):
    """LiteLLM router configuration."""

    num_retries: int = Field(..., ge=0, le=10)
    retry_after: int = Field(..., ge=0, le=3600)
    allowed_fails: int = Field(..., ge=0, le=100)
    cooldown_time: int = Field(..., ge=0, le=3600)


class LlmConfig(BaseModel):
    """LLM configuration."""

    primary_model: ModelConfig
    fallback_models: list[ModelConfig] = Field(default_factory=list)
    embedding_model: EmbeddingModelConfig
    router: RouterConfig

    @field_validator('fallback_models')
    @classmethod
    def validate_fallback_chain(cls, v: list[ModelConfig]) -> list[ModelConfig]:
        if len(v) > _MAX_FALLBACK_MODELS:
            raise ValueError('Maximum 3 fallback models allowed (model 1, 2, 3)')
        return v


class VectorStoreConfig(BaseModel):
    """Aurora pgvector configuration."""

    host: str
    port: int = Field(..., gt=0, le=65535)
    database: str
    username: str
    password: str
    ssl_mode: SslMode = SslMode.REQUIRE
    pool_size: int = Field(..., gt=0, le=100)
    max_overflow: int = Field(..., ge=0, le=50)
    pool_timeout_seconds: int = Field(..., gt=0, le=300)
    pool_recycle_seconds: int = Field(..., gt=0, le=86400)
    hnsw_ef_search: int = Field(..., gt=0, le=1000)
    hnsw_ef_construction: int = Field(..., gt=0, le=1000)
    hnsw_m: int = Field(..., gt=0, le=100)

    def connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return (
            f'postgresql+asyncpg://{self.username}:{self.password}'
            f'@{self.host}:{self.port}/{self.database}'
            f'?sslmode={self.ssl_mode.value}'
        )


class TextractConfig(BaseModel):
    """AWS Textract configuration."""

    async_enabled: bool = True
    poll_interval_seconds: int = Field(..., gt=0, le=60)
    max_poll_attempts: int = Field(..., gt=0, le=1000)
    feature_types: list[str] = Field(default_factory=lambda: ['TABLES', 'FORMS'])
    region: str


class TesseractConfig(BaseModel):
    """Tesseract OCR configuration."""

    languages: list[str] = Field(default_factory=lambda: ['eng'])
    dpi: int = Field(..., gt=0, le=1200)
    config: str = ''


class ChunkingConfig(BaseModel):
    """Document chunking configuration."""

    strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    max_chunk_tokens: int = Field(..., gt=0, le=8192)
    overlap_tokens: int = Field(..., ge=0, le=1000)
    min_chunk_tokens: int = Field(..., gt=0, le=1000)
    respect_boundaries: bool = True

    @model_validator(mode='after')
    def validate_overlap(self) -> ChunkingConfig:
        if self.overlap_tokens >= self.max_chunk_tokens:
            raise ValueError('overlap_tokens must be less than max_chunk_tokens')
        if self.min_chunk_tokens > self.max_chunk_tokens:
            raise ValueError('min_chunk_tokens must be <= max_chunk_tokens')
        return self


class ReadersConfig(BaseModel):
    """Document readers configuration."""

    priority: list[str] = Field(
        default_factory=lambda: ['pdfplumber', 'textract', 'tesseract', 'excel', 'csv', 'docx']
    )
    textract: TextractConfig
    tesseract: TesseractConfig
    chunking: ChunkingConfig


class RerankerConfig(BaseModel):
    """Reranker configuration."""

    provider: str
    model: str
    top_n: int = Field(..., gt=0, le=100)
    timeout_seconds: int = Field(..., gt=0, le=60)
    max_retries: int = Field(..., ge=0, le=10)
    batch_size: int = Field(..., gt=0, le=200)


class CacheConfig(BaseModel):
    """DynamoDB cache configuration."""

    table_name: str
    ttl_seconds: int = Field(..., gt=0, le=2592000)  # max 30 days
    key_prefix: str = ''
    max_entry_size_bytes: int = Field(..., gt=0, le=400000)


class CachesConfig(BaseModel):
    """Caches configuration."""

    answer_cache: CacheConfig
    role_cache: CacheConfig


class QueueConfig(BaseModel):
    """SQS queue configuration."""

    ingestion_queue_url: str
    reprocessing_queue_url: str
    reports_queue_url: str
    dead_letter_queue_url: str
    visibility_timeout_seconds: int = Field(..., gt=0, le=43200)  # max 12 hours
    max_receive_count: int = Field(..., gt=0, le=1000)
    batch_size: int = Field(..., gt=0, le=10)
    wait_time_seconds: int = Field(..., ge=0, le=20)


class StorageConfig(BaseModel):
    """S3 storage configuration."""

    documents_bucket: str
    reports_bucket: str
    backups_bucket: str
    region: str
    presigned_url_expiry_seconds: int = Field(..., gt=0, le=604800)  # max 7 days
    multipart_threshold_mb: int = Field(..., gt=0, le=5000)
    multipart_chunksize_mb: int = Field(..., gt=0, le=5000)


class AuthConfig(BaseModel):
    """Cognito authentication configuration."""

    user_pool_id: str
    client_id: str
    region: str
    jwks_cache_ttl_seconds: int = Field(..., gt=0, le=86400)
    token_verification_clock_skew_seconds: int = Field(..., ge=0, le=300)


class MeteringConfig(BaseModel):
    """Usage metering configuration."""

    table_name: str
    flush_interval_seconds: int = Field(..., gt=0, le=3600)
    batch_size: int = Field(..., gt=0, le=1000)


class AlertThresholds(BaseModel):
    """Alert thresholds."""

    fallback_model_3_used: bool = True
    reranker_down: bool = True
    embedding_retries_exceeded: int = Field(..., gt=0, le=100)
    job_in_retry_list: bool = True
    role_cache_stale_seconds: int = Field(..., gt=0, le=86400)


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    log_format: LogFormat = LogFormat.JSON
    trace_sample_rate: float = Field(..., ge=0.0, le=1.0)
    service_name: str
    otlp_endpoint: str | None = None
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    alerts: AlertThresholds


class SecurityConfig(BaseModel):
    """Security configuration."""

    require_company_id_on_all_queries: bool = True
    pii_detection_enabled: bool = True
    pii_action: PiiAction = PiiAction.MASK
    prompt_injection_detection_enabled: bool = True
    max_question_length: int = Field(..., gt=0, le=100000)
    max_context_tokens: int = Field(..., gt=0, le=1000000)


class SwitchesConfig(BaseModel):
    """Feature switches - both paths must be tested."""

    # LLM & Retrieval
    reranker_enabled: bool = True
    backup_request_enabled: bool = True
    parallel_retrieval_enabled: bool = True
    per_sentence_citation_check: bool = True

    # Ingestion
    async_textract_enabled: bool = True
    ocr_fallback_enabled: bool = True

    # Caching
    answer_cache_enabled: bool = True
    role_cache_enabled: bool = True

    # Observability
    detailed_tracing_enabled: bool = True
    usage_metering_enabled: bool = True


class AppConfig(BaseModel):
    """Application metadata."""

    name: str = 'finsight-ai'
    version: str = '0.1.0'
    environment: Environment = Environment.DEVELOPMENT


# ============================================================
# Root Config Model
# ============================================================


class Config(BaseModel):
    """Root configuration object. Frozen after validation."""

    app: AppConfig
    switches: SwitchesConfig
    llm: LlmConfig
    vector_store: VectorStoreConfig
    readers: ReadersConfig
    reranker: RerankerConfig
    caches: CachesConfig
    queue: QueueConfig
    storage: StorageConfig
    auth: AuthConfig
    metering: MeteringConfig
    observability: ObservabilityConfig
    security: SecurityConfig

    model_config = {
        'frozen': True,
        'extra': 'forbid',  # Reject unknown fields
        'validate_assignment': True,
    }

    @model_validator(mode='after')
    def validate_cross_field_rules(self) -> Config:
        """Validate cross-field constraints."""
        # In production, certain switches must be enabled
        if self.app.environment == Environment.PRODUCTION:
            if not self.switches.reranker_enabled:
                raise ValueError('reranker_enabled must be true in production')
            if not self.switches.backup_request_enabled:
                raise ValueError('backup_request_enabled must be true in production')
            if not self.switches.usage_metering_enabled:
                raise ValueError('usage_metering_enabled must be true in production')
            if self.observability.trace_sample_rate < _MIN_PRODUCTION_TRACE_SAMPLE_RATE:
                raise ValueError('trace_sample_rate must be >= 0.01 in production')
            if not self.security.pii_detection_enabled:
                raise ValueError('pii_detection_enabled must be true in production')
            if self.security.pii_action != PiiAction.MASK:
                raise ValueError("pii_action must be 'mask' in production")

        # Vector store pool sizing
        if self.vector_store.max_overflow > self.vector_store.pool_size:
            raise ValueError('max_overflow must be <= pool_size')

        # Cache TTLs should be reasonable
        if self.caches.answer_cache.ttl_seconds < _MIN_ANSWER_CACHE_TTL_SECONDS:
            raise ValueError('answer_cache.ttl_seconds must be >= 300 (5 minutes)')
        if self.caches.role_cache.ttl_seconds < _MIN_ROLE_CACHE_TTL_SECONDS:
            raise ValueError('role_cache.ttl_seconds must be >= 60 (1 minute)')

        return self
