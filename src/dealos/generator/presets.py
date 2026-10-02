"""Scenario presets. They change configuration only, not the dynamics."""

from __future__ import annotations

from dealos.domain.models import GeneratorConfig

RESOURCE_IDS: tuple[str, ...] = (
    "ae",
    "sales_engineer",
    "legal",
    "security",
    "solutions_architect",
)

RESOURCE_TYPES: dict[str, str] = {
    "ae": "AE",
    "sales_engineer": "Sales Engineer",
    "legal": "Legal",
    "security": "Security",
    "solutions_architect": "Solutions Architect",
}


def _capacities(**overrides: float) -> dict[str, float]:
    values = {
        "ae": 2.0,
        "sales_engineer": 2.0,
        "legal": 1.0,
        "security": 1.0,
        "solutions_architect": 1.0,
    }
    values.update(overrides)
    return values


def _preset(
    name: str,
    *,
    n_deals: int,
    horizon: int,
    capacities: dict[str, float],
    extra_edge_probability: float,
    optional_drop_probability: float,
    partial_start_fraction: float = 0.25,
    protected_task_types: frozenset[str] = frozenset(),
) -> GeneratorConfig:
    return GeneratorConfig(
        name=name,
        n_deals=n_deals,
        horizon=horizon,
        capacities=capacities,
        extra_edge_probability=extra_edge_probability,
        optional_drop_probability=optional_drop_probability,
        partial_start_fraction=partial_start_fraction,
        phi_range=(0.75, 1.0),
        alpha_range=(0.2, 0.35),
        q_range=(0.7, 1.0),
        protected_task_types=protected_task_types,
    )


PRESETS: dict[str, GeneratorConfig] = {
    "balanced": _preset(
        "balanced",
        n_deals=4,
        horizon=40,
        capacities=_capacities(),
        extra_edge_probability=0.08,
        optional_drop_probability=0.2,
    ),
    "legal_bottleneck": _preset(
        "legal_bottleneck",
        n_deals=6,
        horizon=50,
        capacities=_capacities(legal=0.5),
        extra_edge_probability=0.05,
        optional_drop_probability=0.15,
        protected_task_types=frozenset({"legal"}),
    ),
    "technical_bottleneck": _preset(
        "technical_bottleneck",
        n_deals=6,
        horizon=50,
        capacities=_capacities(sales_engineer=0.5, solutions_architect=0.5),
        extra_edge_probability=0.05,
        optional_drop_probability=0.15,
        protected_task_types=frozenset({"technical"}),
    ),
    "resource_constrained": _preset(
        "resource_constrained",
        n_deals=8,
        horizon=30,
        capacities=_capacities(
            ae=0.5,
            sales_engineer=0.5,
            legal=0.5,
            security=0.5,
            solutions_architect=0.5,
        ),
        extra_edge_probability=0.08,
        optional_drop_probability=0.1,
    ),
    "dependency_heavy": _preset(
        "dependency_heavy",
        n_deals=4,
        horizon=60,
        capacities=_capacities(),
        extra_edge_probability=0.75,
        optional_drop_probability=0.0,
        partial_start_fraction=0.25,
    ),
}


def get_preset(name: str) -> GeneratorConfig:
    try:
        return PRESETS[name]
    except KeyError as exc:
        known = ", ".join(sorted(PRESETS))
        raise KeyError(f"unknown preset {name!r}; known presets: {known}") from exc
