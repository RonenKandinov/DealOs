"""Macro relations (Phase 2): relation records, scenario worlds, masks, queries,
ambiguity, validation, and the regression against Phase 1 and the frozen micro model.

Merged from test_macro_relations_models, _scenarios, _masks, _queries, _ambiguity,
_validation, and _regression. Every test body is unchanged apart from two import
aliases: both experiment runners export ``VALIDATED`` and ``execute``, so the Phase 1
runner is imported as ``PHASE1_VALIDATED`` / ``execute_phase1`` and the relations runner
as ``RELATIONS_VALIDATED`` / ``execute_relations``.
"""

from dataclasses import fields
from pathlib import Path

from dealos.domain.models import Task, TaskOccurrence
from dealos.macro_world.experiments.run_macro_world import VALIDATED as PHASE1_VALIDATED
from dealos.macro_world.experiments.run_macro_world import execute as execute_phase1
from dealos.macro_world.relations.experiments.run_macro_relations import VALIDATED as RELATIONS_VALIDATED
from dealos.macro_world.relations.experiments.run_macro_relations import execute as execute_relations
from dealos.macro_world.relations.graph import disposition
from dealos.macro_world.relations.models import (
    BRIDGE,
    MACRO_R0,
    RELATION_ENDS,
    RELATION_SPECS,
    HYPOTHESIS,
    VOCABULARY,
    MacroEvent,
    MacroRelation,
    MacroWorld,
    RelationMask,
    RelationMutation,
    RelationScenario,
    RelationSpec,
    macro_r0,
    relation_spec,
)
from dealos.macro_world.relations.observe import leak_count, observe
from dealos.macro_world.relations.queries import activity_is_not_a_role, recoverable, representable
from dealos.macro_world.relations.scenarios import (
    all_relation_scenarios,
    scenario_mr_a,
    scenario_mr_c,
    scenario_mr_d0,
    scenario_mr_d1,
    scenario_mr_d2,
    scenario_mr_d3,
    scenario_mr_e,
    scenario_mr_f,
    scenario_mr_i,
    scenario_mr_j_department,
)
from dealos.macro_world.relations.validate import (
    RelationEvaluation,
    assess,
    candidate_representation,
    integrity_errors,
    mutation_errors,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "dealos" / "macro_world" / "relations"
FORBIDDEN = (
    "dealos.sim",
    "dealos.policies",
    "dealos.generator",
    "dealos.domain",
    "dealos.org",
    "dealos.analysis",
    "dealos.problem_evolution",
)


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


# ---- Relation records ----


def test_the_baseline_is_only_the_phase1_resource_identity_pair() -> None:
    assert macro_r0().primitives == MACRO_R0
    assert "Role" not in macro_r0().primitives
    assert "ResourceRoleAssociation" in VOCABULARY


def test_resource_role_spec_names_its_endpoints() -> None:
    spec = relation_spec("resource_role")
    assert spec.source_entity == "Resource"
    assert spec.target_entity == "Role"
    assert spec.evidence_rule((), RelationMask()) is False


def test_relation_endpoints_are_macro_entities() -> None:
    for source, target in RELATION_ENDS.values():
        assert source not in BRIDGE
        assert target not in BRIDGE
        assert "Task" not in source and "Task" not in target
        assert "Deal" not in source and "Deal" not in target


def test_a_micro_bridge_target_is_rejected() -> None:
    assert mutation_errors(RelationMutation("AddRelation", "TaskOccurrence"))
    assert mutation_errors(RelationMutation("AddRelation", "Deal"))
    assert mutation_errors(RelationMutation("RewriteCode", "Role"))
    assert mutation_errors(RelationMutation("AddRelation", "reports_to"))
    assert mutation_errors(RelationMutation("AddRelation", "ResourceRoleAssociation")) == ()


# ---- Scenario worlds ----


def test_every_scenario_rebuilds_and_has_intact_relations() -> None:
    first = all_relation_scenarios()
    second = all_relation_scenarios()
    assert [scenario.scenario_id for scenario in first] == [scenario.scenario_id for scenario in second]
    assert len(first) == 15
    for left, right in zip(first, second, strict=True):
        assert left.world == right.world
        assert integrity_errors(left) == ()


def test_the_three_resource_pair_runs_expose_the_same_events() -> None:
    runs = (scenario_mr_d1(), scenario_mr_d2(), scenario_mr_d3())
    observations = [observe(scenario.world, scenario.mask, 5) for scenario in runs]
    assert observations[0] == observations[1] == observations[2]
    semantics = {scenario.world.relations[0].semantic for scenario in runs}
    assert semantics == {"collaborates_with", "substitutes_for", "depends_on"}


def test_the_same_seed_repeats_and_a_new_seed_changes_the_timestamp() -> None:
    scenario = scenario_mr_a()
    assert observe(scenario.world, scenario.mask, 1) == observe(scenario.world, scenario.mask, 1)
    assert observe(scenario.world, scenario.mask, 1)[0].get("timestamp") != observe(scenario.world, scenario.mask, 2)[0].get("timestamp")


# ---- Masks ----


def test_a_hidden_role_is_absent_and_an_exposed_role_matches() -> None:
    scenario = scenario_mr_a()
    hidden = observe(scenario.world, scenario.mask, 0)
    assert all(row.get("role_id") is None for row in hidden)
    assert {row.get("resource_id") for row in hidden} == {"R17", "R22"}
    assert {row.get("activity") for row in hidden} == {"PacketCheck", "ScanCheck"}
    shown = observe(scenario.world, RelationMask(expose_role=True), 0)
    assert {row.get("role_id") for row in shown} == {"role_legal", "role_security"}
    assert leak_count(scenario.world, hidden, scenario.mask) == 0
    assert leak_count(scenario.world, shown, RelationMask(expose_role=True)) == 0


def test_department_can_be_shown_while_the_organization_stays_hidden() -> None:
    scenario = scenario_mr_c()
    rows = observe(scenario.world, scenario.mask, 0)
    assert {row.get("department_id") for row in rows} == {"dept_legal", "dept_security"}
    assert all(row.get("organization_id") is None for row in rows)


def test_authority_holder_fields_stay_hidden_on_the_approve_events() -> None:
    scenario = scenario_mr_e()
    rows = observe(scenario.world, scenario.mask, 0)
    assert {row.get("activity") for row in rows} == {"ApproveDeal"}
    assert all(row.get("authority_holder") is None and row.get("holder_kind") is None for row in rows)
    assert "LegalReviewer" not in {value for row in rows for _name, value in row.values}


# ---- Queries: representable versus recoverable ----


def test_resource_role_is_missing_from_r0_and_hidden_from_the_events() -> None:
    scenario = scenario_mr_a()
    observations = observe(scenario.world, scenario.mask, 0)
    assert representable(macro_r0(), "resource_role") is False
    assert representable(candidate_representation(scenario), "resource_role") is True
    assert recoverable(observations, scenario.mask, "resource_role") is False
    assert activity_is_not_a_role(observations) is True


def test_event_order_and_an_approve_activity_do_not_recover_a_typed_relation() -> None:
    authority = scenario_mr_e()
    authority_events = observe(authority.world, authority.mask, 0)
    assert recoverable(authority_events, authority.mask, "role_authority") is False
    succession = scenario_mr_i()
    succession_events = observe(succession.world, succession.mask, 0)
    assert recoverable(succession_events, succession.mask, "system_system") is False
    assert [row.get("system_id") for row in succession_events] == ["sys_crm", "sys_risk", "sys_approval"]


# ---- Ambiguity ----


def test_resource_pair_types_stay_unresolved() -> None:
    runs = (scenario_mr_d1(), scenario_mr_d2(), scenario_mr_d3())
    assert observe(runs[0].world, runs[0].mask, 0) == observe(runs[1].world, runs[1].mask, 0)
    for scenario in runs:
        evaluation, failures = assess(scenario)
        assert failures == ()
        assert evaluation.ambiguity is True
        assert evaluation.mutation_accepted is False
        assert evaluation.epistemic_status == "HYPOTHESIS"
        assert evaluation.ground_truth_present is True


def test_authority_holder_kind_and_system_order_stay_unresolved() -> None:
    role_authority = scenario_mr_e()
    resource_authority = scenario_mr_f()
    assert observe(role_authority.world, role_authority.mask, 0) == observe(resource_authority.world, resource_authority.mask, 0)
    for scenario in (role_authority, resource_authority, scenario_mr_i()):
        evaluation, failures = assess(scenario)
        assert failures == ()
        assert evaluation.mutation_accepted is False
        assert evaluation.ambiguity is True


# ---- Validation ----


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
    assessed, line = execute_relations(0)
    assert line == RELATIONS_VALIDATED
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


# ---- Regression against Phase 1 and the frozen micro model ----


def test_phase1_still_validates() -> None:
    _results, line = execute_phase1(0)
    assert line == PHASE1_VALIDATED


def test_live_micro_fields_stay_unchanged() -> None:
    assert tuple(field.name for field in fields(Task)) == ("task_id", "deal_id", "task_type", "name")
    assert tuple(field.name for field in fields(TaskOccurrence)) == (
        "occurrence_id",
        "deal_id",
        "task_id",
        "lifecycle",
        "progress",
        "offer_id",
        "readiness_source",
    )


def test_the_relation_package_does_not_import_the_frozen_core_and_the_graph_stays_macro() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.py"))
    for name in FORBIDDEN:
        assert name not in text
    _assessed, line = execute_relations(0)
    assert line == "FIVE HIDDEN FACTS RECOVERABLE WHEN THEIR OWN FIELDS ARE EXPOSED"
    for _scenario, evaluation, failures in _assessed:
        if failures:
            continue
        for name in (evaluation.source_entity, evaluation.target_entity):
            assert "Task" not in name
            assert "Deal" not in name
