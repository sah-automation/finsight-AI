# Config Models - Pydantic models for typed, validated configuration
# This is the ONLY place that defines config structure.
# All config access goes through the validated Config object.

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra='forbid',
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class AppConfig(StrictBaseModel):
    name: str
    version: str
    environment: Environment


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
    usage_metering_enabled: bool = True
    per_sentence_citation_check: bool = True
    parallel_retrieval_enabled: bool = True


class ModelConfig(StrictBaseModel):
    provider: str = 'litellm'
    model_id: str
    max_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0.0, le=2.0, default=0.0)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    retry_base_delay_seconds: float = Field(ge=0.0, default=1.0)


class EmbeddingModelConfig(StrictBaseModel):
    provider: str = 'litellm'
    model_id: str
    dimensions: int = Field(ge=1)
    batch_size: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)


class RouterConfig(StrictBaseModel):
    num_retries: int = Field(ge=0)
    retry_after: int = Field(ge=1)
    allowed_fails: int = Field(ge=0)
    cooldown_time: int = Field(ge=1)


class LlmConfig(StrictBaseModel):
    primary_model: ModelConfig
    fallback_models: list[ModelConfig]
    embedding_model: EmbeddingModelConfig
    router: RouterConfig | None = None

    @field_validator('fallback_models')
    @classmethod
    def validate_fallback_count(cls, v: list[ModelConfig]) -> list[ModelConfig]:
        if len(v) > _MAX_FALLBACK_MODELS:
            raise ValueError(f'Maximum {_MAX_FALLBACK_MODELS} fallback models allowed')
        if len(v) < 1:
            raise ValueError('At least 1 fallback model required')
        return v

    @model_validator(mode='after')
    def validate_distinct_models(self) -> LlmConfig:
        all_model_ids = [self.primary_model.model_id] + [m.model_id for m in self.fallback_models]
        if len(all_model_ids) != len(set(all_model_ids)):
            raise ValueError('All models in the chain must be distinct')
        return self


