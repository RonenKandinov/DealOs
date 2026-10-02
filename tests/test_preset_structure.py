from dealos.domain.graph import has_cycle
from dealos.generator.generate import _TEMPLATE, generate_scenario
from dealos.generator.presets import PRESETS, get_preset

OPTIONAL_BY_TYPE: dict[str, list[str]] = {}
for name, task_type, _preds, optional in _TEMPLATE:
    if optional:
        OPTIONAL_BY_TYPE.setdefault(task_type, []).append(name)


def test_capacity_presets_differ_from_balanced() -> None:
    balanced = get_preset("balanced")
    legal = get_preset("legal_bottleneck")
    technical = get_preset("technical_bottleneck")
    constrained = get_preset("resource_constrained")
    heavy = get_preset("dependency_heavy")

    assert legal.capacities["legal"] < balanced.capacities["legal"]
    assert technical.capacities["sales_engineer"] < balanced.capacities["sales_engineer"]
    assert technical.capacities["solutions_architect"] < balanced.capacities["solutions_architect"]
    assert sum(constrained.capacities.values()) < sum(balanced.capacities.values())
    for resource_id in balanced.capacities:
        assert constrained.capacities[resource_id] < balanced.capacities[resource_id]
    assert heavy.extra_edge_probability > balanced.extra_edge_probability


def test_protected_types_targets_dags_and_seed_reproducibility() -> None:
    for name, config in PRESETS.items():
        required = [
            task_name
            for task_type in config.protected_task_types
            for task_name in OPTIONAL_BY_TYPE.get(task_type, [])
        ]
        first = generate_scenario(config, seed=0)
        assert first.to_dict() == generate_scenario(config, seed=0).to_dict()
        assert first.to_dict() != generate_scenario(config, seed=1).to_dict()
        for seed in range(20):
            scenario = generate_scenario(config, seed)
            assert len(scenario.deals) == config.n_deals
            for resource_id, resource in scenario.resources.items():
                assert resource.capacity == config.capacities[resource_id]
            for deal in scenario.deals.values():
                assert deal.targets
                assert not has_cycle(set(deal.tasks), deal.edges)
                names = {task.name for task in deal.tasks.values()}
                for task_name in required:
                    assert task_name in names, f"{name} seed {seed} dropped protected {task_name}"


def test_dependency_heavy_keeps_the_template_and_adds_edges() -> None:
    template_edges = 12
    total_edges = 0
    for seed in range(20):
        scenario = generate_scenario(get_preset("dependency_heavy"), seed)
        for deal in scenario.deals.values():
            assert len(deal.tasks) == 11
            total_edges += len(deal.edges)
    assert total_edges > 20 * 4 * template_edges
