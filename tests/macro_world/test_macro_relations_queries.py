"""A representation can express a relation the event stream does not recover."""

from dealos.macro_world.relations.models import macro_r0
from dealos.macro_world.relations.observe import observe
from dealos.macro_world.relations.queries import activity_is_not_a_role, recoverable, representable
from dealos.macro_world.relations.scenarios import scenario_mr_a, scenario_mr_e, scenario_mr_i
from dealos.macro_world.relations.validate import candidate_representation


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
