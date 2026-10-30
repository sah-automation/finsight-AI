"""Verify the committed OpenAPI schema matches the generated one."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from finsight.entrypoints.api.app import create_app


def main() -> int:
    app = create_app()
    generated = app.openapi()
    committed_path = Path('docs/openapi.json')
    if not committed_path.exists():
        print(f'Missing committed schema: {committed_path}')
        return 1
    committed = json.loads(committed_path.read_text(encoding='utf-8'))
    if committed != generated:
        print('Committed OpenAPI schema does not match generated schema.')
        return 1
    print('OpenAPI schema is up to date.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
PY
