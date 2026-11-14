"""Contract tests for the MetricRepository port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.repositories.postgres_metric_repository import PostgresMetricRepository
from finsight.core.types import CompanyId, DocumentId
from finsight.domain.entities.metric import Metric

if TYPE_CHECKING:
    from finsight.domain.ports import MetricRepository

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
DOCUMENT = DocumentId('document-a')
OTHER_DOCUMENT = DocumentId('document-b')


def _metric(
    name: str,
    value: float,
    *,
    company: CompanyId = COMPANY,
    period: str = '2025-Q1',
    category: str = 'revenue',
    document_id: DocumentId = DOCUMENT,
    version_id: str = 'version-1',
) -> Metric:
    return Metric(
        company_id=company,
        name=name,
        value=value,
        unit='USD',
        currency='USD',
        period=period,
        category=category,
        document_id=document_id,
        version_id=version_id,
        source_page=1,
    )


@pytest.fixture
def repository() -> MetricRepository:
    return PostgresMetricRepository()


async def _seed(repository: MetricRepository) -> None:
    await repository.upsert_metrics(  # type: ignore[attr-defined]
        COMPANY,
        [
            _metric('revenue', 100.0),
            _metric('revenue', 120.0, period='2025-Q2'),
            _metric('cost', 40.0, category='cost'),
            _metric('revenue', 90.0, document_id=OTHER_DOCUMENT, version_id='version-2'),
        ],
    )
    await repository.upsert_metrics(  # type: ignore[attr-defined]
        OTHER_COMPANY,
        [_metric('revenue', 900.0, company=OTHER_COMPANY)],
    )


class TestMetricRepositoryContract:
    async def test_company_isolation(self, repository: MetricRepository) -> None:
        await _seed(repository)

        metrics = await repository.list_metrics(COMPANY)

        assert len(metrics) == 4
        assert all(metric.company_id == str(COMPANY) for metric in metrics)
        assert all(metric.value != 900.0 for metric in metrics)

    async def test_filters_by_period(self, repository: MetricRepository) -> None:
        await _seed(repository)

        metrics = await repository.list_metrics(COMPANY, period='2025-Q2')

        assert [metric.name for metric in metrics] == ['revenue']
        assert metrics[0].value == 120.0

    async def test_filters_by_category(self, repository: MetricRepository) -> None:
        await _seed(repository)

        costs = await repository.list_metrics(COMPANY, category='cost')
        revenue_or_cost = await repository.list_metrics(COMPANY, categories=['revenue', 'cost'])

        assert [metric.name for metric in costs] == ['cost']
        assert len(revenue_or_cost) == 4

    async def test_filters_by_document_and_version(self, repository: MetricRepository) -> None:
        await _seed(repository)

        by_document = await repository.list_metrics(COMPANY, document_id=str(OTHER_DOCUMENT))
        by_version = await repository.list_metrics(COMPANY, version_id='version-2')
        by_document_list = await repository.list_metrics(
            COMPANY, document_ids=[str(OTHER_DOCUMENT)]
        )

        assert [metric.value for metric in by_document] == [90.0]
        assert [metric.value for metric in by_version] == [90.0]
        assert [metric.value for metric in by_document_list] == [90.0]

    async def test_combines_all_scope_filters(self, repository: MetricRepository) -> None:
        await _seed(repository)

        metrics = await repository.list_metrics(
            COMPANY,
            period='2025-Q1',
            category='revenue',
            document_id=str(DOCUMENT),
            version_id='version-1',
        )

        assert [metric.value for metric in metrics] == [100.0]

    async def test_get_metric_is_tenant_scoped(self, repository: MetricRepository) -> None:
        await _seed(repository)
        metric = (await repository.list_metrics(COMPANY, period='2025-Q1'))[0]

        assert await repository.get_metric(COMPANY, metric.metric_id) is not None
        assert await repository.get_metric(OTHER_COMPANY, metric.metric_id) is None

    async def test_upsert_is_idempotent(self, repository: MetricRepository) -> None:
        await _seed(repository)
        metric = (await repository.list_metrics(COMPANY, period='2025-Q2'))[0]
        updated = _metric('revenue', 125.0, period='2025-Q2')
        updated.metric_id = metric.metric_id

        await repository.upsert_metrics(COMPANY, [updated])

        stored = await repository.list_metrics(COMPANY, period='2025-Q2')
        assert len(stored) == 1
        assert stored[0].value == 125.0

    async def test_upsert_rejects_another_tenant(self, repository: MetricRepository) -> None:
        foreign = _metric('revenue', 900.0, company=OTHER_COMPANY)

        with pytest.raises(ValueError):
            await repository.upsert_metrics(COMPANY, [foreign])  # type: ignore[attr-defined]

    async def test_alias_methods_delegate_to_list(self, repository: MetricRepository) -> None:
        await _seed(repository)

        assert len(await repository.get_metrics(COMPANY)) == 4
        assert len(await repository.find_metrics(COMPANY, category='cost')) == 1
        assert len(await repository.search_metrics(COMPANY, period='2025-Q2')) == 1

    async def test_requires_company_id(self, repository: MetricRepository) -> None:
        with pytest.raises((TypeError, ValueError)):
            await repository.list_metrics(None)  # type: ignore[arg-type]
