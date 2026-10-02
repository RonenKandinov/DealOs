import pytest

from dealos.domain.dynamics import apply_progress, delta_x
from dealos.domain.models import AllocationAction
from dealos.sim.constraints import ActionBoundsError, CapacityViolation
from dealos.sim.env import SalesEnvironment
from tests.builders import make_scenario


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
    state, _info = env.step(AllocationAction({("deal_00", "deal_00:only", "ae"): 1.0}))
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
    env.step(AllocationAction({("deal_00", "deal_00:a", "ae"): 0.4}))
    env.reset()
    with pytest.raises(CapacityViolation):
        env.step(
            AllocationAction(
                {
                    ("deal_00", "deal_00:a", "ae"): 0.6,
                    ("deal_01", "deal_01:b", "ae"): 0.6,
                }
            )
        )


def test_allocation_above_one_is_rejected() -> None:
    scenario = make_scenario(deals=[("deal_00", ["only"], [], ["only"])])
    env = SalesEnvironment(scenario)
    env.reset()
    with pytest.raises(ActionBoundsError):
        env.step(AllocationAction({("deal_00", "deal_00:only", "ae"): 1.2}))


def test_zero_capacity_rejects_allocation_and_blocks_progress() -> None:
    scenario = make_scenario(
        deals=[("deal_00", ["only"], [], ["only"])],
        capacities={"ae": 0.0},
    )
    env = SalesEnvironment(scenario)
    state = env.reset()
    with pytest.raises(CapacityViolation):
        env.step(AllocationAction({("deal_00", "deal_00:only", "ae"): 0.1}))
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
    state, info = env.step(AllocationAction({("deal_00", "deal_00:done", "ae"): 1.0}))
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
    state, _info = env.step(AllocationAction({("deal_00", "deal_00:a", "ae"): 1.0}))
    assert state.task_progress[("deal_00", "deal_00:a")] == 1.0
    assert state.deal_complete["deal_00"] == 0
    state, info = env.step(AllocationAction({("deal_00", "deal_00:b", "ae"): 1.0}))
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
    state, _info = env.step(AllocationAction({("deal_00", "deal_00:only", "ae"): 1.0}))
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
