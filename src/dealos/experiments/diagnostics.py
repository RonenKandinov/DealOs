"""Trajectory diagnostics for an existing rollout.

These calculations read a scenario, a progress vector, and the actions a policy
already chose. They do not change dynamics, policies, capacities, horizons, or
the objective, which remains the number of completed deals.

Definitions
-----------
Target vs non-target progress
    Unweighted mean of task progress at the horizon. A task is a target when it
    belongs to its deal's target set. Each task is one observation. Progress is
    not weighted by phi, alpha, or deal size.

Task-state buckets
    Share of tasks with progress <= 0, progress strictly between 0 and
    completion, and progress within the simulator's completion tolerance of 1.
    The completion bucket uses the same ``is_complete`` rule as deal completion.

Critical path of an unfinished deal
    For each target, the longest predecessor chain (most edges). A source has
    depth 0. Walking backward, the predecessor on that chain is the one whose
    depth is exactly one less. Ties go to the larger remaining gap ``1 - x``,
    then to the lexicographically larger task id. The deal's critical path is
    the target path with the largest remaining work, then the larger target id.
    Remaining work is the sum of ``max(0, 1 - x)`` along that path, including
    the target.

Unfinished-deal labels, applied only when at least one target is incomplete:
    A. Every target task has progress >= 0.8.
    B. Otherwise, some non-target task on a longest path to a target has depth
       <= 1 and progress < 0.5.
    C. Otherwise mixed: the deal is unfinished, targets are below 0.8, and the
       longest paths are not held by that early-predecessor condition.
    Label A is checked first. A finished deal is not labeled.

Resource idle, measured at decision time (start-of-step progress) for each
resource with positive capacity. The three parts sum to that capacity:
    allocated
        Sum of ``a`` on this resource.
    unused, no compatible eligible work
        Capacity minus allocated, when no incomplete task has readiness above
        the blockage threshold and suitability ``q > 0`` for this resource.
        Eligibility matches ``eligible_tasks``.
    unused, despite eligible work
        Capacity minus allocated, when at least one such task exists.
    Resources with zero capacity are omitted from the averages. Averages are
    the mean over steps of each resource, then the mean across resources.
    This does not replace utilization.

Allocation concentration
    On a step with positive total allocation, group ``a`` by task (summed over
    resources), divide by the step's total allocation, and take the Herfindahl
    index, the sum of squared shares. One task receiving the whole allocation
    has index 1. Equal shares across ``n`` tasks have index ``1/n``. Steps with
    no allocation are omitted from the Herfindahl mean. The mean number of
    tasks with positive allocation includes steps with none, as zero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from dealos.domain.dynamics import is_complete
from dealos.domain.graph import predecessors
from dealos.domain.models import AllocationAction, DealGraph, Scenario
from dealos.experiments.structure import task_depth
from dealos.policies.base import Policy, readiness_of
from dealos.sim.env import SalesEnvironment

NEAR_TARGET_PROGRESS = 0.8
EARLY_INCOMPLETE_PROGRESS = 0.5
EARLY_DEPTH_AT_MOST = 1


@dataclass(frozen=True)
class ResourceIdle:
    """One resource at one decision. The three amounts sum to its capacity."""

    allocated: float
    unused_no_eligible: float
    unused_despite_eligible: float


@dataclass(frozen=True)
class StepConcentration:
    """``herfindahl`` is None when the step allocates nothing."""

    herfindahl: float | None
    tasks_with_allocation: int


@dataclass(frozen=True)
class UnfinishedDealDiagnosis:
    deal_id: str
    label: str
    min_target_progress: float
    mean_target_progress: float
    critical_path: tuple[str, ...]
    critical_residual: float
    early_hold: bool
    front_progress: float | None


@dataclass(frozen=True)
class RunDiagnosis:
    preset: str
    seed: int
    policy: str
    completed_deals: int
    steps: int
    mean_target_progress: float | None
    mean_nontarget_progress: float | None
    n_target_tasks: int
    n_nontarget_tasks: int
    fraction_zero: float
    fraction_partial: float
    fraction_one: float
    unfinished: tuple[UnfinishedDealDiagnosis, ...]
    mean_allocated_fraction: float
    mean_unused_no_eligible_fraction: float
    mean_unused_despite_eligible_fraction: float
    idle_fractions_by_resource: dict[str, tuple[float, float, float]]
    mean_herfindahl: float | None
    mean_tasks_with_allocation: float


def task_buckets(progress_values: Sequence[float], completion_tolerance: float) -> tuple[float, float, float]:
    """Fractions ``(x <= 0, 0 < x < complete, complete)``."""

    count = len(progress_values)
    if count == 0:
        return (0.0, 0.0, 0.0)
    zeros = 0
    partials = 0
    ones = 0
    for value in progress_values:
        if value <= 0.0:
            zeros += 1
        elif is_complete(value, completion_tolerance):
            ones += 1
        else:
            partials += 1
    return (zeros / count, partials / count, ones / count)


def mean_progress(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def step_idle(
    scenario: Scenario,
    progress: Mapping[tuple[str, str], float],
    action: AllocationAction,
    capacities: Mapping[str, float] | None = None,
) -> dict[str, ResourceIdle]:
    """Split each resource's capacity at the progress vector the policy saw."""

    caps = capacities if capacities is not None else {
        resource_id: resource.capacity for resource_id, resource in scenario.resources.items()
    }
    used = action.used_by_resource()
    parts: dict[str, ResourceIdle] = {}
    for resource_id, capacity in caps.items():
        allocated = used.get(resource_id, 0.0)
        slack = capacity - allocated
        if _has_compatible_eligible(scenario, progress, resource_id):
            parts[resource_id] = ResourceIdle(allocated, 0.0, slack)
        else:
            parts[resource_id] = ResourceIdle(allocated, slack, 0.0)
    return parts


