#!/usr/bin/env python3
"""Check that infra/localstack/init.sh matches the test configuration profile.

The local object store bootstrap must create the exact buckets, queues and
tables that ``config/test.yaml`` references. This check fails loudly on drift
instead of letting a fresh stack start with the wrong resources.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from finsight.core.config import Environment, load_config

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_SCRIPT = REPO_ROOT / 'infra' / 'localstack' / 'init.sh'


def _array_values(text: str, name: str) -> list[str]:
    match = re.search(rf'{re.escape(name)}=\(([^)]*)\)', text)
    if match is None:
        raise ValueError(f'could not find {name} array in {INIT_SCRIPT}')
    return [
        token.strip().strip('"').strip("'") for token in match.group(1).split() if token.strip()
    ]


def _with_env_placeholders() -> None:
    env_example = REPO_ROOT / '.env.example'
    if not env_example.exists():
        return
    for raw_line in env_example.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.split('  #', 1)[0].strip())


def main() -> int:
    _with_env_placeholders()
    config = load_config(Environment.TEST)

    init_text = INIT_SCRIPT.read_text(encoding='utf-8')
    failures: list[str] = []

    buckets = _array_values(init_text, 'BUCKETS')
    expected_buckets = [
        config.storage.documents_bucket,
        config.storage.reports_bucket,
        config.storage.backups_bucket,
    ]
    if buckets != expected_buckets:
        failures.append(f'BUCKETS drift: bootstrap={buckets!r}, configured={expected_buckets!r}')

    queues = _array_values(init_text, 'QUEUES')
    expected_queues = [
        config.queue.ingestion_queue_url.rsplit('/', 1)[-1],
        config.queue.reprocessing_queue_url.rsplit('/', 1)[-1],
        config.queue.reports_queue_url.rsplit('/', 1)[-1],
        config.queue.dead_letter_queue_url.rsplit('/', 1)[-1],
    ]
    if queues != expected_queues:
        failures.append(f'QUEUES drift: bootstrap={queues!r}, configured={expected_queues!r}')

    tables = _array_values(init_text, 'TABLES')
    expected_tables = [
        config.caches.answer_cache.table_name,
        config.caches.role_cache.table_name,
        config.metering.table_name,
    ]
    if tables != expected_tables:
        failures.append(f'TABLES drift: bootstrap={tables!r}, configured={expected_tables!r}')

    if 'put-bucket-cors' not in init_text:
        failures.append('bootstrap sets no CORS rules (missing put-bucket-cors)')
    if 'AllowedMethods' not in init_text or '"PUT"' not in init_text:
        failures.append('CORS rule does not allow browser presigned uploads (PUT)')
    if 'ExposeHeaders' not in init_text or 'ETag' not in init_text:
        failures.append('CORS rule does not expose ETag for browser uploads')

    if failures:
        print('Local bootstrap parity check FAILED:', file=sys.stderr)
        for failure in failures:
            print(f'  - {failure}', file=sys.stderr)
        return 1

    print('Local bootstrap parity check OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
