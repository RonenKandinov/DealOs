"""Four decision-gate screens. V1 is only called, never changed.

Screening band, fixed before these runs, matches the previous validation:
completed-deal means differ by at least 0.25, residual means by at least 0.25,
or completion-day means by at least 2. Idle-despite uses an absolute band of 0.02.
"""

from __future__ import annotations

import random
import statistics
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from dealos.domain.models import AllocationAction, DealGraph, Scenario, Task, task_of_occurrence
from dealos.experiments.controlled import (
    assert_only_changed,
    baseline_scenario,
    collect_baseline,
    with_capacity,
    write_report,
)
from dealos.experiments.diagnostics import _depths, _longest_path, diagnose_rollout
from dealos.experiments.model_validation import (
    REWORK_DROP,
    SCREEN_SEEDS,
    WAIT_DAYS,
    Trajectory,
    _clip,
    _complete_tasks,
    _despite_fraction,
    _install_progress,
    _residual_all,
    _strip,
    _target_mean,
    critical_and_other,
    rollout,
    summarize_rows,
    zero_task_q,
)
from dealos.experiments.runner import default_policy_factories
from dealos.policies.base import eligible_occurrences, greedy_allocate
from dealos.policies.fifo import FIFOPolicy
from dealos.sim.env import SalesEnvironment

COMPLETED_BAND = 0.25
RESIDUAL_BAND = 0.25
DAY_BAND = 2.0
IDLE_BAND = 0.02
RECORDS = Path("records")
POLICIES = ("random", "fifo", "bottleneck")


@dataclass
class ArmResult:
    rows: list[Trajectory]
    supports: dict[tuple[int, str], frozenset[tuple[str, str]]]
    path_hits: int = 0


def fingerprint(scenario: Scenario) -> tuple:
    return (
        scenario.horizon,
        tuple(sorted((key, resource.capacity) for key, resource in scenario.resources.items())),
        tuple(
            sorted(
                (
                    deal_id,
                    tuple(sorted(deal.tasks)),
                    tuple(sorted(deal.edges)),
                    tuple(sorted(deal.targets)),
                )
                for deal_id, deal in scenario.deals.items()
            )
        ),
        tuple(sorted(scenario.alpha.items())),
        tuple(sorted(scenario.suitability.items())),
        tuple(sorted(scenario.phi.items())),
        tuple(sorted(scenario.initial_progress.items())),
    )


def verify_frozen_baseline() -> None:
    """Seeds 0-19 must still match Experiment 0. collect_baseline raises otherwise."""

    collect_baseline()


def require_pytest() -> None:
    completed = subprocess.run(["python", "-m", "pytest", "-q"], check=False)
    if completed.returncode != 0:
        raise RuntimeError("pytest failed; this phase stops")


def band_report(control: list[Trajectory], other: list[Trajectory]) -> str:
    lines = []
    exceeded = False
    for policy in ("fifo", "bottleneck"):
        left = [row for row in control if row.policy == policy]
        right = [row for row in other if row.policy == policy]
        if not left or not right:
            continue
        completed = _mean(row.completed for row in right) - _mean(row.completed for row in left)
        residual = _mean(row.residual_all for row in right) - _mean(row.residual_all for row in left)
        left_days = _days(left)
        right_days = _days(right)
        day = statistics.fmean(right_days) - statistics.fmean(left_days) if left_days and right_days else float("nan")
        idle = _mean(row.idle_despite for row in right) - _mean(row.idle_despite for row in left)
        blocked = _mean(row.blocked_steps for row in right) - _mean(row.blocked_steps for row in left)
        flags = []
        if abs(completed) >= COMPLETED_BAND:
            flags.append("completed")
        if abs(residual) >= RESIDUAL_BAND:
            flags.append("residual")
        if day == day and abs(day) >= DAY_BAND:
            flags.append("completion_day")
        if abs(idle) >= IDLE_BAND:
            flags.append("idle_despite")
        if flags:
            exceeded = True
        day_text = "na" if day != day else f"{day:+.3f}"
        lines.append(
            f"  {policy}: completed {completed:+.3f}, day {day_text}, residual {residual:+.3f}, "
            f"idle_despite {idle:+.3f}, blocked_steps {blocked:+.1f}; "
            f"outside band: {', '.join(flags) if flags else 'none'}"
        )
    lines.append(f"exceeds_screening_band: {exceeded}")
    return "\n".join(lines)


