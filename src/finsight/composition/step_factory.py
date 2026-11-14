"""Step factory for building ingestion pipeline steps."""

from __future__ import annotations

from typing import Any

from finsight.composition.step_deps import STEP_SPECS
from finsight.core.config.models import Config


class StepFactory:
    """Factory for creating ingestion pipeline step instances."""

    def __init__(
        self,
        *,
        document_repository: Any = None,
        document_table_repository: Any = None,
        chunk_repository: Any = None,
        vector_store: Any = None,
        vector_write: Any = None,
        state_store: Any = None,
        metric_repository: Any = None,
        reader: Any = None,
        page_router: Any = None,
        embedding: Any = None,
        answer_cache: Any = None,
        change_event_publisher: Any = None,
        config: Config | None = None,
        unit_of_work: Any = None,
        queue: Any = None,
        job_repository: Any = None,
        virus_scanner: Any = None,
        object_storage: Any = None,
        delta_tracking: bool = True,
        **extra: Any,
    ) -> None:
        self._common = dict(
            document_repository=document_repository,
            document_table_repository=document_table_repository,
            chunk_repository=chunk_repository,
            vector_store=vector_store,
            vector_write=vector_write,
            state_store=state_store,
            store=state_store,
            metric_repository=metric_repository,
            reader=reader,
            page_router=page_router,
            embedding=embedding,
            answer_cache=answer_cache,
            change_event_publisher=change_event_publisher,
            config=config,
            unit_of_work=unit_of_work,
            queue=queue,
            job_repository=job_repository,
            virus_scanner=virus_scanner,
            object_storage=object_storage,
            delta_tracking=delta_tracking,
            **extra,
        )

    def _filter(self, known: set[str]) -> dict[str, Any]:
        return {k: v for k, v in self._common.items() if k in known}

    def _import_class(self, module: str, class_name: str) -> Any:
        import importlib

        mod = importlib.import_module(module)
        return getattr(mod, class_name)

    def create(self, step_name: str) -> Any:
        """Create a step instance by name."""
        spec = STEP_SPECS[step_name]
        cls = self._import_class(spec.module, spec.class_name)
        return cls(**self._filter(spec.known))

    def create_read_step(self) -> Any:
        return self.create('read')

    def create_delta_step(self) -> Any:
        return self.create('delta')

    def create_chunk_step(self) -> Any:
        return self.create('chunk')

    def create_embed_step(self) -> Any:
        return self.create('embed')

    def create_save_step(self) -> Any:
        return self.create('save')

    def create_cascade_step(self) -> Any:
        return self.create('cascade')

    def create_cache_step(self) -> Any:
        return self.create('cache')

    def create_metric_step(self) -> Any:
        return self.create('metric')

    def create_delta_tracking_check_step(self) -> Any:
        return self.create('delta_tracking_check')

    def create_processing_step(self) -> Any:
        return self.create('processing')


__all__ = ['StepFactory']