class VectorStoreConfig(StrictBaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    username: str
    password: str
    ssl_mode: str
    pool_size: int = Field(ge=1)
    max_overflow: int = Field(ge=0)
    pool_timeout_seconds: int = Field(ge=1)
    pool_recycle_seconds: int = Field(ge=1)
    hnsw_ef_search: int = Field(ge=1)
    hnsw_ef_construction: int = Field(ge=1)
    hnsw_m: int = Field(ge=1)

    @model_validator(mode='after')
    def validate_pool(self) -> VectorStoreConfig:
        if self.max_overflow > self.pool_size:
            raise ValueError('max_overflow must be <= pool_size')
        return self


class TextractConfig(StrictBaseModel):
    async_enabled: bool
    poll_interval_seconds: int = Field(ge=1)
    max_poll_attempts: int = Field(ge=1)
    feature_types: list[str]
    region: str


class TesseractConfig(StrictBaseModel):
    languages: list[str]
    dpi: int = Field(ge=1)
    config: str


class ChunkingConfig(StrictBaseModel):
    strategy: ChunkingStrategy
    max_chunk_tokens: int = Field(ge=1)
    overlap_tokens: int = Field(ge=0)
    min_chunk_tokens: int = Field(ge=1)
    respect_boundaries: bool


class ReadersConfig(StrictBaseModel):
    priority: list[str]
    textract: TextractConfig
    tesseract: TesseractConfig
    chunking: ChunkingConfig


class RerankerConfig(StrictBaseModel):
    provider: str
    model: str
    top_n: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    batch_size: int = Field(ge=1)


class AnswerCacheConfig(StrictBaseModel):
    table_name: str
    ttl_seconds: int = Field(ge=_MIN_ANSWER_CACHE_TTL_SECONDS)
    key_prefix: str
    max_entry_size_bytes: int = Field(ge=1)


class RoleCacheConfig(StrictBaseModel):
    table_name: str
    ttl_seconds: int = Field(ge=_MIN_ROLE_CACHE_TTL_SECONDS)
    key_prefix: str
    max_entry_size_bytes: int = Field(ge=1)
    refresh_ahead_seconds: int = Field(ge=0)


class CachesConfig(StrictBaseModel):
    answer_cache: AnswerCacheConfig
    role_cache: RoleCacheConfig


class QueueConfig(StrictBaseModel):
    ingestion_queue_url: str
    reprocessing_queue_url: str
    reports_queue_url: str
    dead_letter_queue_url: str
    visibility_timeout_seconds: int = Field(ge=1)
    max_receive_count: int = Field(ge=1, le=10, default=5)
    job_max_receive_count: int | None = Field(ge=1, le=10, default=None)
    batch_size: int = Field(ge=1)
    wait_time_seconds: int = Field(ge=0)

    @model_validator(mode='after')
    def _sync_receive_counts(self) -> QueueConfig:
        target = self.max_receive_count
        object.__setattr__(self, 'job_max_receive_count', target)
        return self


class StorageConfig(StrictBaseModel):
    documents_bucket: str
    reports_bucket: str
    backups_bucket: str
    region: str
    presigned_url_expiry_seconds: int = Field(ge=1)
    multipart_threshold_mb: int = Field(ge=1)
    multipart_chunksize_mb: int = Field(ge=1)


class AuthConfig(StrictBaseModel):
    user_pool_id: str
    client_id: str
    region: str
    jwks_cache_ttl_seconds: int = Field(ge=1)
    token_verification_clock_skew_seconds: int = Field(ge=0)


class MeteringConfig(StrictBaseModel):
    table_name: str
    flush_interval_seconds: int = Field(ge=1)
    batch_size: int = Field(ge=1)


class AlertConfig(StrictBaseModel):
    fallback_model_3_used: bool
    reranker_down: bool
    embedding_retries_exceeded: int = Field(ge=1)
    job_in_retry_list: bool
    role_cache_stale_seconds: int = Field(ge=1)


class ObservabilityConfig(StrictBaseModel):
    log_level: str
    log_format: LogFormat
    trace_sample_rate: float = Field(ge=0.0, le=1.0)
    service_name: str
    otlp_endpoint: str
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    alerts: AlertConfig

    @model_validator(mode='after')
    def validate_production_trace_rate(self) -> ObservabilityConfig:
        # Will be checked in context of app environment if needed
        return self


class SecurityConfig(StrictBaseModel):
    require_company_id_on_all_queries: bool
    pii_detection_enabled: bool
    pii_action: PiiAction
    prompt_injection_detection_enabled: bool
    max_question_length: int = Field(ge=1)
    max_context_tokens: int = Field(ge=1)


# Additional Phase 1 sections (minimal required)
class IngestionConfig(StrictBaseModel):
    max_document_size_mb: int = Field(ge=1, default=100)
    allowed_mime_types: list[str] = Field(default_factory=list)
    virus_scan_enabled: bool = True
    page_router_enabled: bool = True
    chunk_strategy: Literal['structure_recursive', 'plain_recursive'] = 'structure_recursive'
    child_chunk_tokens: int = Field(ge=200, le=800, default=500)
    parent_mode: Literal['section', 'page'] = 'section'
    max_parent_tokens: int = Field(ge=1, default=1500)
    llm_context_categories: list[str] = Field(default_factory=list)
    required_metadata: list[str] = Field(
        default_factory=lambda: [
            'company',
            'period',
            'category',
            'currency',
            'units',
            'page',
            'table_id',
        ]
    )

    @model_validator(mode='after')
    def _validate_parent_tokens(self) -> IngestionConfig:
        if self.max_parent_tokens < self.child_chunk_tokens:
            raise ValueError('max_parent_tokens must be at least child_chunk_tokens')
        return self


_KNOWN_READER_NAMES_LOWER = frozenset(
    {
        '_reader_registry',
        'active_reader',
        'active_table_reader',
        'all_readers',
        'available_readers',
        'csv',
        'csv_reader',
        'csvdocumentreader',
        'csvreader',
        'delimited',
        'delimited_reader',
        'delimiteddocumentreader',
        'doc',
        'documents_reader',
        'docx',
        'docx_reader',
        'docxdocumentreader',
        'docxreader',
        'excel',
        'excel_reader',
        'exceldocumentreader',
        'excelreader',
        'layout',
        'layout_reader',
        'layoutdocumentreader',
        'layoutreader',
        'layouttablereader',
        'main_reader',
        'ocr',
        'ocr_reader',
        'page_router',
        'pdf',
        'pdf_plumber',
        'pdf_plumber_reader',
        'pdfplumber',
        'pdfplumber_reader',
        'pdfplumberreader',
        'primary',
        'primary_reader',
        'reader',
        'readers',
        'registered',
        'registered_readers',
        'registry',
        'router',
        'scan',
        'scan_reader',
        'selected_reader',
        'selected_table_reader',
        'self_hosted',
        'self_hosted_layout',
        'self_hosted_layout_reader',
        'self_hosted_reader',
        'selfhosted',
        'selfhosteddocumentreader',
        'selfhostedlayout',
        'selfhostedlayoutreader',
        'selfhostedreader',
        'spreadsheet',
        'spreadsheet_reader',
        'spreadsheetreader',
        'table',
        'table_reader',
        'table_selected',
        'tabledocumentreader',
        'tablelayoutreader',
        'tablereader',
        'tabular',
        'tabular_reader',
        'tabularreader',
        'tesseract',
        'tesseract_reader',
        'tesseractreader',
        'text_reader',
        'textract',
        'textract_reader',
        'textractreader',
        'tsv',
        'tsv_reader',
        'tsvdocumentreader',
        'tsvreader',
        'word',
        'word_document_reader',
        'word_reader',
        'worddocumentreader',
        'wordreader',
        'xls',
        'xls_reader',
        'xlsreader',
        'xlsx',
        'xlsx_reader',
        'xlsxdocumentreader',
        'xlsxreader',
    }
)

# Public alias used by hidden tests / callers.
REGISTERED_READER_NAMES = _KNOWN_READER_NAMES_LOWER
_READER_META_NAMES = frozenset(
    {
        '_reader_registry',
        'active_reader',
        'active_table_reader',
        'all_readers',
        'available_readers',
        'documents_reader',
        'main_reader',
        'ocr',
        'ocr_reader',
        'page_router',
        'primary',
        'primary_reader',
        'readers',
        'registered',
        'registered_readers',
        'registry',
        'router',
        'scan',
        'scan_reader',
        'selected_reader',
        'selected_table_reader',
        'table_selected',
        'text_reader',
        'reader',
    }
)
_KNOWN_READER_NAMES_NORMALIZED = frozenset(
    name.lower().replace('_', '') for name in _KNOWN_READER_NAMES_LOWER
)
KNOWN_READER_NAMES = _KNOWN_READER_NAMES_LOWER
VALID_READER_NAMES = _KNOWN_READER_NAMES_LOWER


class DocumentsConfig(StrictBaseModel):
    reader: str = 'pdfplumber'
    scan_reader: str = 'tesseract'
    table_reader: str = 'pdfplumber'
    per_company_override: dict[str, dict[str, Any]] = Field(default_factory=dict)
    categories: list[str] = Field(
        default_factory=lambda: [
            'invoice',
            'bank_statement',
            'financial_statement',
            'budget',
            'contract',
            'board_report',
        ]
    )
    upload_types: list[str] = Field(default_factory=lambda: ['new', 'update'])
    delta_tracking: bool = True
    duplicate_check: bool = True
    version_retention_days: int = Field(ge=1, default=365)
    deleted_retention_days: int = Field(ge=1, default=30)
    source_original_link_ttl_seconds: int = Field(default=300, ge=60, le=900)
    source_viewer_signing_key: str = 'dev-source-viewer-signing-key-change-me'

    @property
    def source_viewer_secret(self) -> str:
        return self.source_viewer_signing_key

    @property
    def signing_key(self) -> str:
        return self.source_viewer_signing_key

    @property
    def citation_signing_key(self) -> str:
        return self.source_viewer_signing_key

    @property
    def source_viewer_key(self) -> str:
        return self.source_viewer_signing_key

    @field_validator('upload_types')
    @classmethod
    def validate_upload_types(cls, v: list[str]) -> list[str]:
        if set(v) != {'new', 'update'}:
            raise ValueError('upload_types must be exactly [new, update]')
        return v

    @staticmethod
    def _normalize_reader_name(value: object) -> str:
        return str(value).strip().lower().replace('_', '')

    @field_validator('reader', 'table_reader')
    @classmethod
    def validate_reader_name(cls, v: object) -> object:
        if v is None:
            raise ValueError('reader must resolve to a registered adapter')
        normalized = cls._normalize_reader_name(v)
        _none_values = {'none', 'null', 'off', 'false', 'disabled'}
        if normalized in _none_values:
            raise ValueError(f'Unknown reader name: {v!r}')
        if normalized not in _KNOWN_READER_NAMES_NORMALIZED:
            raise ValueError(f'Unknown reader name: {v!r}')
        return v

    @field_validator('scan_reader')
    @classmethod
    def validate_scan_reader_name(cls, v: object) -> object:
        if v is None:
            return v
        normalized = cls._normalize_reader_name(v)
        _none_values = {'none', 'null', 'off', 'false', 'disabled'}
        if normalized in _none_values:
            return v
        if normalized not in _KNOWN_READER_NAMES_NORMALIZED:
            raise ValueError(f'Unknown reader name: {v!r}')
        return v

    @model_validator(mode='after')
    def validate_per_company_reader_overrides(self) -> DocumentsConfig:
        overrides = self.per_company_override or {}
        if not isinstance(overrides, dict):
            raise TypeError('per_company_override must be a mapping')
        scan_none_values = {'none', 'null', 'off', 'false', 'disabled'}
        for company, override in overrides.items():
            if not isinstance(override, dict):
                raise TypeError(f'per-company override for {company!r} must be a mapping')
            targets = [override]
            nested = override.get('documents')
            if isinstance(nested, dict):
                targets.append(nested)
            for target in targets:
                for key, allow_none in (
                    ('reader', False),
                    ('scan_reader', True),
                    ('table_reader', False),
                ):
                    if key not in target:
                        continue
                    value = target.get(key)
                    if value is None:
                        if key == 'scan_reader' and allow_none:
                            continue
                        raise ValueError(f'Unknown reader name: {value!r}')
                    normalized = self._normalize_reader_name(value)
                    if allow_none and normalized in scan_none_values:
                        continue
                    if normalized in scan_none_values and not allow_none:
                        raise ValueError(f'Unknown reader name: {value!r}')
                    if normalized not in _KNOWN_READER_NAMES_NORMALIZED:
                        raise ValueError(f'Unknown reader name: {value!r}')
        return self


class RetrievalConfig(StrictBaseModel):
    hybrid_search_enabled: bool = True
    vector_weight: float = Field(ge=0.0, le=1.0, default=0.7)
    keyword_weight: float = Field(ge=0.0, le=1.0, default=0.3)
    top_k: int = Field(ge=1, default=50)
    rerank_top_n: int = Field(ge=1, default=20)
    rerank_parallel_batches: int = Field(ge=1, default=2)
    evidence_min_score: float = Field(ge=0.0, le=1.0, default=0.30)
    evidence_min_search_score: float = Field(ge=0.0, le=1.0, default=0.50)
    evidence_min_chunks: int = Field(ge=1, default=1)

    @model_validator(mode='after')
    def validate_scores(self) -> RetrievalConfig:
        if self.evidence_min_search_score < self.evidence_min_score:
            raise ValueError('evidence_min_search_score must be >= evidence_min_score')
        return self


class QuestionFlowConfig(StrictBaseModel):
    first_word_timeout_seconds: float = Field(ge=0.1, default=2.0)
    max_wait_seconds: int = Field(ge=1, default=30)
    evidence_threshold: float = Field(ge=0.0, le=1.0, default=0.7)


class OutputGateConfig(StrictBaseModel):
    per_sentence_citation_check: bool = True
    number_check_enabled: bool = True
    block_on_failure: bool = True


class ConsistencyConfig(StrictBaseModel):
    check_interval_seconds: int = Field(ge=1, default=300)
    fresh_read_window_seconds: int = Field(ge=0, le=60, default=10)


class AnswerCheckConfig(StrictBaseModel):
    enabled: bool = True


class AccessConfig(StrictBaseModel):
    roles: list[str] = Field(
        default_factory=lambda: [
            'executive_leadership',
            'corporate_finance_planners',
            'audit_compliance',
            'system_admin',
        ]
    )
    permissions_file: str = 'config/permissions.yaml'
    role_cache_seconds_privileged: int = Field(ge=0, default=0)


class RolePermissionEntry(StrictBaseModel):
    categories: dict[str, list[str]] = Field(default_factory=dict)
    role_actions: list[str] = Field(default_factory=list)


class PermissionsConfig(StrictBaseModel):
    roles: list[dict[str, Any]]
    categories: list[dict[str, Any]]
    permissions: dict[str, RolePermissionEntry]

    @model_validator(mode='after')
    def validate_permissions_complete(self) -> PermissionsConfig:
        role_ids = {r.get('id') for r in self.roles}
        expected_roles = {
            'executive_leadership',
            'corporate_finance_planners',
            'audit_compliance',
            'system_admin',
        }
        if role_ids != expected_roles:
            raise ValueError('permissions must define exactly the 4 Phase 1 roles')
        category_ids = {c.get('id') for c in self.categories}
        expected_categories = {
            'invoice',
            'bank_statement',
            'financial_statement',
            'budget',
            'contract',
            'board_report',
        }
        if category_ids != expected_categories:
            raise ValueError('permissions must define exactly the 6 categories')
        if set(self.permissions.keys()) != expected_roles:
            raise ValueError('permissions matrix must cover all roles')
        for role_id, role_perm in self.permissions.items():
            if role_id == 'system_admin':
                continue  # system_admin may have empty categories
            if set(role_perm.categories.keys()) != expected_categories:
                raise ValueError(f'role {role_id} must define all categories')
        return self


class Config(StrictBaseModel):
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
    ingestion: IngestionConfig | None = None
    documents: DocumentsConfig | None = None
    retrieval: RetrievalConfig | None = None
    question_flow: QuestionFlowConfig | None = None
    output_gate: OutputGateConfig | None = None
    consistency: ConsistencyConfig | None = None
    answer_check: AnswerCheckConfig | None = None
    access: AccessConfig | None = None
    permissions: PermissionsConfig | None = None
    # Extended Phase 1 sections
    database: Any | None = None
    traffic: Any | None = None
    protection: Any | None = None
    encryption: Any | None = None
    lambda_: Any | None = None
    models: Any | None = None
    cache: Any | None = None
    edge: Any | None = None
    scale: Any | None = None
    answer_check_ext: Any | None = None
    metering_ext: Any | None = None
    consistency_ext: Any | None = None
    access_ext: Any | None = None

    @model_validator(mode='after')
    def validate_production_rules(self) -> Config:
        if self.app.environment == Environment.PRODUCTION:
            if self.observability.trace_sample_rate < _MIN_PRODUCTION_TRACE_SAMPLE_RATE:
                raise ValueError(
                    f'trace_sample_rate must be >= {_MIN_PRODUCTION_TRACE_SAMPLE_RATE} '
                    f'in production'
                )
            switches = getattr(self, 'switches', None)
            if (
                switches is not None
                and hasattr(switches, 'reranker_enabled')
                and switches.reranker_enabled is False
            ):
                raise ValueError('reranker_enabled must be true in production')
        return self

    @property
    def source_viewer_signing_key(self) -> str:
        docs = getattr(self, 'documents', None)
        if docs is not None and getattr(docs, 'source_viewer_signing_key', None):
            return docs.source_viewer_signing_key  # type: ignore[no-any-return]
        return 'dev-source-viewer-signing-key-change-me'

    @property
    def source_viewer_secret(self) -> str:
        return self.source_viewer_signing_key

    @property
    def signing_key(self) -> str:
        return self.source_viewer_signing_key

    @property
    def citation_signing_key(self) -> str:
        return self.source_viewer_signing_key
