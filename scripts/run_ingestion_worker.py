"""Ingestion worker that consumes SQS ingestion jobs and runs the pipeline."""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import logging
import signal
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger('finsight.ingestion_worker')

try:
    from finsight.core.config import load_config as _load_config
except Exception:  # pragma: no cover
    _load_config = None

try:
    from finsight.composition import build_container as _build_container
except Exception:  # pragma: no cover
    _build_container = None

try:
    from finsight.composition import build_queue as _build_queue
except Exception:  # pragma: no cover
    _build_queue = None

try:
    from finsight.application.ingest_document import IngestionPipeline as _IngestionPipeline
except Exception:  # pragma: no cover
    _IngestionPipeline = None


def load_config(*args: Any, **kwargs: Any) -> Any:
    if _load_config is None:
        raise RuntimeError('load_config is unavailable')
    return _load_config(*args, **kwargs)


def build_container(*args: Any, **kwargs: Any) -> Any:
    if _build_container is None:
        raise RuntimeError('build_container is unavailable')
    return _build_container(*args, **kwargs)


def build_queue(*args: Any, **kwargs: Any) -> Any:
    if _build_queue is None:
        raise RuntimeError('build_queue is unavailable')
    return _build_queue(*args, **kwargs)


def IngestionPipeline(*args: Any, **kwargs: Any) -> Any:
    if _IngestionPipeline is None:
        raise RuntimeError('IngestionPipeline is unavailable')
    return _IngestionPipeline(*args, **kwargs)


__all__ = [
    'IngestionPipeline',
    'acknowledge_message',
    'build_container',
    'build_context',
    'build_pipeline',
    'build_queue',
    'create_context',
    'create_queue',
    'load_config',
    'main',
    'message_to_context',
    'parse_message',
    'parse_message_body',
    'process_message',
    'run',
    'run_worker',
]


