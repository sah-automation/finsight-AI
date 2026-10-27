# Confidence - Value object for confidence scores
# Confidence is a float/score; floats allowed for confidence/scores only.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Confidence:
    """Immutable confidence score."""

    score: float
    reasoning: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise TypeError('Confidence.score must be a float')
        if not (0.0 <= float(self.score) <= 1.0):
            raise ValueError('Confidence.score must be between 0.0 and 1.0')
        object.__setattr__(self, 'score', float(self.score))
        if self.reasoning is not None and not isinstance(self.reasoning, str):
            raise TypeError('Confidence.reasoning must be a string or None')
