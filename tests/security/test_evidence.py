"""Security tests for citation and evidence gates."""

from __future__ import annotations

import pytest

from finsight.core.types import Citation
from finsight.domain.services.evidence import answer_has_evidence, is_citation_valid

pytestmark = pytest.mark.security


class TestCitationEvidence:
    """An answer without a valid source citation must not pass the gate."""

    def test_citation_requires_a_document_id(self) -> None:
        with pytest.raises(TypeError):
            Citation()

    def test_empty_citation_list_has_no_evidence(self) -> None:
        assert not answer_has_evidence([])

    def test_blank_document_id_is_not_valid(self) -> None:
        assert not is_citation_valid(Citation(document_id=''))

    def test_whitespace_document_id_is_not_valid(self) -> None:
        assert not is_citation_valid(Citation(document_id='   '))

    def test_page_number_must_be_positive(self) -> None:
        assert not is_citation_valid(Citation(document_id='doc-1', page_number=0))
        assert not is_citation_valid(Citation(document_id='doc-1', page_number=-1))

    def test_valid_citation_has_evidence(self) -> None:
        citation = Citation(document_id='doc-1', page_number=2)

        assert is_citation_valid(citation)
        assert answer_has_evidence([citation])

    def test_citation_without_page_number_is_valid(self) -> None:
        citation = Citation(document_id='doc-1')

        assert is_citation_valid(citation)
        assert answer_has_evidence([citation])

    def test_one_invalid_citation_invalidates_the_answer(self) -> None:
        valid = Citation(document_id='doc-1', page_number=1)
        invalid = Citation(document_id='', page_number=1)

        assert not answer_has_evidence([valid, invalid])
