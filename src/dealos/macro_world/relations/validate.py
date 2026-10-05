"""Structural checks for one macro relation. The parent representation is not mutated."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.models import Representation
from dealos.macro_world.relations.models import (
    AMBIGUOUS,
    BRIDGE,
    FACT,
    HYPOTHESIS,
    OPERATORS,
    VOCABULARY,
    MacroRelation,
    RelationMutation,
    RelationScenario,
    macro_r0,
)
from dealos.macro_world.relations.observe import leak_count, observe
from dealos.macro_world.relations.queries import (
    activity_is_not_a_role,
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


def mutation_errors(mutation: RelationMutation) -> tuple[str, ...]:
    reasons: list[str] = []
    if mutation.operator not in OPERATORS:
        reasons.append(f"unknown operator {mutation.operator}")
    if mutation.target not in VOCABULARY or mutation.target in BRIDGE:
        reasons.append(f"rejected target {mutation.target}")
    return tuple(reasons)


def candidate_representation(scenario: RelationScenario) -> Representation:
    parent = macro_r0()
    if not scenario.mutations:
        return parent
    names = tuple(mutation.target for mutation in scenario.mutations)
    return parent.with_primitives(names, f"R1-{scenario.scenario_id}")


def commits(scenario: RelationScenario, representable_after: bool) -> bool:
    if scenario.negative or scenario.relation_name in AMBIGUOUS:
        return False
    if not gt_has(scenario.world, scenario.relation_name):
        return False
    if not interpretable(scenario.mask, scenario.relation_name):
        return False
    return representable_after


def integrity_errors(scenario: RelationScenario) -> tuple[str, ...]:
    from dealos.macro_world.relations.models import RELATION_ENDS

    errors: list[str] = []
    for relation in scenario.world.relations:
        if relation.name not in RELATION_ENDS:
            errors.append(f"unknown relation {relation.name}")
            continue
        source, target = RELATION_ENDS[relation.name]
        if source in BRIDGE or target in BRIDGE:
            errors.append(f"{relation.name} crosses into the micro graph")
        if not relation.source_id or not relation.target_id:
            errors.append(f"{relation.relation_id} has an empty endpoint")
    return tuple(errors)


def assess(scenario: RelationScenario, seed: int = 0) -> tuple[RelationEvaluation, tuple[str, ...]]:
    parent = macro_r0()
    observations = observe(scenario.world, scenario.mask, seed)
    repeat = observe(scenario.world, scenario.mask, seed)
    candidate = candidate_representation(scenario)
    before = representable(parent, scenario.relation_name)
    after = representable(candidate, scenario.relation_name)
    recovered = recoverable(observations, scenario.mask, scenario.relation_name)
    ambiguous = scenario.relation_name in AMBIGUOUS or not interpretable(scenario.mask, scenario.relation_name)
    accepted = commits(scenario, after)
    leaks = leak_count(scenario.world, observations, scenario.mask)
    violations = _violations(scenario, observations, accepted)
    regression = not parent.primitives <= candidate.primitives
    evidence = _evidence(observations, scenario.relation_name)
    source, target = _ends(scenario.relation_name)
    evaluation = RelationEvaluation(
        scenario.scenario_id,
        scenario.relation_name,
        source,
        target,
        gt_has(scenario.world, scenario.relation_name),
        evidence,
        before,
        after,
        recovered,
        scenario.epistemic_status if _status_ok(scenario, accepted) else "MISMATCH",
        ambiguous,
        bool(scenario.mutations),
        accepted,
        regression,
        len(candidate.primitives) - len(parent.primitives),
        violations,
        1.0 if leaks == 0 else 0.0,
    )
    failures = _failures(scenario, parent, observations, repeat, evaluation, leaks)
    return evaluation, failures


def _failures(scenario, parent, observations, repeat, evaluation: RelationEvaluation, leaks: int) -> tuple[str, ...]:
    failures: list[str] = []
    if integrity_errors(scenario):
        failures.append("integrity: " + "; ".join(integrity_errors(scenario)))
    for mutation in scenario.mutations:
        if mutation_errors(mutation):
            failures.append("schema: " + "; ".join(mutation_errors(mutation)))
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
    if evaluation.mutation_accepted and evaluation.epistemic_status != FACT:
        failures.append("an accepted relation is not a ground-truth fact")
    if not evaluation.mutation_accepted and evaluation.epistemic_status == FACT:
        failures.append("a fact was not accepted")
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
    if accepted and scenario.relation_name in AMBIGUOUS:
        count += 1
    if scenario.epistemic_status == HYPOTHESIS and accepted:
        count += 1
    return count


def _status_ok(scenario: RelationScenario, accepted: bool) -> bool:
    if accepted:
        return scenario.epistemic_status == FACT
    return scenario.epistemic_status == HYPOTHESIS


def _evidence(observations, relation_name: str) -> bool:
    if relation_name in {"resource_collaborates", "resource_substitutes", "resource_depends"}:
        return any(row.get("resource_id") and row.get("other_resource_id") for row in observations)
    if relation_name == "system_system":
        systems = {row.get("system_id") for row in observations if row.get("system_id")}
        return len(systems) >= 2
    return False


def _ends(relation_name: str) -> tuple[str, str]:
    from dealos.macro_world.relations.models import RELATION_ENDS

    return RELATION_ENDS[relation_name]


def relation_rows(scenario: RelationScenario) -> tuple[MacroRelation, ...]:
    return tuple(relation for relation in scenario.world.relations if relation.name == scenario.relation_name)
