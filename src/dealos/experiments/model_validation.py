"""Model-validation screens. V1 dynamics, policies, and the generator stay frozen.

Every new mechanism is a wrapper around a copied scenario. ``assert_only_changed``
runs before a rollout. Observation noise is never written back into the
environment that steps.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from dealos.domain.models import AllocationAction, DealGraph, Scenario
from dealos.experiments.controlled import (
    assert_only_changed,
    baseline_scenario,
    graph_summary,
)
from dealos.experiments.diagnostics import inspect_unfinished, step_concentration, step_idle
from dealos.experiments.metrics import format_metric, summarize_metric
from dealos.experiments.runner import default_policy_factories
from dealos.experiments.structure import task_depth
from dealos.generator.generate import _specs
from dealos.policies.base import eligible_tasks
from dealos.sim.env import SalesEnvironment

SCREEN_SEEDS = tuple(range(50))
BASELINE_SEEDS = tuple(range(20))
WAIT_DAYS = 10
REWORK_DROP = 0.25


@dataclass
class Trajectory:
    seed: int
    policy: str
    completed: int
    completion_times: dict[str, int | None]
    target_progress: float
    residual_all: float
    blocked_steps: int
    wasted: float
    utilization: float
    herfindahl: float | None
    idle_despite: float
    steps: int
    rework_count: int = 0


def task_order(deal: DealGraph) -> list[str]:
    """Kept tasks in the fixed template order."""

    names = {task.name for task in deal.tasks.values()}
    return [f"{deal.deal_id}:{spec.name}" for spec in _specs() if spec.name in names]


def matched_edges(deal: DealGraph, kind: str) -> frozenset[tuple[str, str]] | None:
    """Skeleton plus filler forward edges so the edge count matches the deal.

    Returns None when the skeleton already has more edges than the baseline
    deal, because the task set would have to shrink to make the counts match.
    """

    order = task_order(deal)
    target = len(deal.edges)
    if kind == "chain":
        skeleton = {(order[i], order[i + 1]) for i in range(len(order) - 1)}
    elif kind == "hub":
        skeleton = {(order[0], other) for other in order[1:]}
    elif kind == "convergence":
        skeleton = _convergence_skeleton(order)
        if skeleton is None:
            return None
    else:
        raise ValueError(kind)
    return _fill_to_count(order, skeleton, target)


def with_topology(scenario: Scenario, kind: str) -> Scenario | None:
    """Replace edges only. None means the edge count could not be matched."""

    deals: dict[str, DealGraph] = {}
    for deal_id, deal in scenario.deals.items():
        edges = matched_edges(deal, kind)
        if edges is None:
            return None
        deals[deal_id] = DealGraph(
            deal_id=deal.deal_id,
            tasks=dict(deal.tasks),
            edges=edges,
            targets=frozenset(deal.targets),
        )
    variant = replace(scenario, deals=deals)
    assert_only_changed(scenario, variant, ("edges:",))
    return variant


def zero_task_q(scenario: Scenario, tasks: set[tuple[str, str]]) -> Scenario:
    """Set q to 0 on the named tasks. Every other suitability entry stays."""

    suitability = {
        key: (0.0 if (key[0], key[1]) in tasks else value)
        for key, value in scenario.suitability.items()
    }
    variant = replace(scenario, suitability=suitability)
    assert_only_changed(scenario, variant, ("q",))
    return variant


def rollout(
    scenario: Scenario,
    policy,
    *,
    rework_rate: float = 0.0,
    rework_seed: int = 0,
    external: set[tuple[str, str]] | None = None,
    wait_days: int = WAIT_DAYS,
) -> Trajectory:
    """V1 step loop plus optional experiment-only rework or external-wait jumps.

    Rework and external completion are applied after ``env.step``. They do not
    call ``apply_progress``. ``rework_rate == 0`` and ``external is None`` is
    the frozen trajectory.
    """

    env = SalesEnvironment(scenario)
    env.reset()
    rng = random.Random(f"{rework_seed}:{rework_rate}:rework")
    blocked = 0
    wasted = 0.0
    util_sum = 0.0
    despite_sum = 0.0
    herfindahls: list[float] = []
    steps = 0
    rework_count = 0
    banned = external or set()
    while not env.is_done():
        state = env.get_state()
        action = policy.select_action(state, scenario)
        if banned:
            action = _strip(action, banned)
        _state, info = env.step(action)
        steps += 1
        blocked += info.blocked_count
        wasted += info.wasted_allocation
        if info.utilization:
            util_sum += sum(info.utilization.values()) / len(info.utilization)
        despite_sum += _despite_fraction(scenario, state.task_progress, action)
        concentration = step_concentration(action)
        if concentration.herfindahl is not None:
            herfindahls.append(concentration.herfindahl)
        if banned and env._state is not None and env._state.time >= wait_days:
            _complete_tasks(env, banned)
        if rework_rate > 0.0 and rng.random() < rework_rate:
            if _rework_one(env, rng):
                rework_count += 1
    final = env.get_state()
    return Trajectory(
        seed=scenario.seed,
        policy=policy.name,
        completed=sum(final.deal_complete.values()),
        completion_times=dict(final.deal_completed_at),
        target_progress=_target_mean(scenario, final.task_progress),
        residual_all=_residual_all(scenario, final.task_progress),
        blocked_steps=blocked,
        wasted=wasted,
        utilization=util_sum / steps if steps else 0.0,
        herfindahl=(sum(herfindahls) / len(herfindahls) if herfindahls else None),
        idle_despite=despite_sum / steps if steps else 0.0,
        steps=steps,
        rework_count=rework_count,
    )


def observed_progress(
    progress: dict[tuple[str, str], float],
    mode: str,
    epsilon: float,
    seed: int,
) -> dict[tuple[str, str], float]:
    """Copy progress. The input mapping is not modified."""

    rng = random.Random(f"{seed}:{mode}:{epsilon}:observe")
    observed: dict[tuple[str, str], float] = {}
    for key, value in progress.items():
        if mode == "exact":
            observed[key] = value
        elif mode == "noise":
            observed[key] = _clip(value + rng.uniform(-epsilon, epsilon))
        elif mode == "interval":
            low = _clip(value - epsilon)
            high = _clip(value + epsilon)
            observed[key] = (low + high) / 2.0
        elif mode == "bias":
            observed[key] = _clip(value + epsilon)
        else:
            raise ValueError(mode)
    return observed


def decision_view(scenario: Scenario, progress: dict[tuple[str, str], float], policy) -> dict[str, object]:
    """Diagnostics and one action on a progress copy. Does not step the scenario."""

    env = SalesEnvironment(scenario)
    env.reset()
    true = dict(env.get_state().task_progress)
    _install_progress(env, dict(progress))
    state = env.get_state()
    action = policy.select_action(state, scenario)
    paths = tuple(
        (deal.deal_id, deal.critical_path, deal.label) for deal in inspect_unfinished(scenario, state.task_progress)
    )
    return {
        "paths": paths,
        "eligible": tuple(eligible_tasks(state, scenario)),
        "action": tuple(sorted((key, round(value, 6)) for key, value in action.allocations.items() if value > 0)),
        "true_unchanged": true == dict(SalesEnvironment(scenario).reset().task_progress),
    }


def deadline_for(deal_id: str) -> int:
    return 30 + 15 * int(deal_id.split("_")[1])


def value_for(deal_id: str) -> float:
    return float(int(deal_id.split("_")[1]) + 1)


def score_trajectory(row: Trajectory) -> dict[str, float]:
    """Four scores of one recorded trajectory. The simulator objective stays Σ y_i."""

    days = [day for day in row.completion_times.values() if day is not None]
    on_time = 0
    value = 0.0
    for deal_id, day in row.completion_times.items():
        if day is None:
            continue
        if day <= deadline_for(deal_id):
            on_time += 1
        value += value_for(deal_id)
    return {
        "count": float(row.completed),
        "time": statistics.fmean(days) if days else float("nan"),
        "deadline": float(on_time),
        "value": value,
    }


def _convergence_skeleton(order: list[str]) -> set[tuple[str, str]] | None:
    if len(order) < 3:
        return None
    join = order[-1]
    prefix = order[:-1]
    mid = len(prefix) // 2
    if mid == 0 or mid == len(prefix):
        return None
    edges: set[tuple[str, str]] = set()
    for group in (prefix[:mid], prefix[mid:]):
        for left, right in zip(group, group[1:]):
            edges.add((left, right))
        edges.add((group[-1], join))
    return edges


def _fill_to_count(
    order: list[str],
    skeleton: set[tuple[str, str]],
    target: int,
) -> frozenset[tuple[str, str]] | None:
    edges = set(skeleton)
    if len(edges) > target:
        return None
    gap = 2
    while len(edges) < target and gap < len(order):
        for index in range(len(order) - gap):
            candidate = (order[index], order[index + gap])
            if candidate in edges:
                continue
            edges.add(candidate)
            if len(edges) == target:
                return frozenset(edges)
        gap += 1
    if len(edges) != target:
        return None
    return frozenset(edges)


def _strip(action: AllocationAction, banned: set[tuple[str, str]]) -> AllocationAction:
    from dealos.domain.models import task_of_occurrence

    return AllocationAction(
        {
            key: value
            for key, value in action.allocations.items()
            if (key[0], task_of_occurrence(key[0], key[1])) not in banned and value > 0.0
        }
    )


def _despite_fraction(scenario: Scenario, progress, action: AllocationAction) -> float:
    parts = step_idle(scenario, progress, action)
    fractions = []
    for resource_id, part in parts.items():
        capacity = scenario.resources[resource_id].capacity
        if capacity <= 0.0:
            continue
        fractions.append(part.unused_despite_eligible / capacity)
    if not fractions:
        return 0.0
    return sum(fractions) / len(fractions)


def _install_progress(env: SalesEnvironment, progress: dict[tuple[str, str], float]) -> None:
    current = env._state
    if current is None:
        raise RuntimeError("environment has no state")
    env._state = env._derive(
        progress=progress,
        time=current.time,
        allocations=dict(current.allocations),
        previous_ready_since=dict(current.ready_since),
        previous_task_completed_at=dict(current.task_completed_at),
        previous_deal_completed_at=dict(current.deal_completed_at),
    )
    env._done_reason = env._reason(env._state)


def _complete_tasks(env: SalesEnvironment, tasks: set[tuple[str, str]]) -> None:
    if env._state is None:
        return
    progress = dict(env._state.task_progress)
    changed = False
    for key in tasks:
        if key in progress and progress[key] < 1.0:
            progress[key] = 1.0
            changed = True
    if changed:
        _install_progress(env, progress)


def _rework_one(env: SalesEnvironment, rng: random.Random) -> bool:
    if env._state is None:
        return False
    progress = dict(env._state.task_progress)
    candidates = [key for key, value in progress.items() if value > 0.0]
    if not candidates:
        return False
    key = candidates[rng.randrange(len(candidates))]
    progress[key] = max(0.0, progress[key] - REWORK_DROP)
    _install_progress(env, progress)
    return True


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


def _target_mean(scenario: Scenario, progress) -> float:
    values = [
        progress[(deal_id, task_id)]
        for deal_id, deal in scenario.deals.items()
        for task_id in deal.targets
    ]
    return sum(values) / len(values) if values else 0.0


def _residual_all(scenario: Scenario, progress) -> float:
    unfinished = inspect_unfinished(scenario, progress)
    n_deals = len(scenario.deals)
    if n_deals == 0:
        return 0.0
    return sum(deal.critical_residual for deal in unfinished) / n_deals


def _max_depth(scenario: Scenario) -> float:
    deepest = 0
    for deal in scenario.deals.values():
        memo: dict[str, int] = {}
        for task_id in deal.tasks:
            deepest = max(deepest, task_depth(deal.edges, task_id, memo))
    return float(deepest)


def critical_and_other(scenario: Scenario) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Tasks on a longest path to an unfinished target, and the rest."""

    progress = dict(scenario.initial_progress)
    on_path: set[tuple[str, str]] = set()
    for deal in inspect_unfinished(scenario, progress):
        for task_id in deal.critical_path:
            on_path.add((deal.deal_id, task_id))
    other = [key for key in scenario.task_keys() if key not in on_path]
    return sorted(on_path), other


