"""Waiting-line adapters (bounded heavy-work scheduling)."""

from .busy_result import BusyResult
from .passthrough_waiting_line import PassthroughWaitingLine
from .waiting_line_adapter import WaitingLineAdapter

__all__ = ['BusyResult', 'PassthroughWaitingLine', 'WaitingLineAdapter']
