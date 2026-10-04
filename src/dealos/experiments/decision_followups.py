"""Follow-up screens for persistent bias and an opposed value-speed trade.

V1 is not modified. Screening band matches the previous decision-gate runs.
"""

from __future__ import annotations

from dealos.domain.models import AllocationAction, Scenario
from dealos.experiments.controlled import assert_only_changed, write_report
from dealos.experiments.decision_screens import (
    RECORDS,
    ArmResult,
    _fifo_order,
    _mean,
    _noisy_rollout,
    _observed_state,
    _require_feasible,
    _support_line,
    _trajectory,
    band_report,
    fingerprint,
    format_arm,
    require_pytest,
    verify_frozen_baseline,
)
from dealos.experiments.horizon_sweep import with_horizon
from dealos.experiments.model_validation import (
    SCREEN_SEEDS,
    Trajectory,
    _clip,
    _despite_fraction,
    baseline_scenario,
    summarize_rows,
)
from dealos.experiments.runner import default_policy_factories
from dealos.policies.base import eligible_tasks, greedy_allocate
from dealos.policies.fifo import FIFOPolicy
from dealos.sim.env import SalesEnvironment

POLICIES = ("random", "fifo", "bottleneck")
OPPOSED_HORIZON = 40
HIGH_VALUE = 10.0
LOW_VALUE = 1.0


def run_followups() -> None:
    verify_frozen_baseline()
    require_pytest()
    bias = run_persistent_bias()
    verify_frozen_baseline()
    require_pytest()
    value = run_opposed_value()
    _update_gap(bias, value)


def run_persistent_bias() -> str:
    true = _collect_observation("true", 0.0)
    fresh = {magnitude: _collect_observation("fresh", magnitude) for magnitude in (0.05, 0.10)}
    bias = {
        sign * magnitude: _collect_observation("bias", sign * magnitude)
        for magnitude in (0.05, 0.10)
        for sign in (1.0, -1.0)
    }
    print("persistent bias done", flush=True)
    lines = [
        "Experiment: fresh symmetric noise versus persistent CRM bias",
        "Hypothesis: a constant observation error creates a different horizon outcome",
        "from an independent symmetric error of the same magnitude.",
        "Mathematical change: none in the transition.",
        "True arm: the policy sees x_true.",
        "Fresh arm: x_obs = clip(x_true + U(-m, m), 0, 1), redrawn every morning.",
        "Bias arm: x_obs = clip(x_true + b, 0, 1), with b fixed at +0.05, -0.05, +0.10, or -0.10.",
        "The simulator steps x_true. ready_since stays the true clock.",
        "Held constant: graphs, capacities, alpha, q, phi, initial progress, T=80, seeds 0-49, policies.",
        "Changed: only the progress copy passed to select_action.",
        "Screening band: completed 0.25, residual 0.25, completion day 2, idle_despite 0.02.",
        "Wasted allocation is reported and is not part of that band.",
        "This summary does not rank policies.",
        "",
        format_arm("true", true),
        f"  wasted {_wasted_line(true)}",
    ]
    for magnitude, arm in fresh.items():
        lines.append(format_arm(f"fresh m={magnitude:.2f}", arm))
        lines.append(f"  wasted {_wasted_line(arm)}")
        lines.append(f"Change from true to fresh {magnitude:.2f}:")
        lines.append(band_report(true.rows, arm.rows))
        lines.append("  " + _support_line(true.supports, arm.supports))
    for level, arm in bias.items():
        lines.append(format_arm(f"bias b={level:+.2f}", arm))
        lines.append(f"  wasted {_wasted_line(arm)}")
        lines.append(f"Change from true to bias {level:+.2f}:")
        lines.append(band_report(true.rows, arm.rows))
        lines.append("  " + _support_line(true.supports, arm.supports))
        fresh_arm = fresh[abs(level)]
        lines.append(f"Change from fresh m={abs(level):.2f} to bias {level:+.2f}:")
        lines.append(band_report(fresh_arm.rows, arm.rows))
        lines.append("  " + _support_line(fresh_arm.supports, arm.supports))
        lines.append(f"  wasted bias-minus-fresh {_wasted_delta(fresh_arm, arm):+.2f}")
    lines.append("")
    lines.append(_bias_verdict(true, fresh, bias))
    text = "\n".join(lines) + "\n"
    write_report(RECORDS / "decision_gate_persistent_bias.txt", text)
    return text


