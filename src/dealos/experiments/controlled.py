"""Controlled experiments on one frozen balanced scenario per seed.

Each condition copies ``baseline_scenario(seed)`` and may change only the
named field. ``assert_only_changed`` runs before any policy. Regenerating
with a different generator config is not used, because one random stream
draws edges, initial progress, phi, alpha, and q together.

``with_edges``, ``with_scaled_q``, ``with_scaled_alpha``, and
``with_initial_progress`` edit one field of a frozen scenario. ``edit_scenario``
stacks those edits and refuses any field that was not requested. A density
multiplier of 1 leaves the original edges in place. Other multipliers set the
extra-edge probability to ``multiplier * baseline extra_edge_probability`` and
redraw only those edges.
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from dealos.domain.graph import predecessors, topological_order
from dealos.domain.models import DealGraph, Scenario
from dealos.experiments.diagnostics import RunDiagnosis, diagnose_rollout
from dealos.experiments.structure import task_depth
from dealos.experiments.horizon_sweep import POLICY_ORDER, with_horizon
from dealos.experiments.metrics import format_metric, summarize_metric
from dealos.experiments.runner import default_policy_factories
from dealos.generator.generate import _expand_predecessors, _specs, generate_scenario
from dealos.generator.presets import RESOURCE_IDS, get_preset

BASELINE_HORIZON = 80
CAPACITY_MULTIPLIERS: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0, 1.25)
RESOURCE_SWEEP_ORDER: tuple[str, ...] = (
    "ae",
    "legal",
    "sales_engineer",
    "security",
    "solutions_architect",
)
GATED_EXPERIMENTS: tuple[str, ...] = (
    "dependency_density",
    "dependency_depth",
    "suitability_q",
    "productivity_alpha",
    "initial_progress",
    "policy_comparison",
    "interactions",
)


@dataclass(frozen=True)
class ConditionRun:
    variable: str
    level: str
    level_value: float
    diagnosis: RunDiagnosis


def baseline_scenario(seed: int) -> Scenario:
    """Balanced graphs and parameters for ``seed``, with the horizon set to 80."""

    return with_horizon(generate_scenario(get_preset("balanced"), seed), BASELINE_HORIZON)


def with_capacity(scenario: Scenario, resource_id: str, capacity: float) -> Scenario:
    """Copy ``scenario`` and change one resource capacity."""

    if resource_id not in scenario.resources:
        raise KeyError(resource_id)
    if capacity < 0:
        raise ValueError("capacity must be non-negative")
    resources = dict(scenario.resources)
    resources[resource_id] = replace(resources[resource_id], capacity=float(capacity))
    capacities = dict(scenario.generator.capacities)
    capacities[resource_id] = float(capacity)
    return replace(
        scenario,
        resources=resources,
        generator=replace(scenario.generator, capacities=capacities),
    )


def with_scaled_q(scenario: Scenario, factor: float) -> Scenario:
    """Scale positive suitability values. Zeros stay zero, so the resource map is unchanged."""

    if factor < 0:
        raise ValueError("q factor must be non-negative")
    suitability = {
        key: (0.0 if value <= 0.0 else min(1.0, value * factor))
        for key, value in scenario.suitability.items()
    }
    return replace(scenario, suitability=suitability)


def with_scaled_alpha(scenario: Scenario, factor: float) -> Scenario:
    """Scale every alpha entry. Suitability is not changed."""

    if factor < 0:
        raise ValueError("alpha factor must be non-negative")
    alpha = {key: value * factor for key, value in scenario.alpha.items()}
    return replace(scenario, alpha=alpha)


def with_initial_progress(scenario: Scenario, level: str) -> Scenario:
    """Replace initial progress only.

    ``baseline`` keeps the stored vector. ``zero`` sets every task to 0.
    ``prefix:k`` completes k dependency-feasible tasks per deal, in topological
    order, and only when every predecessor is already complete.
    """

    if level == "baseline":
        return scenario
    if level == "zero":
        progress = {key: 0.0 for key in scenario.task_keys()}
        return replace(scenario, initial_progress=progress)
    if level.startswith("prefix:"):
        count = int(level.split(":", 1)[1])
        if count < 0:
            raise ValueError("prefix length must be non-negative")
        return replace(scenario, initial_progress=_prefix_progress(scenario, count))
    raise ValueError(f"unknown initial-progress level {level!r}")


def with_edges(scenario: Scenario, probability: float) -> Scenario:
    """Replace edges only. Tasks, targets, and parameters stay on the frozen scenario.

    Template edges are rebuilt for the tasks the baseline kept. Extra forward
    edges are drawn from a stream that is not the scenario generator's stream.
    This function is available for a later density experiment and is not called
    by the baseline or capacity runners.
    """

    if not 0.0 <= probability <= 1.0:
        raise ValueError("edge probability must lie in [0, 1]")
    deals = {
        deal_id: DealGraph(
            deal_id=deal.deal_id,
            tasks=dict(deal.tasks),
            edges=frozenset(_controlled_edges(scenario.seed, deal, probability)),
            targets=frozenset(deal.targets),
        )
        for deal_id, deal in scenario.deals.items()
    }
    return replace(scenario, deals=deals)


def assert_only_changed(base: Scenario, variant: Scenario, allowed: Sequence[str]) -> None:
    """Raise if ``variant`` differs from ``base`` outside ``allowed`` difference names.

    A difference name is ``capacity:ae``, ``edges:deal_00``, ``q``, ``alpha``,
    ``initial_progress``, ``horizon``, or ``phi``. ``allowed`` entries match
    the full name or a prefix, so ``"edges:"`` allows every deal's edges.
    """

    unexpected = [
        name
        for name in field_differences(base, variant)
        if not any(name == item or name.startswith(item) for item in allowed)
    ]
    if unexpected:
        raise RuntimeError(
            "controlled scenario changed fixed fields: " + ", ".join(unexpected)
        )


def field_differences(base: Scenario, variant: Scenario) -> list[str]:
    """Names of fields that differ. Capacity names follow the live resource capacity."""

    diffs: list[str] = []
    if base.seed != variant.seed:
        diffs.append("seed")
    if base.horizon != variant.horizon:
        diffs.append("horizon")
    if base.phi != variant.phi:
        diffs.append("phi")
    if base.alpha != variant.alpha:
        diffs.append("alpha")
    if base.suitability != variant.suitability:
        diffs.append("q")
    if base.initial_progress != variant.initial_progress:
        diffs.append("initial_progress")
    if set(base.deals) != set(variant.deals):
        diffs.append("deal_ids")
    else:
        for deal_id in sorted(base.deals):
            left = base.deals[deal_id]
            right = variant.deals[deal_id]
            if dict(left.tasks) != dict(right.tasks):
                diffs.append(f"tasks:{deal_id}")
            if left.edges != right.edges:
                diffs.append(f"edges:{deal_id}")
            if left.targets != right.targets:
                diffs.append(f"targets:{deal_id}")
    if set(base.resources) != set(variant.resources):
        diffs.append("resource_ids")
    else:
        for resource_id in sorted(base.resources):
            live = variant.resources[resource_id].capacity
            recorded = variant.generator.capacities[resource_id]
            if live != recorded:
                diffs.append(f"capacity_mismatch:{resource_id}")
            if live != base.resources[resource_id].capacity:
                diffs.append(f"capacity:{resource_id}")
    diffs.extend(_generator_differences(base, variant))
    return diffs


def collect_baseline(
    seeds: Sequence[int] = tuple(range(20)),
) -> list[ConditionRun]:
    """T=80 balanced replication. No field is edited after ``baseline_scenario``."""

    factories = default_policy_factories()
    runs: list[ConditionRun] = []
    for seed in seeds:
        scenario = baseline_scenario(seed)
        reference = with_horizon(generate_scenario(get_preset("balanced"), seed), BASELINE_HORIZON)
        assert_only_changed(reference, scenario, ())
        for factory in factories:
            diagnosis = diagnose_rollout(scenario, factory(seed))
            runs.append(ConditionRun("none", "baseline", float(BASELINE_HORIZON), diagnosis))
    _assert_baseline_replication(runs)
    return runs


def collect_capacity_sweep(
    resource_id: str,
    seeds: Sequence[int] = tuple(range(20)),
    multipliers: Sequence[float] = CAPACITY_MULTIPLIERS,
) -> list[ConditionRun]:
    """One resource, several multipliers of its balanced capacity. Everything else stays."""

    if resource_id not in RESOURCE_IDS:
        raise KeyError(resource_id)
    factories = default_policy_factories()
    runs: list[ConditionRun] = []
    for seed in seeds:
        base = baseline_scenario(seed)
        baseline_capacity = base.resources[resource_id].capacity
        for multiplier in multipliers:
            capacity = baseline_capacity * multiplier
            variant = with_capacity(base, resource_id, capacity)
            assert_only_changed(base, variant, (f"capacity:{resource_id}",))
            for factory in factories:
                diagnosis = diagnose_rollout(variant, factory(seed))
                runs.append(
                    ConditionRun(
                        f"capacity:{resource_id}",
                        f"{multiplier:.2f}x",
                        capacity,
                        diagnosis,
                    )
                )
    return runs


def format_experiment_report(runs: Sequence[ConditionRun], setup_lines: Sequence[str]) -> str:
    """Mean and sample standard deviation by level and policy. No ranking."""

    lines = list(setup_lines)
    lines.append("This summary does not rank policies.")
    lines.append("Completed is the mean of sum y_i across seeds.")
    lines.append("Completion day pools finished deals. Residual all deals counts a finished deal as gap 0.")
    lines.append("Idle is allocated / no compatible eligible work / eligible work left unused.")
    lines.append("Utilization is the allocated fraction of each resource's capacity.")
    lines.append("")
    lines.append(_markdown_table(runs))
    lines.append("")
    lines.extend(_detail_blocks(runs))
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _assert_baseline_replication(runs: Sequence[ConditionRun]) -> None:
    """The T=80 horizon sweep finished every FIFO and Bottleneck deal, and Random averaged 0.15."""

    by_policy: dict[str, list[ConditionRun]] = defaultdict(list)
    for run in runs:
        by_policy[run.diagnosis.policy].append(run)
    for policy in ("fifo", "bottleneck"):
        completed = [run.diagnosis.completed_deals for run in by_policy[policy]]
        if not completed or any(value != 4 for value in completed):
            raise RuntimeError(f"baseline replication failed for {policy}: {completed}")
    random_completed = [run.diagnosis.completed_deals for run in by_policy["random"]]
    if not random_completed:
        raise RuntimeError("baseline replication has no random runs")
    random_mean = statistics.fmean(random_completed)
    if abs(random_mean - 0.15) > 1e-9:
        raise RuntimeError(f"baseline random mean completed deals is {random_mean}, expected 0.15")


def _prefix_progress(scenario: Scenario, count: int) -> dict[tuple[str, str], float]:
    progress = {key: 0.0 for key in scenario.task_keys()}
    for deal_id, deal in scenario.deals.items():
        order = topological_order(set(deal.tasks), deal.edges)
        done = 0
        for task_id in order:
            if done >= count:
                break
            preds = predecessors(deal.edges, task_id)
            if all(progress[(deal_id, pred)] >= 1.0 for pred in preds):
                progress[(deal_id, task_id)] = 1.0
                done += 1
    return progress


def _controlled_edges(seed: int, deal: DealGraph, probability: float) -> set[tuple[str, str]]:
    specs = _specs()
    names = {task.name for task in deal.tasks.values()}
    dropped = {spec.name for spec in specs if spec.name not in names}
    preds_of = {spec.name: spec.predecessors for spec in specs}
    edges: set[tuple[str, str]] = set()
    order = [spec.name for spec in specs if spec.name in names]
    for spec in specs:
        if spec.name not in names:
            continue
        task_id = f"{deal.deal_id}:{spec.name}"
        for pred_name in _expand_predecessors(spec.name, preds_of, dropped):
            edges.add((f"{deal.deal_id}:{pred_name}", task_id))
    rng = random.Random(f"{seed}:{deal.deal_id}:{probability:.6f}:extra_edges")
    for index, dest_name in enumerate(order):
        if index == 0 or rng.random() >= probability:
            continue
        source_name = order[rng.randrange(0, index)]
        edges.add((f"{deal.deal_id}:{source_name}", f"{deal.deal_id}:{dest_name}"))
    return edges


def _generator_differences(base: Scenario, variant: Scenario) -> list[str]:
    left = base.generator
    right = variant.generator
    diffs: list[str] = []
    for field_name in (
        "name",
        "n_deals",
        "horizon",
        "extra_edge_probability",
        "optional_drop_probability",
        "partial_start_fraction",
        "phi_range",
        "alpha_range",
        "q_range",
        "protected_task_types",
    ):
        if getattr(left, field_name) != getattr(right, field_name):
            diffs.append(f"generator.{field_name}")
    if set(left.capacities) != set(right.capacities):
        diffs.append("generator.capacity_ids")
    return diffs


def _markdown_table(runs: Sequence[ConditionRun]) -> str:
    header = (
        "| Level | Level value | Policy | Completed | Completion day | Target | Non-target | "
        "Residual unfinished | Residual all | A | B | C | Idle alloc | Idle none | Idle despite | "
        "Herfindahl | Tasks allocated |"
    )
    lines = [header, "|" + "---|" * 17]
    for level, capacity, policy, group in _groups(runs):
        diagnoses = [run.diagnosis for run in group]
        deals = [deal for run in diagnoses for deal in run.unfinished]
        counts = {"A": 0, "B": 0, "C": 0}
        for deal in deals:
            counts[deal.label] += 1
        n_deals = sum(len(run.completion_times) for run in diagnoses)
        unfinished_residual = _mean(deal.critical_residual for deal in deals)
        unfinished_text = "none" if not deals else f"{unfinished_residual:.3f}"
        all_residual = (
            sum(deal.critical_residual for deal in deals) / n_deals if n_deals else float("nan")
        )
        lines.append(
            f"| {level} | {capacity:.4f} | {policy} | {_stat(run.completed_deals for run in diagnoses)} | "
            f"{_completion_stat(diagnoses)} | {_stat_optional(run.mean_target_progress for run in diagnoses)} | "
            f"{_stat_optional(run.mean_nontarget_progress for run in diagnoses)} | "
            f"{unfinished_text} | {all_residual:.3f} | "
            f"{counts['A']} | {counts['B']} | {counts['C']} | "
            f"{_mean(run.mean_allocated_fraction for run in diagnoses):.3f} | "
            f"{_mean(run.mean_unused_no_eligible_fraction for run in diagnoses):.3f} | "
            f"{_mean(run.mean_unused_despite_eligible_fraction for run in diagnoses):.3f} | "
            f"{_mean_optional(run.mean_herfindahl for run in diagnoses):.3f} | "
            f"{_stat(run.mean_tasks_with_allocation for run in diagnoses)} |"
        )
    return "\n".join(lines)


def _detail_blocks(runs: Sequence[ConditionRun]) -> list[str]:
    lines: list[str] = []
    for level, capacity, policy, group in _groups(runs):
        diagnoses = [run.diagnosis for run in group]
        lines.append(f"level={level} level_value={capacity:.4f} policy={policy}")
        lines.append(f"  completed_deals: {_metric(run.completed_deals for run in diagnoses)}")
        lines.append(f"  target_progress: {_metric_optional(run.mean_target_progress for run in diagnoses)}")
        lines.append(f"  nontarget_progress: {_metric_optional(run.mean_nontarget_progress for run in diagnoses)}")
        lines.append(f"  fraction_x_eq_0: {_metric(run.fraction_zero for run in diagnoses)}")
        lines.append(f"  fraction_0_lt_x_lt_1: {_metric(run.fraction_partial for run in diagnoses)}")
        lines.append(f"  fraction_x_eq_1: {_metric(run.fraction_one for run in diagnoses)}")
        days = _finished_days(diagnoses)
        if days:
            lines.append(
                f"  completion_day: {_metric(days)} median={statistics.median(days):.4f} n_deals={len(days)}"
            )
        else:
            lines.append("  completion_day: no finished deals")
        resource_ids = sorted({resource_id for run in diagnoses for resource_id in run.idle_fractions_by_resource})
        for resource_id in resource_ids:
            triples = [
                run.idle_fractions_by_resource[resource_id]
                for run in diagnoses
                if resource_id in run.idle_fractions_by_resource
            ]
            lines.append(
                f"  utilization_{resource_id}: {_metric(item[0] for item in triples)} "
                f"idle_none={_mean(item[1] for item in triples):.4f} "
                f"idle_despite={_mean(item[2] for item in triples):.4f}"
            )
        lines.append(f"  herfindahl: {_metric_optional(run.mean_herfindahl for run in diagnoses)}")
        lines.append(f"  tasks_with_allocation: {_metric(run.mean_tasks_with_allocation for run in diagnoses)}")
    return lines


def _groups(
    runs: Sequence[ConditionRun],
) -> list[tuple[str, float, str, list[ConditionRun]]]:
    order: list[tuple[str, float]] = []
    seen: set[tuple[str, float]] = set()
    for run in runs:
        key = (run.level, run.level_value)
        if key not in seen:
            seen.add(key)
            order.append(key)
    grouped: list[tuple[str, float, str, list[ConditionRun]]] = []
    for level, capacity in order:
        for policy in POLICY_ORDER:
            group = [
                run
                for run in runs
                if run.level == level and run.level_value == capacity and run.diagnosis.policy == policy
            ]
            if group:
                grouped.append((level, capacity, policy, group))
    return grouped


def _finished_days(runs: Iterable[RunDiagnosis]) -> list[float]:
    return [
        float(day)
        for run in runs
        for day in run.completion_times.values()
        if day is not None
    ]


def _completion_stat(runs: Sequence[RunDiagnosis]) -> str:
    days = _finished_days(runs)
    if not days:
        return "none"
    median = statistics.median(days)
    return f"{_stat(days)} med {median:.2f}"


def _metric(values: Iterable[float]) -> str:
    return format_metric(summarize_metric([float(value) for value in values]))


def _metric_optional(values: Iterable[float | None]) -> str:
    present = [float(value) for value in values if value is not None]
    if not present:
        return "n=0"
    return format_metric(summarize_metric(present))


def _stat(values: Iterable[float]) -> str:
    numbers = [float(value) for value in values]
    if len(numbers) < 2:
        return f"{numbers[0]:.3f}" if numbers else "na"
    return f"{statistics.fmean(numbers):.3f} ({statistics.stdev(numbers):.3f})"


def _stat_optional(values: Iterable[float | None]) -> str:
    return _stat(float(value) for value in values if value is not None)


def _mean(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return float("nan")
    return statistics.fmean(numbers)


def _mean_optional(values: Iterable[float | None]) -> float:
    return _mean(float(value) for value in values if value is not None)


def edit_scenario(
    base: Scenario,
    *,
    density: float = 1.0,
    resource_id: str | None = None,
    capacity_multiplier: float = 1.0,
    q_factor: float = 1.0,
    alpha_factor: float = 1.0,
) -> Scenario:
    """Copy ``base`` and change only the factors that differ from 1.

    Density 1 keeps the frozen edges. Any other density redraws edges at
    ``density * extra_edge_probability`` and leaves tasks, targets, and
    parameters alone.
    """

    allowed: list[str] = []
    scenario = base
    if density != 1.0:
        probability = base.generator.extra_edge_probability * density
        scenario = with_edges(scenario, probability)
        allowed.append("edges:")
    if resource_id is not None and capacity_multiplier != 1.0:
        capacity = base.resources[resource_id].capacity * capacity_multiplier
        scenario = with_capacity(scenario, resource_id, capacity)
        allowed.append(f"capacity:{resource_id}")
    if q_factor != 1.0:
        scenario = with_scaled_q(scenario, q_factor)
        allowed.append("q")
    if alpha_factor != 1.0:
        scenario = with_scaled_alpha(scenario, alpha_factor)
        allowed.append("alpha")
    assert_only_changed(base, scenario, tuple(allowed))
    return scenario


def graph_summary(scenario: Scenario) -> dict[str, float]:
    """Edge and depth statistics. Depth is the longest predecessor chain."""

    in_degrees: list[float] = []
    out_degrees: list[float] = []
    depths: list[float] = []
    edge_count = 0
    for deal in scenario.deals.values():
        edge_count += len(deal.edges)
        incoming = {task_id: 0 for task_id in deal.tasks}
        outgoing = {task_id: 0 for task_id in deal.tasks}
        for source, dest in deal.edges:
            outgoing[source] += 1
            incoming[dest] += 1
        in_degrees.extend(incoming.values())
        out_degrees.extend(outgoing.values())
        memo: dict[str, int] = {}
        for task_id in deal.tasks:
            depths.append(float(task_depth(deal.edges, task_id, memo)))
    return {
        "edges": float(edge_count),
        "mean_in_degree": _mean(in_degrees),
        "mean_out_degree": _mean(out_degrees),
        "mean_depth": _mean(depths),
        "max_depth": max(depths) if depths else 0.0,
    }


def q_clip_fraction(scenario: Scenario, factor: float) -> float:
    """Share of positive baseline q values that would exceed 1 after scaling."""

    positive = [value for value in scenario.suitability.values() if value > 0.0]
    if not positive:
        return 0.0
    return sum(1 for value in positive if value * factor > 1.0) / len(positive)


def product_match_fraction(left: Scenario, right: Scenario) -> float:
    """Share of suitable pairs whose alpha*q agrees. Zeros are not suitable."""

    keys = [key for key, value in left.suitability.items() if value > 0.0 or right.suitability[key] > 0.0]
    if not keys:
        return 1.0
    matches = 0
    for key in keys:
        left_product = left.alpha[key] * left.suitability[key]
        right_product = right.alpha[key] * right.suitability[key]
        if abs(left_product - right_product) <= 1e-9:
            matches += 1
    return matches / len(keys)


def collect_edited(
    cells: Sequence[tuple[str, float, dict[str, object]]],
    seeds: Sequence[int] = tuple(range(20)),
    variable: str = "factor",
) -> tuple[list[ConditionRun], dict[str, list[dict[str, float]]]]:
    """Roll out each cell on the frozen baseline. ``cells`` are (level, value, edit kwargs)."""

    factories = default_policy_factories()
    runs: list[ConditionRun] = []
    graphs: dict[str, list[dict[str, float]]] = defaultdict(list)
    for seed in seeds:
        base = baseline_scenario(seed)
        for level, level_value, raw_kwargs in cells:
            kwargs = dict(raw_kwargs)
            scenario = edit_scenario(
                base,
                density=float(kwargs.get("density", 1.0)),
                resource_id=kwargs.get("resource_id"),  # type: ignore[arg-type]
                capacity_multiplier=float(kwargs.get("capacity_multiplier", 1.0)),
                q_factor=float(kwargs.get("q_factor", 1.0)),
                alpha_factor=float(kwargs.get("alpha_factor", 1.0)),
            )
            graphs[level].append(graph_summary(scenario))
            for factory in factories:
                diagnosis = diagnose_rollout(scenario, factory(seed))
                runs.append(ConditionRun(variable, level, level_value, diagnosis))
    return runs, graphs


def format_factor_report(
    runs: Sequence[ConditionRun],
    setup_lines: Sequence[str],
    graphs: dict[str, list[dict[str, float]]] | None = None,
    reference_level: str | None = None,
    extra_lines: Sequence[str] = (),
) -> str:
    """Standard table, graph stats, change from the reference level, and per-seed counts."""

    parts = [format_experiment_report(runs, setup_lines).rstrip()]
    if graphs:
        parts.append(_graph_section(graphs))
    if reference_level is not None:
        parts.append(_delta_section(runs, reference_level))
    parts.append(_per_seed_section(runs))
    if extra_lines:
        parts.append("\n".join(extra_lines))
    return "\n".join(parts).rstrip() + "\n"


def assert_reference_matches_baseline(runs: Sequence[ConditionRun], level: str) -> None:
    """The untouched cell must reproduce Experiment 0's completed-deal counts."""

    selected = [run for run in runs if run.level == level]
    _assert_baseline_replication(selected)


