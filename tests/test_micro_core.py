"""Micro simulator core: graphs, readiness, dynamics, capacity, occurrences, and policies.

Merged from test_graph, test_readiness, test_simulator, test_capacity_and_dynamics,
test_v2_occurrences, and test_policies. Every test body is unchanged.
"""

import pytest

from dealos.domain.dynamics import apply_progress, delta_x, is_complete
from dealos.domain.graph import CycleError, descendants, has_cycle, predecessors, require_dag, successors
from dealos.domain.models import (
    AllocationAction,
    DealGraph,
    OccurrenceLifecycle,
    ReadinessSource,
    Resource,
    Scenario,
    Task,
    primary_occurrence_id,
)
from dealos.domain.readiness import AndMinReadiness
from dealos.experiments.runner import rollout
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.base import is_allocation_eligible
from dealos.policies.bottleneck import BottleneckPolicy, downstream_incomplete_count
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.optimization import OptimizationPolicy
from dealos.policies.random import RandomPolicy
from dealos.sim.constraints import ActionBoundsError, CapacityViolation, validate_action
from dealos.sim.env import SalesEnvironment
from tests.builders import make_scenario


# ---- Graph and readiness ----


def _task(deal_id: str, name: str) -> Task:
    return Task(task_id=f"{deal_id}:{name}", deal_id=deal_id, task_type="commercial", name=name)


def _graph(names: list[str], edges: list[tuple[str, str]], targets: list[str] | None = None) -> DealGraph:
    deal_id = "deal_00"
    tasks = {f"{deal_id}:{name}": _task(deal_id, name) for name in names}
    full_edges = frozenset((f"{deal_id}:{src}", f"{deal_id}:{dst}") for src, dst in edges)
    if targets is None:
        targets = [name for name in names if not any(src == name for src, _dst in edges)]
    return DealGraph(
        deal_id=deal_id,
        tasks=tasks,
        edges=full_edges,
        targets=frozenset(f"{deal_id}:{name}" for name in targets),
    )


def test_task_with_no_predecessors() -> None:
    graph = _graph(["only"], [])
    assert predecessors(graph.edges, "deal_00:only") == ()
    assert successors(graph.edges, "deal_00:only") == ()


def test_multiple_predecessors_and_merge() -> None:
    graph = _graph(
        ["left", "right", "join", "close"],
        [("left", "join"), ("right", "join"), ("join", "close")],
    )
    assert predecessors(graph.edges, "deal_00:join") == ("deal_00:left", "deal_00:right")
    assert descendants(graph.edges, "deal_00:left") == frozenset({"deal_00:join", "deal_00:close"})
    assert descendants(graph.edges, "deal_00:right") == frozenset({"deal_00:join", "deal_00:close"})
    assert descendants(graph.edges, "deal_00:close") == frozenset()


def test_single_task_deal_is_its_own_target() -> None:
    graph = _graph(["only"], [])
    assert graph.targets == frozenset({"deal_00:only"})


def test_cycle_is_rejected() -> None:
    with pytest.raises(CycleError):
        _graph(["a", "b"], [("a", "b"), ("b", "a")], targets=["a"])


def test_self_loop_is_rejected() -> None:
    with pytest.raises(CycleError):
        _graph(["a"], [("a", "a")], targets=["a"])


def test_has_cycle_on_raw_edges() -> None:
    assert has_cycle({"a", "b"}, {("a", "b"), ("b", "a")})
    assert not has_cycle({"a"}, set())


def test_deal_requires_a_target() -> None:
    deal_id = "deal_00"
    task = _task(deal_id, "only")
    with pytest.raises(ValueError):
        DealGraph(
            deal_id=deal_id,
            tasks={task.task_id: task},
            edges=frozenset(),
            targets=frozenset(),
        )


def test_empty_predecessors_are_fully_ready() -> None:
    assert AndMinReadiness().readiness(()) == 1.0


def test_multiple_predecessors_use_the_minimum() -> None:
    assert AndMinReadiness().readiness((0.2, 0.9, 0.4)) == 0.2


def test_readiness_does_not_pull_existing_progress_backward() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["pred", "task"], [("pred", "task")], ["task"])],
        initial={("deal_00", "deal_00:task"): 0.4},
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert state.task_progress[("deal_00", "deal_00:task")] == 0.4
    assert state.task_status[("deal_00", "deal_00:task")].value == "blocked"
    state, info = env.step(AllocationAction({}))
    assert state.task_progress[("deal_00", "deal_00:task")] == 0.4
    assert info.deltas[("deal_00", "deal_00:task")] == 0.0


