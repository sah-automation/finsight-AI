# ruff: noqa: I001, F403, F405
from __future__ import annotations
from ._feedback_0 import *
from ._feedback_1 import *
from ._feedback_2 import *
from ._feedback_3 import *
from ._feedback_4 import *

FeedbackRecord = _FeedbackModel
ReportWrongSourceModel = _FeedbackModel
ReportWrongSourceResponse = _FeedbackModel
WrongSourceReport = _FeedbackModel

__all__ = [
    'FeedbackRecord',
    'ReportWrongSourceModel',
    'ReportWrongSourceResponse',
    'WrongSourceReport',
]
