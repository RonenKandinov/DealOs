"""Several Macro constraints on one ready Micro task, updated one event at a time."""

from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.graph import predecessors
from dealos.domain.models import AllocationAction
from dealos.domain.readiness import AndMinReadiness
from dealos.org.operating.bridge import (
    AUTHORITY_UNAVAILABLE,
    CAN_PROGRESS,
    CAPACITY_UNAVAILABLE,
    EXTERNAL_INFORMATION_UNAVAILABLE,
    INFORMATION_UNAVAILABLE,
    VETO,
    Diagnosis,
    diagnose,
)
from dealos.org.operating.entities import (
    AuthorityGrant,
    CapacityPool,
    Decision,
    ExternalRelation,
    InformationObject,
    Organization,
    System,
    TaskConstraint,
    Veto,
)
from dealos.org.operating.state import OrgState
from dealos.org.operating.transition import (
    Approve,
    IssueVeto,
    Participate,
    ProduceInformation,
    ReceiveExternalInformation,
    Release,
    TransitionError,
    apply,
)
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1
from dealos.sim.env import SalesEnvironment

TASK = ("deal_A", "deal_A:A1")
TASK_NAME = "deal_A:A1"
POOL = "pool"
PROFILE = "profile"
EXTERNAL_PROFILE = "external_profile"
DECISION = "approve_deal"
EXTERNAL = "buyer_profile"

CONSTRAINT = TaskConstraint(
    TASK_NAME,
    capacity_pool_id=POOL,
    information_id=PROFILE,
    decision_id=DECISION,
    external_relation_id=EXTERNAL,
    ready=True,
)


@dataclass(frozen=True)
class TransitionRow:
    sequence: str
    state_id: str
    event: str
    task_id: str
    micro_ready: bool
    micro_readiness: float
    capacity_status: str
    information_status: str
    authority_status: str
    external_information_status: str
    veto_status: str
    blocking_reasons: str
    eligible: bool
    progress_before: float
    progress_after: float
    in_blocked_tasks: bool
    diagnosis: Diagnosis
    state: OrgState


def initial_state() -> OrgState:
    """O_0. Capacity, information, authority, and external information all fail."""

    return organizational_state(capacity=0.0, profile=False, external=False, grant=False, veto=False)


def organizational_state(
    *,
    capacity: float,
    profile: bool,
    external: bool,
    grant: bool,
    veto: bool,
) -> OrgState:
    state = OrgState()
    state.organizations["seller"] = Organization("seller")
    state.organizations["buyer"] = Organization("buyer", external=True)
    state.capacity[POOL] = CapacityPool(POOL, 1.0, capacity)
    state.information[PROFILE] = InformationObject(PROFILE, profile)
    state.information[EXTERNAL_PROFILE] = InformationObject(EXTERNAL_PROFILE, external)
    state.systems["crm"] = System("crm", "seller")
    state.decisions[DECISION] = Decision(DECISION, "ApproveDeal", "open")
    state.external_relations[EXTERNAL] = ExternalRelation(
        EXTERNAL,
        "buyer",
        "seller",
        EXTERNAL_PROFILE,
        kind="configured",
        context_id="deal_A",
    )
    if grant:
        state.authority["grant"] = AuthorityGrant("grant", "approver", "role", DECISION)
    if veto:
        state.vetoes["v1"] = Veto("v1", "security", DECISION, True)
    return state


def primary_trace() -> tuple[TransitionRow, ...]:
    return _trace(
        "primary",
        initial_state(),
        (
            ("O0", "initial", None),
            ("O1", "Release", Release(POOL, 1.0)),
            ("O2", "ProduceInformation", ProduceInformation(PROFILE, "crm")),
            ("O3", "ReceiveExternalInformation", ReceiveExternalInformation(EXTERNAL)),
            ("O4", "AuthorityGrant", "AuthorityGrant"),
        ),
    )


def alternate_trace() -> tuple[TransitionRow, ...]:
    return _trace(
        "alternate",
        initial_state(),
        (
            ("B0", "initial", None),
            ("B1", "AuthorityGrant", "AuthorityGrant"),
            ("B2", "Release", Release(POOL, 1.0)),
            ("B3", "ProduceInformation", ProduceInformation(PROFILE, "crm")),
            ("B4", "ReceiveExternalInformation", ReceiveExternalInformation(EXTERNAL)),
        ),
    )


