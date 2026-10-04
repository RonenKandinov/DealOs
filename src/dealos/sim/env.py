"""SalesEnvironment: reset, step, get_state, is_done.

The simulator has no random number generator. Identical scenario and identical
actions produce identical states.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace

from dealos.domain.dynamics import apply_progress, classify_status, delta_x, is_complete
from dealos.domain.graph import predecessors
from dealos.domain.models import (
    AllocationAction,
    OccurrenceLifecycle,
    Offer,
    PortfolioState,
    ReadinessSource,
    Scenario,
    TaskOccurrence,
    TaskStatus,
)
from dealos.domain.readiness import AndMinReadiness, ReadinessRule
from dealos.policies.base import occurrence_ready
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
        occurrences, primary = self._initial_occurrences(progress)
        self._state = self._derive(
            progress=progress,
            time=0,
            allocations={},
            previous_ready_since={},
            previous_task_completed_at={},
            previous_deal_completed_at={},
            occurrences=occurrences,
            offers={},
            primary_occurrence=primary,
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
            occurrence_ids=set(current.occurrences),
            tolerance=scenario.simulation.capacity_tolerance,
        )
        tolerance = scenario.simulation.completion_tolerance
        new_progress = dict(current.task_progress)
        deltas = {key: 0.0 for key in scenario.task_keys()}
        wasted = 0.0
        occurrences = dict(current.occurrences)
        by_occurrence: dict[str, dict[str, float]] = {}
        for (deal_id, occurrence_id, resource_id), amount in action.allocations.items():
            if amount == 0.0:
                continue
            if occurrences[occurrence_id].deal_id != deal_id:
                raise ValueError(f"occurrence {occurrence_id} is not in deal {deal_id}")
            bucket = by_occurrence.setdefault(occurrence_id, {})
            bucket[resource_id] = bucket.get(resource_id, 0.0) + amount
        for occurrence_id, by_resource in by_occurrence.items():
            occurrence = occurrences[occurrence_id]
            key = (occurrence.deal_id, occurrence.task_id)
            allocated = sum(by_resource.values())
            if not _receives_progress(occurrence, current, scenario):
                wasted += allocated
                if is_complete(current.task_progress[key], tolerance) and occurrence_id == current.primary_occurrence[key]:
                    new_progress[key] = 1.0
                continue
            ready = occurrence_ready(occurrence, current, scenario)
            if ready is None:
                wasted += allocated
                continue
            resource_terms = 0.0
            for resource_id, amount in by_resource.items():
                resource_terms += (
                    scenario.alpha[(occurrence.deal_id, occurrence.task_id, resource_id)]
                    * scenario.suitability[(occurrence.deal_id, occurrence.task_id, resource_id)]
                    * amount
                )
            raw_delta = delta_x(scenario.phi[key], ready, resource_terms)
            if occurrence_id == current.primary_occurrence[key]:
                updated = apply_progress(current.task_progress[key], raw_delta, tolerance)
                new_progress[key] = updated
                deltas[key] = updated - current.task_progress[key]
            else:
                updated = apply_progress(occurrence.progress, raw_delta, tolerance)
                lifecycle = occurrence.lifecycle
                if is_complete(updated, tolerance):
                    lifecycle = OccurrenceLifecycle.COMPLETED
                occurrences[occurrence_id] = replace(occurrence, progress=updated, lifecycle=lifecycle)
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
            occurrences=occurrences,
            offers=dict(current.offers),
            primary_occurrence=dict(current.primary_occurrence),
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
        occurrences: dict[str, TaskOccurrence] | None = None,
        offers: dict[str, Offer] | None = None,
        primary_occurrence: dict[tuple[str, str], str] | None = None,
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
        carried = self._carry_occurrences(
            occurrences or {},
            progress,
            primary_occurrence or {},
            config.completion_tolerance,
        )
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
            occurrences=carried,
            offers=dict(offers or {}),
            primary_occurrence=dict(primary_occurrence or {}),
        )

    def open_occurrence(self, deal_id: str, task_id: str) -> TaskOccurrence:
        """Append a scheduled occurrence of an existing task type. Does not add an offer or an edge."""

        state = self._require_state()
        key = (deal_id, task_id)
        if key not in self.scenario.task_keys():
            raise ValueError(f"unknown task {deal_id}:{task_id}")
        existing = sum(
            1
            for occurrence in state.occurrences.values()
            if occurrence.deal_id == deal_id and occurrence.task_id == task_id
        )
        occurrence = TaskOccurrence(
            occurrence_id=f"{deal_id}:{task_id}#{existing + 1}",
            deal_id=deal_id,
            task_id=task_id,
            lifecycle=OccurrenceLifecycle.SCHEDULED,
            progress=0.0,
            offer_id=None,
            readiness_source=ReadinessSource.UNRESOLVED,
        )
        state.occurrences[occurrence.occurrence_id] = occurrence
        return occurrence

    def set_lifecycle(self, occurrence_id: str, lifecycle: OccurrenceLifecycle) -> TaskOccurrence:
        """Record a lifecycle. Abort and withdraw do not set progress to 1."""

        state = self._require_state()
        current = state.occurrences.get(occurrence_id)
        if current is None:
            raise KeyError(occurrence_id)
        if not isinstance(lifecycle, OccurrenceLifecycle):
            raise TypeError("lifecycle must be an OccurrenceLifecycle")
        updated = replace(current, lifecycle=lifecycle)
        state.occurrences[occurrence_id] = updated
        return updated

    def declare_ready(self, occurrence_id: str) -> TaskOccurrence:
        """Fixture declaration that this extra occurrence may receive progress.

        This is not a predecessor rule. Primary occurrences keep type-level AND-min.
        """

        state = self._require_state()
        current = state.occurrences.get(occurrence_id)
        if current is None:
            raise KeyError(occurrence_id)
        if state.primary_occurrence.get((current.deal_id, current.task_id)) == occurrence_id:
            raise ValueError("primary occurrence readiness stays on the type DAG")
        updated = replace(current, readiness_source=ReadinessSource.DECLARED)
        state.occurrences[occurrence_id] = updated
        return updated

    def record_offer(self, case_id: str, offer_id: str) -> Offer | None:
        """Store an offer only when OfferID is non-empty. Workflow occurrences are not attached."""

        state = self._require_state()
        if case_id not in self.scenario.deals:
            raise ValueError(f"unknown case {case_id}")
        if not offer_id or not offer_id.strip():
            return None
        existing = state.offers.get(offer_id)
        if existing is not None:
            if existing.case_id != case_id:
                raise ValueError(f"offer {offer_id} already belongs to {existing.case_id}")
            return existing
        offer = Offer(offer_id=offer_id, case_id=case_id)
        state.offers[offer_id] = offer
        return offer

    def _require_state(self) -> PortfolioState:
        if self._state is None:
            raise RuntimeError("reset() has not been called")
        return self._state

    def _initial_occurrences(
        self, progress: dict[tuple[str, str], float]
    ) -> tuple[dict[str, TaskOccurrence], dict[tuple[str, str], str]]:
        tolerance = self.scenario.simulation.completion_tolerance
        occurrences: dict[str, TaskOccurrence] = {}
        primary: dict[tuple[str, str], str] = {}
        for (deal_id, task_id), value in progress.items():
            occurrence_id = f"{deal_id}:{task_id}#1"
            lifecycle = (
                OccurrenceLifecycle.COMPLETED
                if is_complete(value, tolerance)
                else OccurrenceLifecycle.ACTIVE
            )
            occurrences[occurrence_id] = TaskOccurrence(
                occurrence_id=occurrence_id,
                deal_id=deal_id,
                task_id=task_id,
                lifecycle=lifecycle,
                progress=value,
            )
            primary[(deal_id, task_id)] = occurrence_id
        return occurrences, primary

    def _carry_occurrences(
        self,
        occurrences: dict[str, TaskOccurrence],
        progress: dict[tuple[str, str], float],
        primary: dict[tuple[str, str], str],
        tolerance: float,
    ) -> dict[str, TaskOccurrence]:
        carried: dict[str, TaskOccurrence] = {}
        for occurrence_id, occurrence in occurrences.items():
            key = (occurrence.deal_id, occurrence.task_id)
            if primary.get(key) != occurrence_id:
                carried[occurrence_id] = occurrence
                continue
            value = progress[key]
            lifecycle = occurrence.lifecycle
            if lifecycle is OccurrenceLifecycle.ACTIVE and is_complete(value, tolerance):
                lifecycle = OccurrenceLifecycle.COMPLETED
            carried[occurrence_id] = replace(occurrence, progress=value, lifecycle=lifecycle)
        return carried

    def _reason(self, state: PortfolioState) -> str | None:
        reasons: list[str] = []
        if state.deal_complete and all(value == 1 for value in state.deal_complete.values()):
            reasons.append("all_deals_complete")
        if state.time >= self.scenario.horizon:
            reasons.append("horizon")
        if not reasons:
            return None
        return "+".join(reasons)


def _receives_progress(occurrence: TaskOccurrence, state: PortfolioState, scenario: Scenario) -> bool:
    """Whether this step may add progress. Suspended and unresolved occurrences may not.

    A primary occurrence that is active still uses the type-level formula, including
    a readiness of zero. That keeps a blocked allocation from moving progress and
    from being recorded as waste.
    """

    if occurrence.lifecycle is not OccurrenceLifecycle.ACTIVE:
        return False
    if occurrence.readiness_source is ReadinessSource.UNRESOLVED:
        return False
    if occurrence.readiness_source is ReadinessSource.DECLARED:
        return True
    key = (occurrence.deal_id, occurrence.task_id)
    return not is_complete(state.task_progress[key], scenario.simulation.completion_tolerance)
