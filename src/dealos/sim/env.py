"""SalesEnvironment: reset, step, get_state, is_done.

The simulator has no random number generator. Identical scenario and identical
actions produce identical states.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from dealos.domain.dynamics import apply_progress, classify_status, delta_x, is_complete
from dealos.domain.graph import predecessors
from dealos.domain.models import AllocationAction, PortfolioState, Scenario, TaskStatus
from dealos.domain.readiness import AndMinReadiness, ReadinessRule
from dealos.sim.constraints import validate_action


@dataclass(frozen=True)
class StepInfo:
    time: int
    deltas: dict[tuple[str, str], float]
    newly_completed_tasks: tuple[tuple[str, str], ...]
    newly_completed_deals: tuple[str, ...]
    utilization: dict[str, float]
    blocked_count: int
    active_deals: int
    wasted_allocation: float
    done: bool
    done_reason: str | None


class SalesEnvironment:
    def __init__(
        self,
        scenario: Scenario,
        readiness_rule: ReadinessRule | None = None,
    ) -> None:
        self.scenario = scenario
        self.readiness_rule: ReadinessRule = readiness_rule or AndMinReadiness()
        self._state: PortfolioState | None = None
        self._done_reason: str | None = None

    def reset(self, scenario: Scenario | None = None) -> PortfolioState:
        if scenario is not None:
            self.scenario = scenario
        progress = {key: float(self.scenario.initial_progress[key]) for key in self.scenario.task_keys()}
        self._state = self._derive(
            progress=progress,
            time=0,
            allocations={},
            previous_ready_since={},
            previous_task_completed_at={},
            previous_deal_completed_at={},
        )
        self._done_reason = self._reason(self._state)
        return self.get_state()

    def get_state(self) -> PortfolioState:
        if self._state is None:
            raise RuntimeError("reset() has not been called")
        return copy.deepcopy(self._state)

    def is_done(self) -> bool:
        if self._state is None:
            raise RuntimeError("reset() has not been called")
        return self._done_reason is not None

    @property
    def done_reason(self) -> str | None:
        return self._done_reason

    def step(self, action: AllocationAction) -> tuple[PortfolioState, StepInfo]:
        if self._state is None:
            raise RuntimeError("reset() has not been called")
        if self.is_done():
            raise RuntimeError("simulation is done")
        scenario = self.scenario
        current = self._state
        validate_action(
            action,
            capacities=dict(current.capacities),
            task_keys=set(scenario.task_keys()),
            tolerance=scenario.simulation.capacity_tolerance,
        )
        tolerance = scenario.simulation.completion_tolerance
        new_progress: dict[tuple[str, str], float] = {}
        deltas: dict[tuple[str, str], float] = {}
        wasted = 0.0
        for deal_id, task_id in scenario.task_keys():
            key = (deal_id, task_id)
            previous = current.task_progress[key]
            if is_complete(previous, tolerance):
                new_progress[key] = 1.0
                deltas[key] = 0.0
                for resource_id in scenario.resources:
                    wasted += action.get(deal_id, task_id, resource_id)
                continue
            ready = self._ready(current.task_progress, deal_id, task_id)
            resource_terms = 0.0
            for resource_id in scenario.resources:
                amount = action.get(deal_id, task_id, resource_id)
                resource_terms += (
                    scenario.alpha[(deal_id, task_id, resource_id)]
                    * scenario.suitability[(deal_id, task_id, resource_id)]
                    * amount
                )
            raw_delta = delta_x(scenario.phi[key], ready, resource_terms)
            updated = apply_progress(previous, raw_delta, tolerance)
            new_progress[key] = updated
            deltas[key] = updated - previous
        applied = {
            key: amount
            for key, amount in action.allocations.items()
            if amount > 0.0
        }
        nxt = self._derive(
            progress=new_progress,
            time=current.time + 1,
            allocations=applied,
            previous_ready_since=current.ready_since,
            previous_task_completed_at=current.task_completed_at,
            previous_deal_completed_at=current.deal_completed_at,
        )
        newly_tasks = tuple(
            key
            for key in scenario.task_keys()
            if not is_complete(current.task_progress[key], tolerance)
            and is_complete(nxt.task_progress[key], tolerance)
        )
        newly_deals = tuple(
            deal_id
            for deal_id in sorted(scenario.deals)
            if current.deal_complete[deal_id] == 0 and nxt.deal_complete[deal_id] == 1
        )
        self._state = nxt
        self._done_reason = self._reason(nxt)
        used = action.used_by_resource()
        utilization = {}
        for resource_id, capacity in nxt.capacities.items():
            allocated = used.get(resource_id, 0.0)
            utilization[resource_id] = allocated / capacity if capacity > 0.0 else 0.0
        info = StepInfo(
            time=nxt.time,
            deltas=deltas,
            newly_completed_tasks=newly_tasks,
            newly_completed_deals=newly_deals,
            utilization=utilization,
            blocked_count=len(nxt.blocked_tasks),
            active_deals=sum(1 for value in nxt.deal_complete.values() if value == 0),
            wasted_allocation=wasted,
            done=self._done_reason is not None,
            done_reason=self._done_reason,
        )
        return self.get_state(), info

    def _ready(self, progress: dict[tuple[str, str], float], deal_id: str, task_id: str) -> float:
        deal = self.scenario.deals[deal_id]
        values = [progress[(deal_id, pred)] for pred in predecessors(deal.edges, task_id)]
        return self.readiness_rule.readiness(values)

    def _derive(
        self,
        *,
        progress: dict[tuple[str, str], float],
        time: int,
        allocations: dict[tuple[str, str, str], float],
        previous_ready_since: dict[tuple[str, str], int | None],
        previous_task_completed_at: dict[tuple[str, str], int | None],
        previous_deal_completed_at: dict[str, int | None],
    ) -> PortfolioState:
        scenario = self.scenario
        config = scenario.simulation
        statuses: dict[tuple[str, str], TaskStatus] = {}
        blocked: set[tuple[str, str]] = set()
        ready_since: dict[tuple[str, str], int | None] = {}
        task_completed_at: dict[tuple[str, str], int | None] = {}
        for deal_id, task_id in scenario.task_keys():
            key = (deal_id, task_id)
            ready = self._ready(progress, deal_id, task_id)
            status = classify_status(
                progress[key],
                ready,
                blocked_readiness_threshold=config.blocked_readiness_threshold,
                completion_tolerance=config.completion_tolerance,
            )
            statuses[key] = status
            if status is TaskStatus.COMPLETED:
                blocked.discard(key)
                previous = previous_task_completed_at.get(key)
                task_completed_at[key] = time if previous is None else previous
                ready_since[key] = previous_ready_since.get(key)
            elif status is TaskStatus.BLOCKED:
                blocked.add(key)
                task_completed_at[key] = None
                ready_since[key] = None
            else:
                task_completed_at[key] = None
                previous_ready = previous_ready_since.get(key)
                ready_since[key] = time if previous_ready is None else previous_ready
        deal_complete: dict[str, int] = {}
        deal_completed_at: dict[str, int | None] = {}
        completed_deals: set[str] = set()
        for deal_id, deal in scenario.deals.items():
            finished = all(
                is_complete(progress[(deal_id, target)], config.completion_tolerance)
                for target in deal.targets
            )
            if finished:
                deal_complete[deal_id] = 1
                completed_deals.add(deal_id)
                previous = previous_deal_completed_at.get(deal_id)
                deal_completed_at[deal_id] = time if previous is None else previous
            else:
                deal_complete[deal_id] = 0
                deal_completed_at[deal_id] = None
        return PortfolioState(
            time=time,
            task_progress=progress,
            task_status=statuses,
            capacities={
                resource_id: resource.capacity
                for resource_id, resource in scenario.resources.items()
            },
            allocations=dict(allocations),
            completed_deals=completed_deals,
            blocked_tasks=blocked,
            ready_since=ready_since,
            task_completed_at=task_completed_at,
            deal_completed_at=deal_completed_at,
            deal_complete=deal_complete,
        )

    def _reason(self, state: PortfolioState) -> str | None:
        reasons: list[str] = []
        if state.deal_complete and all(value == 1 for value in state.deal_complete.values()):
            reasons.append("all_deals_complete")
        if state.time >= self.scenario.horizon:
            reasons.append("horizon")
        if not reasons:
            return None
        return "+".join(reasons)
