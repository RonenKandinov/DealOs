"""The balanced horizon sweep changes T and leaves the generated scenario alone."""

from dealos.experiments.diagnostics import diagnose_rollout
from dealos.experiments.horizon_sweep import same_scenario_body, with_horizon
from dealos.experiments.runner import rollout
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.fifo import FIFOPolicy


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
