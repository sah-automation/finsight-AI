#!/usr/bin/env python3
"""Bootstrap test environment - entry point that delegates to bootstrap.main."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / 'bootstrap'))

from bootstrap.main import main

if __name__ == '__main__':
    import asyncio

    sys.exit(asyncio.run(main()))
