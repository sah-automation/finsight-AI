"""Unit tests for the bootstrap script helper modules."""

from __future__ import annotations

import hashlib
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / 'bootstrap'))

from bootstrap.companies import deterministic_company_id
from bootstrap.documents import compute_file_hash, find_existing_version, load_fixture_manifest
from bootstrap.s3 import guess_content_type


class TestDeterministicCompanyId:
    """The onboarding request_key-derived company id must be stable."""

    def test_same_request_key_gives_same_id(self) -> None:
        first = deterministic_company_id('bootstrap-company-a')
        second = deterministic_company_id('bootstrap-company-a')
        assert first == second

    def test_different_request_keys_give_different_ids(self) -> None:
        assert deterministic_company_id('bootstrap-company-a') != deterministic_company_id(
            'bootstrap-company-b'
        )

    def test_is_uuid5(self) -> None:
        company_id = deterministic_company_id('bootstrap-company-a')
        assert company_id.version == 5


class TestFindExistingVersion:
    """S3 key reconstruction for already-ingested fixtures."""

    @staticmethod
    async def _find(row: Any) -> dict[str, Any] | None:
        class _Result:
            def first(self) -> Any:
                return row

        class _Session:
            async def execute(self, *_args: Any, **_kwargs: Any) -> _Result:
                return _Result()

        company_id = uuid.UUID('11111111-2222-3333-4444-555555555555')
        return await find_existing_version(_Session(), company_id, 'abc123')  # type: ignore[arg-type]

    async def test_returns_none_when_no_row(self) -> None:
        assert await self._find(None) is None

    async def test_rebuilds_key_from_canonical_format(self) -> None:
        version_id = 'aaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        row = type(
            'Row',
            (),
            {
                'document_id': '99999999-8888-7777-6666-555555555555',
                'version_id': version_id,
                'filename': 'report.pdf',
            },
        )()
        found = await self._find(row)
        assert found is not None
        company_id = '11111111-2222-3333-4444-555555555555'
        assert found['s3_key'] == (
            f'{company_id}/documents/99999999-8888-7777-6666-555555555555'
            f'/versions/{version_id}/report.pdf'
        )
        assert found['version_id'] == version_id


class TestLoadFixtureManifest:
    """The real manifest must map onto upload-API-safe values."""

    def test_fixtures_have_valid_categories(self) -> None:
        valid = {
            'invoice',
            'bank_statement',
            'financial_statement',
            'budget',
            'contract',
            'board_report',
        }
        for fixture in load_fixture_manifest():
            assert fixture['category'] in valid, fixture['path']

    def test_fixtures_have_quarter_periods(self) -> None:
        for fixture in load_fixture_manifest():
            year, quarter = fixture['period'].split('-')
            assert year.isdigit(), fixture['path']
            assert quarter in {'Q1', 'Q2', 'Q3', 'Q4'}, fixture['path']

    def test_fixtures_have_upload_statuses(self) -> None:
        for fixture in load_fixture_manifest():
            assert fixture['status'] in {'final', 'draft'}, fixture['path']


class TestComputeFileHash:
    def test_compute_file_hash(self, tmp_path: Path) -> None:
        """Test file hash computation."""
        test_file = tmp_path / 'test.txt'
        test_content = b'Hello, World!'
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        actual_hash = compute_file_hash(test_file)

        assert actual_hash == expected_hash


class TestGuessContentType:
    def test_guess_content_type(self) -> None:
        """Test content type guessing."""
        assert guess_content_type('pdf') == 'application/pdf'
        assert guess_content_type('scan') == 'application/pdf'
        assert guess_content_type('image') == 'image/png'
        assert (
            guess_content_type('xlsx')
            == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert guess_content_type('csv') == 'text/csv'
        assert (
            guess_content_type('docx')
            == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        assert guess_content_type('unknown') == 'application/octet-stream'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
