"""Factor sweeps on the frozen T=80 balanced scenario.

Each cell is built by ``edit_scenario``. A multiplier of 1 does not touch that
field. Density 1 keeps the original edges. The runners write the records and
do not change the simulator.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from dealos.experiments.controlled import (
    ConditionRun,
    assert_reference_matches_baseline,
    baseline_scenario,
    collect_edited,
    edit_scenario,
    format_factor_report,
    product_match_fraction,
    q_clip_fraction,
    write_report,
)
from dealos.experiments.horizon_sweep import POLICY_ORDER

SEEDS = tuple(range(20))
DENSITY_BAND = (0.25, 0.5, 0.75, 1.0, 1.25)
SCALE_BAND = (0.5, 0.75, 1.0, 1.25, 1.5)
GRID = (0.5, 1.0, 1.5)
NARROW = (0.75, 1.0, 1.25)
RECORDS = Path("records")


def density_cells(levels: tuple[float, ...] = DENSITY_BAND) -> list[tuple[str, float, dict[str, object]]]:
    return [(f"{level:.2f}x", level, {"density": level}) for level in levels]


def scale_cells(field: str, levels: tuple[float, ...] = SCALE_BAND) -> list[tuple[str, float, dict[str, object]]]:
    return [(f"{level:.2f}x", level, {field: level}) for level in levels]


def capacity_density_cells(
    resource_id: str,
    densities: tuple[float, ...] = GRID,
    capacities: tuple[float, ...] = GRID,
) -> list[tuple[str, float, dict[str, object]]]:
    cells = []
    for density in densities:
        for capacity in capacities:
            cells.append(
                (
                    f"d{density:.2f}-{resource_id[:2]}{capacity:.2f}",
                    density + capacity / 100.0,
                    {
                        "density": density,
                        "resource_id": resource_id,
                        "capacity_multiplier": capacity,
                    },
                )
            )
    return cells


def run_density() -> list[ConditionRun]:
    runs, graphs = collect_edited(density_cells(), SEEDS, variable="density")
    assert_reference_matches_baseline(runs, "1.00x")
    text = format_factor_report(
        runs,
        [
            "Experiment 3: dependency density",
            "Independent variable: extra-edge probability, as a multiplier of the balanced value 0.08",
            "Levels: 0.25x, 0.50x, 0.75x, 1.00x, 1.25x",
            "The 1.00x cell is the untouched frozen scenario. Other cells redraw only edges.",
            "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
            "Fixed: capacities, phi, alpha, q, initial progress, task sets, targets, objective",
            "Identity: assert_only_changed allows edges: except at 1.00x, where nothing may change.",
        ],
        graphs=graphs,
        reference_level="1.00x",
    )
    write_report(RECORDS / "exp3_density.txt", text)
    return runs


def run_density_capacity() -> list[ConditionRun]:
    runs, graphs = collect_edited(capacity_density_cells("ae"), SEEDS, variable="density_x_ae")
    reference = "d1.00-ae1.00"
    assert_reference_matches_baseline(runs, reference)
    text = format_factor_report(
        runs,
        [
            "Experiment 4: dependency density by AE capacity",
            "Independent variables: edge probability multiplier and ae capacity multiplier",
            "Density levels: 0.50x, 1.00x, 1.50x of extra-edge probability 0.08",
            "AE levels: 0.50x, 1.00x, 1.50x of baseline AE capacity 2",
            "The cell d1.00-ae1.00 is the untouched frozen scenario.",
            "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
            "Fixed: other capacities, phi, alpha, q, initial progress, task sets, targets, objective",
            "Identity: allowed differences are edges: and capacity:ae, and only when that factor is not 1.",
        ],
        graphs=graphs,
        reference_level=reference,
        extra_lines=_capacity_margins(runs, "ae", GRID, GRID),
    )
    write_report(RECORDS / "exp4_density_capacity_interaction.txt", text)
    return runs


def run_q() -> list[ConditionRun]:
    runs, graphs = collect_edited(scale_cells("q_factor"), SEEDS, variable="q")
    assert_reference_matches_baseline(runs, "1.00x")
    clips = []
    for factor in SCALE_BAND:
        fractions = [q_clip_fraction(baseline_scenario(seed), factor) for seed in SEEDS]
        clips.append(f"q {factor:.2f}x fraction of positive q clipped at 1: {statistics.fmean(fractions):.3f}")
    text = format_factor_report(
        runs,
        [
            "Experiment 5: suitability q",
            "Independent variable: positive q, multiplied and clipped to [0, 1]. Zeros stay zero.",
            "Levels: 0.50x, 0.75x, 1.00x, 1.25x, 1.50x",
            "The 1.00x cell is the untouched frozen scenario.",
            "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
            "Fixed: edges, capacities, phi, alpha, initial progress, task sets, targets, objective",
            "Identity: assert_only_changed allows q, except at 1.00x.",
            "Daily progress uses the product alpha * q. This run changes only q.",
        ],
        graphs=graphs,
        reference_level="1.00x",
        extra_lines=clips,
    )
    write_report(RECORDS / "exp5_q.txt", text)
    return runs


def run_alpha() -> list[ConditionRun]:
    runs, graphs = collect_edited(scale_cells("alpha_factor"), SEEDS, variable="alpha")
    assert_reference_matches_baseline(runs, "1.00x")
    text = format_factor_report(
        runs,
        [
            "Experiment 6: productivity alpha",
            "Independent variable: alpha, multiplied with no clip.",
            "Levels: 0.50x, 0.75x, 1.00x, 1.25x, 1.50x",
            "The 1.00x cell is the untouched frozen scenario.",
            "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
            "Fixed: edges, capacities, phi, q, initial progress, task sets, targets, objective",
            "Identity: assert_only_changed allows alpha, except at 1.00x.",
            "Daily progress uses the product alpha * q. This run changes only alpha.",
        ],
        graphs=graphs,
        reference_level="1.00x",
    )
    write_report(RECORDS / "exp6_alpha.txt", text)
    return runs


def run_q_alpha() -> list[ConditionRun]:
    cells = []
    for q_factor in NARROW:
        for alpha_factor in NARROW:
            cells.append(
                (
                    f"q{q_factor:.2f}-a{alpha_factor:.2f}",
                    q_factor + alpha_factor / 100.0,
                    {"q_factor": q_factor, "alpha_factor": alpha_factor},
                )
            )
    runs, graphs = collect_edited(cells, SEEDS, variable="q_x_alpha")
    assert_reference_matches_baseline(runs, "q1.00-a1.00")
    pairs = (
        ((1.0, 1.25), (1.25, 1.0)),
        ((0.75, 1.25), (1.25, 0.75)),
    )
    notes = ["Pairs with the same nominal alpha*q. Match is the share of suitable pairs with equal products."]
    for (q_left, alpha_left), (q_right, alpha_right) in pairs:
        fractions = []
        for seed in SEEDS:
            base = baseline_scenario(seed)
            left = edit_scenario(base, q_factor=q_left, alpha_factor=alpha_left)
            right = edit_scenario(base, q_factor=q_right, alpha_factor=alpha_right)
            fractions.append(product_match_fraction(left, right))
        notes.append(
            f"q {q_left:.2f} alpha {alpha_left:.2f} vs q {q_right:.2f} alpha {alpha_right:.2f}: "
            f"product match {statistics.fmean(fractions):.3f}"
        )
        notes.extend(_pair_outcomes(runs, q_left, alpha_left, q_right, alpha_right))
    text = format_factor_report(
        runs,
        [
            "Experiment 7: q by alpha",
            "Independent variables: q multiplier and alpha multiplier",
            "Levels: 0.75x, 1.00x, 1.25x on each factor. Nine cells.",
            "The cell q1.00-a1.00 is the untouched frozen scenario.",
            "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
            "Fixed: edges, capacities, phi, initial progress, task sets, targets, objective",
            "Identity: allowed differences are q and alpha, and only when that factor is not 1.",
            "q is clipped to 1. Alpha is not clipped. Equal nominal products need not be equal after clipping.",
        ],
        graphs=graphs,
        reference_level="q1.00-a1.00",
        extra_lines=notes,
    )
    write_report(RECORDS / "exp7_q_alpha_interaction.txt", text)
    return runs


def run_resource_density() -> dict[str, list[ConditionRun]]:
    stored: dict[str, list[ConditionRun]] = {}
    sections = [
        "Experiment 8: resource capacity by dependency density",
        "AE is not rerun. Its 3x3 grid is Experiment 4.",
        "Each block below changes one resource capacity and the edge probability.",
        "Density levels: 0.50x, 1.00x, 1.50x of extra-edge probability 0.08",
        "Capacity levels: 0.50x, 1.00x, 1.50x of that resource's baseline",
        "The d1.00-c1.00 cell in each block is the untouched frozen scenario.",
        "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
        "Identity: allowed differences are edges: and capacity:<resource>, only when that factor is not 1.",
        "",
    ]
    for resource_id in ("legal", "sales_engineer", "security", "solutions_architect"):
        runs, graphs = collect_edited(
            capacity_density_cells(resource_id),
            SEEDS,
            variable=f"density_x_{resource_id}",
        )
        reference = f"d1.00-{resource_id[:2]}1.00"
        assert_reference_matches_baseline(runs, reference)
        sections.append(
            format_factor_report(
                runs,
                [f"Resource: {resource_id}"],
                graphs=graphs,
                reference_level=reference,
                extra_lines=_capacity_margins(runs, resource_id, GRID, GRID),
            )
        )
        stored[resource_id] = runs
        print(f"wrote block {resource_id}", flush=True)
    write_report(RECORDS / "exp8_resource_density_interactions.txt", "\n".join(sections))
    return stored


def run_cross_factor() -> list[ConditionRun]:
    cells = []
    for density in NARROW:
        for capacity in NARROW:
            for q_factor in NARROW:
                for alpha_factor in NARROW:
                    cells.append(
                        (
                            f"d{density:.2f}-ae{capacity:.2f}-q{q_factor:.2f}-a{alpha_factor:.2f}",
                            density,
                            {
                                "density": density,
                                "resource_id": "ae",
                                "capacity_multiplier": capacity,
                                "q_factor": q_factor,
                                "alpha_factor": alpha_factor,
                            },
                        )
                    )
    runs, graphs = collect_edited(cells, SEEDS, variable="cross_factor")
    reference = "d1.00-ae1.00-q1.00-a1.00"
    assert_reference_matches_baseline(runs, reference)
    text = format_factor_report(
        runs,
        [
            "Experiment 9: density by AE capacity by q by alpha",
            "Full factorial. Each factor has levels 0.75x, 1.00x, 1.25x. 81 cells.",
            "81 cells x 20 seeds x 3 policies = 4860 rollouts.",
            "The cell d1.00-ae1.00-q1.00-a1.00 is the untouched frozen scenario.",
            "Seeds: 0-19. Horizon: T=80. Policies: random, fifo, bottleneck",
            "Fixed: other capacities, phi, initial progress, task sets, targets, objective",
            "Identity: edges, capacity:ae, q, and alpha may differ only when that factor is not 1.",
            "This is an exploratory grid. It does not support a significance claim.",
        ],
        graphs=graphs,
        reference_level=reference,
    )
    write_report(RECORDS / "exp9_cross_factor.txt", text)
    return runs


def _capacity_margins(
    runs: list[ConditionRun],
    resource_id: str,
    densities: tuple[float, ...],
    capacities: tuple[float, ...],
) -> list[str]:
    low, high = capacities[0], capacities[-1]
    lines = [
        "",
        f"Change from {resource_id} {low:.2f}x to {high:.2f}x at each density. "
        "Completed is a difference of seed means. Completion day is a difference of finished-deal means.",
    ]
    prefix = resource_id[:2]
    for density in densities:
        for policy in POLICY_ORDER:
            low_runs = _cell(runs, f"d{density:.2f}-{prefix}{low:.2f}", policy)
            high_runs = _cell(runs, f"d{density:.2f}-{prefix}{high:.2f}", policy)
            if not low_runs or not high_runs:
                continue
            completed = _completed_mean(high_runs) - _completed_mean(low_runs)
            low_days = _days(low_runs)
            high_days = _days(high_runs)
            day_text = f"{statistics.fmean(high_days) - statistics.fmean(low_days):+.2f}" if low_days and high_days else "na"
            lines.append(
                f"  density {density:.2f}x {policy}: completed {completed:+.3f} completion_day {day_text}"
            )
    return lines


def _pair_outcomes(
    runs: list[ConditionRun],
    q_left: float,
    alpha_left: float,
    q_right: float,
    alpha_right: float,
) -> list[str]:
    left_level = f"q{q_left:.2f}-a{alpha_left:.2f}"
    right_level = f"q{q_right:.2f}-a{alpha_right:.2f}"
    lines = []
    for policy in POLICY_ORDER:
        left = _cell(runs, left_level, policy)
        right = _cell(runs, right_level, policy)
        if not left or not right:
            continue
        lines.append(
            f"  {policy}: {left_level} completed {_completed_mean(left):.3f} "
            f"vs {right_level} completed {_completed_mean(right):.3f}"
        )
    return lines


def _cell(runs: list[ConditionRun], level: str, policy: str) -> list[ConditionRun]:
    return [run for run in runs if run.level == level and run.diagnosis.policy == policy]


def _completed_mean(runs: list[ConditionRun]) -> float:
    return statistics.fmean(run.diagnosis.completed_deals for run in runs)


def _days(runs: list[ConditionRun]) -> list[float]:
    return [
        float(day)
        for run in runs
        for day in run.diagnosis.completion_times.values()
        if day is not None
    ]


def main() -> None:
    print("experiment 3", flush=True)
    run_density()
    print("experiment 4", flush=True)
    run_density_capacity()
    print("experiment 5", flush=True)
    run_q()
    print("experiment 6", flush=True)
    run_alpha()
    print("experiment 7", flush=True)
    run_q_alpha()
    print("experiment 8", flush=True)
    run_resource_density()
    print("experiment 9", flush=True)
    run_cross_factor()
    print("done", flush=True)


if __name__ == "__main__":
    main()
