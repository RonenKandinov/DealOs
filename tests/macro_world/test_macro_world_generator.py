"""Scenario builders are deterministic and keep the seven worlds distinct."""

from dealos.macro_world.generator import world_ambiguous, world_resource_identity
from dealos.macro_world.ground_truth import integrity_errors
from dealos.macro_world.observations import observe
from dealos.macro_world.scenarios import all_scenarios, scenario_a


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