def run_all() -> None:
    verify_frozen_baseline()
    require_pytest()
    noisy = run_noisy_horizon()
    verify_frozen_baseline()
    require_pytest()
    wait = run_known_wait()
    verify_frozen_baseline()
    require_pytest()
    value = run_value_against_speed()
    verify_frozen_baseline()
    require_pytest()
    regression = run_regression_versus_node()
    write_summary(noisy, wait, value, regression)


def run_noisy_horizon() -> str:
    """Policy sees x_obs each morning. The environment steps x_true."""

    stored: dict[float, ArmResult] = {}
    for epsilon in (0.0, 0.05, 0.10):
        stored[epsilon] = _noisy_arm(epsilon)
        print(f"noisy epsilon={epsilon}", flush=True)
    lines = [
        "Experiment: noisy horizon",
        "Hypothesis: decisions made from x_obs = clip(x_true + epsilon, 0, 1) each morning",
        "change the horizon outcome, not only the one-shot action.",
        "Mathematical change: none inside the transition. The policy reads a copy",
        "x_obs,ij = clip(x_true,ij + U(-epsilon, epsilon), 0, 1). epsilon=0 is x_true.",
        "ready_since stays the true clock. The simulator steps the true progress.",
        "Held constant: graphs, capacities, alpha, q, phi, initial progress, T=80, seeds 0-49, policies.",
        "Changed: the progress vector passed to select_action.",
        "Screening band: completed 0.25, residual 0.25, completion day 2, idle_despite 0.02.",
        "This summary does not rank policies.",
        "",
    ]
    for epsilon, arm in stored.items():
        lines.append(format_arm(f"epsilon={epsilon:.2f}", arm))
        lines.append(f"  mean support size: {_mean(len(tasks) for tasks in arm.supports.values()):.2f}")
    control = stored[0.0]
    outcome_moves = False
    for epsilon, arm in stored.items():
        if epsilon == 0.0:
            continue
        lines.append(f"Change from epsilon=0 to {epsilon:.2f}:")
        report = band_report(control.rows, arm.rows)
        lines.append(report)
        outcome_moves = outcome_moves or report.endswith("True")
        lines.append("  " + _support_line(control.supports, arm.supports))
    lines.append("")
    if not outcome_moves:
        lines.append(
            "Verdict: rejected as a trajectory extension. Completion day, completed deals, "
            "and residual stay inside the screening band. The earlier one-shot screen can still "
            "be right that the morning action changes. Whether that action change matters for "
            "the outcome is not supported here. Unresolved: a bias that persists every day, "
            "as opposed to fresh symmetric noise, was not this experiment."
        )
    else:
        lines.append(
            "Verdict: the horizon outcome moves when the policy sees symmetric noise. "
            "x_obs is a candidate decision input. Not promoted into V1. "
            "Unresolved: this is symmetric noise, not a persistent CRM bias."
        )
    text = "\n".join(lines) + "\n"
    write_report(RECORDS / "decision_gate_noisy_horizon.txt", text)
    return text


