"""Structural checks for a candidate. Invalid mutations are rejected and the parent is left as it was."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.ground_truth import integrity_errors
from dealos.macro_world.models import (
    CANDIDATE_PRIMITIVES,
    FORBIDDEN_IMPLICIT,
    HYPOTHESIS,
    OPERATORS,
    Mutation,
    Representation,
)
from dealos.macro_world.queries import representable
from dealos.macro_world.scenarios import Scenario


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    schema_valid: bool
    integrity_valid: bool
    leakage_valid: bool
    regression_valid: bool
    alignment_valid: bool
    reasons: tuple[str, ...]


def mutation_errors(mutation: Mutation) -> tuple[str, ...]:
    reasons: list[str] = []
    if mutation.operator not in OPERATORS:
        reasons.append(f"unknown operator {mutation.operator}")
    if mutation.target not in CANDIDATE_PRIMITIVES or mutation.target in FORBIDDEN_IMPLICIT:
        reasons.append(f"unknown target {mutation.target}")
    return tuple(reasons)


def candidate_representation(scenario: Scenario) -> Representation:
    if not scenario.mutations:
        return scenario.initial
    names = tuple(mutation.target for mutation in scenario.mutations)
    return scenario.initial.with_primitives(names, f"R1-{scenario.scenario_id}")


def scenario_accepts(scenario: Scenario, mutations: tuple[Mutation, ...]) -> bool:
    if scenario.epistemic_status == HYPOTHESIS:
        return len(mutations) == 0
    if not scenario.accept_mutation:
        return len(mutations) == 0
    return mutations == scenario.mutations


def validate_scenario(scenario: Scenario) -> ValidationResult:
    reasons: list[str] = []
    integrity = integrity_errors(scenario.ground_truth)
    reasons.extend(integrity)
    schema_reasons: list[str] = []
    for mutation in scenario.mutations:
        schema_reasons.extend(mutation_errors(mutation))
    reasons.extend(schema_reasons)
    if not scenario_accepts(scenario, scenario.mutations):
        reasons.append("mutation is not accepted for this scenario")
    parent = scenario.initial
    parent_names = parent.primitives
    candidate = candidate_representation(scenario) if not schema_reasons else parent
    added = candidate.primitives - parent_names
    targets = {mutation.target for mutation in scenario.mutations} if not schema_reasons else set()
    leakage_valid = added == targets and not (added & FORBIDDEN_IMPLICIT)
    regression_valid = parent_names <= candidate.primitives
    if not leakage_valid:
        reasons.append("candidate introduces a primitive the mutation did not name")
    if not regression_valid:
        reasons.append("candidate drops an existing primitive")
    alignment_valid = True
    if scenario.accept_mutation and not schema_reasons:
        alignment_valid = representable(candidate, scenario.capability)
        if not alignment_valid:
            reasons.append("candidate cannot express the ground-truth relation")
    return ValidationResult(
        not reasons,
        not schema_reasons,
        not integrity,
        leakage_valid,
        regression_valid,
        alignment_valid,
        tuple(reasons),
    )