def isolated_trace() -> tuple[TransitionRow, ...]:
    steps = (
        ("I-release", "Release", Release(POOL, 1.0)),
        ("I-produce", "ProduceInformation", ProduceInformation(PROFILE, "crm")),
        ("I-receive", "ReceiveExternalInformation", ReceiveExternalInformation(EXTERNAL)),
        ("I-grant", "AuthorityGrant", "AuthorityGrant"),
    )
    return tuple(
        _observe("isolated", state_id, label, _advance(initial_state(), action))
        for state_id, label, action in steps
    )


def veto_trace() -> tuple[TransitionRow, ...]:
    mixed = organizational_state(capacity=0.0, profile=True, external=True, grant=True, veto=False)
    sole = organizational_state(capacity=1.0, profile=True, external=True, grant=True, veto=True)
    return (
        *_trace(
            "veto-with-capacity",
            mixed,
            (
                ("VM0", "initial", None),
                ("VM1", "IssueVeto", IssueVeto("v1", "security", DECISION)),
                ("VM2", "RetractVeto", "RetractVeto"),
            ),
        ),
        *_trace(
            "veto-only",
            sole,
            (
                ("VS0", "initial", None),
                ("VS1", "RetractVeto", "RetractVeto"),
            ),
        ),
    )


def run_all() -> tuple[TransitionRow, ...]:
    return primary_trace() + alternate_trace() + isolated_trace() + veto_trace()


def invariant_failures() -> tuple[str, ...]:
    failures: list[str] = []
    if not baseline_one_occurrence_matches_v1():
        failures.append("seed-0 fingerprint changed")
    bare = initial_state()
    try:
        approved = apply(bare, Approve(DECISION, "approver"))
    except TransitionError:
        approved = None
    if approved is not None and approved.authority:
        failures.append("Approve created an authority grant")
    participated = apply(bare, Participate("R9", "ApproveDeal"))
    if participated.authority:
        failures.append("Participate created an authority grant")
    for row in run_all():
        pool = row.state.capacity[POOL]
        if pool.available < -1e-9 or pool.available > pool.total + 1e-9:
            failures.append(f"{row.state_id} capacity left [0, total]")
        if row.in_blocked_tasks:
            failures.append(f"{row.state_id} is predecessor-blocked")
        if not row.micro_ready:
            failures.append(f"{row.state_id} is not micro-ready")
    return tuple(failures)


def write_report(root: Path) -> str:
    rows = run_all()
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "macro_micro_multiconstraint.csv", rows)
    text = _render(rows, invariant_failures(), baseline_one_occurrence_matches_v1())
    (docs / "macro_micro_multiconstraint_experiment.md").write_text(text, encoding="utf-8")
    return text


def _trace(sequence: str, start: OrgState, steps: tuple[tuple[str, str, object | None], ...]) -> tuple[TransitionRow, ...]:
    state = start
    rows: list[TransitionRow] = []
    for state_id, label, action in steps:
        if action is not None:
            state = _advance(state, action)
        rows.append(_observe(sequence, state_id, label, state))
    return tuple(rows)


def _advance(state: OrgState, action: object) -> OrgState:
    if action == "AuthorityGrant":
        granted = deepcopy(state)
        granted.authority["grant"] = AuthorityGrant("grant", "approver", "role", DECISION)
        return granted
    if action == "RetractVeto":
        cleared = deepcopy(state)
        cleared.vetoes["v1"] = replace(cleared.vetoes["v1"], active=False)
        return cleared
    return apply(state, action)


def _observe(sequence: str, state_id: str, label: str, state: OrgState) -> TransitionRow:
    diagnosis = diagnose(state, CONSTRAINT)
    progress_before, readiness, blocked = _micro_snapshot()
    eligible = diagnosis.reason == CAN_PROGRESS and not diagnosis.blocking_reasons
    if eligible:
        progress_after, blocked_after = _step()
    else:
        progress_after = progress_before
        blocked_after = blocked
    reasons = _reason_set(diagnosis)
    return TransitionRow(
        sequence,
        state_id,
        label,
        TASK_NAME,
        readiness == 1.0 and not blocked,
        readiness,
        _flag(CAPACITY_UNAVAILABLE, reasons),
        _flag(INFORMATION_UNAVAILABLE, reasons),
        _flag(AUTHORITY_UNAVAILABLE, reasons),
        _flag(EXTERNAL_INFORMATION_UNAVAILABLE, reasons),
        _flag(VETO, reasons),
        ";".join(blocker.reason for blocker in diagnosis.blocking_reasons),
        eligible,
        progress_before,
        progress_after,
        blocked_after,
        diagnosis,
        state,
    )


