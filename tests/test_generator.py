from dealos.domain.graph import predecessors
from dealos.domain.models import GeneratorConfig
from dealos.generator.generate import SUITABLE_RESOURCES, generate_scenario
from dealos.generator.presets import PRESETS, get_preset


def test_same_seed_reproduces_the_scenario_and_another_seed_differs() -> None:
    config = get_preset("balanced")
    first = generate_scenario(config, seed=0).to_dict()
    second = generate_scenario(config, seed=0).to_dict()
    other = generate_scenario(config, seed=1).to_dict()
    assert first == second
    assert first != other


def test_presets_produce_dependency_consistent_portfolios() -> None:
    for name in sorted(PRESETS):
        scenario = generate_scenario(get_preset(name), seed=0)
        assert scenario.generator.name == name
        assert len(scenario.deals) == get_preset(name).n_deals
        for deal_id, deal in scenario.deals.items():
            assert deal.targets
            for task_id, progress in (
                (task_id, scenario.initial_progress[(deal_id, task_id)]) for task_id in deal.tasks
            ):
                assert 0.0 <= progress <= 1.0
                if progress >= 1.0:
                    for pred in predecessors(deal.edges, task_id):
                        assert scenario.initial_progress[(deal_id, pred)] >= 1.0
            for task_id, task in deal.tasks.items():
                assert 0.0 < scenario.phi[(deal_id, task_id)] <= 1.0
                suitable = SUITABLE_RESOURCES[task.task_type]
                for resource_id in scenario.resources:
                    alpha = scenario.alpha[(deal_id, task_id, resource_id)]
                    q_value = scenario.suitability[(deal_id, task_id, resource_id)]
                    assert alpha > 0.0
                    assert 0.0 <= q_value <= 1.0
                    if resource_id not in suitable:
                        assert q_value == 0.0
                    else:
                        assert q_value > 0.0


def test_full_template_keeps_and_join_at_integration() -> None:
    config = GeneratorConfig(
        name="full",
        n_deals=1,
        horizon=5,
        capacities={
            "ae": 1.0,
            "sales_engineer": 1.0,
            "legal": 1.0,
            "security": 1.0,
            "solutions_architect": 1.0,
        },
        extra_edge_probability=0.0,
        optional_drop_probability=0.0,
        partial_start_fraction=0.0,
        phi_range=(1.0, 1.0),
        alpha_range=(0.2, 0.2),
        q_range=(1.0, 1.0),
    )
    scenario = generate_scenario(config, seed=0)
    deal = scenario.deals["deal_00"]
    assert predecessors(deal.edges, "deal_00:integration") == (
        "deal_00:security_review",
        "deal_00:solution_design",
    )
    assert "deal_00:signature" in deal.targets


def test_legal_bottleneck_keeps_legal_tasks_and_cuts_legal_capacity() -> None:
    scenario = generate_scenario(get_preset("legal_bottleneck"), seed=2)
    assert scenario.resources["legal"].capacity == 0.5
    for deal in scenario.deals.values():
        names = {task.name for task in deal.tasks.values()}
        assert "legal_review" in names
        assert "contract_redline" in names


def test_dependency_heavy_keeps_every_template_task() -> None:
    scenario = generate_scenario(get_preset("dependency_heavy"), seed=0)
    for deal in scenario.deals.values():
        assert len(deal.tasks) == 11
        assert len(deal.edges) >= 12