def run_known_wait() -> str:
    """Same external-wait physics. The informed arm can see the waiting tasks."""

    blind = _wait_arm(informed=False)
    informed = _wait_arm(informed=True)
    print("wait arms done", flush=True)
    lines = [
        "Experiment: known wait versus blind wait",
        "Hypothesis: telling the existing policies which tasks are externally waiting",
        "changes idle capacity or completion day, relative to stripping that allocation after the choice.",
        "Mathematical change: waiting tasks do not gain progress from allocation.",
        f"At day {WAIT_DAYS} their true progress is set to 1. This is outside apply_progress.",
        "Blind: select_action sees baseline q, then allocation on waiting tasks is removed and not reassigned.",
        "Informed: select_action sees q=0 on those tasks, so greedy fill can use the capacity elsewhere.",
        "The environment scenario is the baseline in both arms.",
        "Waiting tasks are the initial critical-path tasks that are not targets.",
        "Held constant: graphs, capacities, true alpha, true q, phi, initial progress, T=80, seeds 0-49.",
        "Changed: whether the policy is shown q=0 on the waiting tasks.",
        "This summary does not rank policies.",
        "",
        format_arm("blind", blind),
        format_arm("informed", informed),
        "Change from blind to informed:",
        band_report(blind.rows, informed.rows),
        "  " + _support_line(blind.supports, informed.supports),
        "",
    ]
    report = band_report(blind.rows, informed.rows)
    flags = _band_flags(report)
    idle_moves = "idle_despite" in flags
    day_moves = "completion_day" in flags
    if not idle_moves and not day_moves:
        lines.append(
            "Verdict: rejected as a decision-input extension under the existing policies. "
            "Showing the wait does not move idle-despite or completion day outside the band. "
            "The wait remains a physical fact in this test. Unresolved: a rule that is not FIFO, "
            "Bottleneck, or Random might still use the information. That was not tested."
        )
    elif idle_moves and not day_moves:
        lines.append(
            "Verdict: accepted as a diagnostic fact, not as a V1 change. "
            "The informed arm changes idle-despite while completion day stays inside the band. "
            "The remaining wait is relevant to where capacity goes. It is not promoted into the simulator."
        )
    else:
        lines.append(
            "Verdict: unresolved as a pure information effect. Completion day also moves, "
            "so the informed and blind arms do not differ only by idle capacity. "
            "A smaller experiment would hold the action of one policy fixed and change only the other."
        )
    text = "\n".join(lines) + "\n"
    write_report(RECORDS / "decision_gate_known_wait.txt", text)
    return text


def run_value_against_speed() -> str:
    """Label the fast FIFO deal as low value and the slow one as high value. Then swap priority."""

    rows: list[tuple[str, Trajectory, float, float]] = []
    skipped = 0
    factories = {factory(0).name: factory for factory in default_policy_factories()}
    for seed in SCREEN_SEEDS:
        scenario = baseline_scenario(seed)
        before = fingerprint(scenario)
        fifo_row, _support = _standard_rollout(scenario, FIFOPolicy())
        labels = _speed_labels(fifo_row)
        if labels is None:
            skipped += 1
            continue
        fast_id, slow_id, values = labels
        for name in POLICIES:
            policy = factories[name](seed)
            row, _support = _standard_rollout(scenario, policy)
            rows.append((name, row, _portfolio_value(row, values), _mean_day(row)))
        swap_row, _support = _swap_rollout(scenario, fast_id, slow_id)
        rows.append(("swap", swap_row, _portfolio_value(swap_row, values), _mean_day(swap_row)))
        if fingerprint(scenario) != before:
            raise RuntimeError("value-against-speed changed the frozen scenario")
    print("value against speed done", flush=True)
    lines = [
        "Experiment: value against speed",
        "Hypothesis: one declared reallocation can raise synthetic value and lower completion count.",
        "Mathematical change: none in the transition.",
        "Per seed, FIFO's earliest completed deal has V=1 and its latest completed deal has V=10.",
        "Other deals have V=1. Seeds with fewer than two distinct completion days are skipped.",
        "The swap takes FIFO's action and pours the capacity it assigned to the fast deal",
        "onto eligible tasks of the slow deal, using the existing greedy fill and only that freed capacity.",
        "Held constant: graphs, capacities, alpha, q, phi, initial progress, T=80.",
        "Changed: the score labels, and, only in the swap arm, which deal receives that freed capacity.",
        "This is not a new policy family and it is not an optimizer.",
        "This summary does not rank policies.",
        f"Skipped seeds: {skipped}. Scored seeds: {len(SCREEN_SEEDS) - skipped}.",
        "",
    ]
    for name in ("fifo", "bottleneck", "random", "swap"):
        group = [item for item in rows if item[0] == name]
        if not group:
            continue
        lines.append(
            f"{name}: completed {_mean(item[1].completed for item in group):.3f}, "
            f"day {_mean(item[3] for item in group):.3f}, "
            f"value {_mean(item[2] for item in group):.3f}, "
            f"residual {_mean(item[1].residual_all for item in group):.3f}"
        )
    fifo = [item for item in rows if item[0] == "fifo"]
    swap = [item for item in rows if item[0] == "swap"]
    if not fifo or not swap:
        lines.append("Verdict: unresolved. Not enough seeds had two distinct FIFO completion days.")
    else:
        delta_count = _mean(item[1].completed for item in swap) - _mean(item[1].completed for item in fifo)
        delta_value = _mean(item[2] for item in swap) - _mean(item[2] for item in fifo)
        delta_day = _mean(item[3] for item in swap) - _mean(item[3] for item in fifo)
        lines.append(
            f"Swap minus FIFO: completed {delta_count:+.3f}, day {delta_day:+.3f}, value {delta_value:+.3f}."
        )
        count_moves = abs(delta_count) >= COMPLETED_BAND
        value_moves = abs(delta_value) >= 0.5
        opposite = delta_count * delta_value < 0
        if count_moves and value_moves and opposite:
            lines.append(
                "Verdict: the two scores disagree in sign on this declared swap. "
                "Completion count and synthetic value are not the same objective here. "
                "Real values are still required before either score is chosen. Not promoted into V1."
            )
        elif not count_moves and not value_moves:
            lines.append(
                "Verdict: rejected for this swap. Neither completion count nor value leaves a small band. "
                "Unresolved: some other feasible reallocation could still separate them. "
                "The smallest missing piece is real deal values, or a portfolio built so that "
                "speed and value are opposed before looking at the result."
            )
        else:
            lines.append(
                "Verdict: unresolved. The swap moves at least one score, but not as an opposite-signed "
                "conflict between completion count and value. One swap is not every feasible allocation."
            )
    text = "\n".join(lines) + "\n"
    write_report(RECORDS / "decision_gate_value_speed.txt", text)
    return text