def run_opposed_value() -> str:
    """T=80 cannot oppose positive value and completion count if every deal finishes.

    The attempt uses T=40, where FIFO leaves deals unfinished, and a declared focus
    on those unfinished deals. Values are 10 for deals FIFO leaves open and 1 for
    deals FIFO finishes.
    """

    lines = [
        "Experiment: value opposed to completion speed",
        "Hypothesis: some feasible allocation has fewer completed deals and higher total value",
        "than FIFO on the same deals.",
        "At T=80, FIFO completes every deal on these seeds. If every value is positive,",
        "every subset has a lower total value. No feasible allocation can raise value",
        "by completing fewer deals. That comparison is not run as a forced conflict.",
        "Construction: same frozen graphs, horizon set to 40, which is the only change.",
        "Deals FIFO finishes at T=40 get V=1. Deals it leaves open get V=10.",
        "The declared intervention keeps the existing greedy fill and restricts it to the V=10 deals.",
        "Seeds where FIFO finishes every deal or no deal are skipped, because value and speed",
        "are not opposed there.",
        "Held constant within the T=40 comparison: graphs, capacities, alpha, q, phi, initial progress.",
        "This is not a new policy class and it is not an optimizer.",
        "This summary does not rank policies.",
        "",
    ]
    full = _confirm_all_complete()
    lines.append(full)
    skipped = 0
    compared = 0
    conflicts = 0
    fifo_count = []
    focus_count = []
    fifo_value = []
    focus_value = []
    fifo_day = []
    focus_day = []
    fifo_residual = []
    focus_residual = []
    for seed in SCREEN_SEEDS:
        base = baseline_scenario(seed)
        scenario = with_horizon(base, 40)
        assert_only_changed(base, scenario, ("horizon", "generator.horizon"))
        before = fingerprint(base)
        fifo_row, _support = _noisy_rollout(scenario, FIFOPolicy(), 0.0, seed)
        labels = _opposed_labels(fifo_row)
        if labels is None:
            skipped += 1
            continue
        values, high_deals = labels
        focus_row = _focus_rollout(scenario, high_deals)
        if fingerprint(base) != before:
            raise RuntimeError("opposed-value screen changed the frozen T=80 scenario")
        compared += 1
        fifo_count.append(fifo_row.completed)
        focus_count.append(focus_row.completed)
        fifo_value.append(_value_of(fifo_row, values))
        focus_value.append(_value_of(focus_row, values))
        fifo_day.append(_day_of(fifo_row))
        focus_day.append(_day_of(focus_row))
        fifo_residual.append(fifo_row.residual_all)
        focus_residual.append(focus_row.residual_all)
        delta_count = focus_row.completed - fifo_row.completed
        delta_value = focus_value[-1] - fifo_value[-1]
        if delta_count < 0 and delta_value > 0:
            conflicts += 1
    lines.append(f"Skipped seeds at T=40: {skipped}. Compared seeds: {compared}.")
    if compared == 0:
        lines.append(
            "Verdict: stop. No seed at T=40 left a proper opposition between finished and unfinished deals. "
            "The conflict was not constructed."
        )
    else:
        lines.append(
            f"FIFO at T=40: completed {_mean(fifo_count):.3f}, day {_mean_defined(fifo_day):.3f}, "
            f"value {_mean(fifo_value):.3f}, residual {_mean(fifo_residual):.3f}"
        )
        lines.append(
            f"Focus on V=10 deals: completed {_mean(focus_count):.3f}, day {_mean_defined(focus_day):.3f}, "
            f"value {_mean(focus_value):.3f}, residual {_mean(focus_residual):.3f}"
        )
        lines.append(
            f"Focus minus FIFO: completed {_mean(focus_count) - _mean(fifo_count):+.3f}, "
            f"value {_mean(focus_value) - _mean(fifo_value):+.3f}."
        )
        lines.append(f"Seeds with fewer completions and higher value: {conflicts} / {compared}.")
        if conflicts == 0:
            lines.append(
                "Verdict: stop. This feasible focus does not produce Δ completed deals < 0 and Δ value > 0. "
                "At T=80 the conflict is impossible for positive values against an all-completing FIFO trajectory. "
                "At T=40 the declared focus did not buy the high-value deals. "
                "Unresolved: a different feasible allocation might still do so. "
                "Real deal values are what would say whether the opposition exists outside this construction."
            )
        else:
            lines.append(
                "Verdict: a conflict is constructable on the seeds counted above, under T=40 and these labels. "
                "It is not a V1 objective. It does not say which score should be chosen. "
                "Real values are still required before either score is treated as the business objective."
            )
    text = "\n".join(lines) + "\n"
    write_report(RECORDS / "decision_gate_opposed_value.txt", text)
    return text