def _micro_snapshot() -> tuple[float, float, bool]:
    env = SalesEnvironment(chain_debug_scenario())
    micro = env.reset()
    deal = env.scenario.deals["deal_A"]
    readiness = AndMinReadiness().readiness(
        [micro.task_progress[("deal_A", pred)] for pred in predecessors(deal.edges, TASK_NAME)]
    )
    return micro.task_progress[TASK], readiness, TASK in micro.blocked_tasks


def _step() -> tuple[float, bool]:
    env = SalesEnvironment(chain_debug_scenario())
    micro = env.reset()
    occurrence = micro.primary_occurrence[TASK]
    env.step(AllocationAction({("deal_A", occurrence, "ae"): 1.0}))
    after = env.get_state()
    return after.task_progress[TASK], TASK in after.blocked_tasks


def _reason_set(diagnosis: Diagnosis) -> set[str]:
    return {blocker.reason for blocker in diagnosis.blocking_reasons}


def _flag(reason: str, reasons: set[str]) -> str:
    return "blocked" if reason in reasons else "resolved"


def _render(rows: tuple[TransitionRow, ...], failures: tuple[str, ...], fingerprint: bool) -> str:
    by_id = {row.state_id: row for row in rows}
    primary = [row for row in rows if row.sequence == "primary"]
    alternate = [row for row in rows if row.sequence == "alternate"]
    lines = [
        "# Macro-Micro multi-constraint experiment",
        "",
        "## 1. Research question",
        "",
        "For a fixed Micro task, can DealOS represent several organizational constraints at once, update that organizational state by an explicit event, recompute eligibility from the state after the event, and run the existing Micro update only when every configured constraint holds?",
        "",
        "The Micro task is deal_A:A1. Its readiness comes from the existing AND-min rule. Its progress update stays x(t+1) = min(1, x + Δx). The Macro diagnosis is a gate in front of that update.",
        "",
        "## 2. Initial state O0",
        "",
        _state_prose(by_id["O0"]),
        "",
        "## 3. Task constraints",
        "",
        "One TaskConstraint on deal_A:A1 names four requirements. Nothing is inferred from event order, activity names, co-occurrence, timestamps, or participation.",
        "",
        f"- Capacity pool `{POOL}`, required available amount 1.",
        f"- Information object `{PROFILE}`.",
        f"- Decision `{DECISION}`. Eligibility is an AuthorityGrant or an active delegation. Approve does not create a grant.",
        f"- ExternalRelation `{EXTERNAL}`, kind `configured`, context `deal_A`, linked information `{EXTERNAL_PROFILE}`.",
        "",
        f"`{PROFILE}` and `{EXTERNAL_PROFILE}` are different information objects, so producing one does not receive the other.",
        "",
        "## 4. Initial diagnosis",
        "",
        _diagnosis_prose(by_id["O0"]),
        "",
        _table(primary),
        "",
        "## 5. Event 1 and O1",
        "",
        _transition_prose(by_id["O0"], by_id["O1"]),
        "",
        "## 6. Diagnosis after Event 1",
        "",
        _diagnosis_prose(by_id["O1"]),
        "",
        "## 7. Event 2 and O2",
        "",
        _transition_prose(by_id["O1"], by_id["O2"]),
        "",
        "## 8. Diagnosis after Event 2",
        "",
        _diagnosis_prose(by_id["O2"]),
        "",
        "## 9. Event 3 and O3",
        "",
        _transition_prose(by_id["O2"], by_id["O3"]),
        "",
        "## 10. Diagnosis after Event 3",
        "",
        _diagnosis_prose(by_id["O3"]),
        "",
        "## 11. Event 4 and O4",
        "",
        _transition_prose(by_id["O3"], by_id["O4"]),
        "",
        "There is no grant event. O4 places the existing AuthorityGrant record on the decision.",
        "",
        "## 12. Final Micro outcome",
        "",
        _outcome_prose(by_id["O4"]),
        "",
        "## 13. Alternative event ordering",
        "",
        "Sequence B places the grant first, then releases capacity, produces information, and receives the external object. The final eligibility matches sequence A. The intermediate diagnoses follow whichever constraints are still open.",
        "",
        _table(alternate),
        "",
        "## 14. Invariants",
        "",
        f"Invariant failures: {len(failures)}.",
    ]
    if failures:
        lines.extend(f"- {item}" for item in failures)
    lines.extend(
        [
            f"Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: {fingerprint}.",
            f"deal_A:A1 is in blocked_tasks in any recorded state: {any(row.in_blocked_tasks for row in rows)}.",
            "Micro readiness stays 1 and progress stays 0 until a state has no blocking reasons. SalesEnvironment.step runs only in that state.",
            "Release changes pool availability. ProduceInformation changes the named internal object. ReceiveExternalInformation changes the object named by the external relation. AuthorityGrant adds one grant. None of those writes clears a different constraint.",
            "IssueVeto adds an active veto. The operating model has no retract event, so the recorded removal writes the existing Veto.active field to false. A remaining capacity failure stays after that write. Approve and Participate do not add an AuthorityGrant.",
            "",
            "## 15. What the experiment demonstrates",
            "",
            "For a fixed Micro task, this run represents four simultaneous organizational constraints, updates organizational state through explicit events, recomputes the task's organizational eligibility after each state transition, and allows the existing Micro update only when the configured constraints are satisfied.",
            "",
            "## 16. What it does not demonstrate",
            "",
            "It does not show that this constraint set was recovered from a real organization or a real deal log. It does not change Micro readiness, the progress formula, the meaning of blocked_tasks, policies, BPI17 analysis, or the problem-evolution engine. A predecessor-blocked task and an organizationally ineligible task remain different facts.",
            "",
        ]
    )
    return "\n".join(lines)


