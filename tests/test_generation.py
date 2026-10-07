"""Generation and control: seeded portfolios, presets, controlled edits, and the horizon sweep.

Merged from test_generator, test_preset_structure, test_controlled, and test_horizon_sweep.
Every test body is unchanged.
"""

import pytest

from dealos.domain.graph import has_cycle, predecessors
from dealos.domain.models import GeneratorConfig
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
from dealos.experiments.horizon_sweep import same_scenario_body, with_horizon
from dealos.experiments.runner import rollout
from dealos.generator.generate import _TEMPLATE, SUITABLE_RESOURCES, generate_scenario
from dealos.generator.presets import PRESETS, get_preset
from dealos.policies.fifo import FIFOPolicy

OPTIONAL_BY_TYPE: dict[str, list[str]] = {}
for name, task_type, _preds, optional in _TEMPLATE:
    if optional:
        OPTIONAL_BY_TYPE.setdefault(task_type, []).append(name)


# ---- Generator ----


def test_same_seed_reproduces_the_scenario_and_another_seed_differs() -> None:
    config = get_preset("balanced")
    first = generate_scenario(config, seed=0).to_dict()
    second = generate_scenario(config, seed=0).to_dict()
    other = generate_scenario(config, seed=1).to_dict()
    assert first == second
    assert first != other


def test_presets_produce_dependency_consistent_portfolios() -> None:
    for name in sorted(PRESETS):
        scenario = generate_scenario(get_preset(name), seed=0)
        assert scenario.generator.name == name
        assert len(scenario.deals) == get_preset(name).n_deals
        for deal_id, deal in scenario.deals.items():
            assert deal.targets
            for task_id, progress in (
                (task_id, scenario.initial_progress[(deal_id, task_id)]) for task_id in deal.tasks
            ):
                assert 0.0 <= progress <= 1.0
                if progress >= 1.0:
                    for pred in predecessors(deal.edges, task_id):
                        assert scenario.initial_progress[(deal_id, pred)] >= 1.0
            for task_id, task in deal.tasks.items():
                assert 0.0 < scenario.phi[(deal_id, task_id)] <= 1.0
                suitable = SUITABLE_RESOURCES[task.task_type]
                for resource_id in scenario.resources:
                    alpha = scenario.alpha[(deal_id, task_id, resource_id)]
                    q_value = scenario.suitability[(deal_id, task_id, resource_id)]
                    assert alpha > 0.0
                    assert 0.0 <= q_value <= 1.0
                    if resource_id not in suitable:
                        assert q_value == 0.0
                    else:
                        assert q_value > 0.0


def test_full_template_keeps_and_join_at_integration() -> None:
    config = GeneratorConfig(
        name="full",
        n_deals=1,
        horizon=5,
        capacities={
            "ae": 1.0,
            "sales_engineer": 1.0,
            "legal": 1.0,
            "security": 1.0,
            "solutions_architect": 1.0,
        },
        extra_edge_probability=0.0,
        optional_drop_probability=0.0,
        partial_start_fraction=0.0,
        phi_range=(1.0, 1.0),
        alpha_range=(0.2, 0.2),
        q_range=(1.0, 1.0),
    )
    scenario = generate_scenario(config, seed=0)
    deal = scenario.deals["deal_00"]
    assert predecessors(deal.edges, "deal_00:integration") == (
        "deal_00:security_review",
        "deal_00:solution_design",
    )
    assert "deal_00:signature" in deal.targets


def test_legal_bottleneck_keeps_legal_tasks_and_cuts_legal_capacity() -> None:
    scenario = generate_scenario(get_preset("legal_bottleneck"), seed=2)
    assert scenario.resources["legal"].capacity == 0.5
    for deal in scenario.deals.values():
        names = {task.name for task in deal.tasks.values()}
        assert "legal_review" in names
        assert "contract_redline" in names


def test_dependency_heavy_keeps_every_template_task() -> None:
    scenario = generate_scenario(get_preset("dependency_heavy"), seed=0)
    for deal in scenario.deals.values():
        assert len(deal.tasks) == 11
        assert len(deal.edges) >= 12


# ---- Preset structure ----


def test_capacity_presets_differ_from_balanced() -> None:
    balanced = get_preset("balanced")
    legal = get_preset("legal_bottleneck")
    technical = get_preset("technical_bottleneck")
    constrained = get_preset("resource_constrained")
    heavy = get_preset("dependency_heavy")

    assert legal.capacities["legal"] < balanced.capacities["legal"]
    assert technical.capacities["sales_engineer"] < balanced.capacities["sales_engineer"]
    assert technical.capacities["solutions_architect"] < balanced.capacities["solutions_architect"]
    assert sum(constrained.capacities.values()) < sum(balanced.capacities.values())
    for resource_id in balanced.capacities:
        assert constrained.capacities[resource_id] < balanced.capacities[resource_id]
    assert heavy.extra_edge_probability > balanced.extra_edge_probability


def test_protected_types_targets_dags_and_seed_reproducibility() -> None:
    for name, config in PRESETS.items():
        required = [
            task_name
            for task_type in config.protected_task_types
            for task_name in OPTIONAL_BY_TYPE.get(task_type, [])
        ]
        first = generate_scenario(config, seed=0)
        assert first.to_dict() == generate_scenario(config, seed=0).to_dict()
        assert first.to_dict() != generate_scenario(config, seed=1).to_dict()
        for seed in range(20):
            scenario = generate_scenario(config, seed)
            assert len(scenario.deals) == config.n_deals
            for resource_id, resource in scenario.resources.items():
                assert resource.capacity == config.capacities[resource_id]
            for deal in scenario.deals.values():
                assert deal.targets
                assert not has_cycle(set(deal.tasks), deal.edges)
                names = {task.name for task in deal.tasks.values()}
                for task_name in required:
                    assert task_name in names, f"{name} seed {seed} dropped protected {task_name}"


def test_dependency_heavy_keeps_the_template_and_adds_edges() -> None:
    template_edges = 12
    total_edges = 0
    for seed in range(20):
        scenario = generate_scenario(get_preset("dependency_heavy"), seed)
        for deal in scenario.deals.values():
            assert len(deal.tasks) == 11
            total_edges += len(deal.edges)
    assert total_edges > 20 * 4 * template_edges


# ---- Controlled edits ----


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


# ---- Horizon sweep ----


def test_one_seed_keeps_graphs_and_parameters_across_horizons():
    base = generate_scenario(get_preset("balanced"), 0)
    assert base.horizon == 40
    for horizon in (20, 40, 60, 80, 120):
        scenario = with_horizon(base, horizon)
        assert scenario.horizon == horizon
        assert scenario.generator.horizon == horizon
        assert same_scenario_body(base, scenario)


def test_t40_fifo_seed0_matches_the_existing_rollout():
    base = generate_scenario(get_preset("balanced"), 0)
    scenario = with_horizon(base, 40)
    diagnosed = diagnose_rollout(scenario, FIFOPolicy())
    original = rollout(generate_scenario(get_preset("balanced"), 0), FIFOPolicy())
    assert diagnosed.completed_deals == original.completed_deals == 2
    assert diagnosed.steps == original.steps == 40
    assert diagnosed.completion_times == original.completion_times
    assert diagnosed.horizon == 40
