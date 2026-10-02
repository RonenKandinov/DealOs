"""Run the same preset under several policies and several seeds."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from dealos.domain.models import Scenario, SimulationConfig
from dealos.experiments.metrics import ExperimentReport, RunResult, summarize
from dealos.generator.generate import generate_scenario
from dealos.generator.presets import get_preset
from dealos.policies.base import Policy
from dealos.policies.bottleneck import BottleneckPolicy
from dealos.policies.fifo import FIFOPolicy
from dealos.policies.random import RandomPolicy
from dealos.sim.env import SalesEnvironment


def default_policy_factories() -> list[Callable[[int], Policy]]:
    """Runnable V1 policies. OptimizationPolicy is omitted until it can select an action."""

    return [
        lambda seed: RandomPolicy(seed),
        lambda seed: FIFOPolicy(),
        lambda seed: BottleneckPolicy(),
    ]


def rollout(scenario: Scenario, policy: Policy) -> RunResult:
    env = SalesEnvironment(scenario)
    state = env.reset()
    initial_completed = sum(state.deal_complete.values())
    util_sums = {resource_id: 0.0 for resource_id in scenario.resources}
    active_sum = 0.0
    blocked_task_steps = 0
    steps = 0
    while not env.is_done():
        action = policy.select_action(state, scenario)
        state, info = env.step(action)
        steps += 1
        blocked_task_steps += info.blocked_count
        active_sum += info.active_deals
        for resource_id, utilization in info.utilization.items():
            util_sums[resource_id] += utilization
    total_progress = sum(state.task_progress.values())
    task_count = len(state.task_progress)
    mean_task_progress = total_progress / task_count if task_count else 0.0
    mean_utilization = {
        resource_id: (util_sums[resource_id] / steps if steps else 0.0)
        for resource_id in util_sums
    }
    overall = (
        sum(mean_utilization.values()) / len(mean_utilization) if mean_utilization else 0.0
    )
    final_completed = sum(state.deal_complete.values())
    return RunResult(
        preset=scenario.generator.name,
        seed=scenario.seed,
        policy=policy.name,
        completed_deals=final_completed,
        completion_times=dict(state.deal_completed_at),
        total_task_progress=total_progress,
        mean_task_progress=mean_task_progress,
        blocked_task_steps=blocked_task_steps,
        mean_utilization=mean_utilization,
        mean_utilization_overall=overall,
        mean_active_deals=(active_sum / steps if steps else 0.0),
        throughput=((final_completed - initial_completed) / steps if steps else 0.0),
        steps=steps,
        done_reason=env.done_reason,
        unfinished_deals=sum(1 for value in state.deal_complete.values() if value == 0),
    )


def run_experiment(
    preset: str,
    seeds: Sequence[int],
    policies: Sequence[Callable[[int], Policy]] | None = None,
    horizon: int | None = None,
) -> ExperimentReport:
    """Generate one scenario per seed and roll out each policy on that scenario.

    `policies` maps a seed to a fresh policy instance. Reusing one RandomPolicy
    across seeds would continue its random stream and is not the default.
    """

    config = get_preset(preset)
    if horizon is not None:
        config = replace(config, horizon=horizon)
    factories = list(policies) if policies is not None else default_policy_factories()
    runs: list[RunResult] = []
    for seed in seeds:
        scenario = generate_scenario(config, seed)
        for factory in factories:
            runs.append(rollout(scenario, factory(seed)))
    assumptions: dict[str, object] = {
        "preset": config.name,
        "horizon": config.horizon,
        "n_deals": config.n_deals,
        "capacities": {key: config.capacities[key] for key in sorted(config.capacities)},
        "extra_edge_probability": config.extra_edge_probability,
        "optional_drop_probability": config.optional_drop_probability,
        "partial_start_fraction": config.partial_start_fraction,
        "protected_task_types": sorted(config.protected_task_types),
        "phi_range": config.phi_range,
        "alpha_range": config.alpha_range,
        "q_range": config.q_range,
        "readiness": "and_min",
        "capacity_violation": "reject",
        "noise": "none",
        "objective": "sum of completed deals",
        "completion_tolerance": SimulationConfig().completion_tolerance,
        "blocked_readiness_threshold": SimulationConfig().blocked_readiness_threshold,
        "capacity_tolerance": SimulationConfig().capacity_tolerance,
    }
    return ExperimentReport(
        preset=config.name,
        seeds=tuple(seeds),
        assumptions=assumptions,
        runs=runs,
        summary=summarize(runs),
    )
