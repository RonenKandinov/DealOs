"""Allocate first to ready tasks that block the most incomplete downstream work."""

from __future__ import annotations

from dealos.domain.dynamics import is_complete
from dealos.domain.graph import descendants
from dealos.domain.models import AllocationAction, PortfolioState, Scenario
from dealos.policies.base import eligible_tasks, greedy_allocate


def downstream_incomplete_count(state: PortfolioState, scenario: Scenario, deal_id: str, task_id: str) -> int:
    """Number of incomplete tasks reachable from this task, excluding itself."""

    tolerance = scenario.simulation.completion_tolerance
    edges = scenario.deals[deal_id].edges
    return sum(
        1
        for descendant in descendants(edges, task_id)
        if not is_complete(state.task_progress[(deal_id, descendant)], tolerance)
    )


class BottleneckPolicy:
    name = "bottleneck"

    def select_action(self, state: PortfolioState, scenario: Scenario) -> AllocationAction:
        def sort_key(key: tuple[str, str]) -> tuple[int, int, str, str]:
            score = downstream_incomplete_count(state, scenario, key[0], key[1])
            ready_since = state.ready_since.get(key)
            waiting_since = state.time if ready_since is None else ready_since
            return (-score, waiting_since, key[0], key[1])

        order = sorted(eligible_tasks(state, scenario), key=sort_key)
        return greedy_allocate(order, state, scenario)
