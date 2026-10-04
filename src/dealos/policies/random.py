"""Random feasible allocation. The policy RNG is independent of the simulator."""

from __future__ import annotations

import random

from dealos.domain.models import AllocationAction, PortfolioState, Scenario
from dealos.policies.base import eligible_occurrences


class RandomPolicy:
    """Shuffle eligible occurrences and assign random feasible fractions of remaining capacity.

    Construct a new instance per run. Calls advance an internal random.Random(seed),
    so the same seed and the same sequence of states reproduce the same actions.
    With one occurrence per task type, the shuffled sequence matches the historical task list.
    """

    name = "random"

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def select_action(self, state: PortfolioState, scenario: Scenario) -> AllocationAction:
        tolerance = scenario.simulation.capacity_tolerance
        occurrences = eligible_occurrences(state, scenario)
        self._rng.shuffle(occurrences)
        remaining = {
            resource_id: resource.capacity for resource_id, resource in scenario.resources.items()
        }
        allocations: dict[tuple[str, str, str], float] = {}
        resource_ids = sorted(scenario.resources)
        for occurrence in occurrences:
            deal_id = occurrence.deal_id
            task_id = occurrence.task_id
            suitable = [
                resource_id
                for resource_id in resource_ids
                if scenario.suitability[(deal_id, task_id, resource_id)] > 0.0
                and remaining[resource_id] > tolerance
            ]
            self._rng.shuffle(suitable)
            for resource_id in suitable:
                hi = min(1.0, remaining[resource_id])
                if hi <= tolerance:
                    continue
                amount = self._rng.uniform(0.0, hi)
                if amount <= tolerance:
                    continue
                amount = min(amount, remaining[resource_id])
                allocations[(deal_id, occurrence.occurrence_id, resource_id)] = amount
                remaining[resource_id] -= amount
        return AllocationAction(allocations)