def first_controllable(scenario: Scenario, tasks: Sequence[tuple[str, str]]) -> tuple[str, str] | None:
    for deal_id, task_id in tasks:
        if any(scenario.suitability[(deal_id, task_id, resource_id)] > 0.0 for resource_id in scenario.resources):
            return (deal_id, task_id)
    return None


def summarize_rows(rows: Sequence[Trajectory]) -> str:
    if not rows:
        return "n=0"
    completed = summarize_metric([float(row.completed) for row in rows])
    days = [float(day) for row in rows for day in row.completion_times.values() if day is not None]
    day_text = "no finished deals" if not days else format_metric(summarize_metric(days))
    median = "na" if not days else f"{statistics.median(days):.2f}"
    return (
        f"completed {format_metric(completed)}; "
        f"completion_day {day_text} median={median}; "
        f"target {format_metric(summarize_metric([row.target_progress for row in rows]))}; "
        f"residual_all {format_metric(summarize_metric([row.residual_all for row in rows]))}; "
        f"blocked_steps {format_metric(summarize_metric([float(row.blocked_steps) for row in rows]))}; "
        f"utilization {format_metric(summarize_metric([row.utilization for row in rows]))}; "
        f"idle_despite {format_metric(summarize_metric([row.idle_despite for row in rows]))}; "
        f"herfindahl {_optional_metric([row.herfindahl for row in rows])}; "
        f"rework {format_metric(summarize_metric([float(row.rework_count) for row in rows]))}; "
        f"wasted {format_metric(summarize_metric([row.wasted for row in rows]))}"
    )


