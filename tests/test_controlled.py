"""Identity checks for controlled edits on one frozen balanced scenario."""

import pytest

from dealos.domain.graph import predecessors
from dealos.experiments.controlled import (
    assert_only_changed,
    baseline_scenario,
    edit_scenario,
    with_capacity,
    with_edges,
    with_initial_progress,
    with_scaled_alpha,
    with_scaled_q,
)
from dealos.experiments.diagnostics import diagnose_rollout
from dealos.experiments.horizon_sweep import with_horizon
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.fifo import FIFOPolicy


def test_baseline_is_the_horizon_copy_and_seed0_fifo_still_finishes():
    scenario = baseline_scenario(0)
    reference = with_horizon(generate_scenario(get_preset("balanced"), 0), 80)
    assert scenario.horizon == 80
    assert_only_changed(reference, scenario, ())
    diagnosed = diagnose_rollout(scenario, FIFOPolicy())
    original = diagnose_rollout(reference, FIFOPolicy())
    assert diagnosed.completed_deals == original.completed_deals == 4
    assert diagnosed.completion_times == original.completion_times
    assert diagnosed.steps == original.steps


def test_capacity_edit_changes_only_the_named_resource():
    base = baseline_scenario(0)
    variant = with_capacity(base, "ae", base.resources["ae"].capacity * 0.25)
    assert variant.resources["ae"].capacity == 0.5
    assert variant.generator.capacities["ae"] == 0.5
    assert_only_changed(base, variant, ("capacity:ae",))
    assert variant.resources["legal"].capacity == base.resources["legal"].capacity
    same = with_capacity(base, "ae", base.resources["ae"].capacity)
    assert_only_changed(base, same, ())


def test_q_and_alpha_scales_do_not_cross():
    base = baseline_scenario(0)
    scaled_q = with_scaled_q(base, 0.5)
    assert_only_changed(base, scaled_q, ("q",))
    assert scaled_q.alpha == base.alpha
    for key, value in base.suitability.items():
        expected = 0.0 if value <= 0.0 else value * 0.5
        assert scaled_q.suitability[key] == expected
    clipped = with_scaled_q(base, 1.5)
    assert all(0.0 <= value <= 1.0 for value in clipped.suitability.values())
    assert all(value == 0.0 or value == 1.0 for value in clipped.suitability.values())

    scaled_alpha = with_scaled_alpha(base, 0.5)
    assert_only_changed(base, scaled_alpha, ("alpha",))
    assert scaled_alpha.suitability == base.suitability
    task_id = next(iter(base.deals["deal_00"].tasks))
    assert scaled_alpha.alpha[("deal_00", task_id, "ae")] == base.alpha[("deal_00", task_id, "ae")] * 0.5


def test_initial_progress_prefixes_stay_dependency_feasible():
    base = baseline_scenario(0)
    assert_only_changed(base, with_initial_progress(base, "baseline"), ())
    zeros = with_initial_progress(base, "zero")
    assert_only_changed(base, zeros, ("initial_progress",))
    assert all(value == 0.0 for value in zeros.initial_progress.values())
    for count in (1, 2, 3):
        variant = with_initial_progress(base, f"prefix:{count}")
        assert_only_changed(base, variant, ("initial_progress",))
        for deal_id, deal in variant.deals.items():
            completed = [
                task_id
                for task_id in deal.tasks
                if variant.initial_progress[(deal_id, task_id)] >= 1.0
            ]
            assert len(completed) == count
            for task_id in completed:
                for pred in predecessors(deal.edges, task_id):
                    assert variant.initial_progress[(deal_id, pred)] >= 1.0


def test_edge_edit_keeps_tasks_targets_and_parameters():
    base = baseline_scenario(0)
    stripped = with_edges(base, 0.0)
    assert_only_changed(base, stripped, ("edges:",))
    denser = with_edges(base, 0.3)
    assert_only_changed(base, denser, ("edges:",))
    assert any(base.deals[deal_id].edges != denser.deals[deal_id].edges for deal_id in base.deals)
    assert denser.alpha == base.alpha
    assert denser.suitability == base.suitability
    assert denser.initial_progress == base.initial_progress


def test_two_edits_are_rejected_when_only_one_is_allowed():
    base = baseline_scenario(0)
    both = with_scaled_q(with_capacity(base, "ae", 0.5), 0.5)
    with pytest.raises(RuntimeError, match="fixed fields"):
        assert_only_changed(base, both, ("capacity:ae",))


def test_density_edit_is_rejected_when_q_also_changes():
    base = baseline_scenario(0)
    both = with_scaled_q(with_edges(base, 0.04), 0.5)
    with pytest.raises(RuntimeError, match="fixed fields"):
        assert_only_changed(base, both, ("edges:",))


def test_q_edit_is_rejected_when_alpha_also_changes():
    base = baseline_scenario(0)
    both = with_scaled_alpha(with_scaled_q(base, 0.5), 0.5)
    with pytest.raises(RuntimeError, match="fixed fields"):
        assert_only_changed(base, both, ("q",))
    assert_only_changed(base, both, ("q", "alpha"))


def test_edit_scenario_keeps_baseline_edges_at_density_one():
    base = baseline_scenario(0)
    untouched = edit_scenario(base, density=1.0)
    assert_only_changed(base, untouched, ())
    edges_only = edit_scenario(base, density=0.5)
    assert_only_changed(base, edges_only, ("edges:",))
    both = edit_scenario(base, density=0.5, resource_id="ae", capacity_multiplier=0.5)
    assert_only_changed(base, both, ("edges:", "capacity:ae"))
    with pytest.raises(RuntimeError, match="fixed fields"):
        assert_only_changed(base, both, ("edges:",))
