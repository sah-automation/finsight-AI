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
    def validate_binding_rules(self) -> 'Config':
        self._validate_traffic_rules()
        self._validate_lambda_rules()
        self._validate_model_rules()
        self._validate_document_and_ingestion_rules()
        self._validate_access_and_permission_rules()
        return self

    def _validate_traffic_rules(self) -> None:
        traffic = self.traffic
        database = self.database
        switches = self.switches
        if traffic is None:
            return
        if traffic.lambda_reserved_concurrency <= 0:
            raise ValueError('lambda_reserved_concurrency must be above 0')
        if traffic.db_pool_size_per_function < 1:
            raise ValueError('db_pool_size_per_function must be 1 or more')
        if traffic.db_connections_per_request < 1:
            raise ValueError('db_connections_per_request must be 1 or more')
        if traffic.ingestion_max_concurrency < 1:
            raise ValueError('ingestion_max_concurrency must be 1 or more')
        if traffic.ingestion_max_concurrency >= traffic.lambda_reserved_concurrency:
            raise ValueError('ingestion_max_concurrency must be below lambda_reserved_concurrency')
        if (
            switches is not None
            and getattr(switches, 'parallel_steps', True)
            and traffic.db_pool_size_per_function < traffic.db_connections_per_request
        ):
            raise ValueError(
                'db_pool_size_per_function must be at least '
                'db_connections_per_request when parallel_steps is true'
            )
        self._validate_conn_limit(traffic, database)
        if database is not None:
            if traffic.aurora_max_capacity_acu < 1:
                raise ValueError('aurora_max_capacity_acu must be at least 1')
            if traffic.aurora_max_capacity_acu < database.min_capacity_acu:
                raise ValueError('aurora_max_capacity_acu must be at least min_capacity_acu')

    def _validate_conn_limit(
        self, traffic: 'TrafficConfig', database: 'DatabaseConfig | None'
    ) -> None:
        if database is None or database.rds_proxy_enabled:
            return
        connection_limit_per_acu = 100
        needed = traffic.lambda_reserved_concurrency * max(
            traffic.db_pool_size_per_function,
            traffic.db_connections_per_request,
        )
        limit = int(traffic.aurora_max_capacity_acu) * connection_limit_per_acu
        if limit and needed >= limit:
            raise ValueError(
                'lambda_reserved_concurrency times the larger of db_pool_size_per_function '
                'and db_connections_per_request must stay under the Aurora connection limit'
            )

    def _validate_lambda_rules(self) -> None:
        lambda_config = self.lambda_
        traffic = self.traffic
        if lambda_config is None or traffic is None:
            return
        if lambda_config.question_provisioned_concurrency > traffic.lambda_reserved_concurrency:
            raise ValueError(
                'question_provisioned_concurrency must not exceed lambda_reserved_concurrency'
            )

    def _validate_model_rules(self) -> None:  # noqa: PLR0912
        models = self.models
        if models is None:
            return
        if models.backup_request_enabled:
            answer_models = getattr(models, 'answer', None)
            fallbacks = getattr(answer_models, 'primary_fallbacks', None) or []
            if not fallbacks:
                raise ValueError('backup_request_enabled needs fallback 1 of the chosen chain')

        model_ids: list[str] = []
        llm = getattr(self, 'llm', None)
        primary = getattr(llm, 'primary_model', None) if llm is not None else None
        if primary is not None:
            model_ids.append(str(getattr(primary, 'model_id', '')))
        for fallback in getattr(llm, 'fallback_models', None) or []:
            model_ids.append(str(getattr(fallback, 'model_id', '')))
        embedding = getattr(llm, 'embedding_model', None) if llm is not None else None
        if embedding is not None:
            model_ids.append(str(getattr(embedding, 'model_id', '')))
        reranker = getattr(self, 'reranker', None)
        if reranker is not None:
            provider = str(getattr(reranker, 'provider', '') or '')
            model = str(getattr(reranker, 'model', '') or '')
            if model:
                model_ids.append(model if '/' in model or not provider else f'{provider}/{model}')
        answer_cfg = getattr(models, 'answer', None)
        if answer_cfg is not None:
            for value in [getattr(answer_cfg, 'primary', None), getattr(answer_cfg, 'cheap', None)]:
                if value is not None:
                    model_ids.append(str(value))
            for value in [
                *list(getattr(answer_cfg, 'primary_fallbacks', None) or []),
                *list(getattr(answer_cfg, 'cheap_fallbacks', None) or []),
            ]:
                if value is not None:
                    model_ids.append(str(value))
        embedding_cfg = getattr(models, 'embedding', None)
        if embedding_cfg is not None and getattr(embedding_cfg, 'primary', None) is not None:
            model_ids.append(str(embedding_cfg.primary))
        rerank_cfg = getattr(models, 'rerank', None)
        if rerank_cfg is not None and getattr(rerank_cfg, 'primary', None) is not None:
            model_ids.append(str(rerank_cfg.primary))

        model_ids = [item for item in model_ids if item]
        if not model_ids:
            return
        try:
            from finsight.core.config.price_table import PriceNotFoundError, load_price_table  # noqa: PLC0415

            load_price_table().require_models(model_ids)
        except (PriceNotFoundError, Exception) as exc:
            raise ValueError(str(exc)) from exc

    def _validate_document_and_ingestion_rules(self) -> None:
        documents = self.documents
        ingestion = self.ingestion
        if (
            documents is not None
            and documents.delta_tracking
            and ingestion is not None
            and getattr(ingestion, 'chunk_strategy', None) != 'structure_recursive'
        ):
            raise ValueError('delta_tracking requires chunk_strategy structure_recursive')
        if ingestion is not None and documents is not None:
            categories = set(documents.categories or [])
            bad = [
                item for item in (ingestion.llm_context_categories or []) if item not in categories
            ]
            if bad:
                raise ValueError('llm_context_categories entries must be valid categories')
        if documents is not None:
            perm_categories = {
                item.get('id') for item in (self.permissions.categories if self.permissions else [])
            }
            if (
                self.permissions is not None
                and perm_categories
                and set(documents.categories or []) != perm_categories
            ):
                raise ValueError(
                    'documents.categories must match permissions_file categories exactly'
                )
            if not (documents.categories or []):
                raise ValueError('documents.categories must not be empty')

    def _validate_access_and_permission_rules(self) -> None:
        access = self.access
        permissions = self.permissions
        if access is None or permissions is None:
            return
        permission_roles = {item.get('id') for item in (permissions.roles or [])}
        if set(access.roles or []) != permission_roles:
            raise ValueError('access.roles must list every role defined in permissions')
        if hasattr(access, 'role_cache_seconds_privileged'):
            role_cache = getattr(getattr(self, 'caches', None), 'role_cache', None)
            ttl = getattr(role_cache, 'ttl_seconds', None)
            if ttl is not None and access.role_cache_seconds_privileged > ttl:
                raise ValueError('role_cache_seconds_privileged must not exceed role_cache ttl')

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
