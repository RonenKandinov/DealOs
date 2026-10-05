"""Co-occurrence and matching event streams do not settle a relation type."""

from dealos.macro_world.relations.observe import observe
from dealos.macro_world.relations.scenarios import scenario_mr_d1, scenario_mr_d2, scenario_mr_d3, scenario_mr_e, scenario_mr_f, scenario_mr_i
from dealos.macro_world.relations.validate import assess


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
