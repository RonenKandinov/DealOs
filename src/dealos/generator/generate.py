"""Build a reproducible synthetic portfolio from a generator config and seed."""

from __future__ import annotations

import random
from dataclasses import dataclass

from dealos.domain.graph import predecessors, topological_order
from dealos.domain.models import (
    DealGraph,
    GeneratorConfig,
    Resource,
    Scenario,
    SimulationConfig,
    Task,
)
from dealos.generator.presets import RESOURCE_TYPES

# Work packages in one valid topological order. Optional tasks may be dropped.
# Predecessors are AND dependencies.
_TEMPLATE: tuple[tuple[str, str, tuple[str, ...], bool], ...] = (
    ("discovery", "commercial", (), False),
    ("qualification", "commercial", ("discovery",), False),
    ("technical_validation", "technical", ("qualification",), False),
    ("solution_design", "technical", ("technical_validation",), True),
    ("security_review", "security", ("technical_validation",), True),
    ("legal_review", "legal", ("qualification",), False),
    ("contract_redline", "legal", ("legal_review",), True),
    ("integration", "technical", ("solution_design", "security_review"), False),
    ("procurement", "procurement", ("integration", "contract_redline"), False),
    ("executive_approval", "executive", ("procurement",), True),
    ("signature", "commercial", ("executive_approval",), False),
)

# q_jr is zero outside this map. Unsuitable resources contribute nothing.
SUITABLE_RESOURCES: dict[str, frozenset[str]] = {
    "commercial": frozenset({"ae"}),
    "technical": frozenset({"sales_engineer", "solutions_architect"}),
    "legal": frozenset({"legal"}),
    "security": frozenset({"security"}),
    "procurement": frozenset({"ae"}),
    "executive": frozenset({"ae"}),
}


@dataclass(frozen=True)
class _Spec:
    name: str
    task_type: str
    predecessors: tuple[str, ...]
    optional: bool


def _specs() -> tuple[_Spec, ...]:
    return tuple(_Spec(name, task_type, preds, optional) for name, task_type, preds, optional in _TEMPLATE)


