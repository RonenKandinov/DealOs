"""Identity checks for the four decision-gate screens."""

from dealos.experiments.decision_screens import fingerprint, _noisy_rollout
from dealos.experiments.diagnostics import diagnose_rollout
from dealos.experiments.model_validation import baseline_scenario, rollout
from dealos.policies.fifo import FIFOPolicy


def test_zero_noise_matches_the_frozen_rollout():
    scenario = baseline_scenario(0)
    before = fingerprint(scenario)
    wrapped, _support = _noisy_rollout(scenario, FIFOPolicy(), 0.0, 0)
    original = diagnose_rollout(scenario, FIFOPolicy())
    assert wrapped.completed == original.completed_deals
    assert wrapped.completion_times == original.completion_times
    assert fingerprint(scenario) == before


def test_undisturbed_wrapper_matches_frozen_completion():
    scenario = baseline_scenario(0)
    wrapped = rollout(scenario, FIFOPolicy(), rework_rate=0.0)
    original = diagnose_rollout(scenario, FIFOPolicy())
    assert wrapped.completion_times == original.completion_times
