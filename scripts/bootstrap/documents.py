"""Fixture loading and document creation for test bootstrap."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from sqlalchemy import text

from bootstrap.s3 import upload_fixtures_to_s3
from finsight.composition import create_upload_use_case

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger('bootstrap_test_data.fixtures')


def load_fixture_manifest() -> list[dict[str, Any]]:
    """Load fixture documents from manifest.yaml."""
    manifest_path = (
        Path(__file__).parent.parent.parent / 'tests' / 'fixtures' / 'documents' / 'manifest.yaml'
    )
    with manifest_path.open('r', encoding='utf-8') as f:
        manifest = yaml.safe_load(f)

    # Map manifest categories to valid DocumentCategory enum values
    category_map = {
        'annual_report': 'financial_statement',
        'interim_report': 'financial_statement',
        'draft': 'financial_statement',  # draft is a status, not a category
        'bank_statement': 'bank_statement',
        'invoice': 'invoice',
        'budget': 'budget',
        'ledger': 'financial_statement',
        'board_notes': 'board_report',
        'revenue_by_region': 'financial_statement',
    }

    # Map manifest periods to YYYY-QX or YYYY-MM format expected by upload API
    def map_period(period: str) -> str:
        if period.startswith('FY'):
            year = period[2:]
            return f'{year}-Q4'
        if period.startswith('Q'):
            # Q3 FY2026 -> 2026-Q3
            parts = period.split()
            quarter = parts[0]  # Q3
            year = parts[1][2:]  # FY2026 -> 2026
            return f'{year}-{quarter}'
        return period

    fixtures = []
    for doc in manifest['documents']:
        # Map manifest status to upload API status (draft/final)
        upload_status = 'final' if doc['status'] == 'final' else 'draft'
        # Map category to valid DocumentCategory
        doc_category = category_map.get(doc['category'], 'financial_statement')
        # Map period to expected format
        upload_period = map_period(doc['period'])
        fixtures.append(
            {
                'path': doc['path'],
                'company': doc['company'],
                'category': doc_category,
                'period': upload_period,
                'status': upload_status,
                'document_type': doc.get('document_type', doc['category']),
                'file_type': doc['file_type'],
            }
        )
    return fixtures


FIXTURE_DOCUMENTS = load_fixture_manifest()


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with filepath.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


async def find_existing_version(
    session: Any, company_id: uuid.UUID, file_hash: str
) -> dict[str, Any] | None:
    """Return an existing version row for ``(company_id, file_hash)``, if any.

    Makes the bootstrap idempotent: fixtures already ingested by a previous
    run are reused instead of creating duplicate document versions. The S3
    key is rebuilt from the canonical upload key format because the
    ``documents.storage_key`` column is not populated by the upload flow.
    """
    result = await session.execute(
        text(
            'SELECT dv.id AS version_id, dv.document_id AS document_id, '
            'dv.filename AS filename '
            'FROM document_versions dv '
            'WHERE dv.company_id = :company_id AND dv.file_hash = :file_hash '
            'LIMIT 1'
        ),
        {'company_id': str(company_id), 'file_hash': file_hash},
    )
    row = result.first()
    if row is None:
        return None
    document_id = str(row.document_id)
    version_id = str(row.version_id)
    filename = str(row.filename)
    s3_key = f'{company_id}/documents/{document_id}/versions/{version_id}/{filename}'
    return {
        'document_id': document_id,
        'version_id': version_id,
        's3_key': s3_key,
    }


async def create_documents_and_upload(
    config: Any,
    session: Any,
    company_ids: dict[str, uuid.UUID],
    fixtures_dir: Path,
) -> list[dict[str, Any]]:
    """Create documents/versions via upload API and upload files to S3."""
    upload_use_case = create_upload_use_case(config=config, session=session)

    # First create all documents/versions via upload API
    created_records = []
    for fixture in FIXTURE_DOCUMENTS:
        company_slug = fixture['company']
        company_id = company_ids[company_slug]
        filepath = fixtures_dir / fixture['path']

        if not filepath.exists():
            logger.warning('Fixture file not found: %s', filepath)
            continue

        file_hash = compute_file_hash(filepath)

        # Idempotency: reuse a version ingested by a previous bootstrap run.
        existing = await find_existing_version(session, company_id, file_hash)
        if existing is not None:
            logger.info(
                'Document for %s already ingested (version=%s), reusing',
                fixture['path'],
                existing['version_id'],
            )
            created_records.append(
                {
                    'fixture': fixture,
                    'company_id': company_id,
                    'document_id': existing['document_id'],
                    'version_id': existing['version_id'],
                    's3_key': existing['s3_key'],
                    'file_hash': file_hash,
                    'file_size': filepath.stat().st_size,
                    'filepath': filepath,
                }
            )
            continue

        logger.info(
            'Creating document: %s (company=%s, hash=%s...)',
            fixture['path'],
            company_slug,
            file_hash[:16],
        )

        # Use the public upload API to create document and version
        upload_result = await upload_use_case.run(
            company_id=str(company_id),
            document_category=fixture['category'],
            period=fixture['period'],
            status=fixture['status'],
            upload_type='new',
            file=fixture['path'],
            file_hash=file_hash,
        )

        document_id = upload_result.document_id
        version_id = upload_result.version_id
        s3_key = upload_result.key or upload_result.storage_key or upload_result.s3_key

        if not s3_key:
            logger.error('No S3 key returned from upload API for %s', fixture['path'])
            continue

        logger.info(
            'Created document_id=%s version_id=%s, S3 key: %s',
            document_id,
            version_id,
            s3_key,
        )

        created_records.append(
            {
                'fixture': fixture,
                'company_id': company_id,
                'document_id': document_id,
                'version_id': version_id,
                's3_key': s3_key,
                'file_hash': file_hash,
                'file_size': filepath.stat().st_size,
                'filepath': filepath,
            }
        )

    # Then upload all files to S3
    await upload_fixtures_to_s3(config, created_records)

    return created_records
