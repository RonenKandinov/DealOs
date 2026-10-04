"""Identity checks for the model-validation wrappers. They do not change V1."""

from dealos.experiments.controlled import assert_only_changed
from dealos.experiments.diagnostics import diagnose_rollout
from dealos.experiments.model_validation import (
    decision_view,
    matched_edges,
    observed_progress,
    rollout,
    with_topology,
    zero_task_q,
)
from dealos.experiments.controlled import baseline_scenario
from dealos.policies.fifo import FIFOPolicy
from dealos.sim.env import SalesEnvironment


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
    wrapped = rollout(scenario, FIFOPolicy(), rework_rate=0.0)
    original = diagnose_rollout(scenario, FIFOPolicy())
    assert wrapped.completed == original.completed_deals
    assert wrapped.completion_times == original.completion_times
    assert wrapped.rework_count == 0
