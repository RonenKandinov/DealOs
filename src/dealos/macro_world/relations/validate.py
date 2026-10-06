"""Generic checks for one macro relation. Relation-specific rules live on RelationSpec."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from dealos.macro_world.models import Representation
from dealos.macro_world.relations.models import (
    BRIDGE,
    HYPOTHESIS,
    OPERATORS,
    VOCABULARY,
    MacroRelation,
    RelationMutation,
    RelationScenario,
    RelationSpec,
    macro_r0,
    relation_spec,
)
from dealos.macro_world.relations.observe import leak_count, observe
from dealos.macro_world.relations.queries import (
    activity_is_not_a_role,
    evidence_present,
    gt_has,
    interpretable,
    recoverable,
    representable,
)


@dataclass(frozen=True)
class RelationEvaluation:
    scenario_id: str
    relation_name: str
    source_entity: str
    target_entity: str
    ground_truth_present: bool
    observation_evidence_present: bool
    representable_before: bool
    representable_after: bool
    recoverable: bool
    epistemic_status: str
    ambiguity: bool
    mutation_required: bool
    mutation_accepted: bool
    regression: bool
    complexity_delta: int
    epistemic_violations: int
    observation_faithfulness: float


def mutation_errors(mutation: RelationMutation, allowed: frozenset[str] | None = None) -> tuple[str, ...]:
    targets = VOCABULARY if allowed is None else allowed
    reasons: list[str] = []
    if mutation.operator not in OPERATORS:
        reasons.append(f"unknown operator {mutation.operator}")
    if mutation.target not in targets or mutation.target in BRIDGE:
        reasons.append(f"rejected target {mutation.target}")
    return tuple(reasons)


def candidate_representation(scenario: RelationScenario) -> Representation:
    parent = macro_r0()
    if not scenario.mutations:
        return parent
    names = tuple(mutation.target for mutation in scenario.mutations)
    return parent.with_primitives(names, f"R1-{scenario.scenario_id}")


def commits(representable_after: bool, ground_truth: bool, negative: bool, ambiguous: bool, schema_ok: bool) -> bool:
    """Accept a representation extension. Recovery and epistemic status are separate."""

    if negative or ambiguous or not ground_truth or not schema_ok:
        return False
    return representable_after


def integrity_errors(scenario: RelationScenario, specs: Mapping[str, RelationSpec] | None = None) -> tuple[str, ...]:
    errors: list[str] = []
    for relation in scenario.world.relations:
        try:
            spec = relation_spec(relation.name, specs)
        except KeyError:
            errors.append(f"unknown relation {relation.name}")
            continue
        if spec.source_entity in BRIDGE or spec.target_entity in BRIDGE:
            errors.append(f"{relation.name} crosses into the micro graph")
        if not relation.source_id or not relation.target_id:
            errors.append(f"{relation.relation_id} has an empty endpoint")
    return tuple(errors)


def assess(
    scenario: RelationScenario,
    seed: int = 0,
    specs: Mapping[str, RelationSpec] | None = None,
) -> tuple[RelationEvaluation, tuple[str, ...]]:
    spec = relation_spec(scenario.relation_name, specs)
    parent = macro_r0()
    observations = observe(scenario.world, scenario.mask, seed)
    repeat = observe(scenario.world, scenario.mask, seed)
    candidate = candidate_representation(scenario)
    before = representable(parent, scenario.relation_name, specs)
    after = representable(candidate, scenario.relation_name, specs)
    evidence = evidence_present(observations, scenario.mask, scenario.relation_name, specs)
    interpreted = interpretable(observations, scenario.mask, scenario.relation_name, specs)
    recovered = recoverable(observations, scenario.mask, scenario.relation_name, specs)
    ambiguous = not interpreted
    allowed = _allowed_targets(specs)
    schema_ok = all(not mutation_errors(mutation, allowed) for mutation in scenario.mutations)
    accepted = commits(after, gt_has(scenario.world, scenario.relation_name), scenario.negative, ambiguous, schema_ok)
    leaks = leak_count(scenario.world, observations, scenario.mask)
    violations = _violations(scenario, observations, accepted)
    regression = not parent.primitives <= candidate.primitives
    evaluation = RelationEvaluation(
        scenario.scenario_id,
        scenario.relation_name,
        spec.source_entity,
        spec.target_entity,
        gt_has(scenario.world, scenario.relation_name),
        evidence,
        before,
        after,
        recovered,
        scenario.epistemic_status,
        ambiguous,
        bool(scenario.mutations),
        accepted,
        regression,
        len(candidate.primitives) - len(parent.primitives),
        violations,
        1.0 if leaks == 0 else 0.0,
    )
    failures = _failures(scenario, parent, observations, repeat, evaluation, leaks, specs)
    return evaluation, failures


def _failures(
    scenario: RelationScenario,
    parent: Representation,
    observations,
    repeat,
    evaluation: RelationEvaluation,
    leaks: int,
    specs: Mapping[str, RelationSpec] | None,
) -> tuple[str, ...]:
    failures: list[str] = []
    integrity = integrity_errors(scenario, specs)
    if integrity:
        failures.append("integrity: " + "; ".join(integrity))
    allowed = _allowed_targets(specs)
    for mutation in scenario.mutations:
        reasons = mutation_errors(mutation, allowed)
        if reasons:
            failures.append("schema: " + "; ".join(reasons))
    if parent.primitives != macro_r0().primitives:
        failures.append("parent representation changed")
    if evaluation.representable_before != scenario.expect_representable_before:
        failures.append("representable before disagrees")
    if evaluation.representable_after != scenario.expect_representable_after:
        failures.append("representable after disagrees")
    if evaluation.recoverable != scenario.expect_recoverable:
        failures.append("recoverable disagrees")
    if evaluation.ambiguity != scenario.expect_ambiguity:
        failures.append("ambiguity disagrees")
    if evaluation.mutation_accepted != scenario.expect_mutation_accepted:
        failures.append("mutation acceptance disagrees")
    if evaluation.ground_truth_present != scenario.ground_truth_present:
        failures.append("ground truth presence disagrees")
    if evaluation.observation_evidence_present != scenario.observation_evidence_present:
        failures.append("observation evidence disagrees")
    if evaluation.epistemic_status != scenario.epistemic_status:
        failures.append("epistemic status disagrees")
    if evaluation.mutation_accepted and evaluation.epistemic_status == HYPOTHESIS:
        failures.append("a hypothesis was accepted as an established relation")
    if scenario.negative and evaluation.mutation_accepted:
        failures.append("a negative case was accepted")
    if evaluation.ambiguity and evaluation.mutation_accepted:
        failures.append("an ambiguous relation was accepted")
    if observations != repeat:
        failures.append("seed did not repeat")
    if leaks:
        failures.append(f"mask leaked {leaks} values")
    if evaluation.epistemic_violations:
        failures.append("epistemic violation")
    if evaluation.regression:
        failures.append("regression")
    if evaluation.observation_faithfulness != 1.0:
        failures.append("observation faithfulness is below 1")
    return tuple(failures)


def _violations(scenario: RelationScenario, observations, accepted: bool) -> int:
    count = 0
    if not activity_is_not_a_role(observations):
        count += 1
    for observation in observations:
        if observation.get("role_id") and not scenario.mask.expose_role:
            count += 1
        if observation.get("department_id") and not scenario.mask.expose_department:
            count += 1
        if observation.get("organization_id") and not scenario.mask.expose_organization:
            count += 1
        if observation.get("holder_kind") and not scenario.mask.expose_holder_kind:
            count += 1
        if observation.get("relation_type") and not scenario.mask.expose_relation_type:
            count += 1
        if observation.get("authority_holder") and not scenario.mask.expose_authority:
            count += 1
    if scenario.epistemic_status == HYPOTHESIS and accepted:
        count += 1
    return count


def _allowed_targets(specs: Mapping[str, RelationSpec] | None) -> frozenset[str]:
    if specs is None:
        return VOCABULARY
    return frozenset(primitive for spec in specs.values() for primitive in spec.primitives)


def relation_rows(scenario: RelationScenario) -> tuple[MacroRelation, ...]:
    return tuple(relation for relation in scenario.world.relations if relation.name == scenario.relation_name)
