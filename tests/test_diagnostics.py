"""Hand-checked diagnostics on the two-deal chain A1→A2→A3, B1→B2."""

from dataclasses import replace

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.models import primary_occurrence_id, AllocationAction, Resource
from dealos.experiments.diagnostics import (
    diagnose_actions,
    diagnose_rollout,
    inspect_unfinished,
    step_concentration,
    step_idle,
    task_buckets,
)
from dealos.experiments.runner import rollout
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.bottleneck import BottleneckPolicy
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.random import RandomPolicy


def _progress(**values: float) -> dict[tuple[str, str], float]:
    base = {
        ("deal_A", "deal_A:A1"): 0.0,
        ("deal_A", "deal_A:A2"): 0.0,
        ("deal_A", "deal_A:A3"): 0.0,
        ("deal_B", "deal_B:B1"): 0.0,
        ("deal_B", "deal_B:B2"): 0.0,
    }
    for key, value in values.items():
        deal_id, _name = key.split(":")
        base[(deal_id, key)] = value
    return base


def test_task_buckets_and_target_split_on_explicit_progress():
    progress = _progress(**{
        "deal_A:A1": 1.0,
        "deal_A:A2": 0.5,
        "deal_A:A3": 0.875,
        "deal_B:B1": 0.0,
        "deal_B:B2": 0.0,
    })
    # Targets are A3 and B2. Non-targets are A1, A2, B1.
    target_mean = (0.875 + 0.0) / 2
    nontarget_mean = (1.0 + 0.5 + 0.0) / 3
    assert target_mean == 0.4375
    assert nontarget_mean == 0.5
    assert task_buckets(list(progress.values()), 1e-9) == (2 / 5, 2 / 5, 1 / 5)

    scenario = chain_debug_scenario(initial=progress)
    deals = {item.deal_id: item for item in inspect_unfinished(scenario, progress)}
    # A3 = 0.875 >= 0.8, so deal A is near the target even though A2 = 0.5.
    assert deals["deal_A"].label == "A"
    assert deals["deal_A"].early_hold is False
    assert deals["deal_A"].front_progress == 0.5
    assert deals["deal_A"].critical_path == ("deal_A:A1", "deal_A:A2", "deal_A:A3")
    assert deals["deal_A"].critical_residual == 0.0 + 0.5 + 0.125
    # B1 is a depth-0 non-target at 0, and B2 is still 0.
    assert deals["deal_B"].label == "B"
    assert deals["deal_B"].critical_path == ("deal_B:B1", "deal_B:B2")
    assert deals["deal_B"].critical_residual == 2.0
    assert deals["deal_B"].early_hold is True
    assert deals["deal_B"].front_progress == 0.0

    # A target at 0.875 is label A even if the front of the chain is at 0.25.
    ahead = _progress(**{
        "deal_A:A1": 0.25,
        "deal_A:A2": 0.25,
        "deal_A:A3": 0.875,
        "deal_B:B1": 1.0,
        "deal_B:B2": 1.0,
    })
    ahead_deal = inspect_unfinished(scenario, ahead)[0]
    assert ahead_deal.label == "A"
    assert ahead_deal.early_hold is True
    assert ahead_deal.front_progress == 0.25


def test_early_boundary_and_midchain_hold_are_mixed():
    scenario = chain_debug_scenario()
    # A2 = 0.5 is not below the 0.5 early threshold, and A3 = 0.25 is below 0.8.
    boundary = _progress(**{"deal_A:A1": 1.0, "deal_A:A2": 0.5, "deal_A:A3": 0.25, "deal_B:B1": 1.0, "deal_B:B2": 1.0})
    boundary_deals = inspect_unfinished(scenario, boundary)
    assert len(boundary_deals) == 1
    assert boundary_deals[0].deal_id == "deal_A"
    assert boundary_deals[0].label == "C"
    assert boundary_deals[0].critical_residual == 0.5 + 0.75

    # A1 and A2 are done. The open work is the target itself, depth 2.
    midchain = _progress(**{"deal_A:A1": 1.0, "deal_A:A2": 1.0, "deal_A:A3": 0.25, "deal_B:B1": 1.0, "deal_B:B2": 1.0})
    mid = inspect_unfinished(scenario, midchain)[0]
    assert mid.label == "C"
    assert mid.critical_residual == 0.75
    assert mid.early_hold is False
    assert mid.front_progress == 1.0


