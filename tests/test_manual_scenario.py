from dealos.diagnostics.manual_scenario import manual_scenario
from dealos.domain.models import AllocationAction
from dealos.experiments.structure import measure_scenario
from dealos.sim.env import SalesEnvironment


def test_manual_scenario_shape() -> None:
    scenario = manual_scenario()
    measured = measure_scenario(scenario)
    assert measured.n_deals == 2
    assert measured.n_tasks == 7
    assert measured.n_edges == 6
    assert measured.mean_dependency_depth == 1.0
    assert measured.max_dependency_depth == 2
    assert measured.initially_completed == 0
    assert measured.initially_blocked == 5
    assert measured.capacities == {"ae": 1.0}
    assert scenario.deals["deal_00"].targets == frozenset({"deal_00:join"})
    assert scenario.deals["deal_01"].targets == frozenset({"deal_01:end"})


def test_two_hand_calculated_transitions() -> None:
    env = SalesEnvironment(manual_scenario())
    state = env.reset()
    assert all(value == 0.0 for value in state.task_progress.values())

    state, _info = env.step(AllocationAction({("deal_00", "deal_00:start", "ae"): 1.0}))
    assert state.time == 1
    assert state.task_progress[("deal_00", "deal_00:start")] == 1.0
    assert state.task_progress[("deal_00", "deal_00:left")] == 0.0
    assert state.task_progress[("deal_00", "deal_00:right")] == 0.0
    assert state.task_progress[("deal_00", "deal_00:join")] == 0.0
    assert state.task_progress[("deal_01", "deal_01:root")] == 0.0
    assert state.task_status[("deal_00", "deal_00:left")].value == "not_started"
    assert state.task_status[("deal_00", "deal_00:right")].value == "not_started"
    assert state.task_status[("deal_00", "deal_00:join")].value == "blocked"
    assert state.task_status[("deal_01", "deal_01:mid")].value == "blocked"

    state, _info = env.step(
        AllocationAction(
            {
                ("deal_00", "deal_00:left", "ae"): 0.4,
                ("deal_00", "deal_00:right", "ae"): 0.6,
            }
        )
    )
    assert state.time == 2
    assert state.task_progress[("deal_00", "deal_00:left")] == 0.4
    assert state.task_progress[("deal_00", "deal_00:right")] == 0.6
    assert state.task_progress[("deal_00", "deal_00:join")] == 0.0
    assert state.task_progress[("deal_00", "deal_00:start")] == 1.0
    assert state.task_progress[("deal_01", "deal_01:root")] == 0.0
    assert state.task_progress[("deal_01", "deal_01:mid")] == 0.0
    assert state.task_progress[("deal_01", "deal_01:end")] == 0.0
    assert state.task_status[("deal_00", "deal_00:join")].value == "not_started"
    assert state.deal_complete == {"deal_00": 0, "deal_01": 0}
