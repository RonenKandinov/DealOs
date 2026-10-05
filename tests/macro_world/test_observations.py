"""Observations copy exposed ground truth and omit hidden fields."""

from dealos.macro_world.observations import leak_count, observe
from dealos.macro_world.scenarios import scenario_b, scenario_d, scenario_e


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
