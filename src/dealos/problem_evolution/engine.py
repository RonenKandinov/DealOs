"""One evolution cycle. run() does not call itself."""

from __future__ import annotations

from dealos.experiments.runner import rollout
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.fifo import FIFOPolicy
from dealos.problem_evolution.evaluator import evaluate_candidate
from dealos.problem_evolution.generator import generate_candidates
from dealos.problem_evolution.models import (
    EvolutionHistory,
    EvolutionResult,
    Mismatch,
    Representation,
)
from dealos.problem_evolution.proposer import MutationProposer, RuleBasedMutationProposer
from dealos.problem_evolution.selector import select_candidate
from dealos.problem_evolution.validator import validate_candidate

V1_COMPONENTS = (
    ("TaskType", "type_graph"),
    ("DAG", "type_graph"),
    ("Progress", "progress"),
    ("Capacity", "constraint"),
)


def v1_representation() -> Representation:
    from dealos.problem_evolution.models import Component

    return Representation(
        "R0",
        tuple(Component(name, role) for name, role in V1_COMPONENTS),
    )


def baseline_one_occurrence_matches_v1() -> bool:
    """The live simulator still finishes the frozen seed-0 FIFO case."""

    scenario = generate_scenario(get_preset("balanced"), seed=0)
    result = rollout(scenario, FIFOPolicy())
    return result.completed_deals == 2 and result.steps == 40


class ProblemEvolutionEngine:
    def __init__(self, proposer: MutationProposer | None = None) -> None:
        self.proposer = proposer or RuleBasedMutationProposer()

    def run(
        self,
        representation: Representation,
        mismatches: tuple[Mismatch, ...],
        history: tuple[object, ...] = (),
    ) -> EvolutionResult:
        proposals = tuple(self.proposer.propose(representation, mismatches, history))
        candidates = generate_candidates(representation, list(proposals))
        baseline_ok = baseline_one_occurrence_matches_v1()
        validation = [
            validate_candidate(representation, candidate, baseline_regression_passed=baseline_ok)
            for candidate in candidates
        ]
        evaluation = [
            evaluate_candidate(
                candidate,
                mismatches,
                regression_passed=check.compatibility_valid,
            )
            for candidate, check in zip(candidates, validation)
        ]
        selected, explanation = select_candidate(candidates, validation, evaluation)
        record = EvolutionHistory(
            parent=representation,
            mismatches=mismatches,
            proposals=proposals,
            candidates=tuple(candidates),
            validation=tuple(validation),
            evaluation=tuple(evaluation),
            selected_candidate_id=None if selected is None else selected.candidate_id,
        )
        return EvolutionResult(
            history=record,
            selected=selected,
            explanation=explanation,
            generations=1,
            baseline_regression_passed=baseline_ok,
        )
