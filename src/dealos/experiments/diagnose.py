"""Diagnostic summaries for the existing preset × seed × policy runs.

The scenarios, horizons, capacities, and policies are the ones ``run_experiment``
already uses. Nothing here chooses an allocation.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from dealos.experiments.diagnostics import RunDiagnosis, diagnose_rollout
from dealos.experiments.metrics import format_metric, summarize_metric
from dealos.experiments.runner import default_policy_factories
from dealos.experiments.validate import PRESET_ORDER, default_validation_seeds
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset

POLICY_ORDER = ("random", "fifo", "bottleneck")


def collect_diagnostic_runs(
    presets: tuple[str, ...] = PRESET_ORDER,
    seeds: tuple[int, ...] = (),
) -> list[RunDiagnosis]:
    """One generated scenario per seed, then each runnable policy, matching the validation runs."""

    chosen_seeds = seeds or default_validation_seeds()
    factories = default_policy_factories()
    runs: list[RunDiagnosis] = []
    for preset in presets:
        config = get_preset(preset)
        for seed in chosen_seeds:
            scenario = generate_scenario(config, seed)
            for factory in factories:
                runs.append(diagnose_rollout(scenario, factory(seed)))
    return runs


def format_diagnostic_report(runs: list[RunDiagnosis]) -> str:
    """Aggregate diagnostics by preset and policy, plus per-seed rows."""

    lines = [
        "Diagnostic summary of the existing runs.",
        "Objective remains the number of completed deals. These figures describe trajectories.",
        "This summary does not rank policies.",
        "",
        "Idle fractions are allocated / unused because no compatible eligible task existed /",
        "unused while at least one compatible eligible task existed.",
        "Herfindahl is the mean, over steps that allocated something, of the sum of squared",
        "task shares of that step's allocation. 1 means the whole step went to one task.",
        "Unfinished deals: A = every target task has progress >= 0.8;",
        "B = otherwise a depth-0 or depth-1 non-target on a longest path has progress < 0.5;",
        "C = otherwise mixed.",
        "",
    ]
    by_preset: dict[str, list[RunDiagnosis]] = defaultdict(list)
    for run in runs:
        by_preset[run.preset].append(run)
    for preset in PRESET_ORDER:
        preset_runs = by_preset.get(preset, [])
        if not preset_runs:
            continue
        lines.append(f"=== {preset} ===")
        for policy in POLICY_ORDER:
            group = [run for run in preset_runs if run.policy == policy]
            if not group:
                continue
            lines.extend(_policy_block(group))
        lines.append("per seed:")
        lines.extend(_seed_table(preset_runs))
        lines.append("")
    lines.extend(_notable_unfinished(runs))
    return "\n".join(lines).rstrip() + "\n"


def _policy_block(group: list[RunDiagnosis]) -> list[str]:
    policy = group[0].policy
    deals = [deal for run in group for deal in run.unfinished]
    lines = [f"policy={policy} runs={len(group)}"]
    lines.append(f"  completed_deals: {format_metric(summarize_metric(_numbers(run.completed_deals for run in group)))}")
    lines.append(f"  mean_target_progress: {_optional_metric(run.mean_target_progress for run in group)}")
    lines.append(f"  mean_nontarget_progress: {_optional_metric(run.mean_nontarget_progress for run in group)}")
    lines.append(f"  fraction_x_eq_0: {format_metric(summarize_metric(_numbers(run.fraction_zero for run in group)))}")
    lines.append(f"  fraction_0_lt_x_lt_1: {format_metric(summarize_metric(_numbers(run.fraction_partial for run in group)))}")
    lines.append(f"  fraction_x_eq_1: {format_metric(summarize_metric(_numbers(run.fraction_one for run in group)))}")
    counts = _class_counts(deals)
    total = sum(counts.values())
    lines.append(
        "  unfinished_deals: "
        f"n={total} A={counts['A']} B={counts['B']} C={counts['C']} "
        f"({_share(counts['A'], total)} / {_share(counts['B'], total)} / {_share(counts['C'], total)})"
    )
    lines.append(f"  critical_residual: {_class_residual(deals)}")
    lines.append(f"  min_target_progress bins: {_target_bins(deals)}")
    lines.append(
        "  idle_overall: "
        f"{_mean(run.mean_allocated_fraction for run in group):.4f} / "
        f"{_mean(run.mean_unused_no_eligible_fraction for run in group):.4f} / "
        f"{_mean(run.mean_unused_despite_eligible_fraction for run in group):.4f}"
    )
    resource_ids = sorted({resource_id for run in group for resource_id in run.idle_fractions_by_resource})
    for resource_id in resource_ids:
        triples = [run.idle_fractions_by_resource[resource_id] for run in group if resource_id in run.idle_fractions_by_resource]
        lines.append(
            f"  idle_{resource_id}: "
            f"{_mean(item[0] for item in triples):.4f} / "
            f"{_mean(item[1] for item in triples):.4f} / "
            f"{_mean(item[2] for item in triples):.4f}"
        )
    lines.append(f"  herfindahl: {_optional_metric(run.mean_herfindahl for run in group)}")
    lines.append(
        f"  tasks_with_allocation: {format_metric(summarize_metric(_numbers(run.mean_tasks_with_allocation for run in group)))}"
    )
    return lines


def _seed_table(runs: list[RunDiagnosis]) -> list[str]:
    lines = [
        "seed policy completed target nontarget zero partial one A B C "
        "residual front idle_alloc idle_none idle_despite hhi tasks"
    ]
    ordered = sorted(runs, key=lambda run: (POLICY_ORDER.index(run.policy) if run.policy in POLICY_ORDER else 99, run.seed))
    for run in ordered:
        counts = _class_counts(run.unfinished)
        residual = _mean(deal.critical_residual for deal in run.unfinished)
        front_values = [deal.front_progress for deal in run.unfinished if deal.front_progress is not None]
        front = _mean(front_values) if front_values else float("nan")
        lines.append(
            f"{run.seed:2d} {run.policy:11s} {run.completed_deals:9d} "
            f"{_num(run.mean_target_progress)} {_num(run.mean_nontarget_progress)} "
            f"{run.fraction_zero:8.4f} {run.fraction_partial:8.4f} {run.fraction_one:8.4f} "
            f"{counts['A']:3d} {counts['B']:3d} {counts['C']:3d} "
            f"{residual:8.4f} {front:8.4f} "
            f"{run.mean_allocated_fraction:10.4f} {run.mean_unused_no_eligible_fraction:10.4f} "
            f"{run.mean_unused_despite_eligible_fraction:12.4f} "
            f"{_num(run.mean_herfindahl)} {run.mean_tasks_with_allocation:7.2f}"
        )
    return lines


def _notable_unfinished(runs: list[RunDiagnosis]) -> list[str]:
    deals = [
        (run, deal)
        for run in runs
        if run.policy in {"fifo", "bottleneck"}
        for deal in run.unfinished
    ]
    lines = ["=== unfinished deals, fifo and bottleneck ==="]
    if not deals:
        lines.append("No unfinished deals.")
        return lines
    by_label: dict[str, list[tuple[RunDiagnosis, object]]] = defaultdict(list)
    for run, deal in deals:
        by_label[deal.label].append((run, deal))
    lines.append(
        "Counts pool every unfinished deal. "
        f"A={len(by_label['A'])} B={len(by_label['B'])} C={len(by_label['C'])}."
    )
    lines.append("Highest target progress still unfinished (label, preset, seed, policy, deal, min target, residual, front, path):")
    closest = sorted(deals, key=lambda item: (-item[1].min_target_progress, item[0].preset, item[0].seed, item[1].deal_id))
    for run, deal in closest[:12]:
        lines.append(_deal_line(run, deal))
    lines.append("Class B deals with the least progress on a depth-0 or depth-1 non-target:")
    early = sorted(
        by_label["B"],
        key=lambda item: (
            item[1].front_progress if item[1].front_progress is not None else 1.0,
            -item[1].critical_residual,
        ),
    )
    if not early:
        lines.append("  none")
    for run, deal in early[:8]:
        lines.append(_deal_line(run, deal))
    return lines


def _deal_line(run: RunDiagnosis, deal: object) -> str:
    front = "na" if deal.front_progress is None else f"{deal.front_progress:.4f}"
    path = " -> ".join(deal.critical_path)
    return (
        f"  {deal.label} {run.preset} seed={run.seed} {run.policy} {deal.deal_id} "
        f"min_target={deal.min_target_progress:.4f} residual={deal.critical_residual:.4f} "
        f"front={front} path={path}"
    )


def _class_counts(deals: list) -> dict[str, int]:
    counts = {"A": 0, "B": 0, "C": 0}
    for deal in deals:
        counts[deal.label] += 1
    return counts


def _class_residual(deals: list) -> str:
    parts: list[str] = []
    for label in ("A", "B", "C"):
        values = [deal.critical_residual for deal in deals if deal.label == label]
        if not values:
            parts.append(f"{label}=n=0")
        else:
            parts.append(f"{label} n={len(values)} mean={_mean(values):.4f}")
    return " ".join(parts)


def _target_bins(deals: list) -> str:
    edges = (0.0, 0.2, 0.5, 0.8, 1.01)
    labels = ("[0,0.2)", "[0.2,0.5)", "[0.5,0.8)", "[0.8,1]")
    counts = [0, 0, 0, 0]
    for deal in deals:
        value = deal.min_target_progress
        for index in range(4):
            if edges[index] <= value < edges[index + 1]:
                counts[index] += 1
                break
    return " ".join(f"{label}={count}" for label, count in zip(labels, counts, strict=True))


def _numbers(values) -> list[float]:
    return [float(value) for value in values]


def _optional_metric(values) -> str:
    present = [float(value) for value in values if value is not None]
    if not present:
        return "n=0"
    return format_metric(summarize_metric(present))


def _mean(values) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return float("nan")
    return statistics.fmean(numbers)


def _share(count: int, total: int) -> str:
    if total == 0:
        return "0"
    return f"{count / total:.3f}"


def _num(value: float | None) -> str:
    if value is None:
        return "    na"
    return f"{value:8.4f}"


def main() -> None:
    print(format_diagnostic_report(collect_diagnostic_runs()), end="")


if __name__ == "__main__":
    main()
