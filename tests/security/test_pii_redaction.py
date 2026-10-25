"""Security tests for PII handling and log redaction."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from finsight.core.logging import TraceFormatter
from finsight.core.logging.redaction import REDACTED, redact_sensitive_fields
from tests.support.ast_inspection import find_sensitive_log_calls

SRC_ROOT = Path(__file__).parents[2] / 'src' / 'finsight'

pytestmark = pytest.mark.security


class TestFieldRedaction:
    """Sensitive field names must never keep their values."""

    def test_sensitive_fields_are_redacted(self) -> None:
        fields = {
            'question': 'What is revenue?',
            'answer_text': 'Revenue is 10',
            'chunk_text': 'raw chunk',
            'password': '',
            'token': '',
        }

        redacted = redact_sensitive_fields(fields)

        assert set(redacted.values()) == {REDACTED}

    def test_non_sensitive_fields_are_preserved(self) -> None:
        fields = {'company_id': 'company-a', 'trace_id': 'trace-a', 'count': 3}

        assert redact_sensitive_fields(fields) == fields

    def test_field_name_matching_is_case_insensitive(self) -> None:
        assert redact_sensitive_fields({'Question': 'secret'}) == {'Question': REDACTED}


class TestTraceFormatterRedaction:
    """The JSON formatter must redact sensitive extra fields."""

    def test_extra_sensitive_fields_are_redacted_in_json_logs(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(TraceFormatter('%(message)s'))
        logger = logging.getLogger('finsight.security.test')
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        try:
            logger.info(
                'processed',
                extra={'question': 'secret question', 'chunk_text': 'secret chunk'},
            )
        finally:
            logger.handlers = []

        payload = json.loads(stream.getvalue())

        assert payload['question'] == REDACTED
        assert payload['chunk_text'] == REDACTED
        assert payload['message'] == 'processed'


class TestSensitiveLoggingGuard:
    """Business code must not pass sensitive identifiers to a logger."""

    def test_business_code_does_not_log_sensitive_identifiers(self) -> None:
        violations = find_sensitive_log_calls(SRC_ROOT)

        assert not violations, 'Sensitive values passed to a logger:\n' + '\n'.join(
            f'  {path}:{line} {name}' for path, name, line in violations
        )

    def test_scanner_detects_a_sensitive_log_call(self, tmp_path: Path) -> None:
        package = tmp_path / 'application'
        package.mkdir()
        (package / 'flow.py').write_text(
            'import logging\n'
            '\n'
            'logger = logging.getLogger(__name__)\n'
            '\n'
            '\n'
            'def run(question: str) -> None:\n'
            "    logger.info('processing %s', question)\n"
        )

        violations = find_sensitive_log_calls(package)

        assert len(violations) == 1
        assert violations[0][1] == 'question'

    def test_scanner_allows_logging_a_length(self, tmp_path: Path) -> None:
        package = tmp_path / 'application'
        package.mkdir()
        (package / 'flow.py').write_text(
            'import logging\n'
            '\n'
            'logger = logging.getLogger(__name__)\n'
            '\n'
            '\n'
            'def run(question: str) -> None:\n'
            "    logger.info('length=%s', len(question))\n"
        )

        assert find_sensitive_log_calls(package) == []