def _expand_predecessors(
    name: str,
    preds_of: dict[str, tuple[str, ...]],
    dropped: set[str],
    stack: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if name in stack:
        raise RuntimeError(f"template predecessor cycle at {name}")
    expanded: list[str] = []
    for pred in preds_of[name]:
        if pred in dropped:
            expanded.extend(_expand_predecessors(pred, preds_of, dropped, stack + (name,)))
        else:
            expanded.append(pred)
    unique: list[str] = []
    for item in expanded:
        if item not in unique:
            unique.append(item)
    return tuple(unique)


def _build_deal(rng: random.Random, deal_id: str, config: GeneratorConfig) -> DealGraph:
    specs = _specs()
    dropped: set[str] = set()
    for spec in specs:
        if not spec.optional:
            continue
        if spec.task_type in config.protected_task_types:
            continue
        if rng.random() < config.optional_drop_probability:
            dropped.add(spec.name)
    kept = [spec for spec in specs if spec.name not in dropped]
    preds_of = {spec.name: spec.predecessors for spec in specs}
    edges: set[tuple[str, str]] = set()
    tasks: dict[str, Task] = {}
    order = [spec.name for spec in kept]
    for spec in kept:
        task_id = f"{deal_id}:{spec.name}"
        tasks[task_id] = Task(
            task_id=task_id,
            deal_id=deal_id,
            task_type=spec.task_type,
            name=spec.name,
        )
        for pred_name in _expand_predecessors(spec.name, preds_of, dropped):
            edges.add((f"{deal_id}:{pred_name}", task_id))
    for index, dest_name in enumerate(order):
        if index == 0 or rng.random() >= config.extra_edge_probability:
            continue
        source_name = order[rng.randrange(0, index)]
        edges.add((f"{deal_id}:{source_name}", f"{deal_id}:{dest_name}"))
    sinks = []
    for spec in kept:
        task_id = f"{deal_id}:{spec.name}"
        if not any(source == task_id for source, _dest in edges):
            sinks.append(task_id)
    if not sinks:
        raise RuntimeError(f"deal {deal_id} has no sink task to use as a target")
    return DealGraph(
        deal_id=deal_id,
        tasks=tasks,
        edges=frozenset(edges),
        targets=frozenset(sinks),
    )


def _initial_progress(rng: random.Random, deal: DealGraph, config: GeneratorConfig) -> dict[str, float]:
    progress = {task_id: 0.0 for task_id in deal.tasks}
    if rng.random() >= config.partial_start_fraction:
        return progress
    order = topological_order(set(deal.tasks), deal.edges)
    limit = rng.randint(1, max(1, len(order) // 3))
    completed = 0
    for task_id in order:
        if completed >= limit:
            break
        preds = predecessors(deal.edges, task_id)
        if all(progress[pred] >= 1.0 for pred in preds):
            progress[task_id] = 1.0
            completed += 1
    return progress


def _check_config(config: GeneratorConfig) -> None:
    phi_lo, phi_hi = config.phi_range
    alpha_lo, alpha_hi = config.alpha_range
    q_lo, q_hi = config.q_range
    if not (0.0 < phi_lo <= phi_hi <= 1.0):
        raise ValueError("phi_range must lie in (0, 1]")
    if not (0.0 < alpha_lo <= alpha_hi):
        raise ValueError("alpha_range must be positive")
    if not (0.0 <= q_lo <= q_hi <= 1.0):
        raise ValueError("q_range must lie in [0, 1]")
    for name, probability in (
        ("extra_edge_probability", config.extra_edge_probability),
        ("optional_drop_probability", config.optional_drop_probability),
        ("partial_start_fraction", config.partial_start_fraction),
    ):
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"{name} must lie in [0, 1]")
    unknown = set(config.capacities) - set(RESOURCE_TYPES)
    if unknown:
        raise ValueError(f"unknown resources in capacities: {sorted(unknown)}")
    if not config.capacities:
        raise ValueError("at least one resource is required")


def generate_scenario(
    config: GeneratorConfig,
    seed: int,
    simulation: SimulationConfig | None = None,
) -> Scenario:
    """Generate deals, graphs, capacities, and φ, α, q from one random.Random(seed)."""

    _check_config(config)
    rng = random.Random(seed)
    deals: dict[str, DealGraph] = {}
    initial: dict[tuple[str, str], float] = {}
    for index in range(config.n_deals):
        deal_id = f"deal_{index:02d}"
        deal = _build_deal(rng, deal_id, config)
        deals[deal_id] = deal
        for task_id, progress in _initial_progress(rng, deal, config).items():
            initial[(deal_id, task_id)] = progress
    resources = {
        resource_id: Resource(
            resource_id=resource_id,
            resource_type=RESOURCE_TYPES[resource_id],
            capacity=float(config.capacities[resource_id]),
        )
        for resource_id in sorted(config.capacities)
    }
    phi: dict[tuple[str, str], float] = {}
    alpha: dict[tuple[str, str, str], float] = {}
    suitability: dict[tuple[str, str, str], float] = {}
    phi_lo, phi_hi = config.phi_range
    alpha_lo, alpha_hi = config.alpha_range
    q_lo, q_hi = config.q_range
    for deal_id in sorted(deals):
        deal = deals[deal_id]
        for task_id in sorted(deal.tasks):
            phi[(deal_id, task_id)] = rng.uniform(phi_lo, phi_hi)
            task_type = deal.tasks[task_id].task_type
            suitable = SUITABLE_RESOURCES[task_type]
            for resource_id in sorted(resources):
                alpha[(deal_id, task_id, resource_id)] = rng.uniform(alpha_lo, alpha_hi)
                if resource_id in suitable:
                    suitability[(deal_id, task_id, resource_id)] = rng.uniform(q_lo, q_hi)
                else:
                    suitability[(deal_id, task_id, resource_id)] = 0.0
    return Scenario(
        seed=seed,
        simulation=simulation or SimulationConfig(),
        generator=config,
        deals=deals,
        resources=resources,
        phi=phi,
        alpha=alpha,
        suitability=suitability,
        initial_progress=initial,
        horizon=config.horizon,
    )