def step_concentration(action: AllocationAction) -> StepConcentration:
    """Herfindahl of task shares of this step's total allocation."""

    mass_by_task: dict[tuple[str, str], float] = {}
    for (deal_id, task_id, _), amount in action.allocations.items():
        if amount <= 0.0:
            continue
        key = (deal_id, task_id)
        mass_by_task[key] = mass_by_task.get(key, 0.0) + amount
    total = sum(mass_by_task.values())
    if total <= 0.0:
        return StepConcentration(None, 0)
    herfindahl = sum((amount / total) ** 2 for amount in mass_by_task.values())
    return StepConcentration(herfindahl, len(mass_by_task))


def inspect_unfinished(
    scenario: Scenario,
    progress: Mapping[tuple[str, str], float],
) -> tuple[UnfinishedDealDiagnosis, ...]:
    """Critical-path residual and A/B/C label for every unfinished deal."""

    records: list[UnfinishedDealDiagnosis] = []
    for deal_id in sorted(scenario.deals):
        deal = scenario.deals[deal_id]
        if _deal_finished(scenario, deal, progress):
            continue
        records.append(_diagnose_deal(scenario, deal, progress))
    return tuple(records)


def diagnose_actions(scenario: Scenario, actions: Sequence[AllocationAction]) -> RunDiagnosis:
    """Apply an explicit action list, then diagnose. Stops early if the episode ends."""

    env = SalesEnvironment(scenario)
    state = env.reset()
    applied: list[tuple[dict[tuple[str, str], float], AllocationAction, dict[str, float]]] = []
    for action in actions:
        if env.is_done():
            break
        applied.append((dict(state.task_progress), action, dict(state.capacities)))
        state, _info = env.step(action)
    return _assemble(scenario, "fixed_actions", state.task_progress, state.deal_complete, applied)