def run_regression_versus_node() -> str:
    """Same event days. One arm lowers x. The other inserts a new predecessor and leaves x."""

    control = _disturb_arm("none")
    regression = _disturb_arm("regression")
    new_node = _disturb_arm("new_task")
    print("regression versus node done", flush=True)
    seed0 = baseline_scenario(0)
    frozen = diagnose_rollout(seed0, FIFOPolicy())
    wrapped = rollout(seed0, FIFOPolicy(), rework_rate=0.0)
    if wrapped.completion_times != frozen.completion_times:
        raise RuntimeError("undisturbed wrapper does not match the frozen rollout")
    lines = [
        "Experiment: regression versus a new task",
        "Hypothesis: a downward jump in x and a new predecessor are different disturbances.",
        "Mathematical change, regression: with probability 0.20, x := max(0, x - 0.25) on one drawn task.",
        "Mathematical change, new task: on the same draw, add a ready predecessor with progress 0",
        "and the disturbed task's alpha and q. The disturbed progress is left unchanged.",
        "The event coin and the task index are drawn from the fixed initial task list, every step,",
        "so the calendar of attempts matches across arms.",
        "Held constant at the start: graphs, capacities, alpha, q, phi, initial progress, T=80, seeds 0-49.",
        "The new-task arm then adds nodes only on its own copy.",
        "r=0 matches diagnose_rollout for FIFO seed 0.",
        "This summary does not rank policies.",
        "",
        format_arm("r=0", control),
        format_arm("regression", regression),
        format_arm("new_task", new_node),
        "Regression minus r=0:",
        band_report(control.rows, regression.rows),
        "New task minus r=0:",
        band_report(control.rows, new_node.rows),
        f"Seeds where a new node lies on a longest path to a target: {new_node.path_hits} / {len(SCREEN_SEEDS)}.",
        "",
    ]
    reg_moves = band_report(control.rows, regression.rows).endswith("True")
    node_moves = band_report(control.rows, new_node.rows).endswith("True")
    if not reg_moves and not node_moves:
        lines.append(
            "Verdict: both rejected as a transition extension. Neither leaves the screening band. "
            "Do not add regression or a new node to V1 on this evidence."
        )
    elif reg_moves and not node_moves:
        lines.append(
            "Verdict: the downward jump moves the trajectory and the new predecessor does not, "
            "inside this band. They are distinguished. The jump is a candidate extension. "
            "It is not promoted into V1. Real event logs would still be required to set the probability."
        )
    elif node_moves and not reg_moves:
        lines.append(
            "Verdict: the new predecessor moves the trajectory and the downward jump does not, "
            "inside this band. They are distinguished. The new node is a candidate extension. "
            "It is not promoted into V1."
        )
    else:
        lines.append(
            "Verdict: unresolved. Both disturbances leave the screening band, so this test does not "
            "say which representation the transition should use. The smallest next piece is a real "
            "record of whether a disturbance lowers recorded progress or adds a new required task."
        )
    text = "\n".join(lines) + "\n"
    write_report(RECORDS / "decision_gate_regression_vs_node.txt", text)
    return text


