import pytest

from dealos.domain.models import primary_occurrence_id, AllocationAction
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.sim.env import SalesEnvironment
from tests.builders import make_scenario


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
    from dealos.policies.fifo import FIFOPolicy

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
