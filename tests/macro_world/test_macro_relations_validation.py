"""Accepted mutations match ground truth, and refused mutations stay out of the graph."""

from pathlib import Path

from dealos.macro_world.relations.experiments.run_macro_relations import VALIDATED, execute
from dealos.macro_world.relations.graph import disposition
from dealos.macro_world.relations.models import (
    MACRO_R0,
    RELATION_SPECS,
    HYPOTHESIS,
    MacroEvent,
    MacroRelation,
    MacroWorld,
    RelationMask,
    RelationMutation,
    RelationScenario,
    RelationSpec,
    macro_r0,
)
from dealos.macro_world.relations.scenarios import scenario_mr_a, scenario_mr_d0, scenario_mr_j_department
from dealos.macro_world.relations.validate import RelationEvaluation, assess, candidate_representation


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


def test_the_relation_run_keeps_epistemic_fields_apart() -> None:
    assessed, line = execute(0)
    assert line == VALIDATED
    by_scenario = {scenario.scenario_id: evaluation for scenario, evaluation, _failures in assessed}
    assert disposition(by_scenario["MR-A"]) == "hidden"
    assert by_scenario["MR-A"].ground_truth_present is True
    assert by_scenario["MR-A"].recoverable is False
    assert by_scenario["MR-A"].ambiguity is False
    assert by_scenario["MR-A"].representable_after is True
    assert by_scenario["MR-A"].epistemic_status == "FACT"
    assert disposition(by_scenario["MR-D1"]) == "ambiguous"
    assert by_scenario["MR-D1"].ground_truth_present is True
    assert by_scenario["MR-D1"].mutation_accepted is False
    assert disposition(by_scenario["MR-D0"]) == "rejected"
    assert disposition(by_scenario["MR-E"]) == "ambiguous"
    assert disposition(by_scenario["MR-I"]) == "rejected"
    assert disposition(by_scenario["MR-J1"]) == "ambiguous"
    assert disposition(by_scenario["MR-J3"]) == "rejected"
    hidden = {evaluation.relation_name for scenario, evaluation, _failures in assessed if disposition(evaluation) == "hidden"}
    assert hidden == {
        "resource_role",
        "role_department",
        "department_organization",
        "system_produces_information",
        "information_consumed_by_system",
    }
    assert all(not failures for _scenario, _evaluation, failures in assessed)


def test_recoverable_and_inference_stay_distinct_from_hidden_and_rejected() -> None:
    base = _evaluation()
    assert disposition(base) == "hidden"
    assert disposition(_evaluation(recoverable=True)) == "recoverable"
    assert disposition(_evaluation(epistemic_status="INFERENCE", ambiguity=True, mutation_accepted=False)) == "inference"
    assert disposition(_evaluation(ground_truth_present=False, epistemic_status="HYPOTHESIS", mutation_accepted=False)) == "rejected"


def _evaluation(**overrides) -> RelationEvaluation:
    values = dict(
        scenario_id="sample",
        relation_name="resource_role",
        source_entity="Resource",
        target_entity="Role",
        ground_truth_present=True,
        observation_evidence_present=False,
        representable_before=False,
        representable_after=True,
        recoverable=False,
        epistemic_status="FACT",
        ambiguity=False,
        mutation_required=True,
        mutation_accepted=True,
        regression=False,
        complexity_delta=2,
        epistemic_violations=0,
        observation_faithfulness=1.0,
    )
    values.update(overrides)
    return RelationEvaluation(**values)


def test_a_new_spec_runs_through_the_generic_engine(tmp_path=None) -> None:
    root = Path(__file__).resolve().parents[2]
    engine = (root / "src" / "dealos" / "macro_world" / "relations" / "validate.py").read_text(encoding="utf-8")
    queries = (root / "src" / "dealos" / "macro_world" / "relations" / "queries.py").read_text(encoding="utf-8")
    assert "relation_name ==" not in engine and "relation_name in" not in engine
    assert "relation_name ==" not in queries and "relation_name in" not in queries
    spec = RelationSpec(
        "sample_link",
        "SampleSource",
        "SampleTarget",
        frozenset({"SampleObject"}),
        lambda observations, _mask: any(row.get("resource_id") == "S1" for row in observations),
        lambda _observations, _mask: False,
    )
    assert "sample_link" not in RELATION_SPECS
    scenario = RelationScenario(
        "SAMPLE",
        "Sample",
        "A test-only relation.",
        "sample_link",
        MacroWorld(
            relations=(MacroRelation("s1", "sample_link", "S1", "T1", "linked"),),
            events=(MacroEvent("e0001", 1, resource_id="S1"),),
        ),
        RelationMask(),
        (RelationMutation("AddObject", "SampleObject"),),
        False,
        True,
        False,
        True,
        False,
        HYPOTHESIS,
        True,
        True,
        False,
    )
    evaluation, failures = assess(scenario, specs={**RELATION_SPECS, "sample_link": spec})
    assert failures == ()
    assert evaluation.source_entity == "SampleSource"
    assert evaluation.target_entity == "SampleTarget"
    assert evaluation.observation_evidence_present is True
    assert evaluation.ambiguity is True
    assert evaluation.recoverable is False
    assert evaluation.mutation_accepted is False
    assert evaluation.epistemic_status == HYPOTHESIS
