"""Occurrence representation beside the type-level DAG. One occurrence matches V1."""

from dealos.domain.dynamics import is_complete
from dealos.domain.graph import require_dag
from dealos.domain.models import (
    AllocationAction,
    OccurrenceLifecycle,
    ReadinessSource,
    primary_occurrence_id,
)
from dealos.experiments.runner import rollout
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.base import is_allocation_eligible
from dealos.policies.bottleneck import BottleneckPolicy, downstream_incomplete_count
from dealos.policies.fifo import FIFOPolicy
from dealos.sim.constraints import CapacityViolation
from dealos.sim.env import SalesEnvironment
from tests.builders import make_scenario


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
