from dealos.experiments.metrics import (
    completed_deal_distribution,
    format_cli_report,
    format_compact_summary,
    format_report,
    format_seed_details,
)
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
