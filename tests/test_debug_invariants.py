"""Invariant checks against the V1 equations. Not a policy comparison."""

from __future__ import annotations

import json
import time
from pathlib import Path

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.dynamics import is_complete
from dealos.domain.graph import has_cycle, predecessors
from dealos.domain.models import AllocationAction, primary_occurrence_id, task_of_occurrence
from dealos.domain.readiness import AndMinReadiness
from dealos.experiments.runner import rollout
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import PRESETS, get_preset
from dealos.policies.base import eligible_tasks
from dealos.policies.bottleneck import BottleneckPolicy
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.random import RandomPolicy
from dealos.sim.constraints import validate_action
from dealos.sim.env import SalesEnvironment

_LOG = Path(__file__).resolve().parents[1] / "debug-919b8f.log"


def _log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    payload = {
        "sessionId": "919b8f",
        "runId": "invariant-check",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with _LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    # #endregion


def _ready(scenario, progress, deal_id: str, task_id: str) -> float:
    values = [
        progress[(deal_id, pred)]
        for pred in predecessors(scenario.deals[deal_id].edges, task_id)
    ]
    return AndMinReadiness().readiness(values)


def test_readiness_cases() -> None:
    rule = AndMinReadiness()
    assert rule.readiness(()) == 1.0
    assert rule.readiness((0.0,)) == 0.0
    assert rule.readiness((0.4,)) == 0.4
    assert rule.readiness((1.0,)) == 1.0
    assert rule.readiness((0.2, 0.9, 0.5)) == 0.2
    assert rule.readiness((1.0, 1.0)) == 1.0
    _log("H5", "test_debug_invariants.py:readiness", "readiness cases", {"empty": 1.0, "partial_multi": 0.2})


def test_chain_hand_transitions_delay_successor_by_one_day() -> None:
    """A1 -> A2 -> A3 and B1 -> B2. Successor does not move on the day its predecessor finishes."""

    scenario = chain_debug_scenario()
    env = SalesEnvironment(scenario)
    state = env.reset()
    schedule = [
        {("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 1.0},
        {("deal_A", primary_occurrence_id("deal_A", "deal_A:A2"), "ae"): 1.0},
        {("deal_B", primary_occurrence_id("deal_B", "deal_B:B1"), "ae"): 1.0},
        {("deal_A", primary_occurrence_id("deal_A", "deal_A:A3"), "ae"): 1.0},
        {("deal_B", primary_occurrence_id("deal_B", "deal_B:B2"), "ae"): 1.0},
    ]
    expected = [
        {"deal_A:A1": 1.0, "deal_A:A2": 0.0, "deal_A:A3": 0.0, "deal_B:B1": 0.0, "deal_B:B2": 0.0},
        {"deal_A:A1": 1.0, "deal_A:A2": 1.0, "deal_A:A3": 0.0, "deal_B:B1": 0.0, "deal_B:B2": 0.0},
        {"deal_A:A1": 1.0, "deal_A:A2": 1.0, "deal_A:A3": 0.0, "deal_B:B1": 1.0, "deal_B:B2": 0.0},
        {"deal_A:A1": 1.0, "deal_A:A2": 1.0, "deal_A:A3": 1.0, "deal_B:B1": 1.0, "deal_B:B2": 0.0},
        {"deal_A:A1": 1.0, "deal_A:A2": 1.0, "deal_A:A3": 1.0, "deal_B:B1": 1.0, "deal_B:B2": 1.0},
    ]
    expected_deals = [(0, 0), (0, 0), (0, 0), (1, 0), (1, 1)]

    for step_index, (raw_action, after, deals) in enumerate(zip(schedule, expected, expected_deals)):
        before = {f"{deal}:{task.split(':', 1)[1]}": value for (deal, task), value in state.task_progress.items()}
        readiness = {
            f"{deal}:{task.split(':', 1)[1]}": _ready(scenario, state.task_progress, deal, task)
            for deal, task in state.task_progress
        }
        action = AllocationAction(raw_action)
        state, info = env.step(action)
        after_actual = {
            f"{deal}:{task.split(':', 1)[1]}": value for (deal, task), value in state.task_progress.items()
        }
        _log(
            "H1",
            "test_debug_invariants.py:chain",
            "timestep",
            {
                "t_before": step_index,
                "before": before,
                "readiness_at_start": readiness,
                "allocation": {f"{d}:{t}:{r}": a for (d, t, r), a in raw_action.items()},
                "capacity_ae": 1.0,
                "deltas": {f"{d}:{t.split(':', 1)[1]}": delta for (d, t), delta in info.deltas.items()},
                "after": after_actual,
                "completed_deals": dict(state.deal_complete),
            },
        )
        assert after_actual == after
        assert state.deal_complete["deal_A"] == deals[0]
        assert state.deal_complete["deal_B"] == deals[1]
        for value in state.task_progress.values():
            assert 0.0 <= value <= 1.0

    assert info.newly_completed_deals == ("deal_B",)


def test_same_day_allocation_to_successor_adds_no_progress() -> None:
    scenario = chain_debug_scenario()
    env = SalesEnvironment(scenario)
    env.reset()
    state, info = env.step(
        AllocationAction(
            {
                ("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 0.5,
                ("deal_A", primary_occurrence_id("deal_A", "deal_A:A2"), "ae"): 0.5,
            }
        )
    )
    _log(
        "H1",
        "test_debug_invariants.py:same_day",
        "successor allocated while predecessor incomplete",
        {
            "A1": state.task_progress[("deal_A", "deal_A:A1")],
            "A2": state.task_progress[("deal_A", "deal_A:A2")],
            "delta_A2": info.deltas[("deal_A", "deal_A:A2")],
        },
    )
    assert state.task_progress[("deal_A", "deal_A:A1")] == 0.5
    assert state.task_progress[("deal_A", "deal_A:A2")] == 0.0
    assert info.deltas[("deal_A", "deal_A:A2")] == 0.0


def test_existing_progress_is_not_pulled_back_to_readiness() -> None:
    scenario = chain_debug_scenario(initial={("deal_A", "deal_A:A2"): 0.3})
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert state.task_progress[("deal_A", "deal_A:A2")] == 0.3
    assert state.task_status[("deal_A", "deal_A:A2")].value == "blocked"
    state, info = env.step(AllocationAction({}))
    assert state.task_progress[("deal_A", "deal_A:A2")] == 0.3
    assert info.deltas[("deal_A", "deal_A:A2")] == 0.0
    _log("H6", "test_debug_invariants.py:no_pullback", "progress kept ahead of ready", {"A2": 0.3})


def test_incomplete_target_blocks_deal_completion() -> None:
    scenario = chain_debug_scenario(initial={("deal_A", "deal_A:A1"): 1.0, ("deal_A", "deal_A:A2"): 1.0})
    env = SalesEnvironment(scenario)
    state = env.reset()
    assert state.task_progress[("deal_A", "deal_A:A3")] == 0.0
    assert state.deal_complete["deal_A"] == 0
    state, info = env.step(AllocationAction({("deal_A", primary_occurrence_id("deal_A", "deal_A:A3"), "ae"): 1.0}))
    assert state.deal_complete["deal_A"] == 1
    assert info.newly_completed_deals == ("deal_A",)
    assert state.deal_complete["deal_B"] == 0


def test_completed_task_gains_no_further_progress() -> None:
    scenario = chain_debug_scenario(initial={("deal_B", "deal_B:B1"): 1.0})
    env = SalesEnvironment(scenario)
    env.reset()
    state, info = env.step(AllocationAction({("deal_B", primary_occurrence_id("deal_B", "deal_B:B1"), "ae"): 1.0}))
    assert state.task_progress[("deal_B", "deal_B:B1")] == 1.0
    assert info.deltas[("deal_B", "deal_B:B1")] == 0.0
    assert info.wasted_allocation == 1.0


def test_progress_is_bounded_and_monotone_on_the_chain() -> None:
    scenario = chain_debug_scenario()
    env = SalesEnvironment(scenario)
    state = env.reset()
    previous = dict(state.task_progress)
    for _ in range(5):
        state, _info = env.step(AllocationAction({("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 1.0}))
        for key, value in state.task_progress.items():
            assert 0.0 <= value <= 1.0
            assert value + 1e-12 >= previous[key]
        previous = dict(state.task_progress)


def test_policies_respect_bounds_eligibility_and_capacity() -> None:
    violations: list[str] = []
    for preset_name in ("balanced", "legal_bottleneck", "resource_constrained"):
        scenario = generate_scenario(get_preset(preset_name), seed=0)
        policies = [RandomPolicy(0), FIFOPolicy(), BottleneckPolicy()]
        for policy in policies:
            env = SalesEnvironment(scenario)
            state = env.reset()
            for _ in range(6):
                if env.is_done():
                    break
                action = policy.select_action(state, scenario)
                try:
                    validate_action(
                        action,
                        capacities={rid: res.capacity for rid, res in scenario.resources.items()},
                        occurrence_ids=set(state.occurrences),
                        tolerance=scenario.simulation.capacity_tolerance,
                    )
                except Exception as exc:  # noqa: BLE001 - record the violation for the log
                    violations.append(f"{preset_name}:{policy.name}: {exc}")
                eligible = set(eligible_tasks(state, scenario))
                for (deal_id, occurrence_id, resource_id), amount in action.allocations.items():
                    task_id = task_of_occurrence(deal_id, occurrence_id)
                    if amount < 0.0 or amount > 1.0 + scenario.simulation.capacity_tolerance:
                        violations.append(f"bounds {policy.name} {amount}")
                    if scenario.suitability[(deal_id, task_id, resource_id)] == 0.0 and amount > 0.0:
                        violations.append(f"incompatible {policy.name} {resource_id}")
                    if (deal_id, task_id) not in eligible and amount > 0.0:
                        violations.append(f"ineligible {policy.name} {task_id}")
                    if is_complete(state.task_progress[(deal_id, task_id)], scenario.simulation.completion_tolerance):
                        violations.append(f"completed {policy.name} {task_id}")
                before = dict(state.task_progress)
                state, _info = env.step(action)
                for key, value in state.task_progress.items():
                    if value < -1e-12 or value > 1.0 + 1e-12 or value + 1e-12 < before[key]:
                        violations.append(f"progress {policy.name} {key} {before[key]} -> {value}")
                for deal_id, deal in scenario.deals.items():
                    targets_done = all(
                        is_complete(state.task_progress[(deal_id, target)], scenario.simulation.completion_tolerance)
                        for target in deal.targets
                    )
                    if state.deal_complete[deal_id] == 1 and not targets_done:
                        violations.append(f"deal {deal_id}")
                    if state.deal_complete[deal_id] == 0 and targets_done:
                        violations.append(f"missed deal {deal_id}")
    _log("H3", "test_debug_invariants.py:policies", "policy invariant sweep", {"violations": violations})
    assert violations == []


def test_same_seed_reproduces_actions_and_other_seeds_differ() -> None:
    scenario = generate_scenario(get_preset("balanced"), seed=4)

    def trace(policy_seed: int) -> list[tuple[tuple, float]]:
        env = SalesEnvironment(scenario)
        policy = RandomPolicy(policy_seed)
        state = env.reset()
        rows = []
        for _ in range(4):
            action = policy.select_action(state, scenario)
            rows.append(tuple(sorted(action.allocations.items())))
            state, _info = env.step(action)
        return rows

    assert trace(4) == trace(4)
    assert trace(4) != trace(5)
    assert generate_scenario(get_preset("dependency_heavy"), 0).to_dict() == generate_scenario(
        get_preset("dependency_heavy"), 0
    ).to_dict()
    assert generate_scenario(get_preset("dependency_heavy"), 0).to_dict() != generate_scenario(
        get_preset("dependency_heavy"), 1
    ).to_dict()
    for config in PRESETS.values():
        scenario_one = generate_scenario(config, seed=3)
        for deal in scenario_one.deals.values():
            assert not has_cycle(set(deal.tasks), deal.edges)


def test_seed0_balanced_fifo_unchanged() -> None:
    """Fingerprint of the existing rollout, so this debug pass does not move the dynamics."""

    scenario = generate_scenario(get_preset("balanced"), seed=0)
    result = rollout(scenario, FIFOPolicy())
    _log(
        "H2",
        "test_debug_invariants.py:fingerprint",
        "balanced seed 0 fifo",
        {
            "completed_deals": result.completed_deals,
            "mean_task_progress": result.mean_task_progress,
            "steps": result.steps,
            "completion_times": result.completion_times,
        },
    )
    assert result.completed_deals == 2
    assert result.steps == 40
    assert result.completion_times["deal_00"] == 39
    assert result.completion_times["deal_02"] == 28
    assert result.completion_times["deal_01"] is None
    assert result.completion_times["deal_03"] is None