def test_new_progress_is_scaled_by_minimum_predecessor() -> None:
    scenario = make_scenario(
        deals=[
            (
                "deal_00",
                ["left", "right", "join"],
                [("left", "join"), ("right", "join")],
                ["join"],
            )
        ],
        initial={
            ("deal_00", "deal_00:left"): 0.25,
            ("deal_00", "deal_00:right"): 0.8,
        },
    )
    env = SalesEnvironment(scenario)
    env.reset()
    state, _info = env.step(
        AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:join"), "ae"): 1.0})
    )
    assert state.task_progress[("deal_00", "deal_00:join")] == 0.25


# ---- Simulator dynamics ----


def test_status_transitions_and_time_advance() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["pred", "next"], [("pred", "next")], ["next"])],
        horizon=5,
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert state.time == 0
    assert state.task_status[("deal_00", "deal_00:pred")].value == "not_started"
    assert state.task_status[("deal_00", "deal_00:next")].value == "blocked"
    assert ("deal_00", "deal_00:next") in state.blocked_tasks

    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:pred"), "ae"): 1.0}))
    assert state.time == 1
    assert state.task_status[("deal_00", "deal_00:pred")].value == "completed"
    assert state.task_progress[("deal_00", "deal_00:next")] == 0.0
    assert state.task_status[("deal_00", "deal_00:next")].value == "not_started"
    assert state.ready_since[("deal_00", "deal_00:next")] == 1

    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:next"), "ae"): 0.4}))
    assert state.time == 2
    assert state.task_progress[("deal_00", "deal_00:next")] == 0.4
    assert state.task_status[("deal_00", "deal_00:next")].value == "in_progress"

    state, info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:next"), "ae"): 1.0}))
    assert state.time == 3
    assert state.task_status[("deal_00", "deal_00:next")].value == "completed"
    assert info.newly_completed_tasks == (("deal_00", "deal_00:next"),)
    assert state.deal_complete["deal_00"] == 1


def test_independent_branches_block_the_join_until_both_are_done() -> None:
    scenario = make_scenario(
        deals=[
            (
                "deal_00",
                ["left", "right", "join"],
                [("left", "join"), ("right", "join")],
                ["join"],
            )
        ],
        capacities={"ae": 2.0},
        horizon=5,
    )
    env = SalesEnvironment(scenario)
    env.reset()
    state, _info = env.step(
        AllocationAction(
            {
                ("deal_00", primary_occurrence_id("deal_00", "deal_00:left"), "ae"): 1.0,
                ("deal_00", primary_occurrence_id("deal_00", "deal_00:join"), "ae"): 1.0,
            }
        )
    )
    assert state.task_progress[("deal_00", "deal_00:left")] == 1.0
    assert state.task_progress[("deal_00", "deal_00:join")] == 0.0
    assert state.task_status[("deal_00", "deal_00:join")].value == "blocked"

    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:right"), "ae"): 1.0}))
    assert state.task_status[("deal_00", "deal_00:join")].value == "not_started"
    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:join"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:join")] == 1.0
    assert state.deal_complete["deal_00"] == 1


def test_get_state_returns_an_independent_copy() -> None:
    scenario = make_scenario(deals=[("deal_00", ["only"], [], ["only"])])
    env = SalesEnvironment(scenario)
    first = env.reset()
    first.task_progress[("deal_00", "deal_00:only")] = 0.9
    assert env.get_state().task_progress[("deal_00", "deal_00:only")] == 0.0


def test_identical_actions_reproduce_the_same_trajectory() -> None:
    scenario = generate_scenario(get_preset("balanced"), seed=0)
    actions = []
    probe = SalesEnvironment(scenario)
    state = probe.reset()

    policy = FIFOPolicy()
    while not probe.is_done():
        action = policy.select_action(state, scenario)
        actions.append(action)
        state, _info = probe.step(action)
        if len(actions) >= 6:
            break

    def replay() -> list[dict[str, object]]:
        env = SalesEnvironment(scenario)
        snapshots = [env.reset().to_dict()]
        for action in actions:
            nxt, _info = env.step(action)
            snapshots.append(nxt.to_dict())
        return snapshots

    assert replay() == replay()


