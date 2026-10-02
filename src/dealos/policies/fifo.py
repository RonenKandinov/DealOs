"""Allocate first to eligible tasks that have been ready the longest."""

from __future__ import annotations

from dealos.domain.models import AllocationAction, PortfolioState, Scenario
from dealos.policies.base import eligible_tasks, greedy_allocate


class FIFOPolicy:
    name = "fifo"

    def select_action(self, state: PortfolioState, scenario: Scenario) -> AllocationAction:
        def sort_key(key: tuple[str, str]) -> tuple[int, str, str]:
            ready_since = state.ready_since.get(key)
            waiting_since = state.time if ready_since is None else ready_since
            return (waiting_since, key[0], key[1])

        order = sorted(eligible_tasks(state, scenario), key=sort_key)
        return greedy_allocate(order, state, scenario)
