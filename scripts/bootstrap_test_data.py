#!/usr/bin/env python3
"""Bootstrap test environment with document versions and S3 fixture uploads.

This script:
1. Creates companies, documents, and document versions in PostgreSQL for test fixtures
2. Uploads fixture files to LocalStack S3 (test-docs bucket)
3. Purges stale messages from SQS queues
4. Is idempotent (safe to run multiple times)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from finsight.adapters.partitions.partition_manager import PartitionManager
from finsight.adapters.repositories import PostgresDocumentRepository
from finsight.adapters.repositories.company_repository import CompanyRepository
from finsight.composition import build_container
from finsight.core.config import load_config
from finsight.core.types import CompanyId, DocumentId

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('bootstrap_test_data')


# Fixture mapping based on manifest.yaml
FIXTURE_DOCUMENTS = [
    {
        'path': 'pdf__company-a__2025-FY__annual-report.pdf',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'annual_report',
        'period': 'FY2025',
        'status': 'committed',  # document version state
        'document_status': 'committed',  # document status
        'document_type': 'annual_report',
        'file_type': 'pdf',
    },
    {
        'path': 'pdf__company-a__2026-Q3__interim-report.pdf',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'interim_report',
        'period': 'Q3 FY2026',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'interim_report',
        'file_type': 'pdf',
    },
    {
        'path': 'pdf__company-a__2025-FY__annual-report-draft.pdf',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'draft',
        'period': 'FY2025',
        'status': 'received',
        'document_status': 'received',
        'document_type': 'annual_report',
        'file_type': 'pdf',
    },
    {
        'path': 'pdf__company-b__2026-FY__annual-report.pdf',
        'company': 'company-b',
        'company_name': 'Company B',
        'company_slug': 'company-b',
        'category': 'annual_report',
        'period': 'FY2026',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'annual_report',
        'file_type': 'pdf',
    },
    {
        'path': 'scan__company-a__2026-Q3__bank-statement.pdf',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'bank_statement',
        'period': 'Q3 FY2026',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'bank_statement',
        'file_type': 'scan',
    },
    {
        'path': 'image__company-a__2025-FY__vendor-invoice.png',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'invoice',
        'period': 'FY2025',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'invoice',
        'file_type': 'image',
    },
    {
        'path': 'xlsx__company-a__2025-FY__budget-vs-actual.xlsx',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'budget',
        'period': 'FY2025',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'budget',
        'file_type': 'xlsx',
    },
    {
        'path': 'csv__company-a__2025-FY__q4-ledger.csv',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'ledger',
        'period': 'Q4 FY2025',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'ledger',
        'file_type': 'csv',
    },
    {
        'path': 'docx__company-a__2025-FY__board-notes.docx',
        'company': 'company-a',
        'company_name': 'Company A',
        'company_slug': 'company-a',
        'category': 'board_notes',
        'period': 'FY2025',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'board_notes',
        'file_type': 'docx',
    },
    {
        'path': 'csv__company-b__2026-FY__revenue-by-region.csv',
        'company': 'company-b',
        'company_name': 'Company B',
        'company_slug': 'company-b',
        'category': 'revenue_by_region',
        'period': 'FY2026',
        'status': 'committed',
        'document_status': 'committed',
        'document_type': 'revenue_by_region',
        'file_type': 'csv',
    },
]


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with filepath.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_s3_key(company_id: str, document_id: str, version_id: str, filename: str) -> str:
    """Generate S3 key using the same format as the upload flow."""
    # Only use the basename to prevent path traversal
    basename = Path(filename).name
    return f'{company_id}/documents/{document_id}/versions/{version_id}/{basename}'


def guess_content_type(file_type: str) -> str:
    """Guess MIME content type from file type."""
    mapping = {
        'pdf': 'application/pdf',
        'scan': 'application/pdf',
        'image': 'image/png',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'csv': 'text/csv',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    return mapping.get(file_type, 'application/octet-stream')


async def create_companies(session: AsyncSession, config: Any) -> dict[str, uuid.UUID]:
    """Create test companies in the database and ensure partitions exist (idempotent)."""
    company_repo = CompanyRepository(session=session)
    partition_manager = PartitionManager(session_or_engine=session)
    company_ids = {}

    # Unique companies from fixtures
    companies = {
        'company-a': ('Company A', 'company-a'),
        'company-b': ('Company B', 'company-b'),
    }

    for company_slug, (name, slug) in companies.items():
        company_id = uuid.uuid4()
        logger.info('Creating company: %s (%s) with ID %s', name, slug, company_id)
        try:
            await company_repo.create_company(
                company_id=CompanyId(str(company_id)),
                name=name,
                slug=slug,
            )
        except IntegrityError as e:
            if 'companies_slug_key' in str(e):
                # Company with this slug already exists, fetch it
                logger.info('Company %s already exists, fetching existing record', slug)
                result = await session.execute(
                    text('SELECT id FROM companies WHERE slug = :slug'),
                    {'slug': slug},
                )
                row = result.first()
                if row:
                    company_id = uuid.UUID(str(row.id))
                    logger.info(
                        'Found existing company: %s (%s) with ID %s', name, slug, company_id
                    )
                else:
                    raise
            else:
                raise

        company_ids[company_slug] = company_id

        # Ensure partitions exist for this company
        logger.info('  Creating partitions for company %s...', company_id)
        for table_name in [
            'documents',
            'document_versions',
            'document_chunks',
            'document_tables',
            'metrics',
            'answers',
            'audit_logs',
            'jobs',
        ]:
            await partition_manager.ensure_partition_exists(CompanyId(str(company_id)), table_name)
            logger.debug('    Partition for %s ensured', table_name)

    return company_ids


async def create_documents_and_versions(
    session: AsyncSession,
    config: Any,
    company_ids: dict[str, uuid.UUID],
    fixtures_dir: Path,
) -> list[dict[str, Any]]:
    """Create documents and document versions for all fixtures."""
    doc_repo = PostgresDocumentRepository(session=session)
    created_records = []

    for fixture in FIXTURE_DOCUMENTS:
        company_slug = fixture['company']
        company_id = company_ids[company_slug]
        filepath = fixtures_dir / fixture['path']

        if not filepath.exists():
            logger.warning('Fixture file not found: %s', filepath)
            continue

        file_hash = compute_file_hash(filepath)
        file_size = filepath.stat().st_size

        # Create document
        document_id = uuid.uuid4()
        logger.info(
            'Creating document: %s (company=%s, doc_id=%s, hash=%s...)',
            fixture['path'],
            company_slug,
            document_id,
            file_hash[:16],
        )

        await doc_repo.create_document(
            company_id=CompanyId(str(company_id)),
            id=str(document_id),
            filename=fixture['path'],
            content_type=guess_content_type(fixture['file_type']),
            storage_key='',  # Will be set after S3 upload
            checksum_sha256=file_hash,
            document_type=fixture['document_type'],
            period=fixture['period'],
            category=fixture['category'],
            status=fixture.get('document_status', fixture['status']),
            page_count=None,
        )

        # Create document version (version 1)
        version_id = uuid.uuid4()
        version_number = 1

        logger.info('Creating document version: %s (version=%s)', version_id, version_number)

        await doc_repo.create_document_version(
            company_id=CompanyId(str(company_id)),
            document_id=DocumentId(str(document_id)),
            version=version_number,
            state=fixture['status'],
            file_hash=file_hash,
            filename=fixture['path'],
            category=fixture['category'],
            review_scope=None,
        )

        # Generate S3 key
        s3_key = get_s3_key(
            company_id=str(company_id),
            document_id=str(document_id),
            version_id=str(version_id),
            filename=fixture['path'],
        )

        created_records.append(
            {
                'fixture': fixture,
                'company_id': company_id,
                'document_id': document_id,
                'version_id': version_id,
                'version_number': version_number,
                'file_hash': file_hash,
                'file_size': file_size,
                'filepath': filepath,
                's3_key': s3_key,
            }
        )

    return created_records


async def upload_to_s3(
    config: Any,
    records: list[dict[str, Any]],
) -> None:
    """Upload fixture files to LocalStack S3."""
    storage_config = config.storage
    bucket = storage_config.documents_bucket
    region = storage_config.region
    endpoint_url = 'http://localhost:4566'

    logger.info('Uploading to S3 bucket: %s at %s', bucket, endpoint_url)

    # Create S3 client for LocalStack
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id='test',
        aws_secret_access_key='test',  # pragma: allowlist secret
    )

    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=bucket)
    except boto3.exceptions.Boto3Error:
        s3_client.create_bucket(Bucket=bucket)
        logger.info('Created bucket: %s', bucket)

    for record in records:
        filepath = record['filepath']
        s3_key = record['s3_key']
        file_hash = record['file_hash']

        logger.info('Uploading %s to s3://%s/%s', filepath.name, bucket, s3_key)

        # Check if object already exists with same hash
        try:
            head = s3_client.head_object(Bucket=bucket, Key=s3_key)
            existing_etag = head.get('ETag', '').strip('"')
            if existing_etag == file_hash:
                logger.info('  Object already exists with same hash, skipping')
                continue
            logger.info('  Object exists with different hash, overwriting')
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise
            # Object doesn't exist, will upload

        # Upload file
        with filepath.open('rb') as f:
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=f,
                ContentType=guess_content_type(record['fixture']['file_type']),
                Metadata={
                    'file-hash': file_hash,
                    'company-id': str(record['company_id']),
                    'document-id': str(record['document_id']),
                    'version-id': str(record['version_id']),
                },
            )

        logger.info('  Uploaded successfully')

    logger.info('S3 upload complete')


async def purge_sqs_queues(config: Any) -> None:
    """Purge all SQS queues used by the ingestion worker."""
    queue_config = config.queue
    region = 'us-east-1'
    endpoint_url = 'http://localhost:4566'

    queues = [
        queue_config.ingestion_queue_url,
        queue_config.reprocessing_queue_url,
        queue_config.reports_queue_url,
        queue_config.dead_letter_queue_url,
    ]

    logger.info('Purging SQS queues...')

    sqs_client = boto3.client(
        'sqs',
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id='test',
        aws_secret_access_key='test',  # pragma: allowlist secret
    )

    for queue_url in queues:
        try:
            sqs_client.purge_queue(QueueUrl=queue_url)
            logger.info('  Purged: %s', queue_url)
        except sqs_client.exceptions.QueueDoesNotExist:
            logger.warning('  Queue does not exist: %s', queue_url)
        except boto3.exceptions.Boto3Error:
            logger.exception('  Failed to purge %s', queue_url)

    logger.info('SQS purge complete')


async def main() -> int:
    """Main bootstrap function."""
    logger.info('Starting test environment bootstrap...')

    # Load test configuration
    os.environ['ENVIRONMENT'] = 'test'
    config = load_config('test')

    # Build container to get database session
    container = build_container(config=config, mode='standard')
    session = container.session

    if session is None:
        logger.error('Failed to create database session')
        return 1

    fixtures_dir = Path(__file__).parent.parent / 'tests' / 'fixtures' / 'documents'

    try:
        # Step 1: Create companies
        logger.info('Step 1: Creating companies...')
        company_ids = await create_companies(session, config)

        # Step 2: Create documents and document versions
        logger.info('Step 2: Creating documents and document versions...')
        records = await create_documents_and_versions(session, config, company_ids, fixtures_dir)

        # Step 3: Upload files to S3
        logger.info('Step 3: Uploading fixture files to S3...')
        await upload_to_s3(config, records)

        # Step 4: Purge SQS queues
        logger.info('Step 4: Purging SQS queues...')
        await purge_sqs_queues(config)
    except Exception:
        logger.exception('Bootstrap failed')
        return 1
    else:
        logger.info('Bootstrap complete!')
        logger.info('Created %s companies', len(company_ids))
        logger.info('Created %s document versions', len(records))
        logger.info('Uploaded %s files to S3', len(records))
        return 0
    finally:
        if hasattr(session, 'close'):
            await session.close()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
