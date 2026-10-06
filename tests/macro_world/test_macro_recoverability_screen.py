"""Opening a hidden fact's own fields recovers it. An unrelated field does not."""

from dealos.macro_world.relations.recoverability import SCREENED, screen
from dealos.macro_world.relations.scenarios import scenario_mr_d1, scenario_mr_e, scenario_mr_i


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
