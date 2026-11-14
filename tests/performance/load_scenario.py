"""Compatibility alias for the load and performance harness."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import performance_harness as _performance_harness

for _name in dir(_performance_harness):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_performance_harness, _name)
