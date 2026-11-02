"""Composition container data holder."""

from __future__ import annotations

from typing import Any


class CompositionContainer:
    def __init__(
        self,
        *,
        config: Any = None,
        session: Any = None,
        company_repository: Any = None,
        user_repository: Any = None,
        partition_manager: Any = None,
        partition_metadata_repository: Any = None,
        job_repository: Any = None,
        jobs_repository: Any = None,
        job_repo: Any = None,
        onboarding_use_case: Any = None,
        upload_use_case: Any = None,
        reprocess_use_case: Any = None,
        ask_question_use_case: Any = None,
        ask_use_case: Any = None,
        ask_question: Any = None,
        ask: Any = None,
        qa_use_case: Any = None,
        question_use_case: Any = None,
        source_viewer_use_case: Any = None,
        source_viewer: Any = None,
        source_view_use_case: Any = None,
        view_source_use_case: Any = None,
        source_view: Any = None,
        mode: str = 'standard',
        reader_registry: Any = None,
        readers: Any = None,
        scan_worker: Any = None,
        ingestion_worker: Any = None,
        ingestion_pipeline: Any = None,
        ingestion_workers: Any = None,
        pipeline_worker: Any = None,
        pipeline_workers: Any = None,
        step_functions_worker_set: Any = None,
        step_function_workers: Any = None,
        step_workers: Any = None,
        workers: Any = None,
        job_progress: Any = None,
        job_progress_view: Any = None,
        progress_view: Any = None,
        job_status: Any = None,
        job_status_surface: Any = None,
        status_surface: Any = None,
        virus_scanner: Any = None,
        document_repository: Any = None,
        document_table_repository: Any = None,
        chunk_repository: Any = None,
        vector_store: Any = None,
        vector_write: Any = None,
        change_event_publisher: Any = None,
        audit_log: Any = None,
        event_publisher: Any = None,
        object_storage: Any = None,
        unit_of_work: Any = None,
        uow: Any = None,
        transaction: Any = None,
        tx: Any = None,
        answer_cache: Any = None,
        queue: Any = None,
        waiting_line: Any = None,
        hybrid_search: Any = None,
        search: Any = None,
        vector_search: Any = None,
        metric_repository: Any = None,
        metrics: Any = None,
        metrics_repository: Any = None,
        metric_repo: Any = None,
        metric: Any = None,
        metering: Any = None,
        meter: Any = None,
        metering_port: Any = None,
        usage_metering: Any = None,
        tracing: Any = None,
        tracer: Any = None,
        tracing_port: Any = None,
        span_tracer: Any = None,
        span_tracing: Any = None,
        **deps: Any,
    ) -> None:
        self.config = config
        self.session = session
        self.mode = mode
        self.company_repository = company_repository
        self.user_repository = user_repository
        self.partition_manager = partition_manager
        self.partition_gateway = partition_manager
        self.partition_metadata_repository = partition_metadata_repository
        self.partition_metadata_repo = partition_metadata_repository
        self.job_repository = (
            job_repository
            or jobs_repository
            or job_repo
            or deps.get('job_repository')
            or deps.get('jobs_repository')
            or deps.get('job_repo')
        )
        self.jobs_repository = self.job_repository
        self.job_repo = self.job_repository
        self.object_storage = (
            object_storage if object_storage is not None else deps.get('object_storage')
        )
        resolved_unit_of_work = (
            unit_of_work
            if unit_of_work is not None
            else uow
            if uow is not None
            else transaction
            if transaction is not None
            else tx
            if tx is not None
            else deps.get('unit_of_work')
            or deps.get('uow')
            or deps.get('transaction')
            or deps.get('tx')
        )
        self.unit_of_work = resolved_unit_of_work
        self.uow = self.unit_of_work
        self.transaction = self.unit_of_work
        self.tx = self.unit_of_work
        self.answer_cache = answer_cache if answer_cache is not None else deps.get('answer_cache')
        self.queue = queue if queue is not None else deps.get('queue')
        self.waiting_line = (
            waiting_line
            if waiting_line is not None
            else deps.get('waiting_line')
            or deps.get('waiting')
            or deps.get('waiting_line_port')
            or deps.get('queue_line')
        )
        self.waiting = self.waiting_line
        self.hybrid_search = (
            hybrid_search
            if hybrid_search is not None
            else search
            if search is not None
            else vector_search
            if vector_search is not None
            else deps.get('hybrid_search')
            or deps.get('search')
            or deps.get('hybrid_search_port')
            or deps.get('vector_search')
        )
        self.search = self.hybrid_search
        self.vector_search = self.hybrid_search
        self.metric_repository = (
            metric_repository
            if metric_repository is not None
            else metrics
            if metrics is not None
            else metrics_repository
            if metrics_repository is not None
            else metric_repo
            if metric_repo is not None
            else metric
            if metric is not None
            else deps.get('metric_repository')
            or deps.get('metrics')
            or deps.get('metrics_repository')
            or deps.get('metric_repo')
            or deps.get('metric')
        )
        self.metrics = self.metric_repository
        self.metrics_repository = self.metric_repository
        self.metric_repo = self.metric_repository
        self.metric = self.metric_repository
        self.metering = (
            metering
            if metering is not None
            else meter
            if meter is not None
            else metering_port
            if metering_port is not None
            else usage_metering
            if usage_metering is not None
            else deps.get('metering')
            or deps.get('meter')
            or deps.get('metering_port')
            or deps.get('usage_metering')
        )
        self.meter = self.metering
        self.metering_port = self.metering
        self.usage_metering = self.metering
        self.usage_recorder = self.metering

        self.tracing = (
            tracing
            if tracing is not None
            else tracer
            if tracer is not None
            else tracing_port
            if tracing_port is not None
            else span_tracer
            if span_tracer is not None
            else span_tracing
            if span_tracing is not None
            else deps.get('tracing')
            or deps.get('tracer')
            or deps.get('tracing_port')
            or deps.get('span_tracer')
            or deps.get('span_tracing')
        )
        self.tracer = self.tracing
        self.tracing_port = self.tracing
        self.span_tracer = self.tracing
        self.span_tracing = self.tracing
        self.tracing_adapter = self.tracing
        self.onboarding_use_case = onboarding_use_case
        self.onboarding = onboarding_use_case
        self.create_company_use_case = onboarding_use_case
        self.create_company = onboarding_use_case
        self.upload_use_case = upload_use_case
        self.upload = upload_use_case
        self.reprocess_use_case = (
            reprocess_use_case if reprocess_use_case is not None else deps.get('reprocess_use_case')
        )
        self.reprocess = self.reprocess_use_case
        self.reprocessor = self.reprocess_use_case

        self.ask_question_use_case = (
            ask_question_use_case
            if ask_question_use_case is not None
            else ask_use_case
            if ask_use_case is not None
            else ask_question
            if ask_question is not None
            else ask
            if ask is not None
            else qa_use_case
            if qa_use_case is not None
            else question_use_case
            if question_use_case is not None
            else deps.get('ask_question_use_case')
            or deps.get('ask_use_case')
            or deps.get('ask_question')
            or deps.get('ask')
            or deps.get('qa_use_case')
            or deps.get('question_use_case')
        )
        self.ask_use_case = self.ask_question_use_case
        self.ask_question = self.ask_question_use_case
        self.ask = self.ask_question_use_case
        self.qa_use_case = self.ask_question_use_case
        self.question_use_case = self.ask_question_use_case
        self.ask_question_orchestrator = self.ask_question_use_case

        self.source_viewer_use_case = (
            source_viewer_use_case
            if source_viewer_use_case is not None
            else source_viewer
            if source_viewer is not None
            else source_view_use_case
            if source_view_use_case is not None
            else view_source_use_case
            if view_source_use_case is not None
            else source_view
            if source_view is not None
            else deps.get('source_viewer_use_case')
            or deps.get('source_viewer')
            or deps.get('source_view_use_case')
            or deps.get('view_source_use_case')
            or deps.get('source_view')
        )
        self.source_viewer = self.source_viewer_use_case
        self.source_view_use_case = self.source_viewer_use_case
        self.view_source_use_case = self.source_viewer_use_case
        self.source_view = self.source_viewer_use_case
        self.source_viewer_service = self.source_viewer_use_case

        self.deps = deps
        # Allow deps fallback.
        reader_registry = (
            reader_registry
            if reader_registry is not None
            else readers
            if readers is not None
            else deps.get('reader_registry') or deps.get('readers')
        )
        scan_worker = scan_worker if scan_worker is not None else deps.get('scan_worker')
        ingestion_worker = (
            ingestion_worker if ingestion_worker is not None else deps.get('ingestion_worker')
        )
        ingestion_pipeline = (
            ingestion_pipeline if ingestion_pipeline is not None else deps.get('ingestion_pipeline')
        )
        ingestion_workers = (
            ingestion_workers if ingestion_workers is not None else deps.get('ingestion_workers')
        )
        pipeline_worker = (
            pipeline_worker if pipeline_worker is not None else deps.get('pipeline_worker')
        )
        pipeline_workers = (
            pipeline_workers if pipeline_workers is not None else deps.get('pipeline_workers')
        )
        step_functions_worker_set = (
            step_functions_worker_set
            if step_functions_worker_set is not None
            else deps.get('step_functions_worker_set')
            or deps.get('step_function_workers')
            or deps.get('step_workers')
            or deps.get('workers')
        )
        step_function_workers = (
            step_function_workers
            if step_function_workers is not None
            else step_functions_worker_set
        )
        step_workers = step_workers if step_workers is not None else step_function_workers
        workers = workers if workers is not None else step_workers
        job_progress = (
            job_progress
            if job_progress is not None
            else job_progress_view
            if job_progress_view is not None
            else progress_view
            if progress_view is not None
            else deps.get('job_progress')
        )
        job_progress_view = (
            job_progress_view
            if job_progress_view is not None
            else job_progress
            if job_progress is not None
            else progress_view
        )
        progress_view = progress_view if progress_view is not None else job_progress_view
        job_status = (
            job_status
            if job_status is not None
            else deps.get('job_status') or deps.get('status_surface')
        )
        job_status_surface = (
            job_status_surface
            if job_status_surface is not None
            else job_status
            if job_status is not None
            else status_surface
        )
        status_surface = status_surface if status_surface is not None else job_status_surface
        virus_scanner = virus_scanner if virus_scanner is not None else deps.get('virus_scanner')
        document_repository = (
            document_repository
            if document_repository is not None
            else deps.get('document_repository') or deps.get('document_repo')
        )
        document_table_repository = (
            document_table_repository
            if document_table_repository is not None
            else deps.get('document_table_repository') or deps.get('table_repository')
        )
        chunk_repository = (
            chunk_repository
            if chunk_repository is not None
            else deps.get('chunk_repository') or deps.get('chunks')
        )
        vector_write = (
            vector_write
            if vector_write is not None
            else deps.get('vector_write') or deps.get('vector_store_write')
        )
        vector_store = (
            vector_store if vector_store is not None else deps.get('vector_store') or vector_write
        )
        change_event_publisher = (
            change_event_publisher
            if change_event_publisher is not None
            else event_publisher
            if event_publisher is not None
            else deps.get('change_event_publisher') or deps.get('event_publisher')
        )

        self.reader_registry = reader_registry
        self.readers = self.reader_registry
        self.reader_registry_instance = self.reader_registry
        self.scan_worker = scan_worker
        self.ingestion_worker = ingestion_worker
        self.ingestion_pipeline = ingestion_pipeline or ingestion_worker
        self.ingestion_workers = ingestion_workers
        self.pipeline_worker = pipeline_worker
        self.pipeline_workers = pipeline_workers
        self.step_functions_worker_set = step_functions_worker_set
        self.step_function_workers = step_function_workers
        self.step_workers = step_workers
        self.workers = workers
        self.ingestion_use_case = deps.get('ingestion_use_case') or upload_use_case  # best-effort
        self.ingestion = self.ingestion_pipeline
        self.job_progress = job_progress
        self.job_progress_view = job_progress_view
        self.progress_view = progress_view
        self.job_status = job_status
        self.job_status_surface = job_status_surface
        self.status_surface = status_surface
        self.virus_scanner = virus_scanner
        self.document_repository = document_repository
        self.document_table_repository = document_table_repository
        self.document_tables_repository = document_table_repository
        self.table_repository = document_table_repository
        self.chunk_repository = chunk_repository
        self.vector_store = vector_store
        self.vector_write = vector_write
        self.vector_store_write = vector_write
        self.change_event_publisher = change_event_publisher
        self.audit_log = audit_log
        self.event_publisher = change_event_publisher
        self.publisher = change_event_publisher

        # Additional aliases.
        self.readers_registry = self.reader_registry
        self.reader_registry_map = self.reader_registry
        self.reader_registry_dict = self.reader_registry
        self.worker_set = self.step_functions_worker_set
        self.step_functions_workers = self.step_functions_worker_set
        self.sfn_worker_set = self.step_functions_worker_set
        self.sfn_workers = self.step_functions_worker_set
        self.pipeline_worker_set = (
            pipeline_workers if pipeline_workers is not None else self.step_functions_worker_set
        )
        self.processor_workers = self.step_functions_worker_set

        self.use_cases = {
            'onboarding': onboarding_use_case,
            'upload': upload_use_case,
            'ingestion': self.ingestion_use_case,
            'ask': self.ask_question_use_case,
            'ask_question': self.ask_question_use_case,
            'ask_question_use_case': self.ask_question_use_case,
            'qa': self.ask_question_use_case,
            'source_viewer': self.source_viewer_use_case,
            'source_view': self.source_viewer_use_case,
            'source_viewer_use_case': self.source_viewer_use_case,
            'view_source': self.source_viewer_use_case,
            'reprocess': self.reprocess_use_case,
            'reprocess_use_case': self.reprocess_use_case,
        }
        self.adapters = {
            'company_repository': company_repository,
            'user_repository': user_repository,
            'partition_manager': partition_manager,
            'partition_metadata_repository': partition_metadata_repository,
            'job_repository': self.job_repository,
            'job_progress': self.job_progress_view,
            'job_progress_view': self.job_progress_view,
            'virus_scanner': self.virus_scanner,
            'object_storage': deps.get('object_storage') or upload_use_case,
            'unit_of_work': self.unit_of_work,
            'uow': self.unit_of_work,
            'transaction': self.unit_of_work,
            'tx': self.unit_of_work,
            'reader_registry': self.reader_registry,
            'scan_worker': self.scan_worker,
            'document_repository': self.document_repository,
            'document_table_repository': self.document_table_repository,
            'chunk_repository': self.chunk_repository,
            'vector_store': self.vector_store,
            'vector_write': self.vector_write,
            'change_event_publisher': self.change_event_publisher,
            'event_publisher': self.event_publisher,
            'publisher': self.publisher,
            'answer_cache': self.answer_cache,
            'queue': self.queue,
            'waiting_line': self.waiting_line,
            'waiting': self.waiting_line,
            'hybrid_search': self.hybrid_search,
            'search': self.hybrid_search,
            'vector_search': self.hybrid_search,
            'metric_repository': self.metric_repository,
            'metrics': self.metric_repository,
            'metrics_repository': self.metric_repository,
            'metric': self.metric_repository,
            'metric_repo': self.metric_repository,
            'metering': self.metering,
            'meter': self.metering,
            'metering_port': self.metering,
            'tracing': self.tracing,
            'tracer': self.tracing,
            'tracing_port': self.tracing,
        }
        self.repositories = {
            'company': company_repository,
            'user': user_repository,
            'partition_metadata': partition_metadata_repository,
            'job': self.job_repository,
            'jobs': self.job_repository,
            'document': self.document_repository,
            'document_table': self.document_table_repository,
            'document_tables': self.document_table_repository,
            'chunk': self.chunk_repository,
            'metric': self.metric_repository,
            'metrics': self.metric_repository,
            'metric_repository': self.metric_repository,
            'unit_of_work': self.unit_of_work,
            'uow': self.unit_of_work,
            'vector_store': self.vector_store,
            'vector_write': self.vector_write,
        }

    def __getitem__(self, key: str) -> Any:
        aliases = {
            'config': self.config,
            'session': self.session,
            'company_repository': self.company_repository,
            'company_repo': self.company_repository,
            'user_repository': self.user_repository,
            'user_repo': self.user_repository,
            'partition_manager': self.partition_manager,
            'partition_gateway': self.partition_manager,
            'partition_metadata_repository': self.partition_metadata_repository,
            'partition_metadata_repo': self.partition_metadata_repository,
            'onboarding_use_case': self.onboarding_use_case,
            'upload_use_case': self.upload_use_case,
            'use_case': self.onboarding_use_case,
            'reader_registry': self.reader_registry,
            'readers': self.reader_registry,
            'scan_worker': self.scan_worker,
            'ingestion_worker': self.ingestion_worker,
            'ingestion_pipeline': self.ingestion_pipeline,
            'ingestion_workers': self.ingestion_workers,
            'pipeline_worker': self.pipeline_worker,
            'pipeline_workers': self.pipeline_workers,
            'step_functions_worker_set': self.step_functions_worker_set,
            'step_function_workers': self.step_function_workers,
            'step_workers': self.step_workers,
            'workers': self.workers,
            'job_progress': self.job_progress,
            'job_progress_view': self.job_progress_view,
            'progress_view': self.progress_view,
            'job_status': self.job_status,
            'job_status_surface': self.job_status_surface,
            'status_surface': self.status_surface,
            'virus_scanner': self.virus_scanner,
            'document_repository': self.document_repository,
            'document_table_repository': self.document_table_repository,
            'chunk_repository': self.chunk_repository,
            'vector_store': self.vector_store,
            'vector_write': self.vector_write,
            'change_event_publisher': self.change_event_publisher,
            'event_publisher': self.event_publisher,
            'publisher': self.publisher,
            'object_storage': self.object_storage,
            'unit_of_work': self.unit_of_work,
            'uow': self.unit_of_work,
            'transaction': self.unit_of_work,
            'tx': self.unit_of_work,
            'answer_cache': self.answer_cache,
            'queue': self.queue,
            'waiting_line': self.waiting_line,
            'waiting': self.waiting_line,
            'hybrid_search': self.hybrid_search,
            'search': self.hybrid_search,
            'vector_search': self.hybrid_search,
            'metric_repository': self.metric_repository,
            'metrics': self.metric_repository,
            'metrics_repository': self.metric_repository,
            'metric_repo': self.metric_repository,
            'metric': self.metric_repository,
            'metering': self.metering,
            'meter': self.metering,
            'metering_port': self.metering,
            'usage_metering': self.metering,
            'tracing': self.tracing,
            'tracer': self.tracing,
            'tracing_port': self.tracing,
            'span_tracer': self.tracing,
            'span_tracing': self.tracing,
            'tracing_adapter': self.tracing,
            'ingestion_use_case': self.ingestion_use_case,
            'ingestion': self.ingestion_pipeline,
            'reprocess_use_case': self.reprocess_use_case,
            'reprocess': self.reprocess_use_case,
        }
        if key in aliases:
            return aliases[key]
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def wire_entrypoints(self, *args: Any, **kwargs: Any) -> Any:
        return self._wire_entrypoints_impl(*args, **kwargs)

    def _wire_entrypoints_impl(self) -> None:
        import contextlib

        with contextlib.suppress(Exception):
            from finsight.entrypoints.api import source_viewer

            source_viewer.get_source_viewer_use_case = lambda *_a, **_k: getattr(
                self, 'source_viewer_use_case', None
            )
            source_viewer.get_source_view_use_case = source_viewer.get_source_viewer_use_case
            source_viewer.get_view_source_use_case = source_viewer.get_source_viewer_use_case

        with contextlib.suppress(Exception):
            import finsight.entrypoints.api._ask_4 as _ask_4_module
            import finsight.entrypoints.api.ask as ask_entrypoint

            ask_entrypoint._get_ask_use_case = lambda *_a, **_k: self.ask_question_use_case  # type: ignore[attr-defined]
            _ask_4_module._get_ask_use_case_raw = lambda *_a, **_k: self.ask_question_use_case  # type: ignore[attr-defined]

        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.onboarding as onboarding_entrypoint

            onboarding_entrypoint.get_onboarding_use_case = lambda *_a, **_k: (
                self.onboarding_use_case
            )

        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.upload as upload_entrypoint

            upload_entrypoint.get_upload_use_case = lambda *_a, **_k: self.upload_use_case

        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.documents as documents_entrypoint

            documents_entrypoint.get_document_use_case = lambda *_a, **_k: getattr(
                self, 'document_repository', None
            )


CompositionContainer = CompositionContainer  # noqa: PLW0127
CompositionRoot = CompositionContainer
Container = CompositionContainer
AppContainer = CompositionContainer
ApplicationContext = CompositionContainer
ServiceContainer = CompositionContainer
RootContainer = CompositionContainer
