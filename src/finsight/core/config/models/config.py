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

    @model_validator(mode='after')
    def validate_binding_rules(self) -> 'Config':  # noqa: PLR0912, PLR0915
        # Traffic + scale combinations.
        traffic = getattr(self, 'traffic', None)
        database = getattr(self, 'database', None)
        ingestion = getattr(self, 'ingestion', None)
        documents = getattr(self, 'documents', None)
        models = getattr(self, 'models', None)
        access = getattr(self, 'access', None)
        permissions = getattr(self, 'permissions', None)
        question_flow = getattr(self, 'question_flow', None)
        switches = getattr(self, 'switches', None)

        if traffic is not None:
            if traffic.lambda_reserved_concurrency <= 0:
                raise ValueError('lambda_reserved_concurrency must be above 0')
            if traffic.db_pool_size_per_function < 1:
                raise ValueError('db_pool_size_per_function must be 1 or more')
            if traffic.db_connections_per_request < 1:
                raise ValueError('db_connections_per_request must be 1 or more')
            if traffic.ingestion_max_concurrency < 1:
                raise ValueError('ingestion_max_concurrency must be 1 or more')
            if traffic.ingestion_max_concurrency >= traffic.lambda_reserved_concurrency:
                raise ValueError(
                    'ingestion_max_concurrency must be below lambda_reserved_concurrency'
                )
            if (
                switches is not None
                and getattr(switches, 'parallel_steps', True)
                and traffic.db_pool_size_per_function < traffic.db_connections_per_request
            ):
                raise ValueError(
                    'db_pool_size_per_function must be at least db_connections_per_request '
                    'when parallel_steps is true'
                )
            # connection limit (only when proxy disabled)
            if database is not None and not getattr(database, 'rds_proxy_enabled', False):
                connection_limit_per_acu = 100
                needed = traffic.lambda_reserved_concurrency * max(
                    traffic.db_pool_size_per_function,
                    traffic.db_connections_per_request,
                )
                # Conservative Aurora Serverless v2 ceiling: ~100 connections per ACU.
                limit = (
                    int(getattr(traffic, 'aurora_max_capacity_acu', 0) or 0)
                    * connection_limit_per_acu
                )
                if limit and needed >= limit:
                    raise ValueError(
                        'lambda_reserved_concurrency times the larger of db_pool_size_per_function '
                        'and db_connections_per_request must stay under the Aurora connection limit'
                    )

        if database is not None and traffic is not None:
            # aurora_max_capacity_acu lives in traffic in this typed model
            if traffic.aurora_max_capacity_acu < 1:
                raise ValueError('aurora_max_capacity_acu must be at least 1')
            if traffic.aurora_max_capacity_acu < database.min_capacity_acu:
                raise ValueError('aurora_max_capacity_acu must be at least min_capacity_acu')

        # Model timing cross checks handled in ModelsConfig; gate backup request on chain state.
        if models is not None:
            answer_models = getattr(models, 'answer', None)
            if models.backup_request_enabled and answer_models is not None:
                # fallback 1 of primary chain must be present
                fallbacks = getattr(answer_models, 'primary_fallbacks', None) or []
                if not fallbacks:
                    raise ValueError('backup_request_enabled needs fallback 1 of the chosen chain')
            # retry product already in EmbeddingModelConfig

        # Documents / ingestion cross checks.
        if documents is not None and (
            documents.delta_tracking
            and ingestion is not None
            and getattr(ingestion, 'chunk_strategy', None) != 'structure_recursive'
        ):
            raise ValueError('delta_tracking requires chunk_strategy structure_recursive')

        # max_parent_tokens bound by chunk_token_budget if available on question_flow
        if (
            ingestion is not None
            and question_flow is not None
            and getattr(question_flow, 'chunk_token_budget', None) is not None
            and ingestion.max_parent_tokens > question_flow.chunk_token_budget
        ):
            raise ValueError('max_parent_tokens must not exceed chunk_token_budget')

        # Required metadata / context categories checks.
        if ingestion is not None and documents is not None:
            categories = set(documents.categories or [])
            bad = [c for c in (ingestion.llm_context_categories or []) if c not in categories]
            if bad:
                raise ValueError('llm_context_categories entries must be valid categories')
            # required metadata already validated per model

        # Access roles / permissions cross checks.
        if permissions is not None:
            permission_roles = set(
                (permissions.roles and [r.get('id') for r in permissions.roles]) or []
            )
            # expected fixed role set enforced in PermissionsConfig
            if access is not None:
                access_roles = set(access.roles or [])
                if access_roles and access_roles != permission_roles:
                    # require access roles to match permissions exactly
                    pass
        if access is not None and permissions is not None:
            perm_roles = {r.get('id') for r in (permissions.roles or [])}
            if set(access.roles or []) != perm_roles:
                raise ValueError('access.roles must list every role defined in permissions')
            # privileged role cache must not exceed role cache ttl if available
            if hasattr(access, 'role_cache_seconds_privileged'):
                role_cache = getattr(self, 'caches', None)
                role_cache = getattr(role_cache, 'role_cache', None) if role_cache else None
                ttl = getattr(role_cache, 'ttl_seconds', None)
                if ttl is not None and access.role_cache_seconds_privileged > ttl:
                    raise ValueError('role_cache_seconds_privileged must not exceed role_cache ttl')
            # users per company already per model
        if permissions is not None and documents is not None:
            perm_categories = {c.get('id') for c in (permissions.categories or [])}
            if set(documents.categories or []) != perm_categories:
                raise ValueError(
                    'documents.categories must match permissions_file categories exactly'
                )
            if not documents.categories:
                raise ValueError('documents.categories must not be empty')

        # Auth role cache seconds (if represented on role cache ttl) optional; no-op.

        # Encourage both-path proxies: rds_proxy resource existence cannot be checked here.

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
