"""Small hand-built scenarios for simulator tests."""

from __future__ import annotations

from dealos.domain.models import (
    DealGraph,
    GeneratorConfig,
    Resource,
    Scenario,
    SimulationConfig,
    Task,
)


def make_scenario(
    *,
    deals: list[tuple[str, list[str], list[tuple[str, str]], list[str] | None]],
    capacities: dict[str, float] | None = None,
    initial: dict[tuple[str, str], float] | None = None,
    phi: float = 1.0,
    alpha: float = 1.0,
    suitability: float = 1.0,
    horizon: int = 10,
    task_types: dict[str, str] | None = None,
) -> Scenario:
    """Build a scenario.

    Each deal is `(deal_id, task_names, edges_by_short_name, targets_or_none)`.
    Task ids are `{deal_id}:{name}`.
    """

    capacity_values = capacities or {"ae": 1.0}
    graphs: dict[str, DealGraph] = {}
    phi_map: dict[tuple[str, str], float] = {}
    alpha_map: dict[tuple[str, str, str], float] = {}
    q_map: dict[tuple[str, str, str], float] = {}
    progress: dict[tuple[str, str], float] = {}
    for deal_id, names, raw_edges, raw_targets in deals:
        tasks = {}
        for name in names:
            task_id = f"{deal_id}:{name}"
            tasks[task_id] = Task(
                task_id=task_id,
                deal_id=deal_id,
                task_type=(task_types or {}).get(name, "commercial"),
                name=name,
            )
        edges = frozenset(
            (f"{deal_id}:{source}", f"{deal_id}:{dest}") for source, dest in raw_edges
        )
        if raw_targets is None:
            targets = frozenset(
                task_id
                for task_id in tasks
                if not any(source == task_id for source, _dest in edges)
            )
        else:
            targets = frozenset(f"{deal_id}:{name}" for name in raw_targets)
        graphs[deal_id] = DealGraph(deal_id=deal_id, tasks=tasks, edges=edges, targets=targets)
        for task_id in tasks:
            key = (deal_id, task_id)
            phi_map[key] = phi
            progress[key] = 0.0 if initial is None else initial.get(key, 0.0)
            for resource_id in capacity_values:
                alpha_map[(deal_id, task_id, resource_id)] = alpha
                q_map[(deal_id, task_id, resource_id)] = suitability
    resources = {
        resource_id: Resource(resource_id=resource_id, resource_type=resource_id, capacity=capacity)
        for resource_id, capacity in capacity_values.items()
    }
    config = GeneratorConfig(
        name="hand_built",
        n_deals=len(graphs),
        horizon=horizon,
        capacities=capacity_values,
        extra_edge_probability=0.0,
        optional_drop_probability=0.0,
        partial_start_fraction=0.0,
        phi_range=(1.0, 1.0),
        alpha_range=(1.0, 1.0),
        q_range=(1.0, 1.0),
    )
    return Scenario(
        seed=0,
        simulation=SimulationConfig(),
        generator=config,
        deals=graphs,
        resources=resources,
        phi=phi_map,
        alpha=alpha_map,
        suitability=q_map,
        initial_progress=progress,
        horizon=horizon,
    )