def test_step_after_horizon_raises() -> None:
    scenario = make_scenario(deals=[("deal_00", ["only"], [], ["only"])], horizon=1)
    env = SalesEnvironment(scenario)
    env.reset()
    env.step(AllocationAction({}))
    assert env.is_done()
    assert env.done_reason == "horizon"
    with pytest.raises(RuntimeError):
        env.step(AllocationAction({}))


def test_blocked_task_receives_no_progress_from_allocation() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["pred", "next"], [("pred", "next")], ["next"])],
    )
    env = SalesEnvironment(scenario)
    env.reset()
    state, info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:next"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:next")] == 0.0
    assert info.deltas[("deal_00", "deal_00:next")] == 0.0


# ---- Capacity ----


def test_delta_matches_the_formula() -> None:
    assert delta_x(0.5, 0.5, 2.0) == 0.5


def test_progress_is_clamped_to_unit_interval() -> None:
    assert apply_progress(0.2, 5.0, 1e-9) == 1.0
    assert apply_progress(0.0, 0.0, 1e-9) == 0.0
    scenario = make_scenario(
        deals=[("deal_00", ["only"], [], ["only"])],
        phi=10.0,
    )
    env = SalesEnvironment(scenario)
    env.reset()
    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:only"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:only")] == 1.0


def test_feasible_action_is_accepted_and_over_allocation_is_rejected() -> None:
    scenario = make_scenario(
        deals=[
            ("deal_00", ["a"], [], ["a"]),
            ("deal_01", ["b"], [], ["b"]),
        ],
        capacities={"ae": 1.0},
    )
    env = SalesEnvironment(scenario)
    env.reset()
    env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:a"), "ae"): 0.4}))
    env.reset()
    with pytest.raises(CapacityViolation):
        env.step(
            AllocationAction(
                {
                    ("deal_00", primary_occurrence_id("deal_00", "deal_00:a"), "ae"): 0.6,
                    ("deal_01", primary_occurrence_id("deal_01", "deal_01:b"), "ae"): 0.6,
                }
            )
        )


def test_allocation_above_one_is_rejected() -> None:
    scenario = make_scenario(deals=[("deal_00", ["only"], [], ["only"])])
    env = SalesEnvironment(scenario)
    env.reset()
    with pytest.raises(ActionBoundsError):
        env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:only"), "ae"): 1.2}))


def test_zero_capacity_rejects_allocation_and_blocks_progress() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["only"], [], ["only"])],
        capacities={"ae": 0.0},
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    with pytest.raises(CapacityViolation):
        env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:only"), "ae"): 0.1}))
    state, info = env.step(AllocationAction({}))
    assert state.task_progress[("deal_00", "deal_00:only")] == 0.0
    assert info.utilization["ae"] == 0.0


def test_completed_task_stays_complete_and_records_wasted_allocation() -> None:
    scenario = make_scenario(
        deals=[
            ("deal_00", ["done"], [], ["done"]),
            ("deal_01", ["open"], [], ["open"]),
        ],
        initial={("deal_00", "deal_00:done"): 1.0},
        capacities={"ae": 2.0},
        horizon=5,
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert state.task_status[("deal_00", "deal_00:done")].value == "completed"
    assert state.deal_complete["deal_00"] == 1
    assert state.deal_complete["deal_01"] == 0
    assert not env.is_done()
    state, info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:done"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:done")] == 1.0
    assert state.task_status[("deal_00", "deal_00:done")].value == "completed"
    assert info.deltas[("deal_00", "deal_00:done")] == 0.0
    assert info.wasted_allocation == 1.0


def test_all_targets_are_required_for_deal_completion() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["a", "b"], [], ["a", "b"])],
        capacities={"ae": 1.0},
        horizon=5,
    )
    env = SalesEnvironment(scenario)
    env.reset()
    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:a"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:a")] == 1.0
    assert state.deal_complete["deal_00"] == 0
    state, info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:b"), "ae"): 1.0}))
    assert state.deal_complete["deal_00"] == 1
    assert info.newly_completed_deals == ("deal_00",)
    assert state.deal_completed_at["deal_00"] == 2


def test_single_task_deal_completes() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["only"], [], None)],
        horizon=3,
    )
    env = SalesEnvironment(scenario)
    env.reset()
    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:only"), "ae"): 1.0}))
    assert state.deal_complete["deal_00"] == 1
    assert env.is_done()
    assert env.done_reason == "all_deals_complete"


def test_non_target_need_not_be_complete() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["side", "target"], [], ["target"])],
        initial={("deal_00", "deal_00:target"): 1.0},
        horizon=5,
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert state.task_progress[("deal_00", "deal_00:side")] == 0.0
    assert state.deal_complete["deal_00"] == 1


