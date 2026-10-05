"""Accepted mutations match ground truth, and refused mutations stay out of the graph."""

from dealos.macro_world.relations.experiments.run_macro_relations import VALIDATED, execute
from dealos.macro_world.relations.models import MACRO_R0, macro_r0
from dealos.macro_world.relations.scenarios import scenario_mr_a, scenario_mr_d0, scenario_mr_j_department
from dealos.macro_world.relations.validate import assess, candidate_representation


def test_the_parent_representation_survives_a_candidate() -> None:
    scenario = scenario_mr_a()
    parent = macro_r0()
    candidate = candidate_representation(scenario)
    assert parent.primitives == MACRO_R0
    assert parent.primitives < candidate.primitives
    evaluation, failures = assess(scenario)
    assert failures == ()
    assert evaluation.mutation_accepted is True
    assert evaluation.recoverable is False


def test_negative_cases_are_refused() -> None:
    for scenario in (scenario_mr_d0(), scenario_mr_j_department()):
        evaluation, failures = assess(scenario)
        assert failures == ()
        assert evaluation.mutation_accepted is False
        assert evaluation.ground_truth_present is False


def test_the_relation_run_validates_and_commits_only_structural_edges() -> None:
    assessed, edges, line = execute(0)
    assert line == VALIDATED
    assert {edge.relation_name for edge in edges} == {
        "resource_role",
        "role_department",
        "department_organization",
        "system_produces_information",
        "information_consumed_by_system",
    }
    assert all(not failures for _scenario, _evaluation, failures in assessed)
