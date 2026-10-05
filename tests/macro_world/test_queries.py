"""Representable ground truth is not the same question as recoverable evidence."""

from dealos.macro_world.models import micro_representation, r0_representation
from dealos.macro_world.observations import observe
from dealos.macro_world.queries import authorized_holders, performers_of_activity, recoverable, representable
from dealos.macro_world.scenarios import scenario_a, scenario_b, scenario_d, scenario_g
from dealos.macro_world.validator import candidate_representation


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
