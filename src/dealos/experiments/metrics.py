"""Per-run records and cross-seed summaries. No policy ranking."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class RunResult:
    preset: str
    seed: int
    policy: str
    completed_deals: int
    completion_times: dict[str, int | None]
    total_task_progress: float
    blocked_task_steps: int
    mean_utilization: dict[str, float]
    mean_utilization_overall: float
    mean_active_deals: float
    throughput: float
    steps: int
    done_reason: str | None
    unfinished_deals: int


@dataclass
class ExperimentReport:
    preset: str
    seeds: tuple[int, ...]
    assumptions: dict[str, object]
    runs: list[RunResult] = field(default_factory=list)
    summary: dict[str, dict[str, object]] = field(default_factory=dict)


def summarize_metric(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty metric")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def summarize(runs: list[RunResult]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[RunResult]] = {}
    for run in runs:
        grouped.setdefault(run.policy, []).append(run)
    summary: dict[str, dict[str, object]] = {}
    scalar_fields = (
        "completed_deals",
        "total_task_progress",
        "blocked_task_steps",
        "mean_active_deals",
        "mean_utilization_overall",
        "throughput",
        "steps",
        "unfinished_deals",
    )
    for policy in sorted(grouped):
        group = grouped[policy]
        metrics: dict[str, object] = {}
        for name in scalar_fields:
            metrics[name] = summarize_metric([float(getattr(run, name)) for run in group])
        resource_ids = sorted(group[0].mean_utilization)
        metrics["mean_utilization"] = {
            resource_id: summarize_metric([run.mean_utilization[resource_id] for run in group])
            for resource_id in resource_ids
        }
        completion_means: list[float] = []
        for run in group:
            finished = [time for time in run.completion_times.values() if time is not None]
            if finished:
                completion_means.append(statistics.fmean(finished))
        metrics["mean_completion_time"] = (
            summarize_metric(completion_means) if completion_means else None
        )
        summary[policy] = metrics
    return summary


def format_report(report: ExperimentReport) -> str:
    lines = [
        f"preset: {report.preset}",
        f"seeds: {', '.join(str(seed) for seed in report.seeds)}",
        "assumptions:",
    ]
    for key, value in report.assumptions.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    header = (
        f"{'policy':<16} {'completed':>12} {'progress':>12} {'blocked':>12} "
        f"{'active':>12} {'util':>12} {'throughput':>12} {'steps':>8}"
    )
    lines.append(header)
    for policy, metrics in report.summary.items():
        def cell(name: str) -> str:
            stats = metrics[name]
            assert isinstance(stats, dict)
            return f"{float(stats['mean']):.3f}"

        lines.append(
            f"{policy:<16} {cell('completed_deals'):>12} {cell('total_task_progress'):>12} "
            f"{cell('blocked_task_steps'):>12} {cell('mean_active_deals'):>12} "
            f"{cell('mean_utilization_overall'):>12} {cell('throughput'):>12} {cell('steps'):>8}"
        )
    lines.append("")
    lines.append("Cells are means across seeds. count, sample stdev, min, and max are on the summary object.")
    lines.append("Throughput is deals newly completed during the run, divided by steps taken.")
    lines.append("These figures are descriptive. This report does not rank policies.")
    return "\n".join(lines)
