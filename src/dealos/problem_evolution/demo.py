"""One evolution cycle from the simplified V1 representation and the BPI17 mismatches."""

from __future__ import annotations

from dealos.problem_evolution.engine import ProblemEvolutionEngine, v1_representation
from dealos.problem_evolution.mismatch import bpi17_mismatches


def render(result) -> str:
    history = result.history
    lines = [
        f"Current representation: {history.parent.representation_id}",
        "Components: " + ", ".join(component.name for component in history.parent.components),
        "",
        "Detected mismatches:",
    ]
    for mismatch in history.mismatches:
        lines.append(
            f"- {mismatch.mismatch_id} {mismatch.category} [{mismatch.status}] {mismatch.evidence_reference}"
        )
    lines.append("")
    lines.append("Proposals:")
    for proposal in history.proposals:
        lines.append(
            f"- {proposal.operator} from {', '.join(proposal.source_mismatches)}: {proposal.rationale}"
        )
    lines.append("")
    lines.append("Candidates:")
    for candidate in history.candidates:
        names = ", ".join(component.name for component in candidate.representation.components)
        lines.append(f"- {candidate.candidate_id}: {names}")
    lines.append("")
    lines.append("Validation:")
    for item in history.validation:
        lines.append(
            f"- {item.candidate_id}: schema={item.schema_valid} invariant={item.invariant_valid} "
            f"compatibility={item.compatibility_valid}"
        )
    lines.append("")
    lines.append("Evaluation:")
    for item in history.evaluation:
        lines.append(
            f"- {item.candidate_id}: resolved={list(item.mismatches_resolved)} "
            f"partial={list(item.mismatches_partially_resolved)} "
            f"unresolved={list(item.mismatches_unresolved)} "
            f"regression={item.regression_passed} complexity_delta={item.complexity_delta}"
        )
    lines.append("")
    chosen = "none" if result.selected is None else result.selected.candidate_id
    lines.append(f"Selected candidate: {chosen}")
    lines.append(result.explanation)
    lines.append(f"Generations: {result.generations}")
    lines.append(
        "TaskType is the DAG vertex. TaskOccurrence is one execution of that type. "
        "This run does not start another cycle."
    )
    return "\n".join(lines)


def main() -> None:
    engine = ProblemEvolutionEngine()
    result = engine.run(v1_representation(), bpi17_mismatches())
    print(render(result))


if __name__ == "__main__":
    main()