def write_summary(noisy: str, wait: str, value: str, regression: str) -> None:
    text = "\n".join(
        [
            "Decision-gate summary for the four screening experiments.",
            "No mechanism was written into the simulator, the policies, or the generator.",
            "Experiments exp0-exp9 were not modified.",
            "Seeds 0-49. T=80. Screening band: completed 0.25, residual 0.25, day 2, idle_despite 0.02.",
            "This summary does not rank policies and does not force a formulation.",
            "",
            noisy,
            wait,
            value,
            regression,
        ]
    )
    write_report(RECORDS / "decision_gate_summary.txt", text)


def format_arm(title: str, arm: ArmResult) -> str:
    lines = [title]
    for policy in POLICIES:
        group = [row for row in arm.rows if row.policy == policy]
        lines.append(f"  {policy}: {summarize_rows(group)}")
    return "\n".join(lines)


def _noisy_arm(epsilon: float) -> ArmResult:
    rows: list[Trajectory] = []
    supports: dict[tuple[int, str], frozenset[tuple[str, str]]] = {}
    for seed in SCREEN_SEEDS:
        scenario = baseline_scenario(seed)
        before = fingerprint(scenario)
        for factory in default_policy_factories():
            policy = factory(seed)
            row, support = _noisy_rollout(scenario, policy, epsilon, seed)
            rows.append(row)
            supports[(seed, policy.name)] = support
        if fingerprint(scenario) != before:
            raise RuntimeError("noisy horizon changed the frozen scenario")
    return ArmResult(rows, supports)


def _noisy_rollout(scenario: Scenario, policy, epsilon: float, seed: int) -> tuple[Trajectory, frozenset]:
    env = SalesEnvironment(scenario)
    env.reset()
    support: set[tuple[str, str]] = set()
    blocked = 0
    wasted = 0.0
    util_sum = 0.0
    despite_sum = 0.0
    herfindahls: list[float] = []
    steps = 0
    while not env.is_done():
        true_state = env.get_state()
        viewed = true_state if epsilon == 0.0 else _observed_state(env, epsilon, seed, true_state.time)
        action = policy.select_action(viewed, scenario)
        for (deal_id, occurrence_id, _), amount in action.allocations.items():
            if amount > 0.0:
                support.add((deal_id, task_of_occurrence(deal_id, occurrence_id)))
        _state, info = env.step(action)
        steps += 1
        blocked += info.blocked_count
        wasted += info.wasted_allocation
        if info.utilization:
            util_sum += sum(info.utilization.values()) / len(info.utilization)
        despite_sum += _despite_fraction(scenario, true_state.task_progress, action)
        from dealos.experiments.diagnostics import step_concentration

        concentration = step_concentration(action)
        if concentration.herfindahl is not None:
            herfindahls.append(concentration.herfindahl)
    final = env.get_state()
    row = _trajectory(scenario, policy.name, final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, 0)
    return row, frozenset(support)


def _observed_state(env: SalesEnvironment, epsilon: float, seed: int, time: int):
    true = env._state
    if true is None:
        raise RuntimeError("environment has no state")
    rng = random.Random(f"{seed}:{time}:{epsilon}:noisy-horizon")
    progress = {key: _clip(value + rng.uniform(-epsilon, epsilon)) for key, value in true.task_progress.items()}
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


def _wait_arm(informed: bool) -> ArmResult:
    rows: list[Trajectory] = []
    supports: dict[tuple[int, str], frozenset[tuple[str, str]]] = {}
    for seed in SCREEN_SEEDS:
        scenario = baseline_scenario(seed)
        before = fingerprint(scenario)
        on_path, _other = critical_and_other(scenario)
        targets = {(deal_id, task_id) for deal_id, deal in scenario.deals.items() for task_id in deal.targets}
        waiting = set(on_path) - targets
        view = zero_task_q(scenario, waiting) if informed and waiting else scenario
        if informed and waiting:
            assert_only_changed(scenario, view, ("q",))
        for factory in default_policy_factories():
            policy = factory(seed)
            row, support = _wait_rollout(scenario, view, policy, waiting)
            rows.append(row)
            supports[(seed, policy.name)] = support
        if fingerprint(scenario) != before:
            raise RuntimeError("wait screen changed the frozen scenario")
    return ArmResult(rows, supports)


