#!/usr/bin/env python3
"""Alias for ``check_local_bootstrap_parity.py`` (issue #230 naming variants)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().with_name('check_local_bootstrap_parity.py')
_SPEC = importlib.util.spec_from_file_location('check_local_bootstrap_parity', _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

main = _MODULE.main

if __name__ == '__main__':
    raise SystemExit(main())