def _optional_metric(values: Sequence[float | None]) -> str:
    present = [float(value) for value in values if value is not None]
    if not present:
        return "n=0"
    return format_metric(summarize_metric(present))


def run_policies(
    scenario_for: Callable[[int], Scenario | None],
    seeds: Sequence[int],
    **rollout_kwargs,
) -> list[Trajectory] | str:
    """Roll out every policy. A string return is an isolation stop, not a result."""

    rows: list[Trajectory] = []
    factories = default_policy_factories()
    for seed in seeds:
        scenario = scenario_for(seed)
        if scenario is None:
            return f"seed {seed} could not isolate the intended variable"
        for factory in factories:
            rows.append(rollout(scenario, factory(seed), rework_seed=seed, **rollout_kwargs))
    return rows


def moved(control: list[Trajectory], other: list[Trajectory]) -> bool:
    """True when completed deals, completion day, or residual differ past a small band."""

    for policy in ("fifo", "bottleneck"):
        left = [row for row in control if row.policy == policy]
        right = [row for row in other if row.policy == policy]
        if not left or not right:
            continue
        if abs(_mean(row.completed for row in left) - _mean(row.completed for row in right)) >= 0.25:
            return True
        if abs(_mean(row.residual_all for row in left) - _mean(row.residual_all for row in right)) >= 0.25:
            return True
        left_days = [float(day) for row in left for day in row.completion_times.values() if day is not None]
        right_days = [float(day) for row in right for day in row.completion_times.values() if day is not None]
        if left_days and right_days and abs(statistics.fmean(left_days) - statistics.fmean(right_days)) >= 2.0:
            return True
    return False


def _mean(values) -> float:
    numbers = [float(value) for value in values]
    return statistics.fmean(numbers) if numbers else 0.0


def format_policy_block(title: str, rows: list[Trajectory]) -> str:
    lines = [title]
    for policy in ("random", "fifo", "bottleneck"):
        group = [row for row in rows if row.policy == policy]
        lines.append(f"  {policy}: {summarize_rows(group)}")
    return "\n".join(lines)


def graph_line(label: str, scenario: Scenario) -> str:
    summary = graph_summary(scenario)
    return (
        f"{label}: edges={summary['edges']:.0f} mean_depth={summary['mean_depth']:.3f} "
        f"max_depth={_max_depth(scenario):.0f} in={summary['mean_in_degree']:.3f}"
    )
