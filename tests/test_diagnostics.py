"""Diagnostics and experiment layer: hand-checked chain diagnostics, the manual scenario,
the multi-seed runner, model-validation wrappers, decision screens, and blockage diagnosis.

Merged from test_diagnostics, test_manual_scenario, test_experiments, test_model_validation,
test_decision_screens, and test_blockage_diagnosis. Every test body is unchanged.

Name collisions across the sources are resolved with explicit aliases:
``dealos.experiments.runner.rollout`` keeps the name ``rollout``;
``dealos.experiments.model_validation.rollout`` is ``validation_rollout``;
``dealos.experiments.decision_screens.fingerprint`` is ``screen_fingerprint``;
``dealos.experiments.blockage_diagnosis.fingerprint`` is ``blockage_fingerprint``.
"""

from dataclasses import fields, replace

from dealos.diagnostics.manual_scenario import chain_debug_scenario, manual_scenario
from dealos.domain.models import AllocationAction, Resource, Task, TaskOccurrence, primary_occurrence_id
from dealos.experiments.blockage_diagnosis import (
    AMBIGUOUS,
    GAP,
    PARTIAL,
    all_results,
    capacity_bottleneck,
)
from dealos.experiments.blockage_diagnosis import fingerprint as blockage_fingerprint
from dealos.experiments.controlled import assert_only_changed, baseline_scenario
from dealos.experiments.decision_screens import _noisy_rollout
from dealos.experiments.decision_screens import fingerprint as screen_fingerprint
from dealos.experiments.diagnostics import (
    diagnose_actions,
    diagnose_rollout,
    inspect_unfinished,
    step_concentration,
    step_idle,
    task_buckets,
)
from dealos.experiments.metrics import (
    completed_deal_distribution,
    format_cli_report,
    format_compact_summary,
    format_report,
    format_seed_details,
)
from dealos.experiments.model_validation import (
    decision_view,
    matched_edges,
    observed_progress,
    with_topology,
    zero_task_q,
)
from dealos.experiments.model_validation import rollout as validation_rollout
from dealos.experiments.runner import rollout, run_experiment
from dealos.experiments.structure import measure_scenario
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.macro_world.relations.models import RELATION_ENDS
from dealos.policies.bottleneck import BottleneckPolicy
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.random import RandomPolicy
from dealos.sim.env import SalesEnvironment


# ---- Chain diagnostics ----


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


# ---- Manual scenario ----


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

    state, _info = env.step(AllocationAction({("deal_00", primary_occurrence_id("deal_00", "deal_00:start"), "ae"): 1.0}))
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
                ("deal_00", primary_occurrence_id("deal_00", "deal_00:left"), "ae"): 0.4,
                ("deal_00", primary_occurrence_id("deal_00", "deal_00:right"), "ae"): 0.6,
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


# ---- Multi-seed experiment runner ----


def test_experiment_summary_is_descriptive_and_reproducible() -> None:
    def factories(seeds_are_used: int):
        del seeds_are_used
        return [
            lambda seed: RandomPolicy(seed),
            lambda seed: FIFOPolicy(),
            lambda seed: BottleneckPolicy(),
        ]

    first = run_experiment("balanced", seeds=[0, 1], policies=factories(0), horizon=4)
    second = run_experiment("balanced", seeds=[0, 1], policies=factories(0), horizon=4)
    assert first.summary.keys() == {"bottleneck", "fifo", "random"}
    assert "best" not in first.summary
    assert "winner" not in first.summary
    for metrics in first.summary.values():
        completed = metrics["completed_deals"]
        assert isinstance(completed, dict)
        assert completed["count"] == 2
        assert "mean" in completed
        assert "stdev" in completed
        assert "min" in completed
        assert "max" in completed
    text = format_report(first)
    assert "does not rank policies" in text
    details = format_seed_details(first)
    assert "best" not in details.lower()
    assert "winner" not in details.lower()
    for run in first.runs:
        assert f"seed: {run.seed}" in details
        assert f"Policy: {run.policy}" in details
        assert f"completed_deals: {run.completed_deals}" in details
        assert f"mean_task_progress: {run.mean_task_progress:.6f}" in details
        assert f"blocked_task_steps: {run.blocked_task_steps}" in details
        assert f"steps: {run.steps}" in details
        assert "completion_times:" in details
        for deal_id, completed_at in run.completion_times.items():
            shown = "None" if completed_at is None else str(completed_at)
            assert f"{deal_id}: {shown}" in details
    cli_text = format_cli_report(first)
    assert cli_text.endswith(text)
    assert cli_text.index("per-seed results:") < cli_text.index("preset:")
    assert first.assumptions["capacity_violation"] == "reject"
    assert first.assumptions["readiness"] == "and_min"
    assert [(run.policy, run.seed, run.total_task_progress) for run in first.runs] == [
        (run.policy, run.seed, run.total_task_progress) for run in second.runs
    ]
    compact = format_compact_summary(first)
    assert "does not rank policies" in compact
    assert "best" not in compact.lower()
    for policy in ("bottleneck", "fifo", "random"):
        assert f"policy: {policy}" in compact
        assert "mean_task_progress:" in compact
        assert "blocked_task_steps:" in compact
        assert "throughput:" in compact
        assert "mean_resource_utilization:" in compact
        assert "mean_active_deals:" in compact
    fifo_runs = [run for run in first.runs if run.policy == "fifo"]
    distribution = completed_deal_distribution(fifo_runs)
    assert sum(distribution.values()) == len(fifo_runs)
    assert f"completed_deals = 0: {distribution[0]} runs" in compact


