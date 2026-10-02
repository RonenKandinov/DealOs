import pytest

from dealos.domain.models import Resource, Scenario
from dealos.policies.bottleneck import BottleneckPolicy, downstream_incomplete_count
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.optimization import OptimizationPolicy
from dealos.policies.random import RandomPolicy
from dealos.sim.constraints import validate_action
from dealos.sim.env import SalesEnvironment
from tests.builders import make_scenario


def _assert_feasible(scenario: Scenario, action) -> None:
    validate_action(
        action,
        capacities={resource_id: resource.capacity for resource_id, resource in scenario.resources.items()},
        task_keys=set(scenario.task_keys()),
        tolerance=scenario.simulation.capacity_tolerance,
    )
    used = action.used_by_resource()
    for resource_id, resource in scenario.resources.items():
        assert used.get(resource_id, 0.0) <= resource.capacity + scenario.simulation.capacity_tolerance
    for amount in action.allocations.values():
        assert 0.0 <= amount <= 1.0 + scenario.simulation.capacity_tolerance


def test_fifo_serves_the_longest_waiting_task_first() -> None:
    scenario = make_scenario(
        deals=[
            ("deal_00", ["late"], [], ["late"]),
            ("deal_01", ["early"], [], ["early"]),
        ],
        capacities={"ae": 1.0},
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    state.ready_since[("deal_00", "deal_00:late")] = 4
    state.ready_since[("deal_01", "deal_01:early")] = 1
    action = FIFOPolicy().select_action(state, scenario)
    assert ("deal_01", "deal_01:early", "ae") in action.allocations
    assert ("deal_00", "deal_00:late", "ae") not in action.allocations
    _assert_feasible(scenario, action)


def test_bottleneck_prefers_the_task_with_more_incomplete_descendants() -> None:
    scenario = make_scenario(
        deals=[
            (
                "deal_00",
                ["root", "b", "c", "d"],
                [("root", "b"), ("b", "c"), ("c", "d")],
                ["d"],
            ),
            ("deal_01", ["leaf"], [], ["leaf"]),
        ],
        capacities={"ae": 1.0},
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    root = downstream_incomplete_count(state, scenario, "deal_00", "deal_00:root")
    leaf = downstream_incomplete_count(state, scenario, "deal_01", "deal_01:leaf")
    assert root == 3
    assert leaf == 0
    assert root > leaf
    action = BottleneckPolicy().select_action(state, scenario)
    assert ("deal_00", "deal_00:root", "ae") in action.allocations
    assert ("deal_01", "deal_01:leaf", "ae") not in action.allocations


def test_policies_stay_feasible_with_a_zero_capacity_resource() -> None:
    from dealos.generator.generate import generate_scenario
    from dealos.generator.presets import get_preset

    base = generate_scenario(get_preset("balanced"), seed=0)
    resources = dict(base.resources)
    legal = resources["legal"]
    resources["legal"] = Resource(legal.resource_id, legal.resource_type, 0.0)
    scenario = Scenario(
        seed=base.seed,
        simulation=base.simulation,
        generator=base.generator,
        deals=dict(base.deals),
        resources=resources,
        phi=dict(base.phi),
        alpha=dict(base.alpha),
        suitability=dict(base.suitability),
        initial_progress=dict(base.initial_progress),
        horizon=5,
    )
    policies = [RandomPolicy(0), FIFOPolicy(), BottleneckPolicy()]
    for policy in policies:
        env = SalesEnvironment(scenario)
        state = env.reset()
        for _ in range(3):
            if env.is_done():
                break
            action = policy.select_action(state, scenario)
            _assert_feasible(scenario, action)
            assert action.used_by_resource().get("legal", 0.0) == 0.0
            state, _info = env.step(action)


def test_random_policy_is_reproducible() -> None:
    from dealos.generator.generate import generate_scenario
    from dealos.generator.presets import get_preset

    scenario = generate_scenario(get_preset("resource_constrained"), seed=3)
    short = Scenario(
        seed=scenario.seed,
        simulation=scenario.simulation,
        generator=scenario.generator,
        deals=dict(scenario.deals),
        resources=dict(scenario.resources),
        phi=dict(scenario.phi),
        alpha=dict(scenario.alpha),
        suitability=dict(scenario.suitability),
        initial_progress=dict(scenario.initial_progress),
        horizon=4,
    )

    def trace(seed: int) -> list[dict[str, float]]:
        env = SalesEnvironment(short)
        policy = RandomPolicy(seed)
        state = env.reset()
        snapshots = []
        while not env.is_done():
            action = policy.select_action(state, short)
            _assert_feasible(short, action)
            state, _info = env.step(action)
            assert all(0.0 <= value <= 1.0 for value in state.task_progress.values())
            snapshots.append(dict(state.task_progress))
        return snapshots

    assert trace(0) == trace(0)
    assert trace(0) != trace(1)


def test_optimization_policy_is_not_implemented() -> None:
    scenario = make_scenario(deals=[("deal_00", ["only"], [], ["only"])])
    env = SalesEnvironment(scenario)
    state = env.reset()
    with pytest.raises(NotImplementedError):
        OptimizationPolicy().select_action(state, scenario)
