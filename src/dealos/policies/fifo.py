"""Allocate first to eligible occurrences that have been ready the longest."""

from __future__ import annotations

from dealos.domain.models import AllocationAction, PortfolioState, Scenario, TaskOccurrence
from dealos.policies.base import eligible_occurrences, greedy_allocate


class FIFOPolicy:
    name = "fifo"

    def select_action(self, state: PortfolioState, scenario: Scenario) -> AllocationAction:
        def sort_key(occurrence: TaskOccurrence) -> tuple[int, str, str, str]:
            key = (occurrence.deal_id, occurrence.task_id)
            ready_since = state.ready_since.get(key)
            waiting_since = state.time if ready_since is None else ready_since
            return (waiting_since, occurrence.deal_id, occurrence.task_id, occurrence.occurrence_id)

        order = sorted(eligible_occurrences(state, scenario), key=sort_key)
        return greedy_allocate(order, state, scenario)
