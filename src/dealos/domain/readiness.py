"""Readiness rules. V1 implements AND-min only; other rules can be added later."""

from __future__ import annotations

from typing import Protocol, Sequence


class ReadinessRule(Protocol):
    """Maps predecessor progress values to a readiness multiplier in [0, 1]."""

    def readiness(self, predecessor_progress: Sequence[float]) -> float:
        """Return 1 when there are no predecessors."""


class AndMinReadiness:
    """Ready_ij = 1 if Pred is empty, otherwise min over predecessor progress.

    OR, threshold, and veto rules are not implemented. A future rule should
    implement ReadinessRule and be passed into SalesEnvironment.
    """

    def readiness(self, predecessor_progress: Sequence[float]) -> float:
        if len(predecessor_progress) == 0:
            return 1.0
        return float(min(predecessor_progress))