def _wait_rollout(env_scenario, view_scenario, policy, waiting: set[tuple[str, str]]):
    env = SalesEnvironment(env_scenario)
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
        state = env.get_state()
        action = policy.select_action(state, view_scenario)
        action = _strip(action, waiting)
        for (deal_id, occurrence_id, _), amount in action.allocations.items():
            if amount > 0.0:
                support.add((deal_id, task_of_occurrence(deal_id, occurrence_id)))
        _state, info = env.step(action)
        steps += 1
        blocked += info.blocked_count
        wasted += info.wasted_allocation
        if info.utilization:
            util_sum += sum(info.utilization.values()) / len(info.utilization)
        despite_sum += _despite_fraction(env_scenario, state.task_progress, action)
        concentration = step_concentration(action)
        if concentration.herfindahl is not None:
            herfindahls.append(concentration.herfindahl)
        if waiting and env._state is not None and env._state.time >= WAIT_DAYS:
            _complete_tasks(env, waiting)
    final = env.get_state()
    row = _trajectory(env_scenario, policy.name, final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, 0)
    return row, frozenset(support)


def _standard_rollout(scenario: Scenario, policy) -> tuple[Trajectory, frozenset]:
    return _noisy_rollout(scenario, policy, 0.0, scenario.seed)


def _speed_labels(row: Trajectory) -> tuple[str, str, dict[str, float]] | None:
    finished = [(day, deal_id) for deal_id, day in row.completion_times.items() if day is not None]
    if len(finished) < 2:
        return None
    if min(day for day, _deal in finished) == max(day for day, _deal in finished):
        return None
    fast_id = min(finished)[1]
    slow_id = max(finished)[1]
    values = {deal_id: 1.0 for deal_id in row.completion_times}
    values[fast_id] = 1.0
    values[slow_id] = 10.0
    return fast_id, slow_id, values


def _portfolio_value(row: Trajectory, values: dict[str, float]) -> float:
    return sum(values[deal_id] for deal_id, day in row.completion_times.items() if day is not None)


def _mean_day(row: Trajectory) -> float:
    days = [float(day) for day in row.completion_times.values() if day is not None]
    return statistics.fmean(days) if days else float("nan")


def _swap_rollout(scenario: Scenario, fast_id: str, slow_id: str) -> tuple[Trajectory, frozenset]:
    env = SalesEnvironment(scenario)
    env.reset()
    policy = FIFOPolicy()
    support: set[tuple[str, str]] = set()
    blocked = 0
    wasted = 0.0
    util_sum = 0.0
    despite_sum = 0.0
    herfindahls: list[float] = []
    steps = 0
    from dealos.experiments.diagnostics import step_concentration

    while not env.is_done():
        state = env.get_state()
        action = _reassign_fast_to_slow(state, scenario, policy, fast_id, slow_id)
        _require_feasible(scenario, action)
        for (deal_id, occurrence_id, _), amount in action.allocations.items():
            if amount > 0.0:
                support.add((deal_id, task_of_occurrence(deal_id, occurrence_id)))
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
    row = _trajectory(scenario, "swap", final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, 0)
    return row, frozenset(support)


def _reassign_fast_to_slow(state, scenario: Scenario, policy: FIFOPolicy, fast_id: str, slow_id: str) -> AllocationAction:
    original = policy.select_action(state, scenario)
    freed: dict[str, float] = {}
    kept: dict[tuple[str, str, str], float] = {}
    for key, amount in original.allocations.items():
        if amount <= 0.0:
            continue
        if key[0] == fast_id:
            freed[key[2]] = freed.get(key[2], 0.0) + amount
        else:
            kept[key] = amount
    pour = scenario
    for resource_id in scenario.resources:
        pour = with_capacity(pour, resource_id, freed.get(resource_id, 0.0))
    order = [item for item in _fifo_order(state, scenario) if item.deal_id == slow_id]
    extra = greedy_allocate(order, state, pour)
    merged = dict(kept)
    for key, amount in extra.allocations.items():
        if amount <= 0.0:
            continue
        room = 1.0 - merged.get(key, 0.0)
        take = min(amount, max(0.0, room))
        if take > 0.0:
            merged[key] = merged.get(key, 0.0) + take
    return AllocationAction(merged)


