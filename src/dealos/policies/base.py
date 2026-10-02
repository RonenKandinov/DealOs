"""Shared policy interface and the greedy feasible fill used by heuristics."""

from __future__ import annotations

from typing import Protocol, Sequence

from dealos.domain.dynamics import is_complete
from dealos.domain.graph import predecessors
from dealos.domain.models import AllocationAction, PortfolioState, Scenario
from dealos.domain.readiness import AndMinReadiness, ReadinessRule


class Policy(Protocol):
    name: str

    def select_action(self, state: PortfolioState, scenario: Scenario) -> AllocationAction:
        """Return a feasible allocation. The simulator does not repair it."""


def readiness_of(
    scenario: Scenario,
    progress: dict[tuple[str, str], float],
    deal_id: str,
    task_id: str,
    rule: ReadinessRule | None = None,
) -> float:
    values = [
        progress[(deal_id, pred)]
        for pred in predecessors(scenario.deals[deal_id].edges, task_id)
    ]
    return (rule or AndMinReadiness()).readiness(values)


def eligible_tasks(state: PortfolioState, scenario: Scenario) -> list[tuple[str, str]]:
    """Incomplete tasks whose readiness is above the blockage threshold."""

    threshold = scenario.simulation.blocked_readiness_threshold
    tolerance = scenario.simulation.completion_tolerance
    chosen: list[tuple[str, str]] = []
    for deal_id, task_id in scenario.task_keys():
        if is_complete(state.task_progress[(deal_id, task_id)], tolerance):
            continue
        ready = readiness_of(scenario, state.task_progress, deal_id, task_id)
        if ready > threshold:
            chosen.append((deal_id, task_id))
    return chosen


def greedy_allocate(
    order: Sequence[tuple[str, str]],
    state: PortfolioState,
    scenario: Scenario,
) -> AllocationAction:
    """Pour remaining capacity into tasks in the given order.

    For each task, resources are used from highest α·q to lowest until the
    remaining progress gap is covered or capacity is exhausted. Each a_ijr
    is capped at 1 and at the resource's remaining capacity.
    """

    tolerance = scenario.simulation.capacity_tolerance
    completion = scenario.simulation.completion_tolerance
    threshold = scenario.simulation.blocked_readiness_threshold
    remaining = {resource_id: resource.capacity for resource_id, resource in scenario.resources.items()}
    allocations: dict[tuple[str, str, str], float] = {}
    for deal_id, task_id in order:
        progress = state.task_progress[(deal_id, task_id)]
        gap = 1.0 - progress
        if gap <= completion:
            continue
        ready = readiness_of(scenario, state.task_progress, deal_id, task_id)
        if ready <= threshold:
            continue
        scale = scenario.phi[(deal_id, task_id)] * ready
        if scale <= 0.0:
            continue
        ranked: list[tuple[float, str, float]] = []
        for resource_id in scenario.resources:
            productivity = (
                scenario.alpha[(deal_id, task_id, resource_id)]
                * scenario.suitability[(deal_id, task_id, resource_id)]
            )
            if productivity > 0.0 and remaining[resource_id] > tolerance:
                ranked.append((-productivity, resource_id, productivity))
        ranked.sort()
        for _neg, resource_id, productivity in ranked:
            if gap <= completion:
                break
            need = gap / (scale * productivity)
            amount = min(1.0, remaining[resource_id], need)
            if amount <= tolerance:
                continue
            allocations[(deal_id, task_id, resource_id)] = amount
            remaining[resource_id] -= amount
            gap -= scale * productivity * amount
    return AllocationAction(allocations)