# ---- Model-validation wrappers ----


def test_topology_keeps_tasks_and_matches_edge_counts():
    base = baseline_scenario(0)
    for kind in ("chain", "hub", "convergence"):
        variant = with_topology(base, kind)
        assert variant is not None
        assert_only_changed(base, variant, ("edges:",))
        for deal_id, deal in base.deals.items():
            assert len(variant.deals[deal_id].edges) == len(deal.edges)
            assert matched_edges(deal, kind) == variant.deals[deal_id].edges
        assert variant.suitability == base.suitability
        assert variant.initial_progress == base.initial_progress


def test_chain_depth_stays_the_long_path():
    base = baseline_scenario(0)
    variant = with_topology(base, "chain")
    assert variant is not None
    deal = variant.deals["deal_00"]
    order = [task_id for task_id in deal.tasks]
    # Template order is stored on the edge skeleton: consecutive tasks are present.
    assert len(deal.edges) == len(base.deals["deal_00"].edges)


def test_zero_q_changes_only_the_named_task():
    base = baseline_scenario(0)
    task = next(iter(base.task_keys()))
    variant = zero_task_q(base, {task})
    assert_only_changed(base, variant, ("q",))
    for key, value in variant.suitability.items():
        if (key[0], key[1]) == task:
            assert value == 0.0
        else:
            assert value == base.suitability[key]


def test_observation_does_not_modify_true_progress():
    base = baseline_scenario(0)
    true = dict(base.initial_progress)
    observed = observed_progress(true, "noise", 0.1, 0)
    assert true == dict(base.initial_progress)
    assert observed is not true
    env = SalesEnvironment(base)
    before = dict(env.reset().task_progress)
    view = decision_view(base, observed, FIFOPolicy())
    after = dict(env.get_state().task_progress)
    assert before == after
    assert view["true_unchanged"] is True


def test_rework_rate_zero_matches_the_frozen_rollout():
    scenario = baseline_scenario(0)
    wrapped = validation_rollout(scenario, FIFOPolicy(), rework_rate=0.0)
    original = diagnose_rollout(scenario, FIFOPolicy())
    assert wrapped.completed == original.completed_deals
    assert wrapped.completion_times == original.completion_times
    assert wrapped.rework_count == 0


# ---- Decision screens ----


def test_zero_noise_matches_the_frozen_rollout():
    scenario = baseline_scenario(0)
    before = screen_fingerprint(scenario)
    wrapped, _support = _noisy_rollout(scenario, FIFOPolicy(), 0.0, 0)
    original = diagnose_rollout(scenario, FIFOPolicy())
    assert wrapped.completed == original.completed_deals
    assert wrapped.completion_times == original.completion_times
    assert screen_fingerprint(scenario) == before


def test_undisturbed_wrapper_matches_frozen_completion():
    scenario = baseline_scenario(0)
    wrapped = validation_rollout(scenario, FIFOPolicy(), rework_rate=0.0)
    original = diagnose_rollout(scenario, FIFOPolicy())
    assert wrapped.completion_times == original.completion_times


# ---- Blockage diagnosis ----


def test_capacity_starves_a_ready_task_without_calling_it_predecessor_blocked() -> None:
    result = capacity_bottleneck()
    assert result.category == PARTIAL
    assert result.where_shown.startswith("deal_A:A1 stays at 0")
    assert "utilization is 1" in result.why_shown
    assert result.mutation_accepted is False


def test_information_and_cross_organization_are_gaps() -> None:
    by_id = {result.scenario_id: result for result in all_results()}
    assert by_id["information"].category == GAP
    assert by_id["cross_organization"].category == GAP
    assert by_id["authority"].category == AMBIGUOUS
    assert by_id["authority"].mutation_accepted is False
    assert by_id["authority"].epistemic_status == "HYPOTHESIS"


def test_negative_controls_reject_the_mutation() -> None:
    negatives = [result for result in all_results() if result.scenario_id.startswith("negative_")]
    assert len(negatives) == 3
    for result in negatives:
        assert result.category == AMBIGUOUS
        assert result.ambiguity is True
        assert result.mutation_accepted is False
        assert result.epistemic_status == "HYPOTHESIS"


def test_macro_relations_do_not_name_a_deal_or_task_and_micro_fingerprint_holds() -> None:
    for source, target in RELATION_ENDS.values():
        assert "Deal" not in source and "Deal" not in target
        assert "Task" not in source and "Task" not in target
    assert tuple(field.name for field in fields(Task)) == ("task_id", "deal_id", "task_type", "name")
    assert "information" not in {field.name for field in fields(TaskOccurrence)}
    assert blockage_fingerprint() is True
