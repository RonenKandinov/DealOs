"""Mutations are structural, and the scenario run matches its own checks."""

from dealos.macro_world.experiments.run_macro_world import VALIDATED, execute
from dealos.macro_world.models import Mutation
from dealos.macro_world.scenarios import scenario_b, scenario_g
from dealos.macro_world.validator import candidate_representation, mutation_errors, scenario_accepts, validate_scenario


def test_invalid_mutations_are_rejected_and_valid_ones_repeat() -> None:
    assert mutation_errors(Mutation("RewriteCode", "Role"))
    assert mutation_errors(Mutation("AddObject", "person"))
    assert mutation_errors(Mutation("AddObject", "ownership"))
    assert mutation_errors(Mutation("AddState", "Role")) == ()
    assert mutation_errors(Mutation("AddAttribute", "Authority")) == ()
    scenario = scenario_b()
    assert candidate_representation(scenario) == candidate_representation(scenario)
    parent = scenario.initial
    candidate = candidate_representation(scenario)
    assert parent.primitives <= candidate.primitives
    assert parent.primitives == scenario.initial.primitives
    assert validate_scenario(scenario).accepted is True


def test_an_ambiguous_scenario_does_not_accept_a_role_mutation() -> None:
    scenario = scenario_g()
    assert scenario_accepts(scenario, (Mutation("AddObject", "Role"),)) is False
    assert scenario_accepts(scenario, ()) is True
    assert validate_scenario(scenario).accepted is True


def test_role_vector_and_full_run() -> None:
    results, line = execute(0)
    assert line == VALIDATED
    role = next(result for result in results if result.scenario.scenario_id == "B")
    before = dict(role.vector.capabilities_before)
    after = dict(role.vector.capabilities_after)
    assert before["role"] is False
    assert after["role"] is True
    assert role.vector.ground_truth_coverage == 1.0
    assert role.vector.epistemic_violations == 0
    assert role.vector.regression is False
    assert role.vector.complexity_delta == 2
    assert role.recoverable is False
    assert role.vector.mismatches_resolved == ("M002",)
    ambiguous = next(result for result in results if result.scenario.scenario_id == "G")
    assert ambiguous.vector.mismatches_unresolved == ("M007",)
    assert ambiguous.vector.epistemic_violations == 0