def _fifo_order(state, scenario: Scenario):
    def sort_key(occurrence) -> tuple[int, str, str, str]:
        key = (occurrence.deal_id, occurrence.task_id)
        ready_since = state.ready_since.get(key)
        waiting_since = state.time if ready_since is None else ready_since
        return (waiting_since, occurrence.deal_id, occurrence.task_id, occurrence.occurrence_id)

    return sorted(eligible_occurrences(state, scenario), key=sort_key)


def _require_feasible(scenario: Scenario, action: AllocationAction) -> None:
    tolerance = scenario.simulation.capacity_tolerance
    for (_deal_id, _task_id, _resource_id), amount in action.allocations.items():
        if amount < -tolerance or amount > 1.0 + tolerance:
            raise RuntimeError("swap produced an allocation outside [0, 1]; phase stops")
    used = action.used_by_resource()
    for resource_id, resource in scenario.resources.items():
        if used.get(resource_id, 0.0) > resource.capacity + tolerance:
            raise RuntimeError("swap produced an infeasible allocation; phase stops")


def _disturb_arm(mode: str) -> ArmResult:
    rows: list[Trajectory] = []
    supports: dict[tuple[int, str], frozenset[tuple[str, str]]] = {}
    path_hits = 0
    for seed in SCREEN_SEEDS:
        scenario = baseline_scenario(seed)
        before = fingerprint(scenario)
        hit = False
        for factory in default_policy_factories():
            policy = factory(seed)
            row, support, on_path = _disturb_rollout(scenario, policy, mode, seed)
            rows.append(row)
            supports[(seed, policy.name)] = support
            hit = hit or on_path
        if fingerprint(scenario) != before:
            raise RuntimeError("disturbance arm changed the caller's frozen scenario")
        if hit:
            path_hits += 1
    arm = ArmResult(rows, supports)
    arm.path_hits = path_hits
    return arm


def _disturb_rollout(scenario: Scenario, policy, mode: str, seed: int):
    env = SalesEnvironment(scenario)
    env.reset()
    fixed_keys = list(scenario.task_keys())
    rng = random.Random(f"{seed}:0.20:gate-disturbance")
    serial = 0
    support: set[tuple[str, str]] = set()
    blocked = 0
    wasted = 0.0
    util_sum = 0.0
    despite_sum = 0.0
    herfindahls: list[float] = []
    steps = 0
    from dealos.experiments.diagnostics import step_concentration

    while not env.is_done():
        state = env.get_state()
        action = policy.select_action(state, env.scenario)
        for (deal_id, occurrence_id, _), amount in action.allocations.items():
            if amount > 0.0:
                support.add((deal_id, task_of_occurrence(deal_id, occurrence_id)))
        _state, info = env.step(action)
        steps += 1
        blocked += info.blocked_count
        wasted += info.wasted_allocation
        if info.utilization:
            util_sum += sum(info.utilization.values()) / len(info.utilization)
        despite_sum += _despite_fraction(env.scenario, state.task_progress, action)
        concentration = step_concentration(action)
        if concentration.herfindahl is not None:
            herfindahls.append(concentration.herfindahl)
        fire = rng.random() < 0.20
        index = rng.randrange(len(fixed_keys))
        if mode != "none" and fire:
            key = fixed_keys[index]
            if mode == "regression":
                _regress(env, key)
            elif mode == "new_task":
                serial = _insert_predecessor(env, key, serial)
    on_path = _new_nodes_on_longest_path(env) if mode == "new_task" else False
    final = env.get_state()
    row = _trajectory(env.scenario, policy.name, final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, serial)
    return row, frozenset(support), on_path


def _regress(env: SalesEnvironment, key: tuple[str, str]) -> None:
    if env._state is None or key not in env._state.task_progress:
        return
    if env._state.task_progress[key] <= 0.0:
        return
    progress = dict(env._state.task_progress)
    progress[key] = max(0.0, progress[key] - REWORK_DROP)
    _install_progress(env, progress)


