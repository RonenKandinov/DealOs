"""Shared policy interface and the greedy feasible fill used by heuristics."""

from __future__ import annotations

from typing import Protocol, Sequence

from dealos.domain.dynamics import is_complete
from dealos.domain.graph import predecessors
from dealos.domain.models import (
    AllocationAction,
    OccurrenceLifecycle,
    PortfolioState,
    ReadinessSource,
    Scenario,
    TaskOccurrence,
)
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


def occurrence_ready(
    occurrence: TaskOccurrence,
    state: PortfolioState,
    scenario: Scenario,
) -> float | None:
    """Readiness multiplier, or None when no occurrence-level rule exists.

    Primary occurrences use type-level AND-min. Added occurrences stay
    unresolved unless a fixture declared them ready. Declared readiness uses
    Ready = 1 because the log does not supply a predecessor occurrence.
    """

    if occurrence.readiness_source is ReadinessSource.UNRESOLVED:
        return None
    if occurrence.readiness_source is ReadinessSource.DECLARED:
        return 1.0
    return readiness_of(scenario, state.task_progress, occurrence.deal_id, occurrence.task_id)


def is_allocation_eligible(occurrence: TaskOccurrence, state: PortfolioState, scenario: Scenario) -> bool:
    """Active lifecycle and a satisfied readiness value. The two are not one status."""

    if occurrence.lifecycle is not OccurrenceLifecycle.ACTIVE:
        return False
    ready = occurrence_ready(occurrence, state, scenario)
    if ready is None:
        return False
    if occurrence.readiness_source is ReadinessSource.TYPE_AND_MIN:
        tolerance = scenario.simulation.completion_tolerance
        if is_complete(state.task_progress[(occurrence.deal_id, occurrence.task_id)], tolerance):
            return False
        return ready > scenario.simulation.blocked_readiness_threshold
    tolerance = scenario.simulation.completion_tolerance
    return not is_complete(occurrence.progress, tolerance)


def eligible_occurrences(state: PortfolioState, scenario: Scenario) -> list[TaskOccurrence]:
    """Primary occurrences in task-key order, then any declared extra occurrences."""

    chosen: list[TaskOccurrence] = []
    seen: set[str] = set()
    for deal_id, task_id in scenario.task_keys():
        occurrence_id = state.primary_occurrence.get((deal_id, task_id))
        if occurrence_id is None:
            continue
        occurrence = state.occurrences[occurrence_id]
        if is_allocation_eligible(occurrence, state, scenario):
            chosen.append(occurrence)
            seen.add(occurrence_id)
    for occurrence_id in sorted(state.occurrences):
        if occurrence_id in seen:
            continue
        occurrence = state.occurrences[occurrence_id]
        if is_allocation_eligible(occurrence, state, scenario):
            chosen.append(occurrence)
    return chosen


def eligible_tasks(state: PortfolioState, scenario: Scenario) -> list[tuple[str, str]]:
    """Primary task types whose occurrence is eligible. Order matches the historical task scan."""

    return [(item.deal_id, item.task_id) for item in eligible_occurrences(state, scenario) if _is_primary(state, item)]


def _is_primary(state: PortfolioState, occurrence: TaskOccurrence) -> bool:
    return state.primary_occurrence.get((occurrence.deal_id, occurrence.task_id)) == occurrence.occurrence_id


def greedy_allocate(
    order: Sequence[TaskOccurrence],
    state: PortfolioState,
    scenario: Scenario,
) -> AllocationAction:
    """Pour remaining capacity into occurrences in the given order.

    Productivity is the task type's α·q. The action key is the occurrence id.
    """

    tolerance = scenario.simulation.capacity_tolerance
    completion = scenario.simulation.completion_tolerance
    remaining = {resource_id: resource.capacity for resource_id, resource in scenario.resources.items()}
    allocations: dict[tuple[str, str, str], float] = {}
    for occurrence in order:
        if not is_allocation_eligible(occurrence, state, scenario):
            continue
        ready = occurrence_ready(occurrence, state, scenario)
        if ready is None:
            continue
        progress = (
            state.task_progress[(occurrence.deal_id, occurrence.task_id)]
            if _is_primary(state, occurrence)
            else occurrence.progress
        )
        gap = 1.0 - progress
        if gap <= completion:
            continue
        deal_id = occurrence.deal_id
        task_id = occurrence.task_id
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
            allocations[(deal_id, occurrence.occurrence_id, resource_id)] = amount
            remaining[resource_id] -= amount
            gap -= scale * productivity * amount
    return AllocationAction(allocations)
