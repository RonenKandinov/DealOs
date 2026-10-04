"""Structured records for one evolution cycle.

These name representation components. They are not copies of Task, TaskOccurrence,
or AllocationAction, and they do not run the simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Component:
    """One named piece of a representation. TaskType is not TaskOccurrence."""

    name: str
    role: str


@dataclass(frozen=True)
class Representation:
    representation_id: str
    components: tuple[Component, ...]

    def names(self) -> frozenset[str]:
        return frozenset(component.name for component in self.components)

    def with_component(self, component: Component, candidate_id: str) -> Representation:
        return Representation(
            representation_id=candidate_id,
            components=self.components + (component,),
        )


@dataclass(frozen=True)
class Mismatch:
    mismatch_id: str
    category: str
    status: str
    evidence_reference: str
    current_gap: str
    description: str
    candidate_required: bool = True
    prevalence: str | None = None


@dataclass(frozen=True)
class Mutation:
    operator: str
    target: str
    adds: Component


@dataclass(frozen=True)
class MutationProposal:
    operator: str
    target: str
    source_mismatches: tuple[str, ...]
    rationale: str
    mutation: Mutation


@dataclass(frozen=True)
class CandidateRepresentation:
    parent_representation_id: str
    candidate_id: str
    mutations: tuple[Mutation, ...]
    representation: Representation

    @property
    def representation_changes(self) -> tuple[str, ...]:
        return tuple(mutation.adds.name for mutation in self.mutations)


@dataclass(frozen=True)
class ValidationResult:
    candidate_id: str
    schema_valid: bool
    invariant_valid: bool
    compatibility_valid: bool
    reasons: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.schema_valid and self.invariant_valid and self.compatibility_valid


@dataclass(frozen=True)
class EvaluationResult:
    candidate_id: str
    mismatches_resolved: tuple[str, ...]
    mismatches_partially_resolved: tuple[str, ...]
    mismatches_unresolved: tuple[str, ...]
    regression_passed: bool
    complexity_delta: int


@dataclass(frozen=True)
class EvolutionHistory:
    parent: Representation
    mismatches: tuple[Mismatch, ...]
    proposals: tuple[MutationProposal, ...]
    candidates: tuple[CandidateRepresentation, ...]
    validation: tuple[ValidationResult, ...]
    evaluation: tuple[EvaluationResult, ...]
    selected_candidate_id: str | None


@dataclass(frozen=True)
class EvolutionResult:
    history: EvolutionHistory
    selected: CandidateRepresentation | None
    explanation: str
    generations: int = 1
    baseline_regression_passed: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)
