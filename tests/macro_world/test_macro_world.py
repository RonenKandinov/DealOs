"""Macro world: ground-truth models, scenario builders, masking, observations, queries,
the validator, and the recoverability screen.

Merged from test_models, test_macro_world_generator, test_masking, test_observations,
test_queries, test_validator, and test_macro_recoverability_screen. Every test body is
unchanged; shared imports (observe, leak_count, the scenario builders) are listed once.
"""

from dataclasses import fields
from pathlib import Path

import pytest

from dealos.domain.models import Task, TaskOccurrence
from dealos.macro_world.experiments.run_macro_world import VALIDATED, execute, format_cli, main
from dealos.macro_world.generator import (
    reference_world,
    world_ambiguous,
    world_authority,
    world_resource_identity,
    world_resource_role,
)
from dealos.macro_world.ground_truth import integrity_errors
from dealos.macro_world.models import (
    FORBIDDEN_IMPLICIT,
    R0_EXTRA,
    R_MICRO,
    GroundTruth,
    Mutation,
    ObservationMask,
    Resource,
    micro_representation,
    r0_representation,
)
from dealos.macro_world.observations import leak_count, observe
from dealos.macro_world.queries import authorized_holders, performers_of_activity, recoverable, representable
from dealos.macro_world.relations.recoverability import SCREENED, screen
from dealos.macro_world.relations.scenarios import scenario_mr_d1, scenario_mr_e, scenario_mr_i
from dealos.macro_world.scenarios import all_scenarios, scenario_a, scenario_b, scenario_d, scenario_e, scenario_g
from dealos.macro_world.validator import candidate_representation, mutation_errors, scenario_accepts, validate_scenario

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "dealos" / "macro_world"
FORBIDDEN = (
    "dealos.sim",
    "dealos.policies",
    "dealos.generator",
    "dealos.domain",
    "dealos.org",
    "dealos.analysis",
    "dealos.problem_evolution",
)


# ---- Ground-truth models ----


def test_reference_world_relations_point_at_stored_objects() -> None:
    assert integrity_errors(reference_world()) == ()


def test_a_resource_role_must_exist() -> None:
    world = reference_world()
    broken = GroundTruth(organization=world.organization, resources=(Resource("R17", "missing", "org_resource"),))
    errors = integrity_errors(broken)
    assert any("unknown role" in error for error in errors)


def test_live_task_fields_stay_unchanged() -> None:
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


def test_r0_adds_only_the_justified_resource_primitives() -> None:
    assert r0_representation().primitives == R_MICRO | R0_EXTRA
    assert FORBIDDEN_IMPLICIT.isdisjoint(r0_representation().primitives)


def test_adding_a_primitive_returns_a_new_representation() -> None:
    parent = micro_representation()
    child = parent.with_primitives(("Role",), "R1")
    assert parent.primitives == R_MICRO
    assert child.primitives == R_MICRO | {"Role"}
    assert Mutation("AddObject", "Role").target == "Role"


def test_package_does_not_import_the_frozen_core() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.py"))
    for name in FORBIDDEN:
        assert name not in text


# ---- Scenario builders ----


def test_seven_scenarios_have_valid_ground_truth() -> None:
    scenarios = all_scenarios()
    assert [scenario.scenario_id for scenario in scenarios] == list("ABCDEFG")
    for scenario in scenarios:
        assert integrity_errors(scenario.ground_truth) == ()


def test_the_same_scenario_and_seed_repeat() -> None:
    first = scenario_a()
    second = scenario_a()
    assert first.ground_truth == second.ground_truth
    assert observe(first.ground_truth, first.mask, 3) == observe(second.ground_truth, second.mask, 3)


def test_a_different_seed_changes_only_the_timestamp() -> None:
    scenario = scenario_a()
    left = observe(scenario.ground_truth, scenario.mask, 0)
    right = observe(scenario.ground_truth, scenario.mask, 1)
    assert left != right
    assert [row.get("resource_id") for row in left] == [row.get("resource_id") for row in right]
    assert left[0].get("timestamp") != right[0].get("timestamp")


def test_resource_identity_crosses_deals_and_the_ambiguous_world_has_no_role() -> None:
    identity = world_resource_identity()
    assert {deal.deal_id for deal in identity.deals} == {"d1", "d2", "d3"}
    assert {resource.resource_id for resource in identity.resources} == {"R17"}
    ambiguous = world_ambiguous()
    assert ambiguous.roles == ()
    assert ambiguous.belongs_resource_role == ()
    assert ambiguous.authority_rules == ()
    assert {trace.activity for trace in ambiguous.traces} == {"LegalReview", "ContractReview", "Approval"}


# ---- Masking ----


def test_a_hidden_field_never_appears_and_an_exposed_field_matches() -> None:
    world = world_resource_role()
    hidden = ObservationMask()
    shown = ObservationMask(expose_role=True, expose_department=True)
    concealed = observe(world, hidden, 0)
    revealed = observe(world, shown, 0)
    assert concealed[0].get("role_id") is None
    assert revealed[0].get("role_id") == "role_legal_reviewer"
    assert revealed[0].get("department_id") == "dept_legal"
    assert leak_count(world, revealed, shown) == 0
    assert leak_count(world, concealed, hidden) == 0


