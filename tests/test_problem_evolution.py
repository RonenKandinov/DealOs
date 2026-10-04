"""One evolution cycle over representation candidates. The simulator is not edited."""

from pathlib import Path

from dealos.problem_evolution.engine import ProblemEvolutionEngine, v1_representation
from dealos.problem_evolution.evaluator import evaluate_candidate
from dealos.problem_evolution.generator import generate_candidates
from dealos.problem_evolution.mismatch import bpi17_mismatches
from dealos.problem_evolution.models import CandidateRepresentation, Component, Mismatch, Representation
from dealos.problem_evolution.mutations import Mutation, add_occurrence
from dealos.problem_evolution.proposer import RuleBasedMutationProposer
from dealos.problem_evolution.validator import validate_candidate

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "dealos" / "problem_evolution"


def test_m1_proposes_add_occurrence_and_m5_proposes_add_lifecycle() -> None:
    proposals = RuleBasedMutationProposer().propose(v1_representation(), bpi17_mismatches())
    by_source = {proposal.source_mismatches: proposal.operator for proposal in proposals}
    assert by_source[("M1",)] == "AddOccurrence"
    assert by_source[("M5",)] == "AddLifecycle"
    assert by_source[("M2",)] == "AddObject"


def test_hypothesis_does_not_become_a_fact_or_a_handoff() -> None:
    only_gap = (
        Mismatch(
            "M4",
            "resource_change",
            "HYPOTHESIS",
            "resource ids change",
            "no handoff reading",
            "identifier change only",
            candidate_required=False,
        ),
    )
    proposals = RuleBasedMutationProposer().propose(v1_representation(), only_gap)
    assert proposals == []
    text = (PACKAGE / "mutations.py").read_text(encoding="utf-8")
    assert "AddHandoff" not in text


def test_candidates_do_not_mutate_the_parent() -> None:
    parent = v1_representation()
    before = parent.components
    proposals = RuleBasedMutationProposer().propose(parent, bpi17_mismatches())
    candidates = generate_candidates(parent, proposals)
    assert parent.components == before
    assert parent.representation_id == "R0"
    assert "TaskOccurrence" not in parent.names()
    occurrence = next(item for item in candidates if item.mutations[0].operator == "AddOccurrence")
    assert "TaskOccurrence" in occurrence.representation.names()
    assert "TaskType" in occurrence.representation.names()


def test_invalid_candidate_and_regression_failure_are_rejected() -> None:
    parent = v1_representation()
    broken = CandidateRepresentation(
        "R0",
        "Rbad",
        (Mutation("AddHandoff", "handoff", Component("Handoff", "handoff")),),
        Representation("Rbad", parent.components + (Component("Handoff", "handoff"),)),
    )
    invalid = validate_candidate(parent, broken, baseline_regression_passed=True)
    assert not invalid.accepted
    good = CandidateRepresentation(
        "R0",
        "R1",
        (add_occurrence(),),
        parent.with_component(add_occurrence().adds, "R1"),
    )
    failed = validate_candidate(parent, good, baseline_regression_passed=False)
    assert not failed.compatibility_valid
    assert not failed.accepted


def test_one_run_is_one_generation_and_history_is_complete() -> None:
    source = (PACKAGE / "engine.py").read_text(encoding="utf-8")
    assert "while True" not in source
    assert "self.run(" not in source
    engine = ProblemEvolutionEngine()
    result = engine.run(v1_representation(), bpi17_mismatches())
    assert result.generations == 1
    assert result.baseline_regression_passed
    history = result.history
    assert history.parent.representation_id == "R0"
    assert len(history.mismatches) == 4
    assert len(history.proposals) == 3
    assert len(history.candidates) == 3
    assert len(history.validation) == 3
    assert len(history.evaluation) == 3
    assert result.selected is not None
    assert result.selected.candidate_id == history.selected_candidate_id
    assert "TaskOccurrence" in result.selected.representation.names()
    add = next(item for item in history.evaluation if item.candidate_id == result.selected.candidate_id)
    assert "M1" in add.mismatches_resolved
    assert "M4" in add.mismatches_unresolved
    lifecycle = next(
        item
        for item, candidate in zip(history.evaluation, history.candidates)
        if candidate.mutations[0].operator == "AddLifecycle"
    )
    assert lifecycle.mismatches_partially_resolved == ("M5",)
    second = engine.run(v1_representation(), bpi17_mismatches())
    assert second.generations == 1
    assert second.selected is not None
    assert second.selected.candidate_id == result.selected.candidate_id


def test_add_occurrence_evaluation_does_not_resolve_unrelated_mismatches() -> None:
    parent = v1_representation()
    candidate = CandidateRepresentation(
        "R0",
        "R1",
        (add_occurrence(),),
        parent.with_component(add_occurrence().adds, "R1"),
    )
    scored = evaluate_candidate(candidate, bpi17_mismatches(), regression_passed=True)
    assert scored.mismatches_resolved == ("M1",)
    assert "M5" in scored.mismatches_unresolved
    assert "M4" in scored.mismatches_unresolved
