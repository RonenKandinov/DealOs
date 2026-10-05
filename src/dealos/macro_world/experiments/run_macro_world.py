"""Run the seven macro-world scenarios and write one report."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, fields
from pathlib import Path

from dealos.macro_world.metrics import EvaluationVector, evaluate
from dealos.macro_world.models import (
    AuthorityRule,
    CapacityPool,
    Deal,
    Department,
    InformationObject,
    Observation,
    ObservationMask,
    Organization,
    Resource,
    Role,
    System,
    TaskOccurrence,
    TaskType,
    r0_representation,
)
from dealos.macro_world.observations import leak_count, observe
from dealos.macro_world.queries import authorized_holders, recoverable, representable
from dealos.macro_world.scenarios import Scenario, all_scenarios
from dealos.macro_world.validator import ValidationResult, candidate_representation, validate_scenario

VALIDATED = "MACRO WORLD VALIDATED"
REVISION = "MACRO WORLD REQUIRES REVISION"


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    candidate_id: str
    gt_representable_initial: bool
    gt_representable_candidate: bool
    recoverable: bool
    secondary_representable: bool
    secondary_recoverable: bool
    validation: ValidationResult
    vector: EvaluationVector
    reproducible: bool
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def execute(seed: int = 0) -> tuple[tuple[ScenarioResult, ...], str]:
    results = tuple(_assess(scenario, seed) for scenario in all_scenarios())
    line = VALIDATED if results and all(result.ok for result in results) else REVISION
    return results, line


def write_outputs(root: Path, seed: int = 0) -> str:
    results, line = execute(seed)
    _persist(root, results, line, seed)
    return line


def _persist(root: Path, results: tuple[ScenarioResult, ...], line: str, seed: int) -> None:
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "macro_world_scenarios.csv", _scenario_rows(results))
    _write_csv(analysis / "macro_world_evaluation.csv", _evaluation_rows(results))
    (docs / "macro_world_experiment.md").write_text(_report(results, line, seed), encoding="utf-8")


def _assess(scenario: Scenario, seed: int) -> ScenarioResult:
    observations = observe(scenario.ground_truth, scenario.mask, seed)
    repeat = observe(scenario.ground_truth, scenario.mask, seed)
    candidate = candidate_representation(scenario)
    leaks = leak_count(scenario.ground_truth, observations, scenario.mask)
    violations = _violations(scenario, observations)
    validation = validate_scenario(scenario)
    vector = evaluate(scenario, candidate, leaks, violations)
    initial_ok = representable(scenario.initial, scenario.capability)
    candidate_ok = representable(candidate, scenario.capability)
    recovered = recoverable(observations, scenario.mask, scenario.capability)
    secondary_representable = False
    secondary_recovered = False
    if scenario.secondary_capability:
        secondary_representable = representable(candidate, scenario.secondary_capability)
        secondary_recovered = recoverable(observations, scenario.mask, scenario.secondary_capability)
    failures = _failures(
        scenario,
        candidate,
        observations,
        repeat,
        initial_ok,
        candidate_ok,
        recovered,
        secondary_representable,
        secondary_recovered,
        leaks,
        violations,
        validation,
        vector,
    )
    return ScenarioResult(
        scenario,
        candidate.representation_id,
        initial_ok,
        candidate_ok,
        recovered,
        secondary_representable,
        secondary_recovered,
        validation,
        vector,
        observations == repeat,
        failures,
    )


def _failures(
    scenario: Scenario,
    candidate,
    observations: tuple[Observation, ...],
    repeat: tuple[Observation, ...],
    initial_ok: bool,
    candidate_ok: bool,
    recovered: bool,
    secondary_representable: bool,
    secondary_recovered: bool,
    leaks: int,
    violations: int,
    validation: ValidationResult,
    vector: EvaluationVector,
) -> tuple[str, ...]:
    failures: list[str] = []
    if not validation.accepted:
        failures.append("validation rejected: " + "; ".join(validation.reasons))
    if initial_ok != scenario.expect_representable_before:
        failures.append("initial representable flag disagrees with the scenario")
    if candidate_ok != scenario.expect_representable_after:
        failures.append("candidate representable flag disagrees with the scenario")
    if recovered != scenario.expect_recoverable:
        failures.append("recoverable flag disagrees with the scenario")
    if scenario.secondary_capability:
        if secondary_representable != scenario.expect_secondary_representable:
            failures.append("secondary representable flag disagrees with the scenario")
        if secondary_recovered != scenario.expect_secondary_recoverable:
            failures.append("secondary recoverable flag disagrees with the scenario")
    if observations != repeat:
        failures.append("the same seed did not repeat the observations")
    if leaks:
        failures.append(f"mask leaked {leaks} values")
    if violations:
        failures.append(f"epistemic violations {violations}")
    if vector.regression:
        failures.append("regression")
    if vector.observation_faithfulness != 1.0:
        failures.append("observation faithfulness is below 1")
    if scenario.scenario_id == "A" and candidate.primitives != r0_representation().primitives:
        failures.append("scenario A candidate is not the R0 primitive set")
    if scenario.scenario_id == "D" and "Clerk_R2" in authorized_holders(scenario.ground_truth):
        failures.append("the non-authorizing resource was treated as an authority holder")
    if scenario.scenario_id in {"B", "G"}:
        for observation in observations:
            if any(value == "LegalReviewer" for _name, value in observation.values) or observation.get("role_id"):
                failures.append("a role was copied into the observation")
    expected_coverage = 0.0 if scenario.capability == "ambiguous_interpretation" else float(scenario.expect_representable_after)
    if vector.ground_truth_coverage != expected_coverage:
        failures.append("ground-truth coverage disagrees with the candidate")
    return tuple(failures)


def _violations(scenario: Scenario, observations: tuple[Observation, ...]) -> int:
    count = 0
    for observation in observations:
        if observation.get("role_id") and not scenario.mask.expose_role:
            count += 1
        if observation.get("department_id") and not scenario.mask.expose_department:
            count += 1
        if observation.get("authority") and not scenario.mask.expose_authority:
            count += 1
        if observation.get("information_link") and not scenario.mask.expose_information_links:
            count += 1
        if scenario.scenario_id == "B" and observation.get("activity") == "LegalReviewer":
            count += 1
    if scenario.scenario_id == "G" and (scenario.mutations or scenario.epistemic_status != "HYPOTHESIS"):
        count += 1
    if scenario.scenario_id == "D":
        holders = authorized_holders(scenario.ground_truth)
        if "Clerk_R2" in holders or "role_finance_approver" not in holders:
            count += 1
    return count


def _scenario_rows(results: tuple[ScenarioResult, ...]) -> list[dict]:
    rows = []
    for result in results:
        scenario = result.scenario
        rows.append(
            {
                "scenario": scenario.scenario_id,
                "name": scenario.name,
                "missing_primitive": scenario.missing_primitive,
                "initial": scenario.initial.representation_id,
                "candidate": result.candidate_id,
                "gt_representable": result.gt_representable_candidate,
                "observable": result.recoverable,
                "secondary_capability": scenario.secondary_capability,
                "secondary_recoverable": result.secondary_recoverable if scenario.secondary_capability else "",
                "decision": scenario.decision,
                "epistemic_status": scenario.epistemic_status,
                "ok": result.ok,
            }
        )
    return rows


def _evaluation_rows(results: tuple[ScenarioResult, ...]) -> list[dict]:
    rows = []
    for result in results:
        vector = result.vector
        rows.append(
            {
                "scenario": vector.scenario_id,
                "capabilities_before": _pairs(vector.capabilities_before),
                "capabilities_after": _pairs(vector.capabilities_after),
                "mismatches_resolved": " ".join(vector.mismatches_resolved),
                "mismatches_partial": " ".join(vector.mismatches_partial),
                "mismatches_unresolved": " ".join(vector.mismatches_unresolved),
                "ground_truth_coverage": vector.ground_truth_coverage,
                "observation_faithfulness": vector.observation_faithfulness,
                "regression": vector.regression,
                "complexity_delta": vector.complexity_delta,
                "epistemic_violations": vector.epistemic_violations,
                "recoverable": result.recoverable,
            }
        )
    return rows


def _report(results: tuple[ScenarioResult, ...], line: str, seed: int) -> str:
    parts = [
        "# Macro world experiment",
        "",
        "This file is the whole experiment: the worlds, the masks, the representation checks, and the decision.",
        "",
        "## 1. Objective",
        "",
        "The ground truth is an organizational world, the observation is the part a mask exposes, and the representation is only what the named primitives can express. Hidden ground truth is not copied into the event stream.",
        "",
        "## 2. Ground Truth schema",
        "",
        _schema(Organization),
        _schema(Deal),
        _schema(Department),
        _schema(Role),
        _schema(Resource),
        _schema(System),
        _schema(TaskType),
        _schema(TaskOccurrence),
        _schema(InformationObject),
        _schema(AuthorityRule),
        _schema(CapacityPool),
        "Relations: belongs_to(resource, role), belongs_to(role, department), performs(resource, occurrence), requires(occurrence, information), produces(system, information), consumes(system, information), authorizes(holder, action), allocated_to(resource, occurrence), depends_on(task, task).",
        "",
        "## 3. Observation schema",
        "",
        "An observation carries event_id and only the fields the mask exposes: timestamp, deal_id, activity, lifecycle, resource_id, system_id, information_id, role_id, department_id, authority, information_link, capacity.",
        _schema(ObservationMask),
        "",
        "## 4. Representation R0",
        "",
        "R_micro is TaskType, DAG, TaskOccurrence, Lifecycle, Progress, Capacity.",
        "R0 is R_micro plus PersistentResourceIdentifier and ResourceOccurrenceAssociation.",
        "R0 has no Role, Department, Authority, InformationDependency, System, Ownership, or Handoff primitive.",
        "Scenario A starts from R_micro. Scenarios B through G start from R0.",
        "",
        "## 5. Scenario definitions",
        "",
        "| Scenario | Missing primitive | Initial | Candidate | GT representable | Observable | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        scenario = result.scenario
        observable = _yes(result.recoverable)
        if scenario.secondary_capability:
            observable = (
                f"{scenario.capability} {_yes(result.recoverable)}; "
                f"{scenario.secondary_capability} {_yes(result.secondary_recoverable)}"
            )
        parts.append(
            "| {id} {name} | {missing} | {initial} | {candidate} | {gt} | {obs} | {decision} |".format(
                id=scenario.scenario_id,
                name=scenario.name,
                missing=scenario.missing_primitive,
                initial=scenario.initial.representation_id,
                candidate=result.candidate_id,
                gt=_yes(result.gt_representable_candidate),
                obs=observable,
                decision=scenario.decision,
            )
        )
    parts.extend(["", "Seed used for timestamps: {seed}.".format(seed=seed), ""])
    for result in results:
        scenario = result.scenario
        parts.append(f"Scenario {scenario.scenario_id}, {scenario.name}. {scenario.purpose}")
        parts.append("")
    parts.extend(
        [
            "## 6. Mismatches",
            "",
        ]
    )
    for result in results:
        mismatch = result.scenario.mismatch
        parts.append(
            f"{mismatch.mismatch_id} ({mismatch.epistemic_status}): {mismatch.evidence} Missing capability: {mismatch.missing_capability}."
        )
    parts.extend(["", "## 7. Candidate mutations", ""])
    for result in results:
        names = ", ".join(f"{mutation.operator}({mutation.target})" for mutation in result.scenario.mutations) or "none"
        parts.append(f"Scenario {result.scenario.scenario_id}: {names}.")
    parts.extend(["", "## 8. Validation", ""])
    for result in results:
        parts.append(
            f"Scenario {result.scenario.scenario_id}: accepted {result.validation.accepted}. Schema {result.validation.schema_valid}. Integrity {result.validation.integrity_valid}. Leakage check {result.validation.leakage_valid}. Regression check {result.validation.regression_valid}. Alignment {result.validation.alignment_valid}."
        )
    parts.extend(["", "## 9. Ground Truth coverage", ""])
    for result in results:
        parts.append(f"Scenario {result.scenario.scenario_id}: {result.vector.ground_truth_coverage:.1f}.")
    parts.extend(
        [
            "",
            "## 10. Observation recoverability",
            "",
            "Representable and recoverable are separate. A candidate can express a ground-truth relation while the mask still hides it.",
            "",
        ]
    )
    for result in results:
        extra = ""
        if result.scenario.secondary_capability:
            extra = f" {result.scenario.secondary_capability} recoverable: {_yes(result.secondary_recoverable)}."
        parts.append(
            f"Scenario {result.scenario.scenario_id}: {result.scenario.capability} recoverable: {_yes(result.recoverable)}.{extra}"
        )
    parts.extend(["", "## 11. Epistemic violations", ""])
    for result in results:
        parts.append(f"Scenario {result.scenario.scenario_id}: {result.vector.epistemic_violations}.")
    parts.extend(["", "## 12. Regression checks", ""])
    for result in results:
        parts.append(
            f"Scenario {result.scenario.scenario_id}: regression {str(result.vector.regression).lower()}, complexity delta {result.vector.complexity_delta}."
        )
    parts.extend(["", "## 13. Final conclusions", ""])
    parts.extend(_conclusions(results))
    parts.extend(["", "## Decision", "", line, ""])
    return "\n".join(parts)


def _conclusions(results: tuple[ScenarioResult, ...]) -> list[str]:
    expressed = []
    recovered = []
    needs_evidence = []
    observation_justified = []
    representation_only = []
    unresolved = []
    expanded = []
    for result in results:
        scenario = result.scenario
        label = f"{scenario.scenario_id} {scenario.missing_primitive}"
        if result.gt_representable_candidate and scenario.capability != "ambiguous_interpretation":
            expressed.append(f"{scenario.scenario_id} {scenario.capability}")
        if result.recoverable:
            recovered.append(f"{scenario.scenario_id} {scenario.capability}")
        if result.gt_representable_candidate and not result.recoverable and scenario.capability != "ambiguous_interpretation":
            needs_evidence.append(f"{scenario.scenario_id} {scenario.capability}")
        if scenario.secondary_capability and result.secondary_representable and not result.secondary_recoverable:
            needs_evidence.append(f"{scenario.scenario_id} {scenario.secondary_capability}")
        if scenario.accept_mutation and result.recoverable:
            observation_justified.append(label)
        elif scenario.accept_mutation:
            representation_only.append(label)
        if scenario.epistemic_status == "HYPOTHESIS":
            unresolved.append(scenario.scenario_id)
        before = dict(result.vector.capabilities_before)
        after = dict(result.vector.capabilities_after)
        if any(after[name] and not before[name] for name in after):
            expanded.append(scenario.scenario_id)
    ready = "A is the resource-occurrence relation. F records one resource id across three deals and a hidden finite pool, with no allocation chosen. B, C, D, and E are schema extensions whose relations are still hidden. G is unresolved."
    return [
        f"1. Representable relations in the candidate for each scenario: {', '.join(expressed)}.",
        f"2. Recoverable from the masked events: {', '.join(recovered)}.",
        f"3. Representable and still requiring evidence: {', '.join(needs_evidence)}.",
        f"4. Mutations justified by the exposed events: {', '.join(observation_justified)}. Representation extensions that the events do not recover: {', '.join(representation_only)}.",
        f"5. Unresolved hypotheses: {', '.join(unresolved)}.",
        f"6. The macro candidates add a relation the starting representation lacked in scenarios {', '.join(expanded)}.",
        f"7. Ready for a later problem formulation: {ready}",
    ]


def _schema(cls: type) -> str:
    names = ", ".join(item.name for item in fields(cls))
    return f"{cls.__name__}: {names}."


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _pairs(pairs: tuple[tuple[str, bool], ...]) -> str:
    return " ".join(f"{name}={'yes' if value else 'no'}" for name, value in pairs)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def format_cli(results: tuple[ScenarioResult, ...], line: str, seed: int, root: Path) -> str:
    lines = [f"seed {seed}", ""]
    for result in results:
        scenario = result.scenario
        observed = _yes(result.recoverable)
        if scenario.secondary_capability:
            observed = (
                f"{scenario.capability} {_yes(result.recoverable)}, "
                f"{scenario.secondary_capability} {_yes(result.secondary_recoverable)}"
            )
        status = "ok" if result.ok else "FAILED: " + "; ".join(result.failures)
        lines.append(
            f"{scenario.scenario_id} {scenario.name}: {scenario.initial.representation_id} -> {result.candidate_id}"
        )
        lines.append(f"  ground truth representable: {_yes(result.gt_representable_candidate)}")
        lines.append(f"  recoverable from events: {observed}")
        lines.append(f"  {scenario.decision}")
        lines.append(f"  {status}")
        for observation in observe(scenario.ground_truth, scenario.mask, seed):
            shown = ", ".join(f"{name}={value}" for name, value in observation.values)
            lines.append(f"  event {shown}")
        lines.append("")
    lines.append(f"report: {root / 'docs' / 'macro_world_experiment.md'}")
    lines.append(line)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the controlled macro-world scenarios and write one report."
    )
    parser.add_argument("--seed", type=int, default=0, help="Timestamp seed. The same seed repeats the events.")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[4]
    results, line = execute(args.seed)
    _persist(root, results, line, args.seed)
    print(format_cli(results, line, args.seed, root))
    return 0 if line == VALIDATED else 1


if __name__ == "__main__":
    raise SystemExit(main())
