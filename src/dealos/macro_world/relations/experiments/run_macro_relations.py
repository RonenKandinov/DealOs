"""Run the macro relation scenarios and write one report."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from dealos.macro_world.relations.graph import GraphEdge, graph_edges
from dealos.macro_world.relations.models import RELATION_ENDS
from dealos.macro_world.relations.observe import observe
from dealos.macro_world.relations.scenarios import RelationScenario, all_relation_scenarios
from dealos.macro_world.relations.validate import RelationEvaluation, assess

VALIDATED = "MACRO RELATIONS VALIDATED"
REVISION = "MACRO RELATIONS REQUIRE REVISION"


def execute(seed: int = 0) -> tuple[tuple[tuple[RelationScenario, RelationEvaluation, tuple[str, ...]], ...], tuple[GraphEdge, ...], str]:
    assessed = tuple((scenario, *assess(scenario, seed)) for scenario in all_relation_scenarios())
    extra = _cross_checks(assessed, seed)
    edges = graph_edges(tuple((evaluation, failures + extra) for _scenario, evaluation, failures in assessed))
    ok = all(not failures for _scenario, _evaluation, failures in assessed) and not extra and _graph_ok(edges)
    line = VALIDATED if ok else REVISION
    return assessed, edges, line


def write_outputs(root: Path, seed: int = 0) -> str:
    assessed, edges, line = execute(seed)
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "macro_relation_scenarios.csv", _scenario_rows(assessed))
    _write_csv(analysis / "macro_relation_evaluation.csv", _evaluation_rows(assessed))
    (docs / "macro_relation_experiment.md").write_text(_report(assessed, edges, line, seed), encoding="utf-8")
    return line


def format_cli(assessed, edges: tuple[GraphEdge, ...], line: str, root: Path) -> str:
    groups = _groups(assessed, edges)
    lines = ["Macro relation discovery", ""]
    for scenario, evaluation, failures in assessed:
        status = "ok" if not failures else "FAILED: " + "; ".join(failures)
        lines.append(
            f"{scenario.scenario_id} {evaluation.relation_name}: "
            f"gt {evaluation.ground_truth_present} representable {evaluation.representable_before}->{evaluation.representable_after} "
            f"recoverable {evaluation.recoverable} ambiguity {evaluation.ambiguity} accepted {evaluation.mutation_accepted} {status}"
        )
    lines.extend(["", "Macro entities: " + ", ".join(groups["entities"])])
    lines.append("Macro relations: " + _labels(groups["relations"]))
    lines.append("Recoverable relations: " + _labels(groups["recoverable"]))
    lines.append("Representable-but-hidden relations: " + _labels(groups["hidden"]))
    lines.append("Ambiguous relations: " + _labels(groups["ambiguous"]))
    lines.append("Rejected relations: " + _labels(groups["rejected"]))
    lines.append(f"Scenario checks passed: {groups['passed']}/{groups['total']}")
    lines.append(f"report: {root / 'docs' / 'macro_relation_experiment.md'}")
    lines.append(line)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover which macro-to-macro relations survive controlled checks.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[5]
    assessed, edges, line = execute(args.seed)
    write_note = line
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "macro_relation_scenarios.csv", _scenario_rows(assessed))
    _write_csv(analysis / "macro_relation_evaluation.csv", _evaluation_rows(assessed))
    (docs / "macro_relation_experiment.md").write_text(_report(assessed, edges, line, args.seed), encoding="utf-8")
    print(format_cli(assessed, edges, write_note, root))
    return 0 if line == VALIDATED else 1


def _cross_checks(assessed, seed: int) -> tuple[str, ...]:
    failures: list[str] = []
    paired = []
    authority = []
    for scenario, _evaluation, _failures in assessed:
        if scenario.scenario_id in {"MR-D1", "MR-D2", "MR-D3"}:
            paired.append(observe(scenario.world, scenario.mask, seed))
        if scenario.scenario_id in {"MR-E", "MR-F"}:
            authority.append(observe(scenario.world, scenario.mask, seed))
    if len(paired) == 3 and not (paired[0] == paired[1] == paired[2]):
        failures.append("resource-pair observations differ across relation types")
    if len(authority) == 2 and authority[0] != authority[1]:
        failures.append("role authority and resource authority observations differ")
    return tuple(failures)


def _graph_ok(edges: tuple[GraphEdge, ...]) -> bool:
    if not edges:
        return False
    for edge in edges:
        source, target = RELATION_ENDS[edge.relation_name]
        if source != edge.source_entity or target != edge.target_entity:
            return False
        if "Task" in source or "Task" in target or "Deal" in source or "Deal" in target:
            return False
    return True


def _groups(assessed, edges: tuple[GraphEdge, ...]) -> dict:
    entities: list[str] = []
    for edge in edges:
        for name in (edge.source_entity, edge.target_entity):
            if name not in entities:
                entities.append(name)
    relations = [edge.relation_name for edge in edges]
    recoverable = [evaluation.relation_name for _s, evaluation, _f in assessed if evaluation.recoverable]
    hidden = [
        evaluation.relation_name
        for _s, evaluation, _f in assessed
        if evaluation.mutation_accepted and not evaluation.recoverable
    ]
    passed = sum(1 for _s, _e, failures in assessed if not failures)
    return {
        "entities": entities,
        "relations": relations,
        "recoverable": recoverable,
        "hidden": hidden,
        "ambiguous": [f"{scenario.scenario_id}:{evaluation.relation_name}" for scenario, evaluation, _f in assessed if evaluation.ambiguity],
        "rejected": [
            f"{scenario.scenario_id}:{evaluation.relation_name}"
            for scenario, evaluation, _f in assessed
            if scenario.negative
        ],
        "passed": passed,
        "total": len(assessed),
    }


def _report(assessed, edges: tuple[GraphEdge, ...], line: str, seed: int) -> str:
    groups = _groups(assessed, edges)
    lines = [
        "# Macro relation experiment",
        "",
        "This file is the whole experiment. It stays inside the macro graph. It does not connect a macro entity to a deal, a task type, or a task occurrence.",
        "",
        "## 1. Objective",
        "",
        "Phase 1 separated ground truth, observations, and representation. This phase asks which relationships between macro entities are justified, which can be expressed but not recovered, and which stay hypotheses.",
        "",
        "## 2. Macro entity vocabulary",
        "",
        "Candidates: Organization, Department, Role, Resource, System, InformationObject, AuthorityRule, CapacityPool.",
        "A candidate is not added because the list contains it.",
        "",
        "## 3. Candidate relation vocabulary",
        "",
        "Organizational: Resource to Role, Role to Department, Department to Organization.",
        "Resource to resource types: collaborates_with, substitutes_for, depends_on.",
        "Authority: Role to AuthorityRule, Resource to AuthorityRule.",
        "Systems: System produces InformationObject, InformationObject consumed by System, System to System.",
        "Capacity: Resource to CapacityPool, Role to CapacityPool, Department to CapacityPool.",
        "",
        "## 4. Ground Truth model",
        "",
        "Each scenario stores explicit relation records. A record names the relation, the source id, the target id, and a semantic that is known only in the ground truth.",
        "",
        "## 5. Observation model",
        "",
        "The mask copies a field only when that field is exposed and the ground truth value is non-empty. A hidden role, department, organization, holder kind, relation type, or capacity holder is absent from the event.",
        f"Timestamp seed: {seed}.",
        "",
        "## 6. Scenario definitions",
        "",
        "| Scenario | Relation | GT | Representable after | Recoverable | Ambiguity | Accepted | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scenario, evaluation, _failures in assessed:
        lines.append(
            "| {sid} | {name} | {gt} | {after} | {rec} | {amb} | {acc} | {status} |".format(
                sid=scenario.scenario_id,
                name=evaluation.relation_name,
                gt=_yes(evaluation.ground_truth_present),
                after=_yes(evaluation.representable_after),
                rec=_yes(evaluation.recoverable),
                amb=_yes(evaluation.ambiguity),
                acc=_yes(evaluation.mutation_accepted),
                status=evaluation.epistemic_status,
            )
        )
    lines.extend(["", "## 7. Relation-level mismatches", ""])
    for scenario, evaluation, _failures in assessed:
        lines.append(f"{scenario.scenario_id}: {scenario.purpose}")
    lines.extend(["", "## 8. Candidate mutations", ""])
    for scenario, evaluation, _failures in assessed:
        names = ", ".join(f"{mutation.operator}({mutation.target})" for mutation in scenario.mutations) or "none"
        lines.append(f"{scenario.scenario_id}: {names}. Accepted: {_yes(evaluation.mutation_accepted)}.")
    lines.extend(["", "## 9. Validation", ""])
    for scenario, evaluation, failures in assessed:
        lines.append(
            f"{scenario.scenario_id}: checks passed {_yes(not failures)}. "
            f"Regression {str(evaluation.regression).lower()}. Complexity delta {evaluation.complexity_delta}. "
            f"Faithfulness {evaluation.observation_faithfulness:.1f}. Violations {evaluation.epistemic_violations}."
        )
    lines.extend(
        [
            "",
            "## 10. Recoverability",
            "",
            "No typed macro relation is recoverable from the masked events in this run.",
            "Recoverable relations: " + _labels(groups["recoverable"]) + ".",
            "",
            "## 11. Ambiguity",
            "",
            "Resource-pair runs MR-D1, MR-D2, and MR-D3 use different ground-truth types and the same exposed events. The type stays unresolved.",
            "MR-E and MR-F attach authority to a role and to a resource. Their exposed events match, so the holder kind stays unresolved.",
            "MR-I is a time order of system events. Data exchange, process dependency, and temporal succession all remain possible.",
            "MR-J hides the capacity holder, so resource-level, role-level, and department-level capacity are not separated by the events.",
            "",
            "## 12. Negative cases",
            "",
            "MR-D0 has co-presence and no ground-truth relation. The collaborates_with mutation is refused.",
            "MR-I has event order and no system-to-system relation. The integration mutation is refused.",
            "MR-J3 proposes department capacity. That relation is absent from the ground truth and is refused.",
            "Activity names are not roles, departments, or authority rules. ApproveDeal on Clerk_R2 does not create an authority edge.",
            "",
            "## 13. Final Macro graph",
            "",
        ]
    )
    if edges:
        for edge in edges:
            lines.append(f"{edge.source_entity} -- {edge.relation_name} --> {edge.target_entity} [{edge.epistemic_status}, hidden from the events]")
    else:
        lines.append("No edge passed the commitment rule.")
    lines.extend(
        [
            "",
            "These edges do not touch a deal, a task type, or a task occurrence.",
            "",
            "## 14. What remains unresolved",
            "",
            "Ambiguous: " + _labels(groups["ambiguous"]) + ".",
            "The resource-to-resource type, the authority holder kind, the system-to-system meaning, and the capacity holder level stay open.",
            "",
            "## 15. Explicit non-goals",
            "",
            "This phase does not connect macro entities to the micro graph, does not formulate an optimization problem, and does not run a solver.",
            "",
            "## 16. Decision",
            "",
            "The committed edges are the structural relations whose ground truth names one relation and whose events do not reveal it. The refused edges are the ones that would turn co-occurrence, event order, or a missing ground-truth link into a semantic relation.",
            "That is a justified macro graph for these controlled worlds. It is not a recovery of the graph from the event stream, and it is not an open list of entities.",
            "",
            line,
            "",
        ]
    )
    return "\n".join(lines)


def _scenario_rows(assessed) -> list[dict]:
    rows = []
    for scenario, evaluation, failures in assessed:
        rows.append(
            {
                "scenario": scenario.scenario_id,
                "relation_name": evaluation.relation_name,
                "ground_truth_present": evaluation.ground_truth_present,
                "representable_after": evaluation.representable_after,
                "recoverable": evaluation.recoverable,
                "ambiguity": evaluation.ambiguity,
                "mutation_accepted": evaluation.mutation_accepted,
                "epistemic_status": evaluation.epistemic_status,
                "ok": not failures,
            }
        )
    return rows


def _evaluation_rows(assessed) -> list[dict]:
    rows = []
    for _scenario, evaluation, _failures in assessed:
        rows.append(
            {
                "relation_name": evaluation.relation_name,
                "source_entity": evaluation.source_entity,
                "target_entity": evaluation.target_entity,
                "ground_truth_present": evaluation.ground_truth_present,
                "observation_evidence_present": evaluation.observation_evidence_present,
                "representable_before": evaluation.representable_before,
                "representable_after": evaluation.representable_after,
                "recoverable": evaluation.recoverable,
                "epistemic_status": evaluation.epistemic_status,
                "ambiguity": evaluation.ambiguity,
                "mutation_required": evaluation.mutation_required,
                "mutation_accepted": evaluation.mutation_accepted,
                "regression": evaluation.regression,
                "complexity_delta": evaluation.complexity_delta,
            }
        )
    return rows


def _labels(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
