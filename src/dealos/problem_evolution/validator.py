"""Schema, invariant, and one-occurrence compatibility checks."""

from __future__ import annotations

from dealos.problem_evolution.models import CandidateRepresentation, Representation, ValidationResult
from dealos.problem_evolution.mutations import OPERATORS

REQUIRED = ("TaskType", "DAG", "Progress", "Capacity")


def validate_candidate(
    parent: Representation,
    candidate: CandidateRepresentation,
    *,
    baseline_regression_passed: bool,
) -> ValidationResult:
    reasons: list[str] = []
    names = candidate.representation.names()
    schema_valid = True
    if candidate.parent_representation_id != parent.representation_id:
        schema_valid = False
        reasons.append("parent id does not match")
    if not candidate.mutations:
        schema_valid = False
        reasons.append("candidate has no mutation")
    for mutation in candidate.mutations:
        if mutation.operator not in OPERATORS:
            schema_valid = False
            reasons.append(f"unknown operator {mutation.operator}")
        if mutation.adds.name not in names:
            schema_valid = False
            reasons.append(f"{mutation.adds.name} was not added")
    if len(names) != len(candidate.representation.components):
        schema_valid = False
        reasons.append("duplicate component name")

    invariant_valid = all(name in names for name in REQUIRED)
    if not invariant_valid:
        reasons.append("candidate drops TaskType, DAG, Progress, or Capacity")
    if "TaskType" in names and "TaskOccurrence" in names:
        pass
    if any(component.name == "Handoff" for component in candidate.representation.components):
        invariant_valid = False
        reasons.append("handoff is not an allowed component")

    compatibility_valid = invariant_valid and baseline_regression_passed
    if not baseline_regression_passed:
        reasons.append("current one-occurrence baseline regression failed")
    return ValidationResult(
        candidate.candidate_id,
        schema_valid,
        invariant_valid,
        compatibility_valid,
        tuple(reasons),
    )
