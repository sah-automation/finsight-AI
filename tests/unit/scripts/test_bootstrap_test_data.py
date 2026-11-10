"""Unit tests for the bootstrap_test_data script."""

from __future__ import annotations

import hashlib

# Import the functions to test
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'scripts'))

from bootstrap_test_data import (
    compute_file_hash,
    get_s3_key,
    guess_content_type,
)


class TestBootstrapHelpers:
    """Test helper functions."""

    def test_compute_file_hash(self, tmp_path: Path) -> None:
        """Test file hash computation."""
        test_file = tmp_path / 'test.txt'
        test_content = b'Hello, World!'
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        actual_hash = compute_file_hash(test_file)

        assert actual_hash == expected_hash

    def test_get_s3_key(self) -> None:
        """Test S3 key generation."""
        key = get_s3_key(
            company_id='company-123',
            document_id='doc-456',
            version_id='ver-789',
            filename='test.pdf',
        )

        assert key == 'company-123/documents/doc-456/versions/ver-789/test.pdf'

    def test_get_s3_key_handles_slashes_in_filename(self) -> None:
        """Test S3 key generation handles filename with path separators."""
        key = get_s3_key(
            company_id='company-123',
            document_id='doc-456',
            version_id='ver-789',
            filename='path/to/test.pdf',
        )

        # Should only use the basename
        assert key == 'company-123/documents/doc-456/versions/ver-789/test.pdf'

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
