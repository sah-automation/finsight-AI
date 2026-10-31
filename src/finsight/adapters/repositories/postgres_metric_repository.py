"""Aurora/Postgres metric repository implementing the MetricRepository port.

Every statement names ``company_id`` first so the partitioned table is pruned to
one tenant partition and RLS applies as a second lock. Read filters are additive:
period, category, document and document version can be combined in one call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.domain.ports.metric_repository import MetricRepository as MetricRepositoryPort

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.domain.entities.metric import Metric


class PostgresMetricRepository(MetricRepositoryPort, BaseRepository):
    """Read structured finance metrics with tenant-scoped filters.

    When constructed without a session the adapter keeps state in memory for
    contract tests and the pilot composition path. A wired session always uses
    SQL and RLS.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, Metric]] = {}

    async def upsert_metric(self, company_id: Any, *args: Any, **kwargs: Any) -> Metric:
        from ._postgres_metric_repository_upsert_metric import _upsert_metric as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def upsert_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Metric]:
        from ._postgres_metric_repository_upsert_metrics import _upsert_metrics as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def get_metric(self, company_id: Any, *args: Any, **kwargs: Any) -> Metric | None:
        from ._postgres_metric_repository_get_metric import _get_metric as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Metric]:
        from ._postgres_metric_repository_list_metrics import _list_metrics as _adapter_method

        return await _adapter_method(self, company_id, *args, **kwargs)

    def _upsert_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Metric]:
        from ._postgres_metric_repository__upsert_memory import _upsert_memory as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)

    def _list_memory(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Metric]:
        from ._postgres_metric_repository__list_memory import _list_memory as _adapter_method

        return _adapter_method(self, company_id, *args, **kwargs)


# Naming variants used across the project.

# Compatibility aliases (preserved for external imports)
AuroraMetricRepository = PostgresMetricRepository
MetricRepositoryAdapter = PostgresMetricRepository
PostgresMetricRepo = PostgresMetricRepository
RLSMetricRepository = PostgresMetricRepository