def _insert_predecessor(env: SalesEnvironment, key: tuple[str, str], serial: int) -> int:
    if env._state is None or key not in env._state.task_progress:
        return serial
    if env._state.task_progress[key] <= 0.0:
        return serial
    deal_id, task_id = key
    scenario = env.scenario
    deal = scenario.deals[deal_id]
    serial += 1
    new_id = f"{task_id}:rework:{serial}"
    source = deal.tasks[task_id]
    tasks = dict(deal.tasks)
    tasks[new_id] = Task(
        task_id=new_id,
        deal_id=deal_id,
        task_type=source.task_type,
        name=f"rework_{serial}",
    )
    edges = set(deal.edges)
    edges.add((new_id, task_id))
    deals = dict(scenario.deals)
    deals[deal_id] = DealGraph(
        deal_id=deal_id,
        tasks=tasks,
        edges=frozenset(edges),
        targets=frozenset(deal.targets),
    )
    phi = dict(scenario.phi)
    alpha = dict(scenario.alpha)
    suitability = dict(scenario.suitability)
    initial = dict(scenario.initial_progress)
    phi[(deal_id, new_id)] = scenario.phi[(deal_id, task_id)]
    initial[(deal_id, new_id)] = 0.0
    for resource_id in scenario.resources:
        alpha[(deal_id, new_id, resource_id)] = scenario.alpha[(deal_id, task_id, resource_id)]
        suitability[(deal_id, new_id, resource_id)] = scenario.suitability[(deal_id, task_id, resource_id)]
    env.scenario = replace(
        scenario,
        deals=deals,
        phi=phi,
        alpha=alpha,
        suitability=suitability,
        initial_progress=initial,
    )
    progress = dict(env._state.task_progress)
    progress[(deal_id, new_id)] = 0.0
    _install_progress(env, progress)
    return serial


def _new_nodes_on_longest_path(env: SalesEnvironment) -> bool:
    if env._state is None:
        return False
    progress = env._state.task_progress
    for deal in env.scenario.deals.values():
        depths = _depths(deal)
        for target in deal.targets:
            if target not in depths:
                continue
            path = _longest_path(deal, target, progress, depths)
            if any(":rework:" in task_id for task_id in path):
                return True
    return False


def _trajectory(scenario, policy_name, final, steps, blocked, wasted, util_sum, despite_sum, herfindahls, rework_count):
    return Trajectory(
        seed=scenario.seed,
        policy=policy_name,
        completed=sum(final.deal_complete.values()),
        completion_times=dict(final.deal_completed_at),
        target_progress=_target_mean(scenario, final.task_progress),
        residual_all=_residual_all(scenario, final.task_progress),
        blocked_steps=blocked,
        wasted=wasted,
        utilization=util_sum / steps if steps else 0.0,
        herfindahl=(sum(herfindahls) / len(herfindahls) if herfindahls else None),
        idle_despite=despite_sum / steps if steps else 0.0,
        steps=steps,
        rework_count=rework_count,
    )


def _support_line(control, other) -> str:
    shared = [key for key in control if key in other]
    if not shared:
        return "support comparison: n=0"
    changed = 0
    jaccard_sum = 0.0
    for key in shared:
        left = control[key]
        right = other[key]
        if left != right:
            changed += 1
        union = left | right
        jaccard_sum += (len(left & right) / len(union)) if union else 1.0
    return (
        f"support differs in {changed}/{len(shared)} runs; "
        f"mean Jaccard {jaccard_sum / len(shared):.3f}"
    )


def _band_flags(report: str) -> set[str]:
    flags: set[str] = set()
    for line in report.splitlines():
        if "outside band:" not in line:
            continue
        tail = line.split("outside band:", 1)[1].strip()
        if tail != "none":
            flags.update(part.strip() for part in tail.split(","))
    return flags


def _days(rows: list[Trajectory]) -> list[float]:
    return [float(day) for row in rows for day in row.completion_times.values() if day is not None]
    return [float(day) for row in rows for day in row.completion_times.values() if day is not None]


def _mean(values) -> float:
    numbers = [float(value) for value in values]
    return statistics.fmean(numbers) if numbers else float("nan")


def main() -> None:
    run_all()


if __name__ == "__main__":
    main()