# ---- Occurrences/lifecycle ----


def test_one_occurrence_matches_v1_progress_and_seed0_fifo() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["pred", "next"], [("pred", "next")], ["next"])],
        horizon=5,
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert len(state.occurrences) == 2
    assert all(item.lifecycle is OccurrenceLifecycle.ACTIVE for item in state.occurrences.values())
    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:pred"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:pred")] == 1.0
    primary = state.occurrences[state.primary_occurrence[("deal_00", "deal_00:pred")]]
    assert primary.progress == 1.0
    assert primary.lifecycle is OccurrenceLifecycle.COMPLETED
    assert state.task_progress[("deal_00", "deal_00:next")] == 0.0
    assert len(scenario.deals["deal_00"].tasks) == 2

    balanced = generate_scenario(get_preset("balanced"), seed=0)
    result = rollout(balanced, FIFOPolicy())
    assert result.completed_deals == 2
    assert result.steps == 40


def test_second_occurrence_does_not_add_a_graph_vertex() -> None:
    env = SalesEnvironment(
        make_scenario(deals=[("deal_00", ["pred", "next"], [("pred", "next")], ["next"])])
    )
    env.reset()
    deal = env.scenario.deals["deal_00"]
    edges = set(deal.edges)
    second = env.open_occurrence("deal_00", "deal_00:pred")
    assert second.lifecycle is OccurrenceLifecycle.SCHEDULED
    assert second.offer_id is None
    assert env.scenario.deals["deal_00"].edges == edges
    assert len(env.scenario.deals["deal_00"].tasks) == 2
    require_dag(set(env.scenario.deals["deal_00"].tasks), env.scenario.deals["deal_00"].edges)
    assert sum(
        1
        for item in env.get_state().occurrences.values()
        if item.task_id == "deal_00:pred"
    ) == 2


def test_completed_primary_stays_complete_while_new_occurrence_advances() -> None:
    env = SalesEnvironment(
        make_scenario(
            deals=[
                ("deal_open", ["keep"], [], ["keep"]),
                ("deal_done", ["once"], [], ["once"]),
            ],
            horizon=10,
        )
    )
    env.reset()
    env.step(AllocationAction({("deal_done", primary_occurrence_id("deal_done", "deal_done:once"), "ae"): 1.0}))
    done = env.get_state()
    assert done.deal_complete["deal_done"] == 1
    assert done.task_progress[("deal_done", "deal_done:once")] == 1.0
    extra = env.open_occurrence("deal_done", "deal_done:once")
    env.set_lifecycle(extra.occurrence_id, OccurrenceLifecycle.ACTIVE)
    env.declare_ready(extra.occurrence_id)
    state, _info = env.step(AllocationAction({("deal_done", extra.occurrence_id, "ae"): 0.25}))
    primary = state.occurrences[state.primary_occurrence[("deal_done", "deal_done:once")]]
    moved = state.occurrences[extra.occurrence_id]
    assert primary.progress == 1.0
    assert primary.lifecycle is OccurrenceLifecycle.COMPLETED
    assert moved.progress == 0.25
    assert moved.lifecycle is OccurrenceLifecycle.ACTIVE
    assert state.task_progress[("deal_done", "deal_done:once")] == 1.0
    assert state.deal_complete["deal_done"] == 1
    assert state.deal_complete["deal_open"] == 0


def test_lifecycle_schedule_then_withdraw_and_resume() -> None:
    env = SalesEnvironment(make_scenario(deals=[("deal_00", ["only"], [], ["only"])]))
    env.reset()
    extra = env.open_occurrence("deal_00", "deal_00:only")
    assert extra.lifecycle is OccurrenceLifecycle.SCHEDULED
    withdrawn = env.set_lifecycle(extra.occurrence_id, OccurrenceLifecycle.WITHDRAWN)
    assert withdrawn.lifecycle is OccurrenceLifecycle.WITHDRAWN
    assert withdrawn.progress == 0.0
    primary_id = env.get_state().primary_occurrence[("deal_00", "deal_00:only")]
    env.set_lifecycle(primary_id, OccurrenceLifecycle.SUSPENDED)
    resumed = env.set_lifecycle(primary_id, OccurrenceLifecycle.ACTIVE)
    assert resumed.lifecycle is OccurrenceLifecycle.ACTIVE


