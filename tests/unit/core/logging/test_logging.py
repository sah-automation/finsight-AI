"""Unit tests for configure_logging startup behaviour."""

from __future__ import annotations

import io
import logging

import pytest

from finsight.core.logging import TextFormatter, TraceFormatter, configure_logging


def _root() -> logging.Logger:
    return logging.getLogger()


def test_json_path_configures_json_formatter() -> None:
    configure_logging(level='INFO', format_type='json', service_name='svc')
    root = _root()
    assert root.level == logging.INFO
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, TraceFormatter)
    assert root.handlers[0].name == 'svc'


def test_text_path_configures_text_formatter() -> None:
    configure_logging(level='DEBUG', format_type='text', service_name='svc2')
    root = _root()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, TextFormatter)
    assert root.handlers[0].name == 'svc2'


def test_fail_loud_on_invalid_level() -> None:
    with pytest.raises(ValueError):
        configure_logging(level='NOT_A_LEVEL')


def test_fail_loud_on_invalid_format() -> None:
    with pytest.raises(ValueError):
        configure_logging(format_type='xml')


def test_fail_loud_on_empty_service_name() -> None:
    with pytest.raises(ValueError):
        configure_logging(service_name='   ')


def test_json_output_redacts_sensitive_fields() -> None:
    configure_logging(level='INFO', format_type='json', service_name='svc')
    stream = io.StringIO()
    _root().handlers[0].stream = stream
    logging.getLogger('t').info('msg', extra={'question': 'secret'})
    payload = __import__('json').loads(stream.getvalue())
    assert payload['question'] == '[REDACTED]'
    assert payload['message'] == 'msg'
