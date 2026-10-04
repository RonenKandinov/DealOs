"""Allocate first to eligible occurrences of types that block the most downstream work."""

from __future__ import annotations

from dealos.domain.dynamics import is_complete
from dealos.domain.graph import descendants
from dealos.domain.models import AllocationAction, PortfolioState, Scenario, TaskOccurrence
from dealos.policies.base import eligible_occurrences, greedy_allocate


def downstream_incomplete_count(state: PortfolioState, scenario: Scenario, deal_id: str, task_id: str) -> int:
    """Number of incomplete task types reachable from this type, excluding itself."""

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
        def sort_key(occurrence: TaskOccurrence) -> tuple[int, int, str, str, str]:
            score = downstream_incomplete_count(
                state, scenario, occurrence.deal_id, occurrence.task_id
            )
            key = (occurrence.deal_id, occurrence.task_id)
            ready_since = state.ready_since.get(key)
            waiting_since = state.time if ready_since is None else ready_since
            return (-score, waiting_since, occurrence.deal_id, occurrence.task_id, occurrence.occurrence_id)

        order = sorted(eligible_occurrences(state, scenario), key=sort_key)
        return greedy_allocate(order, state, scenario)
