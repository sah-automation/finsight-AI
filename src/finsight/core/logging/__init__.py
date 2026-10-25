# Core Logging - Structured logging with trace context

from __future__ import annotations

import contextlib
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

try:
    from pythonjsonlogger import jsonlogger
except (ImportError, AttributeError):  # pragma: no cover
    from pythonjsonlogger import jsonlogger

from .redaction import redact_sensitive_fields

if TYPE_CHECKING:
    from types import TracebackType

# Context variables for trace propagation
_trace_id: ContextVar[str | None] = ContextVar('trace_id', default=None)
_company_id: ContextVar[str | None] = ContextVar('company_id', default=None)
_user_id: ContextVar[str | None] = ContextVar('user_id', default=None)
_span_name: ContextVar[str | None] = ContextVar('span_name', default=None)
_switch_values: ContextVar[dict[str, Any] | None] = ContextVar('switch_values', default=None)


try:
    _JsonFormatterBase = jsonlogger.JsonFormatter
except (ImportError, AttributeError):  # pragma: no cover

    class _JsonFormatterBase(logging.Formatter):  # type: ignore[no-redef]
        def add_fields(
            self,
            log_record: dict[str, Any],
            record: logging.LogRecord,
            message_dict: dict[str, Any],
        ) -> None:
            log_record.update(message_dict)
            if record.exc_info:
                log_record['exc_info'] = self.formatException(record.exc_info)
            if record.stack_info:
                log_record['stack_info'] = self.formatStack(record.stack_info)


class TraceFormatter(_JsonFormatterBase):
    """JSON formatter that includes trace context."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        with contextlib.suppress(TypeError, ValueError, AttributeError):
            super().add_fields(log_record, record, message_dict)

        # Add trace context
        if 'timestamp' not in log_record:
            log_record['timestamp'] = datetime.now(UTC).isoformat()
        if 'level' not in log_record:
            log_record['level'] = record.levelname
        if 'logger' not in log_record:
            log_record['logger'] = record.name

        trace_id = _trace_id.get()
        if trace_id:
            log_record['trace_id'] = trace_id

        company_id = _company_id.get()
        if company_id:
            log_record['company_id'] = company_id

        user_id = _user_id.get()
        if user_id:
            log_record['user_id'] = user_id

        span = _span_name.get()
        if span:
            log_record['span'] = span

        switches = _switch_values.get()
        if switches:
            log_record['switches'] = switches

        with contextlib.suppress(TypeError, ValueError, AttributeError):
            log_record.update(redact_sensitive_fields(log_record))


class TextFormatter(logging.Formatter):
    """Human-readable formatter with trace context."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        parts = []

        trace_id = _trace_id.get()
        if trace_id:
            parts.append(f'trace={trace_id[:8]}')

        company_id = _company_id.get()
        if company_id:
            parts.append(f'company={company_id}')

        span = _span_name.get()
        if span:
            parts.append(f'span={span}')

        if parts:
            return f'[{" ".join(parts)}] {base}'
        return base


def configure_logging(
    level: str = 'INFO',
    format_type: str = 'json',
    service_name: str = 'finsight-ai',
) -> None:
    """Configure root logger. Call once at startup."""
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(service_name)

    formatter: logging.Formatter
    if format_type == 'json':
        with contextlib.suppress(TypeError, ValueError, AttributeError):
            candidate: logging.Formatter = TraceFormatter(  # type: ignore[no-untyped-call]
                '%(timestamp)s %(level)s %(logger)s %(message)s',
                rename_fields={'levelname': 'level'},
            )
            handler.setFormatter(candidate)
            handler.set_name(service_name)
            root.addHandler(handler)
            logging.getLogger('boto3').setLevel(logging.WARNING)
            logging.getLogger('botocore').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            logging.getLogger('asyncpg').setLevel(logging.WARNING)
            logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
            return
        formatter = TraceFormatter()  # type: ignore[no-untyped-call]
    else:
        formatter = TextFormatter(
            '%(asctime)s %(levelname)-8s %(name)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Reduce noise from third-party loggers
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncpg').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


# ============================================================
# Trace Context Management
# ============================================================


def set_trace_id(trace_id: str | None = None) -> str:
    """Set trace ID for current context. Returns the trace ID."""
    if trace_id is None:
        trace_id = str(uuid.uuid4())
    _trace_id.set(trace_id)
    return trace_id


def get_trace_id() -> str | None:
    """Get current trace ID."""
    return _trace_id.get()


def set_company_id(company_id: str | None) -> None:
    """Set company ID for current context."""
    _company_id.set(company_id)


def get_company_id() -> str | None:
    """Get current company ID."""
    return _company_id.get()


def set_user_id(user_id: str | None) -> None:
    """Set user ID for current context."""
    _user_id.set(user_id)


def get_user_id() -> str | None:
    """Get current user ID."""
    return _user_id.get()


def set_span_name(span_name: str | None) -> None:
    """Set current span name."""
    _span_name.set(span_name)


def get_span_name() -> str | None:
    """Get current span name."""
    return _span_name.get()


def set_switch_values(switches: dict[str, Any] | None) -> None:
    """Set active switch values for tracing."""
    _switch_values.set(switches)


def get_switch_values() -> dict[str, Any] | None:
    """Get active switch values."""
    return _switch_values.get()


class TraceContext:
    """Context manager for trace context."""

    def __init__(
        self,
        trace_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
        span_name: str | None = None,
        switches: dict[str, Any] | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.company_id = company_id
        self.user_id = user_id
        self.span_name = span_name
        self.switches = switches
        self._old_trace_id: str | None = None
        self._old_company_id: str | None = None
        self._old_user_id: str | None = None
        self._old_span_name: str | None = None
        self._old_switches: dict[str, Any] | None = None

    def __enter__(self) -> TraceContext:
        self._old_trace_id = _trace_id.get()
        self._old_company_id = _company_id.get()
        self._old_user_id = _user_id.get()
        self._old_span_name = _span_name.get()
        self._old_switches = _switch_values.get()

        if self.trace_id is not None:
            _trace_id.set(self.trace_id)
        if self.company_id is not None:
            _company_id.set(self.company_id)
        if self.user_id is not None:
            _user_id.set(self.user_id)
        if self.span_name is not None:
            _span_name.set(self.span_name)
        if self.switches is not None:
            _switch_values.set(self.switches)

        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        _trace_id.set(self._old_trace_id)
        _company_id.set(self._old_company_id)
        _user_id.set(self._old_user_id)
        _span_name.set(self._old_span_name)
        _switch_values.set(self._old_switches)


def trace_context(
    trace_id: str | None = None,
    company_id: str | None = None,
    user_id: str | None = None,
    span_name: str | None = None,
    switches: dict[str, Any] | None = None,
) -> TraceContext:
    """Create a trace context manager."""
    return TraceContext(trace_id, company_id, user_id, span_name, switches)
