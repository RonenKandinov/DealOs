from dealos.experiments.metrics import format_report
from dealos.experiments.runner import run_experiment
from dealos.policies.bottleneck import BottleneckPolicy
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.random import RandomPolicy


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
    assert first.assumptions["capacity_violation"] == "reject"
    assert first.assumptions["readiness"] == "and_min"
    assert [(run.policy, run.seed, run.total_task_progress) for run in first.runs] == [
        (run.policy, run.seed, run.total_task_progress) for run in second.runs
    ]