def _parse_mapping_text(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not (text.startswith('{') and text.endswith('}')):
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return dict(parsed)
    return None


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            text = bytes(value).decode('utf-8')
        except Exception:
            text = str(value)
        parsed = _parse_mapping_text(text)
        if parsed is not None:
            return parsed
        return {'body': text}
    if isinstance(value, str):
        parsed = _parse_mapping_text(value)
        if parsed is not None:
            return parsed
        return {'body': value}
    return {}


def parse_message_body(message: Any) -> dict[str, Any]:
    """Return the parsed (flattened) envelope carried by an SQS message.

    Handles flat, nested (body/message/MessageBody/envelope), wrapped, and
    stringified (JSON or Python repr) legacy envelopes. Derives nothing here;
    build_context performs key-path recovery.
    """
    envelope: dict[str, Any] = {}

    _ID_KEYS = (
        'company_id',
        'companyId',
        'document_id',
        'documentId',
        'doc_id',
        'version_id',
        'document_version_id',
        'versionId',
        'id',
        'key',
        'object_key',
        's3_key',
        'file_key',
        'action',
        'job_id',
        'jobId',
    )

    _WRAPPERS = (
        'Body',
        'body',
        'MessageBody',
        'message',
        'payload',
        'data',
        'detail',
        'input',
        'envelope',
    )

    def absorb(src: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(src, (str, bytes, bytearray)):
            parsed = _coerce_mapping(src)
            # _coerce_mapping returns {'body': ...} for plain strings; only treat
            # as an envelope when it parsed into a real mapping or has id keys.
            if isinstance(parsed, dict) and (
                any(k in parsed for k in _ID_KEYS) or parsed.get('body') != src if False else True
            ):
                # Avoid infinite loops: coerce gives body for plain strings.
                pass
            if isinstance(parsed, dict) and parsed is not None:
                # Only absorb parsed dict if it either contains id keys or is not a synthetic body wrapper.
                if any(k in parsed for k in _ID_KEYS) or not (
                    len(parsed) == 1 and 'body' in parsed and parsed.get('body') == src
                    if isinstance(src, str)
                    else False
                ):
                    absorb(parsed, depth + 1)
                    return
            # plain string body
            envelope.setdefault('body', _coerce_str(src))
            return
        if not isinstance(src, dict):
            return
        for key, value in src.items():
            if key in _WRAPPERS:
                absorb(value, depth + 1)
                continue
            if isinstance(value, str):
                parsed = _parse_mapping_text(value)
                if isinstance(parsed, dict) and any(k in parsed for k in _ID_KEYS):
                    absorb(parsed, depth + 1)
                    continue
            if isinstance(value, dict) and any(k in value for k in _ID_KEYS):
                absorb(value, depth + 1)
                continue
            if value is not None:
                envelope.setdefault(key, value)
        # If no ids resolved yet, scan any dict value containing ids.
        if not any(
            envelope.get(k) is not None for k in ('company_id', 'document_id', 'version_id')
        ):
            for value in src.values():
                if isinstance(value, dict) and any(
                    k in value for k in ('company_id', 'document_id', 'version_id')
                ):
                    absorb(value, depth + 1)
                    break

    if isinstance(message, dict) or isinstance(message, (str, bytes, bytearray)):
        absorb(message, 0)
    elif hasattr(message, '__dict__') and not isinstance(message, (list, tuple, set)):
        converted: dict[str, Any] = {}
        for attr in (
            _ID_KEYS
            + _WRAPPERS
            + ('company', 'tenant', 'ctx', 'context', 'step_context', 'run_context')
        ):
            try:
                val = getattr(message, attr, None)
            except Exception:
                val = None
            if val is not None:
                converted[attr] = val
        # also flatten envelope/message attributes
        env_attr = getattr(message, 'envelope', None)
        msg_attr = getattr(message, 'message', None)
        if isinstance(env_attr, dict):
            converted['envelope'] = env_attr
        if isinstance(msg_attr, dict):
            converted['message'] = msg_attr
        if converted:
            absorb(converted, 0)
        else:
            absorb(_coerce_mapping(str(message)), 0)
    else:
        try:
            absorb(_coerce_mapping(str(message)), 0)
        except Exception:
            pass

    # Ensure ReceiptHandle style keys from a dict message are present.
    if isinstance(message, dict):
        for key in ('ReceiptHandle', 'receipt_handle'):
            if key in message and message.get(key) is not None:
                envelope.setdefault(key, message.get(key))

    return envelope


parse_message = parse_message_body


def _pick(envelope: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in envelope and envelope.get(key) is not None:
            return envelope.get(key)
    return None


def _normalize_key_local(key: Any) -> str:
    if key is None:
        return ''
    return str(key).replace('\\', '/').lstrip('/')


def _parse_key_local(key: Any) -> dict[str, Any]:
    result = {'company_id': None, 'document_id': None, 'version_id': None}
    text = _normalize_key_local(key)
    parts = [p for p in text.split('/') if p]
    if parts:
        result['company_id'] = parts[0]
    if len(parts) >= 5 and parts[1] == 'documents' and parts[3] == 'versions':
        result['document_id'] = parts[2]
        result['version_id'] = parts[4]
    return result


def build_context(envelope_or_message: Any) -> SimpleNamespace:
    envelope = parse_message_body(envelope_or_message)

    company_id = _pick(envelope, 'company_id', 'companyId', 'company', 'tenant_id', 'tenant')
    document_id = _pick(envelope, 'document_id', 'documentId', 'doc_id', 'document')
    version_id = _pick(envelope, 'version_id', 'document_version_id', 'versionId', 'id')
    key = _pick(envelope, 'key', 'object_key', 's3_key', 'file_key')

    # Derive any missing ids from the storage key path (domain storage-key convention).
    if key:
        try:
            parsed = _parse_key_local(key)
            if company_id is None:
                company_id = parsed.get('company_id')
            if document_id is None:
                document_id = parsed.get('document_id')
            if version_id is None:
                version_id = parsed.get('version_id')
        except Exception:
            pass

    ctx = SimpleNamespace(
        company_id=company_id,
        document_id=document_id,
        version_id=version_id,
        key=key or '',
        message=envelope,
    )
    ctx.company = company_id
    ctx.version = version_id
    ctx.envelope = envelope
    return ctx


create_context = build_context
message_to_context = build_context


def build_pipeline(container: Any = None) -> Any:
    if container is None:
        container = build_container(load_config())
    # Prefer the wired 'pipeline' entry from the step-functions worker set.
    worker_set = None
    if container is not None:
        worker_set = getattr(container, 'step_functions_worker_set', None)
        if worker_set is None:
            worker_set = getattr(container, 'workers', None)
        if worker_set is not None and hasattr(worker_set, 'get'):
            candidate = worker_set.get('pipeline')
            if candidate is not None and hasattr(candidate, 'run_pipeline'):
                return candidate
    for attr in (
        'ingestion_pipeline',
        'ingestion_worker',
        'pipeline_worker',
        'pipeline',
        'ingestion',
    ):
        candidate = getattr(container, attr, None) if container is not None else None
        if candidate is not None and hasattr(candidate, 'run_pipeline'):
            return candidate
    pipeline = IngestionPipeline(container=container)
    return pipeline


def create_queue(config: Any = None) -> Any:
    if config is None:
        config = load_config()
    return build_queue(config=config)


def acknowledge_message(queue: Any, message: Any) -> Any:
    if queue is None or not hasattr(queue, 'ack'):
        return None
    return queue.ack(message)


async def process_message(queue: Any, pipeline: Any, message: Any, **kwargs: Any) -> Any:
    """Process a single SQS message end to end."""
    ctx = build_context(message)
    logger.info(
        'Processing ingestion job company=%s document=%s version=%s',
        getattr(ctx, 'company_id', None),
        getattr(ctx, 'document_id', None),
        getattr(ctx, 'version_id', None),
    )
    try:
        result = await pipeline.run_pipeline(ctx)
    except Exception:
        if queue is not None and hasattr(queue, 'nack'):
            _nack_result = queue.nack(message)
            if hasattr(_nack_result, '__await__'):
                await _nack_result
        raise

    status = ''
    if isinstance(result, dict):
        status = str(result.get('status', '')).lower()
    if status in {'failed', 'error', 'needs_review'}:
        if queue is not None and hasattr(queue, 'nack'):
            _nack_result = queue.nack(message)
            if hasattr(_nack_result, '__await__'):
                await _nack_result
        # Surface a non-success result without acking the message.
        return result
    await acknowledge_message(queue, message)
    return result


async def process_one(*args: Any, **kwargs: Any) -> Any:
    if len(args) >= 3:
        return await process_message(args[0], args[1], args[2], **kwargs)
    return await process_message(*args, **kwargs)


async def handle_message(*args: Any, **kwargs: Any) -> Any:
    return await process_message(*args, **kwargs)


async def run_worker(
    queue: Any = None,
    pipeline: Any = None,
    *,
    config: Any = None,
    container: Any = None,
    max_messages: int = 10,
    max_number_of_messages: int | None = None,
    wait_time_seconds: int = 20,
    wait_time: int | None = None,
    poll_interval: float = 0.1,
    max_iterations: int | None = None,
    stop_event: asyncio.Event | None = None,
    **kwargs: Any,
) -> None:
    if max_number_of_messages is not None:
        max_messages = max_number_of_messages
    if wait_time is not None:
        wait_time_seconds = wait_time
    if queue is None or pipeline is None:
        if container is None and config is None:
            config = load_config()
        if container is None:
            container = build_container(config) if config is not None else None
        if queue is None:
            queue = getattr(container, 'queue', None) if container is not None else None
            if queue is None:
                queue = create_queue(config)
        if pipeline is None:
            pipeline = build_pipeline(container)

    if stop_event is None:
        stop_event = asyncio.Event()

    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    def _request_stop() -> None:
        try:
            stop_event.set()
        except Exception:
            pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            if loop is not None:
                loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(sig, lambda *_args: _request_stop())
            except Exception:
                pass

    iterations = 0
    while not stop_event.is_set():
        if max_iterations is not None and iterations >= max_iterations:
            break
        iterations += 1
        try:
            messages = await queue.receive(
                max_number_of_messages=max_messages,
                wait_time_seconds=wait_time_seconds,
            )
        except Exception as exc:
            logger.error('Receive failed: %s', exc, exc_info=True)
            messages = []

        if not isinstance(messages, list):
            messages = list(messages or [])

        for message in messages:
            if stop_event.is_set():
                break
            try:
                await process_message(queue, pipeline, message)
            except Exception as exc:
                logger.exception('Failed to process message %s: %s', message, exc)
                if hasattr(queue, 'nack'):
                    try:
                        await queue.nack(message)
                    except Exception:
                        pass
        await asyncio.sleep(poll_interval)

    logger.info('Ingestion worker shutdown complete')


async def run(*args: Any, **kwargs: Any) -> None:
    await run_worker(*args, **kwargs)


async def amain(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description='Run the FinSight ingestion worker')
    parser.add_argument('--max-messages', type=int, default=10)
    parser.add_argument('--wait-time-seconds', type=int, default=20)
    parser.add_argument('--poll-interval', type=float, default=1.0)
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=None,
        help='Maximum number of poll iterations (for testing)',
    )
    args = parser.parse_args(argv)

    await run_worker(
        max_messages=args.max_messages,
        wait_time_seconds=args.wait_time_seconds,
        poll_interval=args.poll_interval,
        max_iterations=args.max_iterations,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(amain(argv))
    except KeyboardInterrupt:
        logger.info('Interrupted; shutting down')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
