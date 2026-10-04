"""Structured evaluation. There is no single score."""

from __future__ import annotations

from dealos.problem_evolution.models import CandidateRepresentation, EvaluationResult, Mismatch

_EFFECT = {
    "AddOccurrence": {"M1": "RESOLVED"},
    "AddLifecycle": {"M5": "PARTIALLY_RESOLVED"},
    "AddObject": {"M2": "RESOLVED"},
}


def evaluate_candidate(
    candidate: CandidateRepresentation,
    mismatches: tuple[Mismatch, ...],
    *,
    regression_passed: bool,
) -> EvaluationResult:
    effects: dict[str, str] = {}
    for mutation in candidate.mutations:
        effects.update(_EFFECT.get(mutation.operator, {}))
    resolved: list[str] = []
    partial: list[str] = []
    unresolved: list[str] = []
    for mismatch in mismatches:
        mark = effects.get(mismatch.mismatch_id, "UNRESOLVED")
        if mismatch.status == "HYPOTHESIS":
            mark = "UNRESOLVED"
        if mark == "RESOLVED":
            resolved.append(mismatch.mismatch_id)
        elif mark == "PARTIALLY_RESOLVED":
            partial.append(mismatch.mismatch_id)
        else:
            unresolved.append(mismatch.mismatch_id)
    return EvaluationResult(
        candidate_id=candidate.candidate_id,
        mismatches_resolved=tuple(resolved),
        mismatches_partially_resolved=tuple(partial),
        mismatches_unresolved=tuple(unresolved),
        regression_passed=regression_passed,
        complexity_delta=len(candidate.mutations),
    )
