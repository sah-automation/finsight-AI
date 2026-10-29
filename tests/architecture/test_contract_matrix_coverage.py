"""Meta-tests for the contract-test matrix.

Ensures every port promoted to the matrix has a shared, non-placeholder
contract suite. Issue #75.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CONTRACT_DIR = Path(__file__).parent.parent / 'contract'

# Port name -> contract test file. Keep this in sync with tests/contract/README.md.
PORT_CONTRACT_FILES = {
    'AnswerCache': 'test_answer_cache_contract.py',
    'ChangeEventPublisher': 'test_change_event_publisher_contract.py',
    'ChunkRepository': 'test_chunk_repository_contract.py',
    'DocumentRepository': 'test_document_repository_lifecycle.py',
    'VectorWrite': 'test_vector_write_contract.py',
    'JobProgressPort': 'test_job_progress_port_contract.py',
    'VirusScanner': 'test_virus_scanner_contract.py',
    'DocumentReader': 'test_document_reader_contract.py',
}

# Primary adapter exercised by each shared suite.
PORT_ADAPTER_CLASSES = {
    'AnswerCache': 'AnswerCache',
    'ChangeEventPublisher': 'ChangeEventPublisher',
    'ChunkRepository': 'PostgresChunkRepository',
    'DocumentRepository': 'PostgresDocumentRepository',
    'VectorWrite': 'AuroraPgVectorWrite',
    'JobProgressPort': 'JobProgress',
    'VirusScanner': 'VirusScanner',
    'DocumentReader': 'PdfPlumberReader',
}


@pytest.mark.architecture
class TestContractMatrixCoverage:
    def test_every_matrix_port_has_a_contract_file(self) -> None:
        missing = [
            f'{port}: missing {filename}'
            for port, filename in PORT_CONTRACT_FILES.items()
            if not (CONTRACT_DIR / filename).exists()
        ]
        assert not missing, 'Contract matrix gaps:\n' + '\n'.join(f'  {gap}' for gap in missing)

    def test_contract_files_reference_their_adapter(self) -> None:
        stale = []
        for port, filename in PORT_CONTRACT_FILES.items():
            path = CONTRACT_DIR / filename
            if not path.exists():
                continue
            text = path.read_text()
            adapter_name = PORT_ADAPTER_CLASSES[port]
            if adapter_name not in text:
                stale.append(f'{port}: {filename} does not reference {adapter_name}')
        assert not stale, 'Contract suites missing their adapter:\n' + '\n'.join(
            f'  {item}' for item in stale
        )

    def test_no_tracked_placeholder_remains(self) -> None:
        assert not (CONTRACT_DIR / 'test_contract_pending.py').exists()
