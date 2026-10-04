"""Hard checks on a_ijr. Infeasible actions are rejected, not clipped."""

from __future__ import annotations

from dealos.domain.models import AllocationAction


class CapacityViolation(Exception):
    """Raised when Σ_i Σ_j a_ijr exceeds C_r."""

    def __init__(self, resource_id: str, used: float, capacity: float) -> None:
        self.resource_id = resource_id
        self.used = used
        self.capacity = capacity
        super().__init__(
            f"resource {resource_id} allocated {used} exceeds capacity {capacity}"
        )


class ActionBoundsError(ValueError):
    """Raised when an allocation is outside [0, 1] or names an unknown id."""


def validate_action(
    action: AllocationAction,
    *,
    capacities: dict[str, float],
    occurrence_ids: set[str],
    tolerance: float,
) -> None:
    used = {resource_id: 0.0 for resource_id in capacities}
    for (deal_id, occurrence_id, resource_id), amount in action.allocations.items():
        if occurrence_id not in occurrence_ids:
            raise ActionBoundsError(f"unknown occurrence {deal_id}:{occurrence_id}")
        if resource_id not in capacities:
            raise ActionBoundsError(f"unknown resource {resource_id}")
        if amount < -tolerance or amount > 1.0 + tolerance:
            raise ActionBoundsError(
                f"allocation {deal_id}:{occurrence_id}:{resource_id}={amount} is outside [0, 1]"
            )
        if amount > 0.0:
            used[resource_id] += amount
    for resource_id, total in used.items():
        capacity = capacities[resource_id]
        if total > capacity + tolerance:
            raise CapacityViolation(resource_id, total, capacity)
