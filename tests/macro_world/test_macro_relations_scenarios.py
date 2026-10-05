"""Scenario worlds rebuild and the resource-pair masks match."""

from dealos.macro_world.relations.observe import observe
from dealos.macro_world.relations.scenarios import all_relation_scenarios, scenario_mr_a, scenario_mr_d1, scenario_mr_d2, scenario_mr_d3
from dealos.macro_world.relations.validate import integrity_errors


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
