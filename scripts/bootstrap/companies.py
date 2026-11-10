"""Company creation and partition management for test bootstrap."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import text

from finsight.adapters.partitions.partition_manager import (
    DEFAULT_PARTITION_TABLES,
    PartitionManager,
)
from finsight.composition import create_onboarding_use_case
from finsight.core.types import CompanyId

logger = logging.getLogger('bootstrap_test_data.companies')

# Fixture tenants: slug -> display name.
TEST_COMPANIES = {
    'company-a': 'Company A',
    'company-b': 'Company B',
}


def deterministic_company_id(request_key: str) -> uuid.UUID:
    """Company id the onboarding use case derives from a ``request_key``.

    Mirrors ``CreateCompany._company_id_for`` so the bootstrap can check for
    an existing tenant before onboarding (idempotent re-runs).
    """
    return uuid.uuid5(uuid.NAMESPACE_URL, f'finsight:onboarding:{request_key}')


async def find_company_by_id(session: Any, company_id: uuid.UUID) -> uuid.UUID | None:
    """Return the id when a company with this id already exists."""
    result = await session.execute(
        text('SELECT id FROM companies WHERE id = :company_id'),
        {'company_id': str(company_id)},
    )
    row = result.first()
    return uuid.UUID(str(row.id)) if row else None


async def ensure_companies(config: Any, session: Any) -> dict[str, uuid.UUID]:
    """Create test companies via the public onboarding API (idempotent)."""
    onboarding = create_onboarding_use_case(config=config, session=session)
    company_ids = {}

    for company_slug, name in TEST_COMPANIES.items():
        # A fixed request_key makes the onboarding company id deterministic,
        # so repeated runs reuse the same tenant instead of piling up new ones.
        request_key = f'bootstrap-{company_slug}'
        company_id = deterministic_company_id(request_key)

        existing_id = await find_company_by_id(session, company_id)
        if existing_id is not None:
            logger.info('Company %s already exists with ID %s, reusing', name, existing_id)
            company_ids[company_slug] = existing_id
            continue

        logger.info('Creating company: %s (%s)', name, company_slug)
        result = await onboarding.execute(
            name=name,
            request_key=request_key,
            region='us-east-1',
            admin_email=f'admin@{company_slug}.test',
        )
        created_id = uuid.UUID(str(result.company_id))
        logger.info('Created company: %s (%s) with ID %s', name, company_slug, created_id)

        company_ids[company_slug] = created_id

    return company_ids


async def ensure_partitions(config: Any, session: Any, company_ids: dict[str, uuid.UUID]) -> None:
    """Ensure partitions exist for all companies using the public partition manager.

    ``DEFAULT_PARTITION_TABLES`` is the canonical partitioned-table list the
    ``PartitionManager`` itself uses, so no table list is duplicated here.
    """
    partition_manager = PartitionManager(session_or_engine=session)

    for company_id in company_ids.values():
        logger.info('Creating partitions for company %s...', company_id)
        for table_name in DEFAULT_PARTITION_TABLES:
            await partition_manager.ensure_partition_exists(CompanyId(str(company_id)), table_name)
            logger.debug('  Partition for %s ensured', table_name)