def diagnose_rollout(scenario: Scenario, policy: Policy) -> RunDiagnosis:
    """Roll out ``policy`` with the same step loop as ``rollout``, and diagnose it."""

    env = SalesEnvironment(scenario)
    state = env.reset()
    applied: list[tuple[dict[tuple[str, str], float], AllocationAction, dict[str, float]]] = []
    while not env.is_done():
        action = policy.select_action(state, scenario)
        applied.append((dict(state.task_progress), action, dict(state.capacities)))
        state, _info = env.step(action)
    return _assemble(scenario, policy.name, state.task_progress, state.deal_complete, applied)


def _assemble(
    scenario: Scenario,
    policy_name: str,
    progress: Mapping[tuple[str, str], float],
    deal_complete: Mapping[str, int],
    applied: Sequence[tuple[Mapping[tuple[str, str], float], AllocationAction, Mapping[str, float]]],
) -> RunDiagnosis:
    tolerance = scenario.simulation.completion_tolerance
    target_values: list[float] = []
    nontarget_values: list[float] = []
    for deal_id, deal in scenario.deals.items():
        for task_id in deal.tasks:
            value = progress[(deal_id, task_id)]
            if task_id in deal.targets:
                target_values.append(value)
            else:
                nontarget_values.append(value)
    buckets = task_buckets([progress[key] for key in scenario.task_keys()], tolerance)
    idle_means, overall = _mean_idle(applied, scenario)
    herfindahl, mean_tasks = _mean_concentration(applied)
    return RunDiagnosis(
        preset=scenario.generator.name,
        seed=scenario.seed,
        policy=policy_name,
        completed_deals=sum(deal_complete.values()),
        steps=len(applied),
        mean_target_progress=mean_progress(target_values),
        mean_nontarget_progress=mean_progress(nontarget_values),
        n_target_tasks=len(target_values),
        n_nontarget_tasks=len(nontarget_values),
        fraction_zero=buckets[0],
        fraction_partial=buckets[1],
        fraction_one=buckets[2],
        unfinished=inspect_unfinished(scenario, progress),
        mean_allocated_fraction=overall[0],
        mean_unused_no_eligible_fraction=overall[1],
        mean_unused_despite_eligible_fraction=overall[2],
        idle_fractions_by_resource=idle_means,
        mean_herfindahl=herfindahl,
        mean_tasks_with_allocation=mean_tasks,
    )


def _mean_idle(
    applied: Sequence[tuple[Mapping[tuple[str, str], float], AllocationAction, Mapping[str, float]]],
    scenario: Scenario,
) -> tuple[dict[str, tuple[float, float, float]], tuple[float, float, float]]:
    sums: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    for progress, action, capacities in applied:
        for resource_id, part in step_idle(scenario, progress, action, capacities).items():
            capacity = capacities[resource_id]
            if capacity <= 0.0:
                continue
            fractions = (
                part.allocated / capacity,
                part.unused_no_eligible / capacity,
                part.unused_despite_eligible / capacity,
            )
            if resource_id not in sums:
                sums[resource_id] = [0.0, 0.0, 0.0]
                counts[resource_id] = 0
            for index, value in enumerate(fractions):
                sums[resource_id][index] += value
            counts[resource_id] += 1
    means = {
        resource_id: (
            sums[resource_id][0] / counts[resource_id],
            sums[resource_id][1] / counts[resource_id],
            sums[resource_id][2] / counts[resource_id],
        )
        for resource_id in sorted(sums)
    }
    if not means:
        return means, (0.0, 0.0, 0.0)
    overall = tuple(sum(item[index] for item in means.values()) / len(means) for index in range(3))
    return means, (overall[0], overall[1], overall[2])


def _mean_concentration(
    applied: Sequence[tuple[Mapping[tuple[str, str], float], AllocationAction, Mapping[str, float]]],
) -> tuple[float | None, float]:
    if not applied:
        return None, 0.0
    herfindahls: list[float] = []
    task_counts: list[int] = []
    for _progress, action, _capacities in applied:
        step = step_concentration(action)
        task_counts.append(step.tasks_with_allocation)
        if step.herfindahl is not None:
            herfindahls.append(step.herfindahl)
    mean_tasks = sum(task_counts) / len(task_counts)
    if not herfindahls:
        return None, mean_tasks
    return sum(herfindahls) / len(herfindahls), mean_tasks