def _collect_observation(mode: str, magnitude: float) -> ArmResult:
    rows: list[Trajectory] = []
    supports: dict[tuple[int, str], frozenset[tuple[str, str]]] = {}
    for seed in SCREEN_SEEDS:
        scenario = baseline_scenario(seed)
        before = fingerprint(scenario)
        for factory in default_policy_factories():
            policy = factory(seed)
            row, support = _observation_rollout(scenario, policy, mode, magnitude, seed)
            rows.append(row)
            supports[(seed, policy.name)] = support
        if fingerprint(scenario) != before:
            raise RuntimeError("observation screen changed the frozen scenario")
    print(f"observation {mode} {magnitude}", flush=True)
    return ArmResult(rows, supports)


def _observation_rollout(scenario, policy, mode: str, magnitude: float, seed: int):
    env = SalesEnvironment(scenario)
    env.reset()
    support: set[tuple[str, str]] = set()
    blocked = 0
    wasted = 0.0
    util_sum = 0.0
    despite_sum = 0.0
    herfindahls: list[float] = []
    steps = 0
    from dealos.experiments.diagnostics import step_concentration

    while not env.is_done():
        true_state = env.get_state()
        viewed = _view_for(env, mode, magnitude, seed, true_state.time)
        action = policy.select_action(viewed, scenario)
        for (deal_id, task_id, _), amount in action.allocations.items():
            if amount > 0.0:
                support.add((deal_id, task_id))
        _state, info = env.step(action)
        steps += 1
        blocked += info.blocked_count
        wasted += info.wasted_allocation
        if info.utilization:
            util_sum += sum(info.utilization.values()) / len(info.utilization)
        despite_sum += _despite_fraction(scenario, true_state.task_progress, action)
        concentration = step_concentration(action)
        if concentration.herfindahl is not None:
            herfindahls.append(concentration.herfindahl)
    final = env.get_state()
    row = _trajectory(scenario, policy.name, final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, 0)
    return row, frozenset(support)


def _view_for(env: SalesEnvironment, mode: str, magnitude: float, seed: int, time: int):
    if mode == "true" or magnitude == 0.0 and mode != "bias":
        return env.get_state()
    if mode == "fresh":
        return _observed_state(env, magnitude, seed, time)
    if mode == "bias":
        true = env._state
        if true is None:
            raise RuntimeError("environment has no state")
        progress = {key: _clip(value + magnitude) for key, value in true.task_progress.items()}
        ghost = SalesEnvironment(env.scenario)
        ghost.reset()
        ghost._state = ghost._derive(
            progress=progress,
            time=true.time,
            allocations={},
            previous_ready_since=dict(true.ready_since),
            previous_task_completed_at=dict(true.task_completed_at),
            previous_deal_completed_at=dict(true.deal_completed_at),
        )
        return ghost.get_state()
    raise ValueError(mode)


def _confirm_all_complete() -> str:
    completed = []
    for seed in SCREEN_SEEDS:
        scenario = baseline_scenario(seed)
        row, _support = _noisy_rollout(scenario, FIFOPolicy(), 0.0, seed)
        completed.append(row.completed)
        if fingerprint(scenario) != fingerprint(baseline_scenario(seed)):
            raise RuntimeError("T=80 check changed the frozen scenario")
    mean_completed = _mean(completed)
    return (
        f"T=80 FIFO completed-deal mean on seeds 0-49: {mean_completed:.3f}. "
        + (
            "Every compared trajectory that completes all deals has the maximum positive-value score."
            if all(value == max(completed) and value == len(baseline_scenario(0).deals) for value in completed)
            else "FIFO does not complete every deal on every seed, so the T=80 impossibility does not apply uniformly."
        )
    )


def _opposed_labels(row: Trajectory) -> tuple[dict[str, float], set[str]] | None:
    finished = {deal_id for deal_id, day in row.completion_times.items() if day is not None}
    unfinished = {deal_id for deal_id in row.completion_times if deal_id not in finished}
    if not finished or not unfinished:
        return None
    values = {deal_id: (LOW_VALUE if deal_id in finished else HIGH_VALUE) for deal_id in row.completion_times}
    return values, unfinished


