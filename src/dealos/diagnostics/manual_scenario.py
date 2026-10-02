"""A two-deal portfolio small enough to update by hand.

One shared resource, ae, with capacity 1. Every φ, α, and q is 1, and every
task starts at progress 0. One business day of a full allocation therefore
adds exactly that allocation to a ready task:

    Δx = Ready * a
    x <- min(1, x + Δx)

deal_00 has a branch and an AND join:

    start -> left  -> join
    start -> right -> join

deal_01 is a chain:

    root -> mid -> end

Targets are join and end. Both deals draw on ae, and the allocations of one
day must sum to at most 1.

Transition 1. Allocate a=1 to deal_00:start.

    x_start = min(1, 0 + 1) = 1
    every other task stays at 0, because it receives a=0
    join stays blocked: its predecessors are still 0 on this day

After the day, left and right become ready for the next day. join does not,
because left and right are still 0.

Transition 2. Allocate 0.4 to left and 0.6 to right.

    x_left = 0 + 1 * 0.4 = 0.4
    x_right = 0 + 1 * 0.6 = 0.6
    x_join stays 0
    deal_01 stays at 0

After that day, join's readiness for a later day is min(0.4, 0.6) = 0.4.
"""

from __future__ import annotations

from dealos.domain.models import (
    DealGraph,
    GeneratorConfig,
    Resource,
    Scenario,
    SimulationConfig,
    Task,
)


def _task(deal_id: str, name: str) -> Task:
    return Task(task_id=f"{deal_id}:{name}", deal_id=deal_id, task_type="commercial", name=name)


def chain_debug_scenario(
    initial: dict[tuple[str, str], float] | None = None,
) -> Scenario:
    """Two short chains sharing one resource, with parameters chosen for hand arithmetic.

    deal_A: A1 -> A2 -> A3, target A3
    deal_B: B1 -> B2, target B2

    Resource ae has capacity 1. φ = α = q = 1, so a ready task moves by exactly a.
    """

    specs = {
        "deal_A": (["A1", "A2", "A3"], [("A1", "A2"), ("A2", "A3")], ["A3"]),
        "deal_B": (["B1", "B2"], [("B1", "B2")], ["B2"]),
    }
    deals: dict[str, DealGraph] = {}
    phi: dict[tuple[str, str], float] = {}
    alpha: dict[tuple[str, str, str], float] = {}
    suitability: dict[tuple[str, str, str], float] = {}
    progress: dict[tuple[str, str], float] = {}
    supplied = initial or {}
    for deal_id, (names, raw_edges, targets) in specs.items():
        tasks = {f"{deal_id}:{name}": _task(deal_id, name) for name in names}
        edges = frozenset((f"{deal_id}:{src}", f"{deal_id}:{dst}") for src, dst in raw_edges)
        deals[deal_id] = DealGraph(
            deal_id=deal_id,
            tasks=tasks,
            edges=edges,
            targets=frozenset(f"{deal_id}:{name}" for name in targets),
        )
        for task_id in tasks:
            phi[(deal_id, task_id)] = 1.0
            alpha[(deal_id, task_id, "ae")] = 1.0
            suitability[(deal_id, task_id, "ae")] = 1.0
            progress[(deal_id, task_id)] = float(supplied.get((deal_id, task_id), 0.0))
    config = GeneratorConfig(
        name="chain_debug",
        n_deals=2,
        horizon=5,
        capacities={"ae": 1.0},
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
        deals=deals,
        resources={"ae": Resource("ae", "AE", 1.0)},
        phi=phi,
        alpha=alpha,
        suitability=suitability,
        initial_progress=progress,
        horizon=5,
    )


def manual_scenario() -> Scenario:
    deals: dict[str, DealGraph] = {}
    specs = {
        "deal_00": (
            ["start", "left", "right", "join"],
            [("start", "left"), ("start", "right"), ("left", "join"), ("right", "join")],
            ["join"],
        ),
        "deal_01": (
            ["root", "mid", "end"],
            [("root", "mid"), ("mid", "end")],
            ["end"],
        ),
    }
    phi: dict[tuple[str, str], float] = {}
    alpha: dict[tuple[str, str, str], float] = {}
    suitability: dict[tuple[str, str, str], float] = {}
    initial: dict[tuple[str, str], float] = {}
    for deal_id, (names, raw_edges, targets) in specs.items():
        tasks = {f"{deal_id}:{name}": _task(deal_id, name) for name in names}
        edges = frozenset((f"{deal_id}:{src}", f"{deal_id}:{dst}") for src, dst in raw_edges)
        deals[deal_id] = DealGraph(
            deal_id=deal_id,
            tasks=tasks,
            edges=edges,
            targets=frozenset(f"{deal_id}:{name}" for name in targets),
        )
        for task_id in tasks:
            phi[(deal_id, task_id)] = 1.0
            alpha[(deal_id, task_id, "ae")] = 1.0
            suitability[(deal_id, task_id, "ae")] = 1.0
            initial[(deal_id, task_id)] = 0.0
    config = GeneratorConfig(
        name="manual",
        n_deals=2,
        horizon=5,
        capacities={"ae": 1.0},
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
        deals=deals,
        resources={"ae": Resource("ae", "AE", 1.0)},
        phi=phi,
        alpha=alpha,
        suitability=suitability,
        initial_progress=initial,
        horizon=5,
    )
