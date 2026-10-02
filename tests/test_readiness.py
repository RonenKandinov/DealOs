from dealos.domain.models import AllocationAction
from dealos.domain.readiness import AndMinReadiness
from dealos.sim.env import SalesEnvironment
from tests.builders import make_scenario


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
        AllocationAction({("deal_00", "deal_00:join", "ae"): 1.0})
    )
    assert state.task_progress[("deal_00", "deal_00:join")] == 0.25
