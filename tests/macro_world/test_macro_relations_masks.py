"""Hidden macro fields stay off the event, and exposed fields match the ground truth."""

from dealos.macro_world.relations.models import RelationMask
from dealos.macro_world.relations.observe import leak_count, observe
from dealos.macro_world.relations.scenarios import scenario_mr_a, scenario_mr_c, scenario_mr_e


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