def _graph_section(graphs: dict[str, list[dict[str, float]]]) -> str:
    lines = [
        "",
        "Graph structure by level, mean across seeds. Depth is the longest predecessor chain.",
        "level edges mean_in mean_out mean_depth max_depth",
    ]
    for level, rows in graphs.items():
        lines.append(
            f"{level} {_mean(row['edges'] for row in rows):.2f} "
            f"{_mean(row['mean_in_degree'] for row in rows):.3f} "
            f"{_mean(row['mean_out_degree'] for row in rows):.3f} "
            f"{_mean(row['mean_depth'] for row in rows):.3f} "
            f"{_mean(row['max_depth'] for row in rows):.2f}"
        )
    return "\n".join(lines)


def _delta_section(runs: Sequence[ConditionRun], reference_level: str) -> str:
    lines = ["", f"Change from level {reference_level}. Completed is a difference of seed means."]
    reference: dict[str, list[ConditionRun]] = defaultdict(list)
    for run in runs:
        if run.level == reference_level:
            reference[run.diagnosis.policy].append(run)
    seen: list[str] = []
    for run in runs:
        if run.level not in seen:
            seen.append(run.level)
    for level in seen:
        if level == reference_level:
            continue
        for policy in POLICY_ORDER:
            group = [run for run in runs if run.level == level and run.diagnosis.policy == policy]
            base = reference.get(policy, [])
            if not group or not base:
                continue
            completed = _mean(run.diagnosis.completed_deals for run in group) - _mean(
                run.diagnosis.completed_deals for run in base
            )
            group_days = _finished_days(run.diagnosis for run in group)
            base_days = _finished_days(run.diagnosis for run in base)
            if group_days and base_days:
                day_text = f"{_mean(group_days) - _mean(base_days):+.2f}"
            else:
                day_text = "na"
            lines.append(f"  {level} {policy}: completed {completed:+.3f} completion_day {day_text}")
    return "\n".join(lines)


def _per_seed_section(runs: Sequence[ConditionRun]) -> str:
    lines = ["", "Per seed completed deals.", "seed level policy completed"]
    for run in runs:
        lines.append(
            f"{run.diagnosis.seed} {run.level} {run.diagnosis.policy} {run.diagnosis.completed_deals}"
        )
    return "\n".join(lines)