def _focus_rollout(scenario: Scenario, high_deals: set[str]) -> Trajectory:
    env = SalesEnvironment(scenario)
    env.reset()
    blocked = 0
    wasted = 0.0
    util_sum = 0.0
    despite_sum = 0.0
    herfindahls: list[float] = []
    steps = 0
    from dealos.experiments.diagnostics import step_concentration

    while not env.is_done():
        state = env.get_state()
        order = [key for key in _fifo_order(state, scenario) if key[0] in high_deals]
        action = greedy_allocate(order, state, scenario)
        _require_feasible(scenario, action)
        _state, info = env.step(action)
        steps += 1
        blocked += info.blocked_count
        wasted += info.wasted_allocation
        if info.utilization:
            util_sum += sum(info.utilization.values()) / len(info.utilization)
        despite_sum += _despite_fraction(scenario, state.task_progress, action)
        concentration = step_concentration(action)
        if concentration.herfindahl is not None:
            herfindahls.append(concentration.herfindahl)
    final = env.get_state()
    return _trajectory(scenario, "focus", final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, 0)


def _value_of(row: Trajectory, values: dict[str, float]) -> float:
    return sum(values[deal_id] for deal_id, day in row.completion_times.items() if day is not None)


def _day_of(row: Trajectory) -> float:
    days = [float(day) for day in row.completion_times.values() if day is not None]
    if not days:
        return float("nan")
    return sum(days) / len(days)


def _mean_defined(values: list[float]) -> float:
    usable = [value for value in values if value == value]
    return _mean(usable) if usable else float("nan")


def _wasted_line(arm: ArmResult) -> str:
    return ", ".join(
        f"{policy}={_mean(row.wasted for row in arm.rows if row.policy == policy):.2f}" for policy in POLICIES
    )


def _wasted_delta(left: ArmResult, right: ArmResult) -> float:
    return _mean(row.wasted for row in right.rows) - _mean(row.wasted for row in left.rows)


def _bias_verdict(true: ArmResult, fresh: dict[float, ArmResult], bias: dict[float, ArmResult]) -> str:
    material = []
    for level, arm in bias.items():
        report = band_report(fresh[abs(level)].rows, arm.rows)
        if report.endswith("True"):
            material.append(f"{level:+.2f}")
    if not material:
        return (
            "Verdict: persistent bias does not create a materially different outcome requirement "
            "from fresh noise of the same magnitude, inside the screening band. "
            "Both can still differ from the true state. Unresolved: a bias that is shared across "
            "tasks in a deal, rather than added separately to every task, was not tested. "
            "Not promoted into V1."
        )
    return (
        "Verdict: persistent bias differs from fresh noise outside the screening band "
        f"at levels {', '.join(material)}. They are not the same observation error for horizon outcomes. "
        "Neither is promoted into V1. A real CRM error log is what would say which error actually occurs."
    )


def _update_gap(bias: str, value: str) -> None:
    if "does not create a materially different" in bias:
        nxt = (
            "Next gap: do not add a separate persistent-bias state on this evidence. "
            "Fresh noise already moves the horizon outcome. Real CRM logs are what would show "
            "whether the error is a fresh draw or a constant offset."
        )
    elif "differs from fresh noise" in bias:
        nxt = (
            "Next gap: the observation error itself. Persistent bias and fresh noise were separated "
            "by the screening band, so they are not interchangeable. Real CRM logs are required "
            "before either is represented. Do not implement that extension yet."
        )
    else:
        nxt = "Next gap: reread the bias verdict. The automatic summary could not classify it."
    if "conflict is constructable" in value:
        nxt += (
            " A completion-count versus value conflict is constructable in the T=40 screen. "
            "Choosing a score still requires real deal values."
        )
    else:
        nxt += (
            " A completion-count versus value conflict was not established by the declared focus. "
            "Do not add a value objective from this run."
        )
    addition = "\n".join(
        [
            "",
            "Follow-up screens. These do not replace the labels above.",
            "",
            bias,
            value,
            "",
            nxt,
            "No model extension is implemented from these screens.",
        ]
    )
    path = RECORDS / "model_gap_analysis.txt"
    current = path.read_text(encoding="utf-8").rstrip()
    marker = "Follow-up screens. These do not replace the labels above."
    if marker in current:
        current = current.split(marker)[0].rstrip()
    path.write_text(current + "\n" + addition + "\n", encoding="utf-8")


def main() -> None:
    run_followups()


if __name__ == "__main__":
    main()
