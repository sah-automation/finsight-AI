"""Deep module: Save step for the ingestion pipeline."""

from __future__ import annotations

from typing import Any

from .pipeline_step_worker import (
    PipelineStepWorker,
)
from .save_step_operations import SaveStepOperations
from .step_context import (  # noqa: F401
    Context,
    IngestionContext,
    IngestionStepContext,
    PipelineContext,
    PipelineStepContext,
    StepContext,
)

__all__ = [
    'Context',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineContext',
    'PipelineSaveStep',
    'PipelineStepContext',
    'Save',
    'SaveDeep',
    'SaveModule',
    'SaveStep',
    'SaveStepDeep',
    'StepContext',
    'TransactionalSave',
]

aliases = [
    'DeepSaveStep',
    'PipelineSaveStep',
    'Save',
    'SaveDeep',
    'SaveModule',
    'SaveStep',
    'SaveStepDeep',
    'TransactionalSave',
]


class SaveStep(SaveStepOperations, PipelineStepWorker):
    """Commit a fully-populated ingestion context via injected ports."""

    step_name = 'save'

    def __init__(
        self,
        *,
        document_repository: Any = None,
        document_repo: Any = None,
        documents: Any = None,
        document_store: Any = None,
        document_table_repository: Any = None,
        document_tables_repository: Any = None,
        document_table_repo: Any = None,
        table_repository: Any = None,
        tables_repository: Any = None,
        table_store: Any = None,
        chunk_repository: Any = None,
        chunks: Any = None,
        chunk_store: Any = None,
        document_chunks: Any = None,
        vector_store: Any = None,
        vectors: Any = None,
        vector_repository: Any = None,
        search: Any = None,
        vector_write: Any = None,
        vector_writer: Any = None,
        metric_repository: Any = None,
        metrics: Any = None,
        metrics_repository: Any = None,
        figures: Any = None,
        extracted_metrics: Any = None,
        answer_cache: Any = None,
        cache: Any = None,
        answer_cache_port: Any = None,
        change_event_publisher: Any = None,
        event_publisher: Any = None,
        publisher: Any = None,
        change_publisher: Any = None,
        config: Any = None,
        settings: Any = None,
        configuration: Any = None,
        app_config: Any = None,
        unit_of_work: Any = None,
        uow: Any = None,
        transaction: Any = None,
        tx: Any = None,
        state_store: Any = None,
        store: Any = None,
        context_store: Any = None,
        step_state_store: Any = None,
        delta_tracking: Any = None,
        container: Any = None,
        composition: Any = None,
        root: Any = None,
        app: Any = None,
        context: Any = None,
    ) -> None:
        container_obj = None
        for candidate in (container, composition, root, app, context):
            if candidate is not None and not isinstance(candidate, (str, bytes, dict)):
                container_obj = candidate
                break

        alias_dict = lambda names_values: names_values  # noqa: E731
        del alias_dict

        def _pick(mapping: dict[str, Any]) -> Any:
            for v in mapping.values():
                if v is not None:
                    return v
            return None

        doc_repo = _pick(
            {
                'document_repository': document_repository,
                'document_repo': document_repo,
                'documents': documents,
                'document_store': document_store,
            }
        )
        table_repo = _pick(
            {
                'document_table_repository': document_table_repository,
                'document_tables_repository': document_tables_repository,
                'document_table_repo': document_table_repo,
                'table_repository': table_repository,
                'tables_repository': tables_repository,
                'table_store': table_store,
            }
        )
        chunk_repo = _pick(
            {
                'chunk_repository': chunk_repository,
                'chunks': chunks,
                'chunk_store': chunk_store,
                'document_chunks': document_chunks,
            }
        )
        vector_store_value = _pick(
            {
                'vector_store': vector_store,
                'vectors': vectors,
                'vector_repository': vector_repository,
                'search': search,
                'vector_write': vector_write,
                'vector_writer': vector_writer,
            }
        )
        metric_repo = _pick(
            {
                'metric_repository': metric_repository,
                'metrics': metrics,
                'metrics_repository': metrics_repository,
                'figures': figures,
                'extracted_metrics': extracted_metrics,
            }
        )
        cache = _pick(
            {
                'answer_cache': answer_cache,
                'cache': cache,
                'answer_cache_port': answer_cache_port,
            }
        )
        pub = _pick(
            {
                'change_event_publisher': change_event_publisher,
                'event_publisher': event_publisher,
                'publisher': publisher,
                'change_publisher': change_publisher,
            }
        )
        cfg = _pick(
            {
                'config': config,
                'settings': settings,
                'configuration': configuration,
                'app_config': app_config,
            }
        )
        uow_value = _pick(
            {
                'unit_of_work': unit_of_work,
                'uow': uow,
                'transaction': transaction,
                'tx': tx,
            }
        )
        st = _pick(
            {
                'state_store': state_store,
                'store': store,
                'context_store': context_store,
                'step_state_store': step_state_store,
            }
        )

        if container_obj is not None:
            if doc_repo is None:
                doc_repo = getattr(container_obj, 'document_repository', doc_repo)
            if table_repo is None:
                table_repo = getattr(
                    container_obj, 'document_table_repository', table_repo
                ) or getattr(container_obj, 'table_repository', table_repo)
            if chunk_repo is None:
                chunk_repo = getattr(container_obj, 'chunk_repository', chunk_repo)
            if vector_store_value is None:
                vector_store_value = getattr(container_obj, 'vector_store', vector_store_value)
            if metric_repo is None:
                metric_repo = getattr(container_obj, 'metric_repository', metric_repo)
            if cache is None:
                cache = getattr(container_obj, 'answer_cache', cache)
            if pub is None:
                pub = getattr(container_obj, 'change_event_publisher', pub) or getattr(
                    container_obj, 'event_publisher', pub
                )
            if cfg is None:
                cfg = getattr(container_obj, 'config', cfg)
            if uow_value is None:
                uow_value = getattr(container_obj, 'unit_of_work', uow_value)

        super().__init__(
            document_repository=doc_repo,
            document_table_repository=table_repo,
            chunk_repository=chunk_repo,
            vector_store=vector_store_value,
            metric_repository=metric_repo,
            answer_cache=cache,
            change_event_publisher=pub,
            config=cfg,
            unit_of_work=uow_value,
            step_name='save',
            delta_tracking=delta_tracking,
        )
        self.state_store = st


DeepSaveStep = SaveStep
Save = SaveStep
SaveDeep = SaveStep
SaveModule = SaveStep
SaveStepDeep = SaveStep
TransactionalSave = SaveStep
PipelineSaveStep = SaveStep
