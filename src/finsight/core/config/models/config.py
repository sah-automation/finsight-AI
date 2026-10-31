from pydantic import model_validator

from .access_config import AccessConfig
from .answer_check_config import AnswerCheckConfig
from .app_config import AppConfig
from .auth_config import AuthConfig
from .cache_config import CacheConfig
from .caches_config import CachesConfig
from .consistency_config import ConsistencyConfig
from .database_config import DatabaseConfig
from .documents_config import DocumentsConfig
from .edge_config import EdgeConfig
from .encryption_config import EncryptionConfig
from .environment import Environment
from .ingestion_config import IngestionConfig
from .lambda_config import LambdaConfig
from .llm_config import LlmConfig
from .metering_config import MeteringConfig
from .models_config import ModelsConfig
from .observability_config import ObservabilityConfig
from .output_gate_config import OutputGateConfig
from .permissions_config import PermissionsConfig
from .protection_config import ProtectionConfig
from .question_flow_config import QuestionFlowConfig
from .queue_config import QueueConfig
from .readers_config import ReadersConfig
from .reranker_config import RerankerConfig
from .retrieval_config import RetrievalConfig
from .scale_config import ScaleConfig
from .security_config import SecurityConfig
from .storage_config import StorageConfig
from .strict_base_model import (
    _MIN_PRODUCTION_TRACE_SAMPLE_RATE,
    StrictBaseModel,
)
from .switches_config import SwitchesConfig
from .traffic_config import TrafficConfig
from .vector_store_config import VectorStoreConfig


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
    # Extended Phase 1 typed sections
    database: DatabaseConfig | None = None
    traffic: TrafficConfig | None = None
    protection: ProtectionConfig | None = None
    encryption: EncryptionConfig | None = None
    lambda_: LambdaConfig | None = None
    models: ModelsConfig | None = None
    cache: CacheConfig | None = None
    edge: EdgeConfig | None = None
    scale: ScaleConfig | None = None

    @model_validator(mode='after')
    def validate_production_rules(self) -> 'Config':
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
        raise ValueError('SOURCE_VIEWER_SIGNING_KEY must be configured')

    @property
    def source_viewer_secret(self) -> str:
        return self.source_viewer_signing_key

    @property
    def signing_key(self) -> str:
        return self.source_viewer_signing_key

    @property
    def citation_signing_key(self) -> str:
        return self.source_viewer_signing_key