def _has_compatible_eligible(
    scenario: Scenario,
    progress: Mapping[tuple[str, str], float],
    resource_id: str,
) -> bool:
    threshold = scenario.simulation.blocked_readiness_threshold
    tolerance = scenario.simulation.completion_tolerance
    for deal_id, task_id in scenario.task_keys():
        if is_complete(progress[(deal_id, task_id)], tolerance):
            continue
        if readiness_of(scenario, progress, deal_id, task_id) <= threshold:
            continue
        if scenario.suitability.get((deal_id, task_id, resource_id), 0.0) > 0.0:
            return True
    return False


def _deal_finished(
    scenario: Scenario,
    deal: DealGraph,
    progress: Mapping[tuple[str, str], float],
) -> bool:
    tolerance = scenario.simulation.completion_tolerance
    return all(
        is_complete(progress[(deal.deal_id, target)], tolerance) for target in deal.targets
    )


def _diagnose_deal(
    scenario: Scenario,
    deal: DealGraph,
    progress: Mapping[tuple[str, str], float],
) -> UnfinishedDealDiagnosis:
    depths = _depths(deal)
    paths = {
        target: _longest_path(deal, target, progress, depths) for target in deal.targets
    }
    target_values = [progress[(deal.deal_id, target)] for target in deal.targets]
    chosen = max(deal.targets, key=lambda target: (_residual(deal.deal_id, paths[target], progress), target))
    front_values = [
        value
        for target in deal.targets
        for value in _front_progresses(deal, paths[target], progress, depths)
    ]
    early = any(value < EARLY_INCOMPLETE_PROGRESS for value in front_values)
    if target_values and all(value >= NEAR_TARGET_PROGRESS for value in target_values):
        label = "A"
    elif early:
        label = "B"
    else:
        label = "C"
    return UnfinishedDealDiagnosis(
        deal_id=deal.deal_id,
        label=label,
        min_target_progress=min(target_values),
        mean_target_progress=sum(target_values) / len(target_values),
        critical_path=paths[chosen],
        critical_residual=_residual(deal.deal_id, paths[chosen], progress),
        early_hold=early,
        front_progress=(min(front_values) if front_values else None),
    )


def _depths(deal: DealGraph) -> dict[str, int]:
    memo: dict[str, int] = {}
    for task_id in deal.tasks:
        task_depth(deal.edges, task_id, memo)
    return memo


def _longest_path(
    deal: DealGraph,
    target_id: str,
    progress: Mapping[tuple[str, str], float],
    depths: Mapping[str, int],
) -> tuple[str, ...]:
    chain = [target_id]
    current = target_id
    while depths[current] > 0:
        needed = depths[current] - 1
        candidates = [pred for pred in predecessors(deal.edges, current) if depths[pred] == needed]
        chosen = max(
            candidates,
            key=lambda pred: (1.0 - progress[(deal.deal_id, pred)], pred),
        )
        chain.append(chosen)
        current = chosen
    chain.reverse()
    return tuple(chain)


def _residual(
    deal_id: str,
    path: Sequence[str],
    progress: Mapping[tuple[str, str], float],
) -> float:
    return sum(max(0.0, 1.0 - progress[(deal_id, task_id)]) for task_id in path)


def _front_progresses(
    deal: DealGraph,
    path: Sequence[str],
    progress: Mapping[tuple[str, str], float],
    depths: Mapping[str, int],
) -> list[float]:
    """Progress of non-target tasks on ``path`` whose depth is 0 or 1."""

    values: list[float] = []
    for task_id in path:
        if task_id in deal.targets:
            continue
        if depths[task_id] > EARLY_DEPTH_AT_MOST:
            continue
        values.append(progress[(deal.deal_id, task_id)])
    return values