def _state_prose(row: TransitionRow) -> str:
    pool = row.state.capacity[POOL]
    return (
        f"Micro readiness is {row.micro_readiness}, progress is {row.progress_before}, "
        f"and deal_A:A1 is in blocked_tasks: {row.in_blocked_tasks}. "
        f"Pool `{POOL}` available is {pool.available} of total {pool.total}. "
        f"`{PROFILE}` available is {row.state.information[PROFILE].available}. "
        f"`{EXTERNAL_PROFILE}` available is {row.state.information[EXTERNAL_PROFILE].available}. "
        f"Authority grants on `{DECISION}`: {len(row.state.authority)}."
    )


def _diagnosis_prose(row: TransitionRow) -> str:
    where = f"Task `{row.task_id}`."
    why = f"Blocking reasons: {row.blocking_reasons or 'none'}."
    evidence = _evidence_text(row)
    return (
        f"{where} Micro readiness is {row.micro_readiness}. Macro eligible is {row.eligible}. "
        f"First reason, kept for the existing single-reason field, is `{row.diagnosis.reason}`. "
        f"{why} Evidence: {evidence}. Progress after the gate is {row.progress_after}."
    )


def _transition_prose(before: TransitionRow, after: TransitionRow) -> str:
    removed = _reason_set(before.diagnosis) - _reason_set(after.diagnosis)
    kept = _reason_set(before.diagnosis) & _reason_set(after.diagnosis)
    return (
        f"{before.state_id} -- {after.event} --> {after.state_id}. "
        f"Removed: {', '.join(sorted(removed)) or 'none'}. "
        f"Still blocking: {', '.join(sorted(kept)) or 'none'}. "
        f"Eligible: {after.eligible}. Progress: {after.progress_after}."
    )


def _outcome_prose(row: TransitionRow) -> str:
    return (
        f"O4 reason is `{row.diagnosis.reason}`. Eligible is {row.eligible}. "
        f"Progress moves from {row.progress_before} to {row.progress_after} by one existing allocation step. "
        f"Micro readiness at the start of that step is {row.micro_readiness}."
    )


def _evidence_text(row: TransitionRow) -> str:
    if not row.diagnosis.blocking_reasons:
        return "no blocker"
    parts = []
    for blocker in row.diagnosis.blocking_reasons:
        fields = ", ".join(f"{key}={value}" for key, value in blocker.evidence)
        parts.append(f"{blocker.reason} [{fields}]")
    return "; ".join(parts)


def _table(rows: list[TransitionRow]) -> str:
    lines = [
        "| State | Event | Capacity | Information | Authority | External | Veto | Diagnosis | Eligible | Progress |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        count = len(row.diagnosis.blocking_reasons)
        summary = "none" if count == 0 else f"{count} blocker" + ("s" if count != 1 else "")
        lines.append(
            f"| {row.state_id} | {row.event} | {row.capacity_status} | {row.information_status} | "
            f"{row.authority_status} | {row.external_information_status} | {row.veto_status} | "
            f"{summary} | {row.eligible} | {row.progress_after} |"
        )
    return "\n".join(lines)


def _write_csv(path: Path, rows: tuple[TransitionRow, ...]) -> None:
    fields = (
        "state_id",
        "event",
        "task_id",
        "micro_ready",
        "capacity_status",
        "information_status",
        "authority_status",
        "external_information_status",
        "blocking_reasons",
        "eligible",
        "progress_before",
        "progress_after",
        "sequence",
        "veto_status",
        "micro_readiness",
        "in_blocked_tasks",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: getattr(row, name) for name in fields})


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    print(write_report(root))


if __name__ == "__main__":
    main()
