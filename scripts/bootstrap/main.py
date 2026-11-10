"""Main bootstrap orchestrator for test environment setup."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from bootstrap.companies import ensure_companies, ensure_partitions
from bootstrap.documents import create_documents_and_upload
from finsight.composition import build_container
from finsight.core.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('bootstrap_test_data')


async def main() -> int:
    """Main bootstrap function."""
    logger.info('Starting test environment bootstrap...')

    # Load .env so AWS_ENDPOINT_URL/test credentials reach the config seam.
    load_dotenv()

    # Load test configuration (ENVIRONMENT=test should be set externally)
    config = load_config('test')

    # Build container to get database session
    container = build_container(config=config, mode='standard')
    session = container.session

    if session is None:
        logger.error('Failed to create database session')
        return 1

    fixtures_dir = Path(__file__).parent.parent.parent / 'tests' / 'fixtures' / 'documents'

    try:
        # Step 1: Create companies
        logger.info('Step 1: Creating companies...')
        company_ids = await ensure_companies(config, session)

        # Step 2: Ensure partitions
        logger.info('Step 2: Ensuring partitions...')
        await ensure_partitions(config, session, company_ids)

        # Step 3: Create documents/versions and upload to S3
        logger.info('Step 3: Creating documents and uploading to S3...')
        records = await create_documents_and_upload(config, session, company_ids, fixtures_dir)

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
