"""Balanced horizon sweep. One generated scenario per seed; only T changes.

Graphs, capacities, alpha, suitability, phi, and initial progress are copied
from that scenario. A fresh policy instance is built for every horizon so a
RandomPolicy seed is not continued from a shorter run.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import replace

from dealos.domain.models import Scenario
from dealos.experiments.diagnostics import RunDiagnosis, diagnose_rollout
from dealos.experiments.runner import default_policy_factories
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset

HORIZONS: tuple[int, ...] = (20, 40, 60, 80, 120)
POLICY_ORDER = ("random", "fifo", "bottleneck")


def with_horizon(scenario: Scenario, horizon: int) -> Scenario:
    """Same deals and parameters, with the episode length set to ``horizon``."""

    if horizon < 0:
        raise ValueError("horizon must be non-negative")
    return replace(
        scenario,
        horizon=horizon,
        generator=replace(scenario.generator, horizon=horizon),
    )


def same_scenario_body(left: Scenario, right: Scenario) -> bool:
    """True when two scenarios differ at most in the horizon field."""

    left_caps = {key: resource.capacity for key, resource in left.resources.items()}
    right_caps = {key: resource.capacity for key, resource in right.resources.items()}
    left_gen = replace(left.generator, horizon=0)
    right_gen = replace(right.generator, horizon=0)
    return (
        left.seed == right.seed
        and left.deals == right.deals
        and left.phi == right.phi
        and left.alpha == right.alpha
        and left.suitability == right.suitability
        and left.initial_progress == right.initial_progress
        and left_caps == right_caps
        and left_gen == right_gen
    )


def collect_balanced_horizon_sweep(
    seeds: tuple[int, ...] = tuple(range(20)),
    horizons: tuple[int, ...] = HORIZONS,
) -> list[RunDiagnosis]:
    """300 runs when called with the default seeds and horizons."""

    config = get_preset("balanced")
    factories = default_policy_factories()
    runs: list[RunDiagnosis] = []
    for seed in seeds:
        base = generate_scenario(config, seed)
        for horizon in horizons:
            scenario = with_horizon(base, horizon)
            if not same_scenario_body(base, scenario) or scenario.horizon != horizon:
                raise RuntimeError(f"horizon {horizon} changed seed {seed} beyond T")
            for factory in factories:
                runs.append(diagnose_rollout(scenario, factory(seed)))
    return runs


def format_horizon_report(runs: list[RunDiagnosis]) -> str:
    lines = [
        "Balanced horizon sweep. One generated scenario per seed; only T changes.",
        "Seeds 0-19. Policies are listed in runner order. This summary does not rank policies.",
        "Completed is the mean of sum y_i over 20 seeds (4 deals each, 80 deals in the pool).",
        "Target and non-target progress are unweighted means of task progress.",
        "Buckets are shares of tasks at x<=0, 0<x<1, and x complete.",
        "Residual unfinished is the mean critical-path gap over deals still open.",
        "Residual all deals counts a finished deal as gap 0, so finished deals pull that mean down.",
        "A/B/C counts are unfinished deals only. A: every target >= 0.8.",
        "B: otherwise a depth-0 or depth-1 non-target on a longest path has progress < 0.5.",
        "C: otherwise mixed.",
        "Idle is allocated / no compatible eligible work / eligible work left unused.",
        "Herfindahl is the mean concentration of each step's allocation across tasks.",
        "Completion days are the simulator's deal_completed_at values. on T counts deals",
        "whose completion day equals that run's horizon.",
        "runs hitting T counts seeds whose rollout took exactly T steps.",
        "",
        _markdown_table(runs),
        "",
        "Same-seed completed-deal difference, FIFO minus Bottleneck:",
    ]
    lines.extend(_paired_gaps(runs))
    lines.append("")
    lines.append("Per seed, completed deals:")
    lines.extend(_per_seed(runs))
    return "\n".join(lines).rstrip() + "\n"


def _markdown_table(runs: list[RunDiagnosis]) -> str:
    header = (
        "| T | Policy | Completed | Target | Non-target | x=0 | partial | x=1 | "
        "Residual unfinished | Residual all deals | A | B | C | "
        "Idle alloc | Idle none | Idle despite | Herfindahl | "
        "Finished deals | Mean completion day | Completions on T | Runs hitting T |"
    )
    separator = "|" + "---|" * 21
    lines = [header, separator]
    for horizon in HORIZONS:
        for policy in POLICY_ORDER:
            group = [run for run in runs if run.horizon == horizon and run.policy == policy]
            if not group:
                continue
            lines.append(_row(horizon, policy, group))
    return "\n".join(lines)


def _row(horizon: int, policy: str, group: list[RunDiagnosis]) -> str:
    deals = [deal for run in group for deal in run.unfinished]
    counts = {"A": 0, "B": 0, "C": 0}
    for deal in deals:
        counts[deal.label] += 1
    n_deals = sum(len(run.completion_times) for run in group)
    unfinished_residual = _mean(deal.critical_residual for deal in deals)
    all_residual = (
        sum(deal.critical_residual for deal in deals) / n_deals if n_deals else float("nan")
    )
    finished_days = [
        day
        for run in group
        for day in run.completion_times.values()
        if day is not None
    ]
    on_horizon = sum(
        1
        for run in group
        for day in run.completion_times.values()
        if day == run.horizon
    )
    hitting = sum(1 for run in group if run.steps == run.horizon)
    return (
        f"| {horizon} | {policy} | {_mean(run.completed_deals for run in group):.2f} | "
        f"{_mean_optional(run.mean_target_progress for run in group):.3f} | "
        f"{_mean_optional(run.mean_nontarget_progress for run in group):.3f} | "
        f"{_mean(run.fraction_zero for run in group):.3f} | "
        f"{_mean(run.fraction_partial for run in group):.3f} | "
        f"{_mean(run.fraction_one for run in group):.3f} | "
        f"{unfinished_residual:.3f} | {all_residual:.3f} | "
        f"{counts['A']} | {counts['B']} | {counts['C']} | "
        f"{_mean(run.mean_allocated_fraction for run in group):.3f} | "
        f"{_mean(run.mean_unused_no_eligible_fraction for run in group):.3f} | "
        f"{_mean(run.mean_unused_despite_eligible_fraction for run in group):.3f} | "
        f"{_mean_optional(run.mean_herfindahl for run in group):.3f} | "
        f"{len(finished_days)} | {_mean(finished_days):.2f} | {on_horizon} | {hitting} |"
    )


def _paired_gaps(runs: list[RunDiagnosis]) -> list[str]:
    lines: list[str] = []
    by_key: dict[tuple[int, int, str], int] = {
        (run.horizon, run.seed, run.policy): run.completed_deals for run in runs
    }
    for horizon in HORIZONS:
        gaps = [
            by_key[(horizon, seed, "fifo")] - by_key[(horizon, seed, "bottleneck")]
            for seed in sorted({run.seed for run in runs if run.horizon == horizon})
            if (horizon, seed, "fifo") in by_key and (horizon, seed, "bottleneck") in by_key
        ]
        if not gaps:
            continue
        lines.append(
            f"  T={horizon}: n={len(gaps)} mean={statistics.fmean(gaps):.2f} "
            f"min={min(gaps)} max={max(gaps)}"
        )
    return lines


def _per_seed(runs: list[RunDiagnosis]) -> list[str]:
    by_seed: dict[int, list[RunDiagnosis]] = defaultdict(list)
    for run in runs:
        by_seed[run.seed].append(run)
    header = "seed"
    for horizon in HORIZONS:
        for policy in POLICY_ORDER:
            header += f" {horizon}/{policy[0]}"
    lines = [header]
    for seed in sorted(by_seed):
        cells = [f"{seed:4d}"]
        indexed = {(run.horizon, run.policy): run.completed_deals for run in by_seed[seed]}
        for horizon in HORIZONS:
            for policy in POLICY_ORDER:
                cells.append(f"{indexed[(horizon, policy)]:2d}")
        lines.append(" ".join(cells))
    return lines


def _mean(values) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return float("nan")
    return statistics.fmean(numbers)


def _mean_optional(values) -> float:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return float("nan")
    return statistics.fmean(numbers)


def main() -> None:
    print(format_horizon_report(collect_balanced_horizon_sweep()), end="")


if __name__ == "__main__":
    main()