def test_suspended_occurrence_does_not_receive_progress() -> None:
    env = SalesEnvironment(make_scenario(deals=[("deal_00", ["only"], [], ["only"])]))
    env.reset()
    primary_id = env.get_state().primary_occurrence[("deal_00", "deal_00:only")]
    env.set_lifecycle(primary_id, OccurrenceLifecycle.SUSPENDED)
    state, info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:only"), "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:only")] == 0.0
    assert state.occurrences[primary_id].progress == 0.0
    assert state.occurrences[primary_id].lifecycle is OccurrenceLifecycle.SUSPENDED
    assert info.wasted_allocation == 1.0
    assert state.deal_complete["deal_00"] == 0


def test_aborted_and_withdrawn_are_not_successful_completion() -> None:
    env = SalesEnvironment(make_scenario(deals=[("deal_00", ["only"], [], ["only"])], horizon=5))
    env.reset()
    primary_id = env.get_state().primary_occurrence[("deal_00", "deal_00:only")]
    aborted = env.set_lifecycle(primary_id, OccurrenceLifecycle.ABORTED)
    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:only"), "ae"): 1.0}))
    aborted = state.occurrences[primary_id]
    assert aborted.lifecycle is OccurrenceLifecycle.ABORTED
    assert aborted.progress == 0.0
    assert not _succeeded(aborted)
    assert state.deal_complete["deal_00"] == 0

    env.set_lifecycle(primary_id, OccurrenceLifecycle.WITHDRAWN)
    state, _info = env.step(AllocationAction({}))
    withdrawn = state.occurrences[primary_id]
    assert withdrawn.lifecycle is OccurrenceLifecycle.WITHDRAWN
    assert withdrawn.progress == 0.0
    assert not _succeeded(withdrawn)
    assert state.deal_complete["deal_00"] == 0


def test_offer_id_is_optional_and_workflow_does_not_require_one() -> None:
    env = SalesEnvironment(make_scenario(deals=[("deal_00", ["review"], [], ["review"])]))
    env.reset()
    assert env.record_offer("deal_00", "") is None
    assert env.record_offer("deal_00", "   ") is None
    assert env.get_state().offers == {}
    offer = env.record_offer("deal_00", "Offer_1")
    assert offer is not None
    assert offer.offer_id == "Offer_1"
    assert offer.case_id == "deal_00"
    workflow = env.open_occurrence("deal_00", "deal_00:review")
    assert workflow.offer_id is None
    assert "Offer_1" in env.get_state().offers
    assert all(item.offer_id is None for item in env.get_state().occurrences.values())


def test_two_occurrences_take_independent_allocations_and_share_capacity() -> None:
    env = SalesEnvironment(
        make_scenario(
            deals=[("deal_00", ["A", "B"], [("A", "B")], ["B"])],
            capacities={"ae": 1.0, "se": 1.0},
            horizon=5,
        )
    )
    env.reset()
    first = primary_occurrence_id("deal_00", "deal_00:A")
    second = env.open_occurrence("deal_00", "deal_00:A")
    env.set_lifecycle(second.occurrence_id, OccurrenceLifecycle.ACTIVE)
    untouched = env.get_state()
    assert untouched.occurrences[second.occurrence_id].readiness_source is ReadinessSource.UNRESOLVED
    state, info = env.step(AllocationAction({("deal_00", second.occurrence_id, "ae"): 0.4}))
    assert state.occurrences[second.occurrence_id].progress == 0.0
    assert info.wasted_allocation == 0.4
    env.declare_ready(second.occurrence_id)
    state, _info = env.step(
        AllocationAction(
            {
                ("deal_00", first, "ae"): 0.4,
                ("deal_00", second.occurrence_id, "se"): 0.6,
            }
        )
    )
    assert state.occurrences[first].progress == 0.4
    assert state.occurrences[second.occurrence_id].progress == 0.6
    assert state.task_progress[("deal_00", "deal_00:A")] == 0.4
    assert state.task_progress[("deal_00", "deal_00:B")] == 0.0
    state, _info = env.step(AllocationAction({("deal_00", first, "ae"): 1.0}))
    assert state.occurrences[first].lifecycle is OccurrenceLifecycle.COMPLETED
    assert state.occurrences[first].progress == 1.0
    assert state.occurrences[second.occurrence_id].progress == 0.6
    assert state.occurrences[second.occurrence_id].lifecycle is OccurrenceLifecycle.ACTIVE
    require_dag(set(env.scenario.deals["deal_00"].tasks), env.scenario.deals["deal_00"].edges)
    env2 = SalesEnvironment(
        make_scenario(deals=[("deal_00", ["A"], [], ["A"])], capacities={"ae": 1.0})
    )
    env2.reset()
    other = env2.open_occurrence("deal_00", "deal_00:A")
    env2.set_lifecycle(other.occurrence_id, OccurrenceLifecycle.ACTIVE)
    env2.declare_ready(other.occurrence_id)
    try:
        env2.step(
            AllocationAction(
                {
                    ("deal_00", primary_occurrence_id("deal_00", "deal_00:A"), "ae"): 0.6,
                    ("deal_00", other.occurrence_id, "ae"): 0.6,
                }
            )
        )
    except CapacityViolation:
        return
    raise AssertionError("occurrences did not share capacity")


