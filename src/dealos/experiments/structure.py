"""Measured structure of generated scenarios. Preset names are not treated as evidence."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from dealos.domain.graph import has_cycle, predecessors
from dealos.domain.models import Scenario, TaskStatus
from dealos.sim.env import SalesEnvironment


def task_depth(edges: frozenset[tuple[str, str]], task_id: str, memo: dict[str, int]) -> int:
    """Edges on the longest path from a source to this task. Sources have depth 0."""

    if task_id in memo:
        return memo[task_id]
    preds = predecessors(edges, task_id)
    if not preds:
        memo[task_id] = 0
        return 0
    depth = 1 + max(task_depth(edges, pred, memo) for pred in preds)
    memo[task_id] = depth
    return depth


@dataclass(frozen=True)
class ScenarioStructure:
    preset: str
    seed: int
    n_deals: int
    n_tasks: int
    n_edges: int
    tasks_per_deal: float
    mean_dependency_depth: float
    max_dependency_depth: int
    edges_per_task: float
    tasks_by_type: dict[str, int]
    capacities: dict[str, float]
    q_zero_by_resource: dict[str, int]
    initially_completed: int
    initially_blocked: int
    is_dag: bool
    deals_missing_targets: int


def measure_scenario(scenario: Scenario) -> ScenarioStructure:
    """Count tasks, edges, depth, capacities, q=0 pairs, and the initial blocked set.

    Initial status comes from SalesEnvironment.reset(), so "blocked" means the
    simulator's rule: incomplete and readiness at or below the configured threshold.
    """

    n_tasks = 0
    n_edges = 0
    depths: list[int] = []
    tasks_by_type: dict[str, int] = {}
    missing_targets = 0
    acyclic = True
    for deal in scenario.deals.values():
        n_tasks += len(deal.tasks)
        n_edges += len(deal.edges)
        if not deal.targets:
            missing_targets += 1
        if has_cycle(set(deal.tasks), deal.edges):
            acyclic = False
        memo: dict[str, int] = {}
        for task_id in deal.tasks:
            depths.append(task_depth(deal.edges, task_id, memo))
            task_type = deal.tasks[task_id].task_type
            tasks_by_type[task_type] = tasks_by_type.get(task_type, 0) + 1
    q_zero = {resource_id: 0 for resource_id in scenario.resources}
    for (_deal_id, _task_id, resource_id), suitability in scenario.suitability.items():
        if suitability == 0.0:
            q_zero[resource_id] = q_zero.get(resource_id, 0) + 1
    state = SalesEnvironment(scenario).reset()
    initially_completed = sum(status is TaskStatus.COMPLETED for status in state.task_status.values())
    n_deals = len(scenario.deals)
    return ScenarioStructure(
        preset=scenario.generator.name,
        seed=scenario.seed,
        n_deals=n_deals,
        n_tasks=n_tasks,
        n_edges=n_edges,
        tasks_per_deal=(n_tasks / n_deals if n_deals else 0.0),
        mean_dependency_depth=(statistics.fmean(depths) if depths else 0.0),
        max_dependency_depth=(max(depths) if depths else 0),
        edges_per_task=(n_edges / n_tasks if n_tasks else 0.0),
        tasks_by_type=tasks_by_type,
        capacities={resource_id: resource.capacity for resource_id, resource in scenario.resources.items()},
        q_zero_by_resource=q_zero,
        initially_completed=initially_completed,
        initially_blocked=len(state.blocked_tasks),
        is_dag=acyclic,
        deals_missing_targets=missing_targets,
    )


def _spread(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty structure sample")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


@dataclass(frozen=True)
class StructureSummary:
    preset: str
    n_scenarios: int
    n_deals: dict[str, float | int]
    n_tasks: dict[str, float | int]
    n_edges: dict[str, float | int]
    tasks_per_deal: dict[str, float | int]
    mean_dependency_depth: dict[str, float | int]
    max_dependency_depth: dict[str, float | int]
    edges_per_task: dict[str, float | int]
    tasks_by_type: dict[str, dict[str, float | int]]
    capacities: dict[str, float]
    capacities_constant: bool
    q_zero_by_resource: dict[str, dict[str, float | int]]
    initially_completed: dict[str, float | int]
    initially_blocked: dict[str, float | int]
    all_dags: bool
    deals_missing_targets: int
    extra_edge_probability: float
    optional_drop_probability: float
    protected_task_types: tuple[str, ...]
    horizon: int


def summarize_structures(samples: list[ScenarioStructure]) -> StructureSummary:
    if not samples:
        raise ValueError("no scenarios to summarize")
    first = samples[0]
    capacities = dict(first.capacities)
    constant = all(sample.capacities == capacities for sample in samples)
    type_names = sorted({name for sample in samples for name in sample.tasks_by_type})
    resource_ids = sorted(capacities)
    return StructureSummary(
        preset=first.preset,
        n_scenarios=len(samples),
        n_deals=_spread([float(sample.n_deals) for sample in samples]),
        n_tasks=_spread([float(sample.n_tasks) for sample in samples]),
        n_edges=_spread([float(sample.n_edges) for sample in samples]),
        tasks_per_deal=_spread([sample.tasks_per_deal for sample in samples]),
        mean_dependency_depth=_spread([sample.mean_dependency_depth for sample in samples]),
        max_dependency_depth=_spread([float(sample.max_dependency_depth) for sample in samples]),
        edges_per_task=_spread([sample.edges_per_task for sample in samples]),
        tasks_by_type={
            name: _spread([float(sample.tasks_by_type.get(name, 0)) for sample in samples])
            for name in type_names
        },
        capacities=capacities,
        capacities_constant=constant,
        q_zero_by_resource={
            resource_id: _spread([float(sample.q_zero_by_resource.get(resource_id, 0)) for sample in samples])
            for resource_id in resource_ids
        },
        initially_completed=_spread([float(sample.initially_completed) for sample in samples]),
        initially_blocked=_spread([float(sample.initially_blocked) for sample in samples]),
        all_dags=all(sample.is_dag for sample in samples),
        deals_missing_targets=sum(sample.deals_missing_targets for sample in samples),
        extra_edge_probability=0.0,
        optional_drop_probability=0.0,
        protected_task_types=(),
        horizon=0,
    )


def format_spread(stats: dict[str, float | int]) -> str:
    return (
        f"n={stats['count']} mean={float(stats['mean']):.4f} "
        f"std={float(stats['stdev']):.4f} min={float(stats['min']):.4f} max={float(stats['max']):.4f}"
    )


def format_structure_summary(summary: StructureSummary) -> str:
    lines = [
        f"preset: {summary.preset}",
        f"scenarios: {summary.n_scenarios}",
        f"configured_extra_edge_probability: {summary.extra_edge_probability}",
        f"configured_optional_drop_probability: {summary.optional_drop_probability}",
        f"configured_protected_task_types: {list(summary.protected_task_types)}",
        f"configured_horizon: {summary.horizon}",
        f"all_dags: {summary.all_dags}",
        f"deals_missing_targets: {summary.deals_missing_targets}",
        f"capacities_constant_across_seeds: {summary.capacities_constant}",
        "capacities: " + ", ".join(f"{key}={value}" for key, value in sorted(summary.capacities.items())),
        f"n_deals: {format_spread(summary.n_deals)}",
        f"n_tasks: {format_spread(summary.n_tasks)}",
        f"n_edges: {format_spread(summary.n_edges)}",
        f"tasks_per_deal: {format_spread(summary.tasks_per_deal)}",
        f"edges_per_task: {format_spread(summary.edges_per_task)}",
        "mean_dependency_depth: " + format_spread(summary.mean_dependency_depth),
        "max_dependency_depth: " + format_spread(summary.max_dependency_depth),
        "dependency_depth is the longest predecessor chain. Sources have depth 0.",
        f"initially_completed_tasks: {format_spread(summary.initially_completed)}",
        f"initially_blocked_tasks: {format_spread(summary.initially_blocked)}",
        "tasks_by_type:",
    ]
    for name, stats in summary.tasks_by_type.items():
        lines.append(f"  {name}: {format_spread(stats)}")
    lines.append("tasks_with_q_zero:")
    for resource_id, stats in summary.q_zero_by_resource.items():
        lines.append(f"  {resource_id}: {format_spread(stats)}")
    return "\n".join(lines)