def test_idle_split_and_herfindahl_on_the_chain():
    scenario = chain_debug_scenario()
    zeros = _progress()
    both = AllocationAction({
        ("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 0.25,
        ("deal_B", primary_occurrence_id("deal_B", "deal_B:B1"), "ae"): 0.75,
    })
    idle = step_idle(scenario, zeros, both)
    # A1 and B1 are eligible. Capacity is 1, so nothing is left idle.
    assert idle["ae"] == type(idle["ae"])(1.0, 0.0, 0.0)
    concentration = step_concentration(both)
    assert concentration.tasks_with_allocation == 2
    assert concentration.herfindahl == 0.25**2 + 0.75**2

    partial = AllocationAction({("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 0.25})
    partial_idle = step_idle(scenario, zeros, partial)
    # Eligible work exists, and 0.75 of capacity is left unused.
    assert partial_idle["ae"].allocated == 0.25
    assert partial_idle["ae"].unused_no_eligible == 0.0
    assert partial_idle["ae"].unused_despite_eligible == 0.75
    assert step_concentration(partial).herfindahl == 1.0

    done = _progress(**{
        "deal_A:A1": 1.0,
        "deal_A:A2": 1.0,
        "deal_A:A3": 1.0,
        "deal_B:B1": 1.0,
        "deal_B:B2": 1.0,
    })
    empty = AllocationAction({})
    no_work = step_idle(scenario, done, empty)
    assert no_work["ae"].allocated == 0.0
    assert no_work["ae"].unused_no_eligible == 1.0
    assert no_work["ae"].unused_despite_eligible == 0.0
    assert step_concentration(empty).herfindahl is None
    assert step_concentration(empty).tasks_with_allocation == 0

    # Two resource keys on one task are one task in the Herfindahl.
    collapsed = AllocationAction({
        ("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 0.25,
        ("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "legal"): 0.75,
    })
    assert step_concentration(collapsed).tasks_with_allocation == 1
    assert step_concentration(collapsed).herfindahl == 1.0


def test_unsuitable_resource_is_unused_because_no_compatible_work():
    scenario = chain_debug_scenario()
    suitability = dict(scenario.suitability)
    alpha = dict(scenario.alpha)
    for deal_id, task_id in scenario.task_keys():
        suitability[(deal_id, task_id, "legal")] = 0.0
        alpha[(deal_id, task_id, "legal")] = 1.0
    resources = dict(scenario.resources)
    resources["legal"] = Resource("legal", "Legal", 1.0)
    scenario = replace(scenario, resources=resources, suitability=suitability, alpha=alpha)
    action = AllocationAction({("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 1.0})
    idle = step_idle(scenario, _progress(), action)
    assert idle["ae"].unused_despite_eligible == 0.0
    assert idle["ae"].allocated == 1.0
    assert idle["legal"].allocated == 0.0
    assert idle["legal"].unused_no_eligible == 1.0
    assert idle["legal"].unused_despite_eligible == 0.0


def test_one_step_chain_matches_hand_calculation():
    scenario = chain_debug_scenario()
    action = AllocationAction({("deal_A", primary_occurrence_id("deal_A", "deal_A:A1"), "ae"): 1.0})
    diagnosis = diagnose_actions(scenario, [action])
    # Same-day rule: only A1 moves. phi = alpha = q = readiness = 1, so A1 ends at 1.
    assert diagnosis.steps == 1
    assert diagnosis.completed_deals == 0
    assert diagnosis.mean_target_progress == 0.0
    assert diagnosis.mean_nontarget_progress == 1.0 / 3.0
    assert diagnosis.fraction_zero == 0.8
    assert diagnosis.fraction_partial == 0.0
    assert diagnosis.fraction_one == 0.2
    labels = {item.deal_id: item.label for item in diagnosis.unfinished}
    assert labels == {"deal_A": "B", "deal_B": "B"}
    residuals = {item.deal_id: item.critical_residual for item in diagnosis.unfinished}
    assert residuals == {"deal_A": 2.0, "deal_B": 2.0}
    assert diagnosis.mean_allocated_fraction == 1.0
    assert diagnosis.mean_unused_no_eligible_fraction == 0.0
    assert diagnosis.mean_unused_despite_eligible_fraction == 0.0
    assert diagnosis.mean_herfindahl == 1.0
    assert diagnosis.mean_tasks_with_allocation == 1.0


def test_diagnostic_rollout_matches_existing_completed_counts():
    scenario = generate_scenario(get_preset("balanced"), 0)
    factories = (lambda: RandomPolicy(0), lambda: FIFOPolicy(), lambda: BottleneckPolicy())
    for factory in factories:
        diagnosed = diagnose_rollout(scenario, factory())
        original = rollout(scenario, factory())
        assert diagnosed.completed_deals == original.completed_deals
        assert diagnosed.steps == original.steps
        assert diagnosed.completed_deals == len(scenario.deals) - len(diagnosed.unfinished)
