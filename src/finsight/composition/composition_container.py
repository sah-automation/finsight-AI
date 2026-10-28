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
        chunk_repository: Any = None,
        vector_store: Any = None,
        vector_write: Any = None,
        change_event_publisher: Any = None,
        event_publisher: Any = None,
        object_storage: Any = None,
        answer_cache: Any = None,
        queue: Any = None,
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
        self.answer_cache = answer_cache if answer_cache is not None else deps.get('answer_cache')
        self.queue = queue if queue is not None else deps.get('queue')
        self.onboarding_use_case = onboarding_use_case
        self.onboarding = onboarding_use_case
        self.create_company_use_case = onboarding_use_case
        self.create_company = onboarding_use_case
        self.upload_use_case = upload_use_case
        self.upload = upload_use_case
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
        self.chunk_repository = chunk_repository
        self.vector_store = vector_store
        self.vector_write = vector_write
        self.vector_store_write = vector_write
        self.change_event_publisher = change_event_publisher
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
            'reader_registry': self.reader_registry,
            'scan_worker': self.scan_worker,
            'document_repository': self.document_repository,
            'chunk_repository': self.chunk_repository,
            'vector_store': self.vector_store,
            'vector_write': self.vector_write,
            'change_event_publisher': self.change_event_publisher,
            'event_publisher': self.event_publisher,
            'publisher': self.publisher,
            'answer_cache': self.answer_cache,
            'queue': self.queue,
        }
        self.repositories = {
            'company': company_repository,
            'user': user_repository,
            'partition_metadata': partition_metadata_repository,
            'job': self.job_repository,
            'jobs': self.job_repository,
            'document': self.document_repository,
            'chunk': self.chunk_repository,
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
            'chunk_repository': self.chunk_repository,
            'vector_store': self.vector_store,
            'vector_write': self.vector_write,
            'change_event_publisher': self.change_event_publisher,
            'event_publisher': self.event_publisher,
            'publisher': self.publisher,
            'object_storage': self.object_storage,
            'answer_cache': self.answer_cache,
            'queue': self.queue,
            'ingestion_use_case': self.ingestion_use_case,
            'ingestion': self.ingestion_pipeline,
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

    def wire_entrypoints(self) -> None:
        import contextlib

        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.onboarding as onboarding_entrypoint

            onboarding_entrypoint.get_onboarding_use_case = lambda *_a, **_k: (
                self.onboarding_use_case
            )
        with contextlib.suppress(Exception):
            import finsight.entrypoints.api.upload as upload_entrypoint

            upload_entrypoint.get_upload_use_case = lambda *_a, **_k: self.upload_use_case


CompositionContainer = CompositionContainer  # noqa: PLW0127
CompositionRoot = CompositionContainer
Container = CompositionContainer
AppContainer = CompositionContainer
ApplicationContext = CompositionContainer
ServiceContainer = CompositionContainer
RootContainer = CompositionContainer
