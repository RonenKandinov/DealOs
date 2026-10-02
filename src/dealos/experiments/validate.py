"""Run every preset on seeds 0..19 and print descriptive validation output.

Usage: python -m dealos.experiments.validate
"""

from __future__ import annotations

import argparse
from dataclasses import replace

from dealos.experiments.metrics import format_compact_summary
from dealos.experiments.runner import run_experiment
from dealos.experiments.structure import (
    StructureSummary,
    format_structure_summary,
    measure_scenario,
    summarize_structures,
)
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import PRESETS, get_preset

PRESET_ORDER: tuple[str, ...] = (
    "balanced",
    "legal_bottleneck",
    "technical_bottleneck",
    "resource_constrained",
    "dependency_heavy",
)


def default_validation_seeds() -> tuple[int, ...]:
    return tuple(range(20))


def structure_for_preset(preset: str, seeds: tuple[int, ...]) -> StructureSummary:
    config = get_preset(preset)
    samples = [measure_scenario(generate_scenario(config, seed)) for seed in seeds]
    summary = summarize_structures(samples)
    return replace(
        summary,
        extra_edge_probability=config.extra_edge_probability,
        optional_drop_probability=config.optional_drop_probability,
        protected_task_types=tuple(sorted(config.protected_task_types)),
        horizon=config.horizon,
    )


def format_capacity_comparison(structures: dict[str, StructureSummary]) -> str:
    """Place measured capacities and graph density next to each other."""

    lines = [
        "measured preset differences:",
        "These lines compare configuration and measured structure.",
        "They are not policy results.",
    ]
    balanced = structures["balanced"]
    for name in PRESET_ORDER:
        summary = structures[name]
        capacity_bits = ", ".join(
            f"{key}={summary.capacities[key]}" for key in sorted(summary.capacities)
        )
        lines.append(
            f"{name}: capacities({capacity_bits}) "
            f"extra_edge_p={summary.extra_edge_probability} "
            f"mean_edges={float(summary.n_edges['mean']):.2f} "
            f"mean_edges_per_task={float(summary.edges_per_task['mean']):.3f} "
            f"mean_depth={float(summary.mean_dependency_depth['mean']):.3f} "
            f"mean_max_depth={float(summary.max_dependency_depth['mean']):.3f}"
        )
    lines.append(
        "legal capacity: "
        f"balanced={balanced.capacities['legal']} "
        f"legal_bottleneck={structures['legal_bottleneck'].capacities['legal']}"
    )
    lines.append(
        "technical capacity: "
        f"balanced sales_engineer={balanced.capacities['sales_engineer']} "
        f"solutions_architect={balanced.capacities['solutions_architect']}; "
        f"technical_bottleneck sales_engineer={structures['technical_bottleneck'].capacities['sales_engineer']} "
        f"solutions_architect={structures['technical_bottleneck'].capacities['solutions_architect']}"
    )
    balanced_total = sum(balanced.capacities.values())
    constrained_total = sum(structures["resource_constrained"].capacities.values())
    lines.append(
        f"total capacity: balanced={balanced_total} resource_constrained={constrained_total}"
    )
    lines.append(
        "configured extra-edge probability: "
        f"balanced={balanced.extra_edge_probability} "
        f"dependency_heavy={structures['dependency_heavy'].extra_edge_probability}"
    )
    return "\n".join(lines)


def format_validation(seeds: tuple[int, ...] | None = None) -> str:
    chosen = default_validation_seeds() if seeds is None else seeds
    if any(name not in PRESETS for name in PRESET_ORDER):
        missing = [name for name in PRESET_ORDER if name not in PRESETS]
        raise KeyError(f"missing presets: {missing}")
    blocks = [
        "V1 validation",
        f"seeds: {', '.join(str(seed) for seed in chosen)}",
        "policies: bottleneck, fifo, random",
        "OptimizationPolicy is not run.",
        "Figures below are descriptive. This report does not rank policies.",
        "",
        "structure",
    ]
    structures: dict[str, StructureSummary] = {}
    for preset in PRESET_ORDER:
        structures[preset] = structure_for_preset(preset, chosen)
        blocks.append(format_structure_summary(structures[preset]))
        blocks.append("")
    blocks.append(format_capacity_comparison(structures))
    blocks.append("")
    blocks.append("policy rollouts")
    for preset in PRESET_ORDER:
        report = run_experiment(preset, chosen)
        blocks.append(format_compact_summary(report))
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate presets and baseline policies. Does not rank policies."
    )
    parser.add_argument("--seeds", type=int, nargs="*", default=None)
    args = parser.parse_args(argv)
    seeds = None if args.seeds is None else tuple(args.seeds)
    print(format_validation(seeds), end="")


if __name__ == "__main__":
    main()