def test_suspended_can_be_ready_and_active_can_be_unready() -> None:
    env = SalesEnvironment(
        make_scenario(deals=[("deal_00", ["pred", "next"], [("pred", "next")], ["next"])])
    )
    env.reset()
    env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:pred"), "ae"): 1.0}))
    nxt = primary_occurrence_id("deal_00", "deal_00:next")
    state = env.get_state()
    assert state.occurrences[nxt].lifecycle is OccurrenceLifecycle.ACTIVE
    assert is_allocation_eligible(state.occurrences[nxt], state, env.scenario)
    env.set_lifecycle(nxt, OccurrenceLifecycle.SUSPENDED)
    state = env.get_state()
    assert state.occurrences[nxt].lifecycle is OccurrenceLifecycle.SUSPENDED
    assert not is_allocation_eligible(state.occurrences[nxt], state, env.scenario)
    blocked = SalesEnvironment(
        make_scenario(deals=[("deal_00", ["pred", "next"], [("pred", "next")], ["next"])])
    )
    blocked.reset()
    state = blocked.get_state()
    nxt = primary_occurrence_id("deal_00", "deal_00:next")
    assert state.occurrences[nxt].lifecycle is OccurrenceLifecycle.ACTIVE
    assert not is_allocation_eligible(state.occurrences[nxt], state, blocked.scenario)


def test_fifo_and_bottleneck_rank_occurrences_by_the_type() -> None:
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
    assert ( "deal_01", primary_occurrence_id("deal_01", "deal_01:early"), "ae") in action.allocations
    chain = make_scenario(
        deals=[
            ("deal_00", ["root", "b", "c"], [("root", "b"), ("b", "c")], ["c"]),
        ],
        capacities={"ae": 1.0},
    )
    env = SalesEnvironment(chain)
    env.reset()
    extra = env.open_occurrence("deal_00", "deal_00:root")
    env.set_lifecycle(extra.occurrence_id, OccurrenceLifecycle.ACTIVE)
    env.declare_ready(extra.occurrence_id)
    state = env.get_state()
    assert downstream_incomplete_count(state, chain, "deal_00", "deal_00:root") == 2
    action = BottleneckPolicy().select_action(state, chain)
    assert ("deal_00", primary_occurrence_id("deal_00", "deal_00:root"), "ae") in action.allocations
    assert ("deal_00", extra.occurrence_id, "ae") not in action.allocations


def _succeeded(occurrence) -> bool:
    tolerance = 1e-9
    return occurrence.lifecycle is OccurrenceLifecycle.COMPLETED and is_complete(
        occurrence.progress, tolerance
    )


# ---- Policies ----


def _assert_feasible(scenario: Scenario, action, state) -> None:
    validate_action(
        action,
        capacities={resource_id: resource.capacity for resource_id, resource in scenario.resources.items()},
        occurrence_ids=set(state.occurrences),
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
    assert ("deal_01", primary_occurrence_id("deal_01", "deal_01:early"), "ae") in action.allocations
    assert ("deal_00", primary_occurrence_id("deal_00", "deal_00:late"), "ae") not in action.allocations
    _assert_feasible(scenario, action, state)


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
    assert ("deal_00", primary_occurrence_id("deal_00", "deal_00:root"), "ae") in action.allocations
    assert ("deal_01", primary_occurrence_id("deal_01", "deal_01:leaf"), "ae") not in action.allocations


def test_policies_stay_feasible_with_a_zero_capacity_resource() -> None:
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
            _assert_feasible(scenario, action, state)
            assert action.used_by_resource().get("legal", 0.0) == 0.0
            state, _info = env.step(action)


def test_random_policy_is_reproducible() -> None:
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
            _assert_feasible(short, action, state)
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
