"""Deterministic selection. Invalid and regressing candidates are dropped first."""

from __future__ import annotations

from dealos.problem_evolution.models import CandidateRepresentation, EvaluationResult, ValidationResult


def select_candidate(
    candidates: list[CandidateRepresentation],
    validation: list[ValidationResult],
    evaluation: list[EvaluationResult],
) -> tuple[CandidateRepresentation | None, str]:
    accepted = {item.candidate_id for item in validation if item.accepted}
    scored = [item for item in evaluation if item.candidate_id in accepted and item.regression_passed]
    if not scored:
        return None, "No candidate passed validation and the one-occurrence regression."
    scored.sort(
        key=lambda item: (
            -len(item.mismatches_resolved),
            -len(item.mismatches_partially_resolved),
            item.complexity_delta,
            item.candidate_id,
        )
    )
    chosen = scored[0]
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    peers = [
        item.candidate_id
        for item in scored
        if len(item.mismatches_resolved) == len(chosen.mismatches_resolved)
        and len(item.mismatches_partially_resolved) == len(chosen.mismatches_partially_resolved)
        and item.complexity_delta == chosen.complexity_delta
    ]
    explanation = (
        f"{chosen.candidate_id} is selected because it resolves {len(chosen.mismatches_resolved)} "
        f"mismatch(es) ({', '.join(chosen.mismatches_resolved) or 'none'}), "
        f"partially resolves {len(chosen.mismatches_partially_resolved)}, "
        f"and adds {chosen.complexity_delta} component(s)."
    )
    if len(peers) > 1:
        explanation += (
            f" {', '.join(peers)} match on those counts. "
            f"{chosen.candidate_id} comes first by candidate id."
        )
    return by_id[chosen.candidate_id], explanation