def test_the_same_seed_and_mask_repeat_and_authority_follows_the_rule() -> None:
    world = world_authority()
    mask = ObservationMask(expose_authority=True)
    assert observe(world, mask, 4) == observe(world, mask, 4)
    rows = {row.get("resource_id"): row.get("authority") for row in observe(world, mask, 4)}
    assert rows["Fin_R1"] == "ApproveDeal"
    assert rows["Clerk_R2"] is None


# ---- Observations ----


def test_exposed_resource_ids_match_the_traces() -> None:
    scenario = scenario_b()
    observations = observe(scenario.ground_truth, scenario.mask, 0)
    assert [row.get("resource_id") for row in observations] == ["R17", "R17"]
    assert {row.get("activity") for row in observations} == {"PacketCheck"}
    assert leak_count(scenario.ground_truth, observations, scenario.mask) == 0


def test_a_hidden_role_is_absent_from_every_event() -> None:
    scenario = scenario_b()
    observations = observe(scenario.ground_truth, scenario.mask, 0)
    for observation in observations:
        assert observation.get("role_id") is None
        assert observation.get("department_id") is None
        assert "LegalReviewer" not in {value for _name, value in observation.values}


def test_authority_and_information_links_stay_off_the_default_stream() -> None:
    authority = scenario_d()
    hidden = observe(authority.ground_truth, authority.mask, 0)
    assert {row.get("activity") for row in hidden} == {"ApproveDeal"}
    assert all(row.get("authority") is None for row in hidden)
    information = scenario_e()
    exposed = observe(information.ground_truth, information.mask, 0)
    assert {row.get("system_id") for row in exposed} == {"sys_crm", "sys_risk", "sys_approval"}
    assert all(row.get("information_link") is None for row in exposed)
    assert all(row.get("information_id") is None for row in exposed)


# ---- Queries: representable versus recoverable ----


def test_resource_identity_is_missing_from_micro_and_present_in_r0() -> None:
    scenario = scenario_a()
    observations = observe(scenario.ground_truth, scenario.mask, 0)
    assert representable(micro_representation(), "resource_occurrence_identity") is False
    assert representable(r0_representation(), "resource_occurrence_identity") is True
    assert recoverable(observations, scenario.mask, "resource_occurrence_identity") is True


def test_role_and_authority_are_not_read_off_activity_names() -> None:
    role = scenario_b()
    role_events = observe(role.ground_truth, role.mask, 0)
    assert representable(r0_representation(), "role") is False
    assert representable(candidate_representation(role), "role") is True
    assert recoverable(role_events, role.mask, "role") is False
    authority = scenario_d()
    events = observe(authority.ground_truth, authority.mask, 0)
    assert recoverable(events, authority.mask, "authority") is False
    assert representable(r0_representation(), "authority") is False
    assert representable(candidate_representation(authority), "authority") is True
    holders = authorized_holders(authority.ground_truth)
    performers = performers_of_activity(authority.ground_truth, "ApproveDeal")
    assert "role_finance_approver" in holders
    assert "Clerk_R2" in performers
    assert "Clerk_R2" not in holders


def test_the_ambiguous_scenario_stays_unresolved() -> None:
    scenario = scenario_g()
    observations = observe(scenario.ground_truth, scenario.mask, 0)
    assert scenario.epistemic_status == "HYPOTHESIS"
    assert scenario.mutations == ()
    assert representable(scenario.initial, "ambiguous_interpretation") is False
    assert recoverable(observations, scenario.mask, "ambiguous_interpretation") is False
    assert all(row.get("role_id") is None and row.get("authority") is None for row in observations)


# ---- Validator and scenario run ----


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


def test_cli_prints_the_masked_events_and_rejects_unknown_arguments(capsys) -> None:
    results, line = execute(0)
    text = format_cli(results, line, 0, Path("."))
    assert "PacketCheck" in text
    assert "LegalReviewer" not in text
    assert "ApproveDeal" in text
    assert "authority=" not in text
    assert text.strip().splitlines()[-1] == VALIDATED
    assert main(["--seed", "0"]) == 0
    with pytest.raises(SystemExit) as caught:
        main(["--nope"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert "MACRO WORLD VALIDATED" in captured.out
    assert "unrecognized arguments" in captured.err


# ---- Recoverability screen ----


def test_the_five_hidden_facts_recover_only_through_their_own_fields() -> None:
    rows = screen(0)
    assert [row.scenario_id for row in rows] == ["MR-A", "MR-B", "MR-C", "MR-G", "MR-H"]
    assert all(row.ok for row in rows)
    assert rows[0].flags_opened == ("expose_role",)
    assert "expose_authority" not in rows[0].flags_opened
    assert rows[2].flags_opened == ("expose_organization",)
    assert rows[3].flags_opened == ("expose_information",)


def test_ambiguous_and_rejected_relations_are_not_in_the_screen() -> None:
    screened = {row.relation_name for row in screen(0)}
    for scenario in (scenario_mr_d1(), scenario_mr_e(), scenario_mr_i()):
        assert scenario.relation_name not in screened or scenario.scenario_id not in {row.scenario_id for row in screen(0)}
    assert "system_system" not in screened
    assert "role_authority" not in screened
    assert "resource_collaborates" not in screened


def test_screen_result_line() -> None:
    assert all(row.ok for row in screen(1))
    assert SCREENED.startswith("FIVE HIDDEN FACTS")
