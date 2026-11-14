"""Compatibility alias for the golden scoring harness."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import compare_results as _compare_results
import run_golden as _run_golden

for _name in dir(_run_golden):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_run_golden, _name)
for _name in dir(_compare_results):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_compare_results, _name)
